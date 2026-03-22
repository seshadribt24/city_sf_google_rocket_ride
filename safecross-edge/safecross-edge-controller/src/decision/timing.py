"""Walk-time extension calculation based on crossing geometry and card type."""

from __future__ import annotations

import math
from typing import Any

from src.reader_interface.protocol import (
    CARD_TYPE_DISABLED_RTC,
    CARD_TYPE_SENIOR_RTC,
)


def calculate_extension(
    card_type: int,
    crossing_width_ft: float,
    base_walk_time_sec: int,
    config: dict[str, Any],
) -> int:
    """Calculate the required walk-time extension in whole seconds.

    Args:
        card_type: NFC card type constant (e.g. ``CARD_TYPE_SENIOR_RTC``).
        crossing_width_ft: Physical crossing width in feet.
        base_walk_time_sec: Default walk phase duration in seconds.
        config: Timing config with keys ``senior_walk_speed_ft_per_sec``,
            ``disabled_walk_speed_ft_per_sec``, ``min_extension_sec``,
            ``max_extension_sec``.

    Returns:
        Extension in seconds (0 if card type is not eligible or base time
        is already sufficient).
    """
    if card_type == CARD_TYPE_SENIOR_RTC:
        walk_speed: float = config["senior_walk_speed_ft_per_sec"]
    elif card_type == CARD_TYPE_DISABLED_RTC:
        walk_speed = config["disabled_walk_speed_ft_per_sec"]
    else:
        return 0

    required_time = math.ceil(crossing_width_ft / walk_speed)
    extension = max(0, required_time - base_walk_time_sec)

    if extension == 0:
        return 0

    extension = max(extension, config["min_extension_sec"])
    extension = min(extension, config["max_extension_sec"])
    return extension
