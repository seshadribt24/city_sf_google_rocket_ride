"""Signal controller state machine — extension lifecycle per crossing.

Manages the state machine for each crossing's extension lifecycle,
from idle through extension request, active walk, restoration, and
cooldown. Polls SNMP every 500ms during active states.
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .config_manager import CrossingConfig
    from .event_logger import EventLogger
    from .ntcip_client import NTCIPClient

logger = logging.getLogger(__name__)

# Maximum retries before resetting from ERROR to IDLE
MAX_ERROR_RETRIES = 3

# Maximum time in ERROR state before forced reset (seconds)
ERROR_TIMEOUT_SEC = 30


class ExtensionState(Enum):
    """States in the per-crossing extension lifecycle."""

    IDLE = "idle"
    EXTENSION_REQUESTED = "extension_requested"
    WALK_EXTENDED = "walk_extended"
    RESTORING = "restoring"
    COOLDOWN = "cooldown"
    ERROR = "error"


class SignalStateMachine:
    """Per-crossing extension lifecycle state machine.

    State transitions:
        IDLE -> EXTENSION_REQUESTED  (valid tap, SNMP SET sent)
        EXTENSION_REQUESTED -> WALK_EXTENDED  (SNMP ack, phase is PED_WALK)
        EXTENSION_REQUESTED -> ERROR  (SNMP timeout/error)
        EXTENSION_REQUESTED -> IDLE  (phase changed before we could extend)
        WALK_EXTENDED -> RESTORING  (phase transitioned to PED_CLEAR)
        WALK_EXTENDED -> ERROR  (lost SNMP communication)
        RESTORING -> COOLDOWN  (base timing restored)
        RESTORING -> ERROR  (restore SNMP SET failed)
        COOLDOWN -> IDLE  (cooldown elapsed)
        ERROR -> IDLE  (after retries exhausted or timeout)

    Attributes:
        crossing_config: Configuration for this crossing.
        ntcip: NTCIP client for signal controller communication.
        db: Event logger for state transition logging.
        state: Current extension state.
    """

    def __init__(
        self,
        crossing_config: CrossingConfig,
        ntcip: NTCIPClient,
        db: EventLogger,
    ) -> None:
        """Initialize the state machine for a crossing.

        Args:
            crossing_config: Configuration for this crossing.
            ntcip: NTCIP client instance.
            db: Event logger for recording state transitions.
        """
        self.crossing_config = crossing_config
        self.ntcip = ntcip
        self.db = db
        self.state = ExtensionState.IDLE
        self._state_entered_at: float = time.monotonic()
        self._error_retries: int = 0

    async def tick(self) -> None:
        """Advance the state machine based on current signal phase.

        Called every 500ms by the main event loop. Reads the current
        signal phase state via SNMP and performs the appropriate state
        transition. All transitions are logged with timestamps.

        Do NOT rely on timers alone — always read actual phase state.
        """
        # TODO: Read current phase state via SNMP
        # TODO: Switch on self.state and check transition conditions
        # TODO: Log all transitions to the state_transitions table
        raise NotImplementedError

    async def transition_to(self, new_state: ExtensionState, trigger: str = "") -> None:
        """Transition to a new state with logging.

        Args:
            new_state: The target state.
            trigger: Description of what caused this transition.
        """
        # TODO: Log the transition (from_state, to_state, trigger)
        # TODO: Update self.state and self._state_entered_at
        raise NotImplementedError

    def _time_in_state(self) -> float:
        """Return seconds elapsed since entering the current state."""
        return time.monotonic() - self._state_entered_at

    async def _handle_idle(self) -> None:
        """Handle tick while in IDLE state. No action needed."""
        # TODO: No-op, waiting for tap event
        pass

    async def _handle_extension_requested(self) -> None:
        """Handle tick while in EXTENSION_REQUESTED state.

        Check if the SNMP SET was acknowledged and the phase is now PED_WALK.
        Transition to WALK_EXTENDED, ERROR, or IDLE as appropriate.
        """
        # TODO: Check phase state, transition accordingly
        raise NotImplementedError

    async def _handle_walk_extended(self) -> None:
        """Handle tick while in WALK_EXTENDED state.

        Poll phase state every 500ms to detect when walk phase ends
        (PED_WALK -> PED_CLEAR). Do NOT rely on timers alone.
        """
        # TODO: Poll phase state, transition to RESTORING when PED_CLEAR
        raise NotImplementedError

    async def _handle_restoring(self) -> None:
        """Handle tick while in RESTORING state.

        Restore base timing via SNMP SET. Transition to COOLDOWN or ERROR.
        """
        # TODO: Restore base timing, transition on success/failure
        raise NotImplementedError

    async def _handle_cooldown(self) -> None:
        """Handle tick while in COOLDOWN state.

        Wait for cooldown_sec to elapse, then transition to IDLE.
        """
        # TODO: Check elapsed time, transition to IDLE when cooldown complete
        raise NotImplementedError

    async def _handle_error(self) -> None:
        """Handle tick while in ERROR state.

        Retry up to MAX_ERROR_RETRIES times or reset after ERROR_TIMEOUT_SEC.
        """
        # TODO: Check retry count and timeout, transition to IDLE
        raise NotImplementedError
