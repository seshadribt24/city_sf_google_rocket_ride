"""Tests for the signal state machine — extension lifecycle transitions.

Covers:
- IDLE -> EXTENSION_REQUESTED on valid tap
- EXTENSION_REQUESTED -> WALK_EXTENDED on SNMP ack
- EXTENSION_REQUESTED -> ERROR on SNMP timeout
- WALK_EXTENDED -> RESTORING on PED_CLEAR detection
- RESTORING -> COOLDOWN on base timing restore
- COOLDOWN -> IDLE after elapsed time
- ERROR -> IDLE after retry exhaustion
- No transition from IDLE on rejected tap
- Preemption during any state handled correctly
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.ntcip_client import PhaseState
from src.signal_state import ExtensionState, SignalStateMachine


class TestIdleState:
    """Tests for behavior in IDLE state."""

    def test_initial_state_is_idle(
        self, sample_crossing_ns, mock_ntcip_client, event_db
    ) -> None:
        """State machine starts in IDLE."""
        # TODO: sm = SignalStateMachine(sample_crossing_ns, mock_ntcip_client, event_db)
        # TODO: assert sm.state == ExtensionState.IDLE
        pass

    def test_transition_to_extension_requested(
        self, sample_crossing_ns, mock_ntcip_client, event_db
    ) -> None:
        """Valid tap transitions from IDLE to EXTENSION_REQUESTED."""
        # TODO: sm.transition_to(ExtensionState.EXTENSION_REQUESTED)
        # TODO: assert sm.state == ExtensionState.EXTENSION_REQUESTED
        pass

    def test_no_transition_on_rejected_tap(
        self, sample_crossing_ns, mock_ntcip_client, event_db
    ) -> None:
        """Rejected tap does not change state from IDLE."""
        # TODO: Keep state in IDLE, assert no transition
        pass


class TestExtensionRequestedState:
    """Tests for EXTENSION_REQUESTED state transitions."""

    def test_to_walk_extended_on_ack(
        self, sample_crossing_ns, mock_ntcip_client, event_db
    ) -> None:
        """SNMP ack with PED_WALK transitions to WALK_EXTENDED."""
        # TODO: Mock phase state as PED_WALK
        # TODO: sm.tick(), assert WALK_EXTENDED
        pass

    def test_to_error_on_snmp_timeout(
        self, sample_crossing_ns, mock_ntcip_client, event_db
    ) -> None:
        """SNMP timeout transitions to ERROR."""
        # TODO: Mock SNMP timeout
        # TODO: sm.tick(), assert ERROR
        pass

    def test_to_idle_on_phase_change(
        self, sample_crossing_ns, mock_ntcip_client, event_db
    ) -> None:
        """Phase change before extension transitions back to IDLE."""
        # TODO: Mock phase as PED_CLEAR (missed it)
        # TODO: sm.tick(), assert IDLE
        pass


class TestWalkExtendedState:
    """Tests for WALK_EXTENDED state transitions."""

    def test_to_restoring_on_ped_clear(
        self, sample_crossing_ns, mock_ntcip_client, event_db
    ) -> None:
        """PED_CLEAR detection transitions to RESTORING."""
        # TODO: Mock phase as PED_CLEAR
        # TODO: sm.tick(), assert RESTORING
        pass

    def test_to_error_on_snmp_loss(
        self, sample_crossing_ns, mock_ntcip_client, event_db
    ) -> None:
        """Lost SNMP communication transitions to ERROR."""
        # TODO: Mock SNMP failure
        # TODO: sm.tick(), assert ERROR
        pass


class TestRestoringState:
    """Tests for RESTORING state transitions."""

    def test_to_cooldown_on_restore_success(
        self, sample_crossing_ns, mock_ntcip_client, event_db
    ) -> None:
        """Successful base timing restore transitions to COOLDOWN."""
        # TODO: Mock restore_base_timing returning True
        # TODO: sm.tick(), assert COOLDOWN
        pass

    def test_to_error_on_restore_failure(
        self, sample_crossing_ns, mock_ntcip_client, event_db
    ) -> None:
        """Failed restore transitions to ERROR."""
        # TODO: Mock restore_base_timing returning False
        # TODO: sm.tick(), assert ERROR
        pass


class TestCooldownState:
    """Tests for COOLDOWN state transitions."""

    def test_to_idle_after_cooldown_elapsed(
        self, sample_crossing_ns, mock_ntcip_client, event_db
    ) -> None:
        """IDLE reached after cooldown_sec elapses."""
        # TODO: Fast-forward time past cooldown
        # TODO: sm.tick(), assert IDLE
        pass


class TestErrorState:
    """Tests for ERROR state transitions."""

    def test_to_idle_after_retry_exhaustion(
        self, sample_crossing_ns, mock_ntcip_client, event_db
    ) -> None:
        """ERROR transitions to IDLE after max retries or timeout."""
        # TODO: Exhaust retries or exceed timeout
        # TODO: sm.tick(), assert IDLE
        pass


class TestPreemptionHandling:
    """Tests for preemption during any state."""

    def test_preemption_during_walk_extended(
        self, sample_crossing_ns, mock_ntcip_client, event_db
    ) -> None:
        """Preemption during WALK_EXTENDED is handled safely."""
        # TODO: Mock preemption active during WALK_EXTENDED
        # TODO: Verify no timing override attempted
        pass
