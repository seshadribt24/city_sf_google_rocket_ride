"""Tests for signal controller safety validation.

Every test exercises a specific safety rule in check_safety() or
validate_extension_request().  This is safety-critical code — all
tests must pass.
"""

from __future__ import annotations

import pytest

from src.signal_interface.safety import (
    WRITABLE_OID_ALLOWLIST,
    check_safety,
    validate_extension_request,
)


# -----------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------

def _base_config() -> dict:
    """Return a minimal valid timing config dict."""
    return {"max_walk_time_sec": 45, "min_extension_sec": 3, "max_extension_sec": 13}


def _ok_params(**overrides) -> dict:
    """Return a set of check_safety kwargs that pass all rules."""
    defaults = dict(
        oid_name="PED_WALK_TIME",
        proposed_value=20,
        current_value=12,
        baseline_value=12,
        config=_base_config(),
        preemption_active=False,
        last_write_timestamp=None,
        now=None,
        cycle_length_sec=90.0,
    )
    defaults.update(overrides)
    return defaults


# =================================================================
# check_safety — OID allowlist
# =================================================================


class TestAllowlist:
    def test_allowlist_blocks_unknown_oid(self) -> None:
        allowed, reason = check_safety(**_ok_params(oid_name="VEHICLE_GREEN_TIME"))
        assert allowed is False
        assert reason.startswith("oid_not_in_allowlist")
        assert "VEHICLE_GREEN_TIME" in reason

    def test_allowlist_allows_ped_walk_time(self) -> None:
        allowed, reason = check_safety(**_ok_params(oid_name="PED_WALK_TIME"))
        assert (allowed, reason) == (True, "ok")

    def test_allowlist_allows_ped_call(self) -> None:
        allowed, reason = check_safety(**_ok_params(oid_name="PED_CALL"))
        assert (allowed, reason) == (True, "ok")


# =================================================================
# check_safety — preemption
# =================================================================


class TestPreemption:
    def test_preemption_blocks_write(self) -> None:
        allowed, reason = check_safety(**_ok_params(preemption_active=True))
        assert (allowed, reason) == (False, "preemption_active")


# =================================================================
# check_safety — baseline
# =================================================================


class TestBaseline:
    def test_below_baseline_blocked(self) -> None:
        allowed, reason = check_safety(**_ok_params(proposed_value=8, baseline_value=12))
        assert allowed is False
        assert "below_baseline" in reason
        assert "proposed=8" in reason
        assert "baseline=12" in reason

    def test_equal_to_baseline_allowed(self) -> None:
        allowed, reason = check_safety(**_ok_params(proposed_value=12, baseline_value=12))
        assert (allowed, reason) == (True, "ok")


# =================================================================
# check_safety — absolute max
# =================================================================


class TestMaxWalkTime:
    def test_exceeds_max_blocked(self) -> None:
        allowed, reason = check_safety(**_ok_params(
            proposed_value=50, config={"max_walk_time_sec": 45},
        ))
        assert allowed is False
        assert "exceeds_max" in reason
        assert "proposed=50" in reason
        assert "max=45" in reason

    def test_within_max_allowed(self) -> None:
        allowed, reason = check_safety(**_ok_params(
            proposed_value=25, config={"max_walk_time_sec": 45},
        ))
        assert (allowed, reason) == (True, "ok")


# =================================================================
# check_safety — rate limit
# =================================================================


class TestRateLimit:
    def test_rate_limit_blocks_rapid_writes(self) -> None:
        allowed, reason = check_safety(**_ok_params(
            last_write_timestamp=100.0, now=130.0, cycle_length_sec=90.0,
        ))
        assert allowed is False
        assert "rate_limited" in reason
        assert "30.0s" in reason

    def test_rate_limit_allows_after_cycle(self) -> None:
        allowed, reason = check_safety(**_ok_params(
            last_write_timestamp=100.0, now=180.0, cycle_length_sec=90.0,
        ))
        assert (allowed, reason) == (True, "ok")

    def test_rate_limit_allows_first_write(self) -> None:
        allowed, reason = check_safety(**_ok_params(
            last_write_timestamp=None, now=100.0,
        ))
        assert (allowed, reason) == (True, "ok")


# =================================================================
# check_safety — all rules pass
# =================================================================


class TestAllRulesPass:
    def test_all_rules_pass(self) -> None:
        allowed, reason = check_safety(**_ok_params())
        assert (allowed, reason) == (True, "ok")


# =================================================================
# validate_extension_request
# =================================================================


class TestValidateExtension:
    def test_validate_clamps_to_minimum(self) -> None:
        clamped, warnings = validate_extension_request(
            extension_sec=1, baseline_walk_sec=7, config=_base_config(),
        )
        assert clamped == 3
        assert warnings == ["clamped_to_minimum"]

    def test_validate_clamps_to_maximum(self) -> None:
        clamped, warnings = validate_extension_request(
            extension_sec=20, baseline_walk_sec=7, config=_base_config(),
        )
        assert clamped == 13
        assert warnings == ["clamped_to_maximum"]

    def test_validate_clamps_to_absolute_max(self) -> None:
        clamped, warnings = validate_extension_request(
            extension_sec=13, baseline_walk_sec=38, config=_base_config(),
        )
        assert clamped == 7
        assert "clamped_to_absolute_max" in warnings

    def test_validate_zero_extension(self) -> None:
        clamped, warnings = validate_extension_request(
            extension_sec=0, baseline_walk_sec=7, config=_base_config(),
        )
        assert clamped == 0
        assert warnings == ["no_extension_needed"]

    def test_validate_negative_extension(self) -> None:
        clamped, warnings = validate_extension_request(
            extension_sec=-3, baseline_walk_sec=7, config=_base_config(),
        )
        assert clamped == 0
        assert warnings == ["no_extension_needed"]
