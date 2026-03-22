"""Timing engine — calculates pedestrian walk phase extension duration.

Determines how many extra seconds to grant based on crossing width,
using a target walking speed of 2.5 ft/sec (slower than MUTCD standard
of 3.5 ft/sec to accommodate elderly and disabled pedestrians).
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config_manager import CrossingConfig

logger = logging.getLogger(__name__)

# Target walking speed for accessible pedestrians (ft/sec)
ACCESSIBLE_WALK_SPEED = 2.5

# Hard-coded safety ceiling: never exceed this total walk time (seconds)
MAX_TOTAL_WALK_SEC = 45


class TimingEngine:
    """Calculates extension duration for each crossing.

    Supports multiple formula modes via config, but currently only
    implements 'linear_by_width'.

    Attributes:
        crossings: Mapping of crossing_id to CrossingConfig.
    """

    def __init__(self, crossings: list[CrossingConfig]) -> None:
        """Initialize the timing engine with crossing configurations.

        Args:
            crossings: List of crossing configurations from the intersection config.
        """
        self.crossings = {c.crossing_id: c for c in crossings}

    def calculate_extension(self, crossing_id: str) -> int:
        """Calculate pedestrian walk phase extension in seconds.

        Uses the 'linear_by_width' formula:
            needed_total = crossing_width_ft / 2.5
            already_provided = base_walk_sec + base_clearance_sec
            raw_extension = needed_total - already_provided
            extension = clamp(ceil(raw_extension), min_extension_sec, max_extension_sec)

        Also enforces the hard-coded 45-second total walk time ceiling.

        Args:
            crossing_id: The crossing to calculate for.

        Returns:
            Integer seconds of extension to grant.

        Raises:
            KeyError: If crossing_id is not found in config.
        """
        # TODO: Implement linear_by_width formula
        # TODO: Clamp between min_extension_sec and max_extension_sec
        # TODO: Enforce MAX_TOTAL_WALK_SEC ceiling
        raise NotImplementedError

    def get_base_walk(self, crossing_id: str) -> int:
        """Return the base walk time for a crossing.

        Args:
            crossing_id: The crossing to look up.

        Returns:
            Base walk time in seconds.
        """
        # TODO: Return crossing config base_walk_sec
        raise NotImplementedError

    def get_total_walk_time(self, crossing_id: str, extension_sec: int) -> int:
        """Calculate total walk time (base + extension) with safety cap.

        Args:
            crossing_id: The crossing to calculate for.
            extension_sec: Proposed extension in seconds.

        Returns:
            Capped total walk time in seconds (never exceeds MAX_TOTAL_WALK_SEC).
        """
        # TODO: Return min(base_walk + extension, MAX_TOTAL_WALK_SEC)
        raise NotImplementedError
