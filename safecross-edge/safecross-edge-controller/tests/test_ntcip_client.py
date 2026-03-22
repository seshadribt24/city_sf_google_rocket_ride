"""Tests for the NTCIP/SNMP client — OID construction and safety bounds.

Covers:
- Correct OID construction for each phase number
- SNMP SET value within safety bounds
- SET value above 45-second ceiling rejected
- SET value above config max rejected
- Preemption check reads correct OIDs
- Mock responses: success, timeout, error
- Vendor profile OID override works correctly
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.config_manager import SignalControllerConfig
from src.ntcip_client import (
    NTCIP_BASE,
    EconoliteCobaltProfile,
    McCainProfile,
    NTCIPClient,
    PhaseState,
    SNMPError,
    VendorOIDProfile,
    get_vendor_profile,
)


class TestVendorOIDProfiles:
    """Tests for vendor OID profile system."""

    def test_base_profile_ped_walk_oid(self) -> None:
        """Base profile returns correct phaseWalk OID for a given phase."""
        # TODO: profile = VendorOIDProfile()
        # TODO: assert profile.ped_walk_time_oid(4) == f"{NTCIP_BASE}.1.2.1.7.4"
        pass

    def test_base_profile_ped_call_oid(self) -> None:
        """Base profile returns correct phasePedCall OID."""
        # TODO: assert profile.ped_call_oid(8) == f"{NTCIP_BASE}.1.3.1.3.8"
        pass

    def test_base_profile_preempt_oid(self) -> None:
        """Base profile returns correct preemptState OID."""
        # TODO: assert profile.preempt_state_oid(1) == f"{NTCIP_BASE}.6.5.1.4.1"
        pass

    def test_econolite_cobalt_inherits_base(self) -> None:
        """Econolite Cobalt profile uses base OIDs (no overrides)."""
        # TODO: Verify EconoliteCobaltProfile matches VendorOIDProfile
        pass

    def test_get_vendor_profile_known_model(self) -> None:
        """get_vendor_profile returns correct profile for known model."""
        # TODO: assert isinstance(get_vendor_profile("econolite_cobalt"), EconoliteCobaltProfile)
        pass

    def test_get_vendor_profile_unknown_model(self) -> None:
        """get_vendor_profile returns base profile for unknown model."""
        # TODO: assert type(get_vendor_profile("unknown")) is VendorOIDProfile
        pass


class TestOIDConstruction:
    """Tests for per-phase OID construction."""

    def test_ped_walk_time_oid_phase_4(self) -> None:
        """phaseWalk OID for phase 4."""
        # TODO: Verify OID string construction
        pass

    def test_ped_walk_time_oid_phase_8(self) -> None:
        """phaseWalk OID for phase 8."""
        # TODO: Verify OID string construction
        pass

    def test_ped_clear_time_oid(self) -> None:
        """phasePedClear OID for a given phase."""
        # TODO: Verify OID string construction
        pass


class TestSafetyBounds:
    """Tests for SNMP SET safety constraints."""

    def test_set_value_within_bounds_accepted(self) -> None:
        """SET with value within safety bounds succeeds."""
        # TODO: Mock SNMP SET success for a valid value
        pass

    def test_set_value_above_45_sec_ceiling_rejected(self) -> None:
        """SET with value > 45 seconds is rejected."""
        # TODO: Call set_ped_walk_time with 50, verify rejection
        pass

    def test_set_value_above_config_max_rejected(self) -> None:
        """SET with value > base + max_extension is rejected."""
        # TODO: Call set_ped_walk_time exceeding config max
        pass


class TestPreemptionCheck:
    """Tests for preemption status checking."""

    def test_no_preemption_returns_false(self) -> None:
        """No active preemption returns False."""
        # TODO: Mock SNMP GET returning no preemption, verify False
        pass

    def test_active_preemption_returns_true(self) -> None:
        """Active preemption returns True."""
        # TODO: Mock SNMP GET returning active preemption, verify True
        pass


class TestSNMPOperations:
    """Tests for SNMP GET/SET with mocked responses."""

    def test_snmp_get_success(self) -> None:
        """SNMP GET returns value on success."""
        # TODO: Mock successful SNMP GET response
        pass

    def test_snmp_get_timeout_raises(self) -> None:
        """SNMP GET raises SNMPError on timeout."""
        # TODO: Mock timeout, verify SNMPError raised
        pass

    def test_snmp_set_success_returns_true(self) -> None:
        """SNMP SET returns True on acknowledgment."""
        # TODO: Mock successful SNMP SET, verify True
        pass

    def test_snmp_set_error_returns_false(self) -> None:
        """SNMP SET returns False on error."""
        # TODO: Mock SNMP error, verify False
        pass
