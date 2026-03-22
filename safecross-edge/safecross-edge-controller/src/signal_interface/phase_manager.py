"""Pedestrian walk-time extension state machine.

This is the core safety-critical module that manages the lifecycle of a
single pedestrian walk-time extension: request → extend → restore.

The state machine guarantees that baseline timing is **always** restored
after every extension attempt, regardless of the outcome (success,
timeout, preemption, SNMP failure).
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable

from src.signal_interface import safety
from src.signal_interface.ntcip_objects import (
    CONTROLLER_DESCRIPTION,
    PED_CALL,
    PED_PHASE_STATUS,
    PED_WALK_TIME,
    PREEMPT_STATUS,
    get_oid,
)
from src.signal_interface.snmp_client import SNMPClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

POLL_INTERVAL_SEC: float = 0.5
PREEMPT_POLL_INTERVAL_SEC: float = 1.0
EXTENSION_TIMEOUT_SEC: float = 60.0
RESTORE_RETRY_DELAY_SEC: float = 2.0
RESTORE_MAX_RETRIES: int = 3
ERROR_RECOVERY_INTERVAL_SEC: float = 30.0
DEFAULT_COOLDOWN_SEC: int = 120


# ---------------------------------------------------------------------------
# State enum
# ---------------------------------------------------------------------------


class PhaseState(Enum):
    """States of the walk-time extension lifecycle."""

    IDLE = "idle"
    EXTENSION_REQUESTED = "extension_requested"
    WALK_EXTENDED = "walk_extended"
    RESTORING = "restoring"
    COOLDOWN = "cooldown"
    ERROR = "error"


# ---------------------------------------------------------------------------
# PhaseManager
# ---------------------------------------------------------------------------


class PhaseManager:
    """Manages pedestrian walk-time extensions for a single intersection.

    Args:
        snmp_client: An ``SNMPClient`` (or compatible mock) for controller I/O.
        config: Timing config dict with keys ``max_walk_time_sec``,
            ``min_extension_sec``, ``max_extension_sec``, ``cooldown_sec``.
        _clock: Injectable clock for testability (default ``time.monotonic``).
    """

    def __init__(
        self,
        snmp_client: SNMPClient,
        config: dict[str, Any],
        _clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._snmp = snmp_client
        self._config = config
        self._clock = _clock

        # State
        self._state: PhaseState = PhaseState.IDLE
        self._baseline_walk_times: dict[int, int] = {}
        self._last_write_time: float | None = None
        self._extension_request_time: float | None = None
        self._current_extension_phase: int | None = None
        self._cooldown_start_time: float | None = None
        self._last_error_check_time: float | None = None

        # Preemption polling
        self._last_preempt_check_time: float = 0.0
        self._cached_preempt: bool = False

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> PhaseState:
        return self._state

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def process_tap(self, phase: int, extension_sec: int) -> bool:
        """Attempt a walk-time extension for *phase*.

        Returns ``True`` if the extension was successfully requested,
        ``False`` if denied for any reason.
        """
        # 1. Guard: only from IDLE
        if self._state != PhaseState.IDLE:
            logger.info(
                "process_tap rejected: state=%s (not IDLE)", self._state.value,
            )
            return False

        # 2. Preemption check
        preempt = await self._check_preemption(force=True)
        if preempt:
            logger.info("process_tap rejected: preemption active")
            return False

        # 3. Read current walk time (becomes baseline)
        walk_oid = get_oid(PED_WALK_TIME, phase)
        current_raw = await self._snmp.snmp_get(walk_oid)
        if current_raw is None:
            logger.warning("process_tap: cannot read PED_WALK_TIME for phase %d", phase)
            return False
        baseline = int(current_raw)
        self._baseline_walk_times[phase] = baseline

        # 4. Clamp extension via safety module
        clamped, warnings = safety.validate_extension_request(
            extension_sec, baseline, self._config,
        )
        if warnings:
            logger.info("validate_extension_request warnings: %s", warnings)
        if clamped == 0:
            logger.info("process_tap: extension clamped to 0, nothing to do")
            return False

        # 5. Safety check on proposed value
        target = baseline + clamped
        now = self._clock()
        allowed, reason = safety.check_safety(
            oid_name="PED_WALK_TIME",
            proposed_value=target,
            current_value=baseline,
            baseline_value=baseline,
            config=self._config,
            preemption_active=False,  # already checked above
            last_write_timestamp=self._last_write_time,
            now=now,
        )
        if not allowed:
            logger.info("process_tap: safety check blocked: %s", reason)
            return False

        # 6. SNMP SET
        set_ok = await self._snmp.snmp_set(walk_oid, target)

        if set_ok:
            # 7. Verify write
            readback = await self._snmp.snmp_get(walk_oid)
            if readback is not None and int(readback) == target:
                self._last_write_time = self._clock()
                self._extension_request_time = self._clock()
                self._current_extension_phase = phase
                self._transition(PhaseState.EXTENSION_REQUESTED, "tap_accepted")
                return True
            else:
                logger.warning(
                    "process_tap: verify failed (expected %d, got %s), "
                    "falling back to PED_CALL",
                    target, readback,
                )

        # 8. Fallback: place a ped call
        call_oid = get_oid(PED_CALL, phase)
        call_ok = await self._snmp.snmp_set(call_oid, 1)
        if call_ok:
            self._last_write_time = self._clock()
            self._extension_request_time = self._clock()
            self._current_extension_phase = phase
            self._transition(PhaseState.EXTENSION_REQUESTED, "ped_call_fallback")
            return True

        logger.error("process_tap: both SET and PED_CALL failed for phase %d", phase)
        return False

    # ------------------------------------------------------------------
    # Monitor loop
    # ------------------------------------------------------------------

    async def monitor_loop(self) -> None:
        """Background task — polls signal state and drives transitions."""
        while True:
            await self._tick()
            await asyncio.sleep(POLL_INTERVAL_SEC)

    async def _tick(self) -> None:
        """Execute one iteration of the state machine."""
        state = self._state

        if state == PhaseState.IDLE:
            return

        # In all non-IDLE states, check preemption
        if state in (PhaseState.EXTENSION_REQUESTED, PhaseState.WALK_EXTENDED):
            preempt = await self._check_preemption()
            if preempt:
                self._transition(PhaseState.RESTORING, "preemption_detected")
                return  # restore will execute on the next tick

        if state == PhaseState.EXTENSION_REQUESTED:
            await self._tick_extension_requested()
        elif state == PhaseState.WALK_EXTENDED:
            await self._tick_walk_extended()
        elif state == PhaseState.RESTORING:
            await self._tick_restoring()
        elif state == PhaseState.COOLDOWN:
            self._tick_cooldown()
        elif state == PhaseState.ERROR:
            await self._tick_error()

    # -- Per-state tick handlers -----------------------------------------------

    async def _tick_extension_requested(self) -> None:
        now = self._clock()

        # Timeout: signal cycle passed without serving our ped phase
        if (
            self._extension_request_time is not None
            and now - self._extension_request_time > EXTENSION_TIMEOUT_SEC
        ):
            self._transition(PhaseState.RESTORING, "extension_timeout")
            return

        # Check if ped phase entered WALK
        phase = self._current_extension_phase
        if phase is not None and await self._ped_phase_is_walk(phase):
            self._transition(PhaseState.WALK_EXTENDED, "ped_walk_started")

    async def _tick_walk_extended(self) -> None:
        phase = self._current_extension_phase
        if phase is None:
            self._transition(PhaseState.RESTORING, "no_phase_tracked")
            return

        # Walk ended?
        if not await self._ped_phase_is_walk(phase):
            self._transition(PhaseState.RESTORING, "walk_phase_ended")

    async def _tick_restoring(self) -> None:
        phase = self._current_extension_phase
        if phase is None:
            # Nothing to restore — go straight to cooldown
            self._transition(PhaseState.COOLDOWN, "nothing_to_restore")
            return

        success = await self._restore_baseline(phase)
        if success:
            self._transition(PhaseState.COOLDOWN, "baseline_restored")
        else:
            logger.critical(
                "Failed to restore baseline for phase %d after %d retries",
                phase, RESTORE_MAX_RETRIES,
            )
            self._transition(PhaseState.ERROR, "restore_failed")

    def _tick_cooldown(self) -> None:
        cooldown_sec = self._config.get("cooldown_sec", DEFAULT_COOLDOWN_SEC)
        if (
            self._cooldown_start_time is not None
            and self._clock() - self._cooldown_start_time >= cooldown_sec
        ):
            self._transition(PhaseState.IDLE, "cooldown_expired")

    async def _tick_error(self) -> None:
        now = self._clock()

        # Only probe every ERROR_RECOVERY_INTERVAL_SEC
        if (
            self._last_error_check_time is not None
            and now - self._last_error_check_time < ERROR_RECOVERY_INTERVAL_SEC
        ):
            return

        self._last_error_check_time = now

        # Try contacting controller
        desc = await self._snmp.snmp_get(CONTROLLER_DESCRIPTION)
        if desc is None:
            return  # still unreachable

        # Controller is back — check if baseline is already correct
        phase = self._current_extension_phase
        if phase is not None and phase in self._baseline_walk_times:
            walk_oid = get_oid(PED_WALK_TIME, phase)
            current = await self._snmp.snmp_get(walk_oid)
            if current is not None and int(current) == self._baseline_walk_times[phase]:
                logger.info(
                    "Error recovery: phase %d baseline confirmed correct", phase,
                )
                self._transition(PhaseState.IDLE, "error_recovered")
                return

            # Try one more restore attempt
            ok = await self._snmp.snmp_set(walk_oid, self._baseline_walk_times[phase])
            if ok:
                readback = await self._snmp.snmp_get(walk_oid)
                if readback is not None and int(readback) == self._baseline_walk_times[phase]:
                    self._transition(PhaseState.IDLE, "error_recovered_after_restore")
                    return
        else:
            # No baseline to check — just recover
            self._transition(PhaseState.IDLE, "error_recovered")

    # ------------------------------------------------------------------
    # Restore baseline
    # ------------------------------------------------------------------

    async def _restore_baseline(self, phase: int) -> bool:
        """Restore original walk time. Retries up to 3 times.

        Returns ``True`` on success, ``False`` if all retries fail.
        """
        baseline = self._baseline_walk_times.get(phase)
        if baseline is None:
            logger.warning("_restore_baseline: no saved baseline for phase %d", phase)
            return True  # nothing to restore

        walk_oid = get_oid(PED_WALK_TIME, phase)

        for attempt in range(RESTORE_MAX_RETRIES):
            ok = await self._snmp.snmp_set(walk_oid, baseline)
            if ok:
                readback = await self._snmp.snmp_get(walk_oid)
                if readback is not None and int(readback) == baseline:
                    del self._baseline_walk_times[phase]
                    return True

            if attempt < RESTORE_MAX_RETRIES - 1:
                await asyncio.sleep(RESTORE_RETRY_DELAY_SEC)

        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _ped_phase_is_walk(self, phase: int) -> bool:
        """Check if *phase* is currently in the pedestrian WALK state."""
        raw = await self._snmp.snmp_get(PED_PHASE_STATUS)
        if raw is None:
            return False
        try:
            status = int(raw)
        except (TypeError, ValueError):
            if isinstance(raw, (bytes, bytearray)) and len(raw) > 0:
                byte_index = (phase - 1) // 8
                bit_index = (phase - 1) % 8
                if byte_index < len(raw):
                    return bool(raw[byte_index] & (1 << bit_index))
            return False
        return bool(status & (1 << (phase - 1)))

    async def _check_preemption(self, *, force: bool = False) -> bool:
        """Read preemption status, rate-limited to 1s intervals."""
        now = self._clock()
        if not force and (now - self._last_preempt_check_time < PREEMPT_POLL_INTERVAL_SEC):
            return self._cached_preempt

        self._last_preempt_check_time = now
        raw = await self._snmp.snmp_get(get_oid(PREEMPT_STATUS, 1))
        if raw is not None and int(raw) > 0:
            self._cached_preempt = True
        else:
            self._cached_preempt = False
        return self._cached_preempt

    def _transition(self, new_state: PhaseState, reason: str) -> None:
        """Perform a state transition with logging and timer resets."""
        old = self._state
        self._state = new_state
        logger.info(
            "PhaseManager: %s -> %s (%s)", old.value, new_state.value, reason,
        )

        # Per-state entry actions
        if new_state == PhaseState.COOLDOWN:
            self._cooldown_start_time = self._clock()
        elif new_state == PhaseState.ERROR:
            self._last_error_check_time = None
        elif new_state == PhaseState.IDLE:
            self._current_extension_phase = None
            self._extension_request_time = None
            self._cooldown_start_time = None
