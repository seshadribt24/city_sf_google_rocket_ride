"""Tests for the classifier filter — tap validation and deduplication.

Covers:
- Senior RTC card -> accepted
- Disabled RTC card -> accepted
- Standard adult card -> rejected_card_type
- Same UID within 5 sec -> rejected_duplicate
- Same UID after 6 sec -> accepted (dedup expired)
- Tap during cooldown -> rejected_cooldown
- Tap after cooldown -> accepted
- Tap during preemption -> rejected_preemption
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.classifier_filter import ClassifierFilter, TapFilterResult
from src.config_manager import CrossingConfig, TimingRulesConfig
from src.message_protocol import CardTapEvent, CardType, ReadMethod


@pytest.fixture
def timing_rules() -> TimingRulesConfig:
    """Default timing rules for filter tests."""
    return TimingRulesConfig(
        cooldown_sec=120,
        max_extensions_per_cycle=1,
        extension_formula="linear_by_width",
        eligible_card_types=["SENIOR_RTC", "DISABLED_RTC"],
        extend_during_active_walk=True,
        block_during_preemption=True,
    )


def _make_tap(card_type: CardType, uid: bytes = b"\x01\x02\x03\x04") -> CardTapEvent:
    """Helper to create a CardTapEvent with given card type and UID."""
    return CardTapEvent(
        card_type=card_type,
        uid=uid,
        timestamp_ms=100000,
        read_method=ReadMethod.APPDIR,
    )


class TestCardTypeFilter:
    """Tests for card type eligibility check."""

    def test_senior_rtc_accepted(
        self, sample_crossing_ns, timing_rules, mock_ntcip_client
    ) -> None:
        """SENIOR_RTC card type is accepted."""
        # TODO: Create filter, check tap with SENIOR_RTC
        # TODO: assert result == TapFilterResult.ACCEPTED
        pass

    def test_disabled_rtc_accepted(
        self, sample_crossing_ns, timing_rules, mock_ntcip_client
    ) -> None:
        """DISABLED_RTC card type is accepted."""
        # TODO: Create filter, check tap with DISABLED_RTC
        # TODO: assert result == TapFilterResult.ACCEPTED
        pass

    def test_standard_card_rejected(
        self, sample_crossing_ns, timing_rules, mock_ntcip_client
    ) -> None:
        """STANDARD card type is rejected."""
        # TODO: Create filter, check tap with STANDARD
        # TODO: assert result == TapFilterResult.REJECTED_CARD_TYPE
        pass

    def test_youth_card_rejected(
        self, sample_crossing_ns, timing_rules, mock_ntcip_client
    ) -> None:
        """YOUTH card type is rejected by default config."""
        # TODO: assert result == TapFilterResult.REJECTED_CARD_TYPE
        pass


class TestDuplicateDetection:
    """Tests for duplicate tap detection (same UID within 5 seconds)."""

    def test_same_uid_within_5sec_rejected(
        self, sample_crossing_ns, timing_rules, mock_ntcip_client
    ) -> None:
        """Same UID tapped within 5 seconds is rejected as duplicate."""
        # TODO: Check same tap twice in quick succession
        # TODO: Second check should return REJECTED_DUPLICATE
        pass

    def test_same_uid_after_6sec_accepted(
        self, sample_crossing_ns, timing_rules, mock_ntcip_client
    ) -> None:
        """Same UID tapped after 6 seconds is accepted (TTL expired)."""
        # TODO: Check tap, advance time by 6 seconds, check again
        # TODO: Second check should return ACCEPTED (assuming cooldown also reset)
        pass

    def test_different_uid_accepted(
        self, sample_crossing_ns, timing_rules, mock_ntcip_client
    ) -> None:
        """Different UIDs are not treated as duplicates."""
        # TODO: Check two taps with different UIDs
        # TODO: Both should pass duplicate check
        pass


class TestCooldownCheck:
    """Tests for per-crossing cooldown enforcement."""

    def test_tap_during_cooldown_rejected(
        self, sample_crossing_ns, timing_rules, mock_ntcip_client
    ) -> None:
        """Tap during cooldown period is rejected."""
        # TODO: Record extension granted, immediately check new tap
        # TODO: assert result == TapFilterResult.REJECTED_COOLDOWN
        pass

    def test_tap_after_cooldown_accepted(
        self, sample_crossing_ns, timing_rules, mock_ntcip_client
    ) -> None:
        """Tap after cooldown period has elapsed is accepted."""
        # TODO: Record extension, advance time past cooldown_sec
        # TODO: assert result == TapFilterResult.ACCEPTED
        pass


class TestMaxExtensionsPerCycle:
    """Tests for per-cycle extension limit."""

    def test_over_limit_rejected(
        self, sample_crossing_ns, timing_rules, mock_ntcip_client
    ) -> None:
        """Tap exceeding max_extensions_per_cycle is rejected."""
        # TODO: Record max_extensions_per_cycle extensions, check another
        # TODO: assert result == TapFilterResult.REJECTED_MAX_EXTENSIONS
        pass


class TestPreemptionCheck:
    """Tests for preemption rejection."""

    def test_tap_during_preemption_rejected(
        self, sample_crossing_ns, timing_rules, mock_ntcip_client
    ) -> None:
        """Tap during active preemption is rejected."""
        # TODO: Mock ntcip.check_preemption_active returning True
        # TODO: assert result == TapFilterResult.REJECTED_PREEMPTION
        pass

    def test_tap_without_preemption_passes(
        self, sample_crossing_ns, timing_rules, mock_ntcip_client
    ) -> None:
        """Tap without active preemption passes the preemption check."""
        # TODO: Mock ntcip.check_preemption_active returning False
        # TODO: Preemption check should pass
        pass
