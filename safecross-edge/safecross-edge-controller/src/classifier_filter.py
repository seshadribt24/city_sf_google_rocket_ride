"""Classifier filter — validates and deduplicates tap events.

Before a tap event triggers a signal extension, it must pass several
checks: card type eligibility, duplicate detection, cooldown, max
extensions per cycle, and preemption status. Every tap is logged
regardless of filter outcome.
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config_manager import CrossingConfig, TimingRulesConfig
    from .message_protocol import CardTapEvent
    from .ntcip_client import NTCIPClient

logger = logging.getLogger(__name__)


class TapFilterResult(Enum):
    """Result of running a tap event through the classifier filter."""

    ACCEPTED = "accepted"
    REJECTED_CARD_TYPE = "rejected_card_type"
    REJECTED_COOLDOWN = "rejected_cooldown"
    REJECTED_DUPLICATE = "rejected_duplicate"
    REJECTED_PREEMPTION = "rejected_preemption"
    REJECTED_MAX_EXTENSIONS = "rejected_max_ext"


class ClassifierFilter:
    """Validates and filters tap events before granting extensions.

    Runs a series of checks in order: card type, duplicate, cooldown,
    max extensions per cycle, and preemption. All results are logged
    for analytics.

    Attributes:
        crossing_config: Configuration for the crossing this filter serves.
        timing_rules: Global timing rules from intersection config.
    """

    def __init__(
        self,
        crossing_config: CrossingConfig,
        timing_rules: TimingRulesConfig,
    ) -> None:
        """Initialize the classifier filter.

        Args:
            crossing_config: Crossing-specific configuration.
            timing_rules: Timing rules from the intersection config.
        """
        self.crossing_config = crossing_config
        self.timing_rules = timing_rules
        # TODO: Initialize TTL cache for duplicate detection
        # TODO: Initialize per-crossing cooldown tracking
        # TODO: Initialize per-cycle extension counter

    async def check(
        self,
        event: CardTapEvent,
        ntcip: NTCIPClient,
    ) -> TapFilterResult:
        """Run all filter checks on a tap event in order.

        Checks are run in this order (short-circuits on first rejection):
        1. Card type eligibility
        2. Duplicate tap detection (same UID within 5 seconds)
        3. Cooldown check (per-crossing)
        4. Max extensions per cycle
        5. Preemption check (async SNMP query)

        Args:
            event: The card tap event to validate.
            ntcip: NTCIP client for preemption check.

        Returns:
            TapFilterResult indicating acceptance or rejection reason.
        """
        # TODO: Run checks in order, return first rejection or ACCEPTED
        raise NotImplementedError

    def _check_card_type(self, event: CardTapEvent) -> TapFilterResult | None:
        """Check if the card type is in the eligible list.

        Args:
            event: The card tap event.

        Returns:
            REJECTED_CARD_TYPE if ineligible, None if passed.
        """
        # TODO: Check event.card_type against self.timing_rules.eligible_card_types
        raise NotImplementedError

    def _check_duplicate(self, event: CardTapEvent) -> TapFilterResult | None:
        """Check if the same card UID was seen within the last 5 seconds.

        Maintains a small TTL cache of recent UIDs to prevent
        double-counting from multiple taps.

        Args:
            event: The card tap event.

        Returns:
            REJECTED_DUPLICATE if seen recently, None if passed.
        """
        # TODO: Check UID against TTL cache, update cache
        raise NotImplementedError

    def _check_cooldown(self) -> TapFilterResult | None:
        """Check if this crossing is still in cooldown from a recent extension.

        Args: None (uses internal state).

        Returns:
            REJECTED_COOLDOWN if in cooldown period, None if passed.
        """
        # TODO: Compare current time against last extension timestamp
        raise NotImplementedError

    def _check_max_extensions(self) -> TapFilterResult | None:
        """Check if max extensions per signal cycle has been reached.

        Args: None (uses internal state).

        Returns:
            REJECTED_MAX_EXTENSIONS if limit reached, None if passed.
        """
        # TODO: Check cycle extension counter against config limit
        raise NotImplementedError

    def record_extension_granted(self) -> None:
        """Record that an extension was granted for cooldown/counter tracking.

        Called by the main loop after a successful extension.
        """
        # TODO: Update last extension time and cycle counter
        raise NotImplementedError

    def reset_cycle(self) -> None:
        """Reset the per-cycle extension counter.

        Called when a new signal cycle begins.
        """
        # TODO: Reset cycle extension counter
        raise NotImplementedError
