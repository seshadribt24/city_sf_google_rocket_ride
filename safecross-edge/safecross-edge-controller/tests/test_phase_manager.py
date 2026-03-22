"""Tests for the PhaseManager state machine.

Covers the full extension lifecycle, preemption handling, timeout,
error recovery, restore retries, and the critical safety invariant
that baseline timing is always restored.
"""

from __future__ import annotations

from unittest.mock import patch, AsyncMock

import pytest

from src.signal_interface.phase_manager import (
    EXTENSION_TIMEOUT_SEC,
    RESTORE_MAX_RETRIES,
    PhaseManager,
    PhaseState,
)
from src.signal_interface.ntcip_objects import (
    CONTROLLER_DESCRIPTION,
    PED_CALL,
    PED_PHASE_STATUS,
    PED_WALK_TIME,
    PREEMPT_STATUS,
    get_oid,
)
from tests.conftest import MockSNMPClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PHASE = 4
BASELINE_WALK = 7
EXTENSION = 10
TARGET = BASELINE_WALK + EXTENSION  # 17


class FakeClock:
    """Deterministic clock for testing time-dependent behaviour."""

    def __init__(self, start: float = 1000.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


def _make_config(**overrides) -> dict:
    defaults = {
        "max_walk_time_sec": 45,
        "min_extension_sec": 3,
        "max_extension_sec": 13,
        "cooldown_sec": 120,
    }
    defaults.update(overrides)
    return defaults


def _make_manager(
    mock_client: MockSNMPClient | None = None,
    clock: FakeClock | None = None,
    **config_overrides,
) -> tuple[PhaseManager, MockSNMPClient, FakeClock]:
    """Create a PhaseManager wired to a pre-populated mock."""
    if clock is None:
        clock = FakeClock()
    if mock_client is None:
        mock_client = MockSNMPClient()

    # Pre-populate OID store
    mock_client.set_value(get_oid(PED_WALK_TIME, PHASE), BASELINE_WALK)
    mock_client.set_value(PED_PHASE_STATUS, 0)  # no phases in walk
    mock_client.set_value(get_oid(PREEMPT_STATUS, 1), 0)  # no preemption
    mock_client.set_value(CONTROLLER_DESCRIPTION, "TestController")

    config = _make_config(**config_overrides)
    mgr = PhaseManager(mock_client, config, _clock=clock)
    return mgr, mock_client, clock


def _set_ped_walk_active(mock: MockSNMPClient, phase: int = PHASE) -> None:
    """Set the PED_PHASE_STATUS bitmap so *phase* appears to be in WALK."""
    mock.set_value(PED_PHASE_STATUS, 1 << (phase - 1))


def _clear_ped_walk(mock: MockSNMPClient) -> None:
    mock.set_value(PED_PHASE_STATUS, 0)


def _set_preemption(mock: MockSNMPClient, active: bool = True) -> None:
    mock.set_value(get_oid(PREEMPT_STATUS, 1), 1 if active else 0)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHappyPath:

    @pytest.mark.asyncio
    async def test_happy_path_full_lifecycle(self):
        """IDLE → tap → EXTENSION_REQUESTED → WALK_EXTENDED → RESTORING
        → COOLDOWN → IDLE.  Baseline must be restored."""
        mgr, mock, clock = _make_manager()

        # 1. Tap
        result = await mgr.process_tap(PHASE, EXTENSION)
        assert result is True
        assert mgr.state == PhaseState.EXTENSION_REQUESTED

        # Verify SET was called with correct value
        walk_oid = get_oid(PED_WALK_TIME, PHASE)
        set_calls = [(oid, val) for oid, val in mock.set_log if oid == walk_oid]
        assert len(set_calls) >= 1
        assert set_calls[0][1] == TARGET

        # Verify baseline saved
        assert mgr._baseline_walk_times[PHASE] == BASELINE_WALK

        # 2. Ped phase goes to WALK
        clock.advance(1.1)  # past preempt poll interval
        _set_ped_walk_active(mock)
        await mgr._tick()
        assert mgr.state == PhaseState.WALK_EXTENDED

        # 3. Walk ends
        clock.advance(1.1)
        _clear_ped_walk(mock)
        await mgr._tick()
        assert mgr.state == PhaseState.RESTORING

        # 4. Restore executes (next tick)
        await mgr._tick()
        assert mgr.state == PhaseState.COOLDOWN
        # Baseline restored in mock store
        assert mock.get_value(walk_oid) == BASELINE_WALK

        # 5. Cooldown expires
        clock.advance(120)
        await mgr._tick()
        assert mgr.state == PhaseState.IDLE

        # Baseline dict cleaned up
        assert PHASE not in mgr._baseline_walk_times


class TestPreemption:

    @pytest.mark.asyncio
    async def test_preemption_during_extension_requested(self):
        mgr, mock, clock = _make_manager()
        await mgr.process_tap(PHASE, EXTENSION)
        assert mgr.state == PhaseState.EXTENSION_REQUESTED

        _set_preemption(mock)
        clock.advance(1.1)
        await mgr._tick()
        assert mgr.state == PhaseState.RESTORING

    @pytest.mark.asyncio
    async def test_preemption_during_walk_extended(self):
        mgr, mock, clock = _make_manager()
        await mgr.process_tap(PHASE, EXTENSION)

        # Advance to WALK_EXTENDED
        clock.advance(1.1)
        _set_ped_walk_active(mock)
        await mgr._tick()
        assert mgr.state == PhaseState.WALK_EXTENDED

        # Preemption fires
        _set_preemption(mock)
        clock.advance(1.1)
        await mgr._tick()
        assert mgr.state == PhaseState.RESTORING


class TestTimeout:

    @pytest.mark.asyncio
    async def test_extension_timeout(self):
        """Signal cycle passes without serving ped phase → RESTORING."""
        mgr, mock, clock = _make_manager()
        await mgr.process_tap(PHASE, EXTENSION)
        assert mgr.state == PhaseState.EXTENSION_REQUESTED

        # Never set ped walk bit; advance past timeout
        clock.advance(EXTENSION_TIMEOUT_SEC + 1)
        await mgr._tick()
        assert mgr.state == PhaseState.RESTORING


class TestSNMPFailures:

    @pytest.mark.asyncio
    async def test_snmp_timeout_goes_to_error(self):
        mgr, mock, clock = _make_manager()
        await mgr.process_tap(PHASE, EXTENSION)

        # Advance to WALK_EXTENDED
        clock.advance(1.1)
        _set_ped_walk_active(mock)
        await mgr._tick()
        assert mgr.state == PhaseState.WALK_EXTENDED

        # Walk ends → RESTORING
        clock.advance(1.1)
        _clear_ped_walk(mock)
        await mgr._tick()
        assert mgr.state == PhaseState.RESTORING

        # Make all SETs fail so restore fails
        mock.simulate_failure(sets=True)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await mgr._tick()
        assert mgr.state == PhaseState.ERROR

        # New taps should be rejected while in ERROR
        result = await mgr.process_tap(PHASE, EXTENSION)
        assert result is False

    @pytest.mark.asyncio
    async def test_error_recovery(self):
        mgr, mock, clock = _make_manager()
        await mgr.process_tap(PHASE, EXTENSION)

        # Drive to ERROR state
        clock.advance(1.1)
        _set_ped_walk_active(mock)
        await mgr._tick()
        clock.advance(1.1)
        _clear_ped_walk(mock)
        await mgr._tick()
        mock.simulate_failure(sets=True)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await mgr._tick()
        assert mgr.state == PhaseState.ERROR

        # Clear failures, set baseline correct in store
        mock.clear_failures()
        mock.set_value(get_oid(PED_WALK_TIME, PHASE), BASELINE_WALK)

        # Advance past error recovery interval
        clock.advance(30)
        await mgr._tick()
        assert mgr.state == PhaseState.IDLE


class TestRestoreBaseline:

    @pytest.mark.asyncio
    async def test_restore_baseline_retries(self):
        """First 2 SETs fail, 3rd succeeds → returns True."""
        mgr, mock, clock = _make_manager()
        mgr._baseline_walk_times[PHASE] = BASELINE_WALK

        mock.fail_next_n_sets(2)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await mgr._restore_baseline(PHASE)

        assert result is True
        # 2 failed + 1 successful = 3 SET calls to walk OID
        walk_oid = get_oid(PED_WALK_TIME, PHASE)
        walk_sets = [(o, v) for o, v in mock.set_log if o == walk_oid]
        assert len(walk_sets) == 3
        # Baseline cleaned up
        assert PHASE not in mgr._baseline_walk_times

    @pytest.mark.asyncio
    async def test_restore_baseline_all_retries_fail(self):
        """All 3 retries fail → returns False."""
        mgr, mock, clock = _make_manager()
        mgr._baseline_walk_times[PHASE] = BASELINE_WALK

        mock.simulate_failure(sets=True)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await mgr._restore_baseline(PHASE)

        assert result is False
        walk_oid = get_oid(PED_WALK_TIME, PHASE)
        walk_sets = [(o, v) for o, v in mock.set_log if o == walk_oid]
        assert len(walk_sets) == RESTORE_MAX_RETRIES


class TestTapRejection:

    @pytest.mark.asyncio
    async def test_tap_rejected_during_cooldown(self):
        mgr, mock, clock = _make_manager()
        # Force into COOLDOWN
        mgr._state = PhaseState.COOLDOWN
        mgr._cooldown_start_time = clock()

        result = await mgr.process_tap(PHASE, EXTENSION)
        assert result is False
        assert mgr.state == PhaseState.COOLDOWN

    @pytest.mark.asyncio
    async def test_tap_rejected_during_error(self):
        mgr, mock, clock = _make_manager()
        mgr._state = PhaseState.ERROR

        result = await mgr.process_tap(PHASE, EXTENSION)
        assert result is False
        assert mgr.state == PhaseState.ERROR


class TestSafetyIntegration:

    @pytest.mark.asyncio
    async def test_safety_check_blocks_extension(self):
        """Config max_walk_time_sec=8, baseline=7 → extension clamped to 1."""
        mgr, mock, clock = _make_manager(max_walk_time_sec=8)

        result = await mgr.process_tap(PHASE, EXTENSION)
        # Extension should be clamped: max_ext=13 but absolute max is 8,
        # so clamped to 8 - 7 = 1.  Safety should allow this.
        assert result is True
        walk_oid = get_oid(PED_WALK_TIME, PHASE)
        set_calls = [(o, v) for o, v in mock.set_log if o == walk_oid]
        assert set_calls[0][1] == 8  # baseline(7) + clamped(1)


class TestBaselineAlwaysRestored:
    """The critical safety invariant: after any scenario, baseline is restored."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "scenario",
        [
            "happy_path",
            "preempt_during_requested",
            "preempt_during_walk",
            "extension_timeout",
            "error_and_recovery",
        ],
    )
    async def test_baseline_always_restored(self, scenario: str):
        mgr, mock, clock = _make_manager()
        walk_oid = get_oid(PED_WALK_TIME, PHASE)

        await mgr.process_tap(PHASE, EXTENSION)

        if scenario == "happy_path":
            clock.advance(1.1)
            _set_ped_walk_active(mock)
            await mgr._tick()
            clock.advance(1.1)
            _clear_ped_walk(mock)
            await mgr._tick()

        elif scenario == "preempt_during_requested":
            _set_preemption(mock)
            clock.advance(1.1)
            await mgr._tick()

        elif scenario == "preempt_during_walk":
            clock.advance(1.1)
            _set_ped_walk_active(mock)
            await mgr._tick()
            _set_preemption(mock)
            clock.advance(1.1)
            await mgr._tick()

        elif scenario == "extension_timeout":
            clock.advance(EXTENSION_TIMEOUT_SEC + 1)
            await mgr._tick()

        elif scenario == "error_and_recovery":
            clock.advance(1.1)
            _set_ped_walk_active(mock)
            await mgr._tick()
            clock.advance(1.1)
            _clear_ped_walk(mock)
            await mgr._tick()
            # Force restore failure
            mock.simulate_failure(sets=True)
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await mgr._tick()
            assert mgr.state == PhaseState.ERROR
            # Recover
            mock.clear_failures()
            mock.set_value(walk_oid, BASELINE_WALK)
            clock.advance(30)
            await mgr._tick()

        # Drive through remaining states to IDLE
        for _ in range(5):
            if mgr.state == PhaseState.RESTORING:
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    await mgr._tick()
            elif mgr.state == PhaseState.COOLDOWN:
                clock.advance(120)
                await mgr._tick()
            elif mgr.state == PhaseState.IDLE:
                break
            else:
                await mgr._tick()

        # THE critical assertion: baseline is restored
        assert mock.get_value(walk_oid) == BASELINE_WALK
