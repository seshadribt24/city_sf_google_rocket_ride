"""Tests for walk-time extension calculation."""

from __future__ import annotations

import pytest

from src.decision.timing import calculate_extension
from src.reader_interface.protocol import (
    CARD_TYPE_DISABLED_RTC,
    CARD_TYPE_SENIOR_RTC,
    CARD_TYPE_STANDARD,
)


def _cfg(**overrides) -> dict:
    defaults = {
        "senior_walk_speed_ft_per_sec": 3.0,
        "disabled_walk_speed_ft_per_sec": 2.5,
        "min_extension_sec": 3,
        "max_extension_sec": 13,
    }
    defaults.update(overrides)
    return defaults


def test_senior_60ft_crossing():
    # ceil(60 / 3.0) = 20, extension = 20 - 12 = 8
    ext = calculate_extension(CARD_TYPE_SENIOR_RTC, 60, 12, _cfg())
    assert ext == 8


def test_disabled_60ft_crossing():
    # ceil(60 / 2.5) = 24, extension = 24 - 12 = 12
    ext = calculate_extension(CARD_TYPE_DISABLED_RTC, 60, 12, _cfg())
    assert ext == 12


def test_narrow_crossing_no_extension():
    # ceil(30 / 3.0) = 10, extension = 10 - 12 = -2 → 0
    # extension == 0, so return 0 (min_extension only applies if extension > 0)
    ext = calculate_extension(CARD_TYPE_SENIOR_RTC, 30, 12, _cfg())
    assert ext == 0


def test_wide_crossing_clamped():
    # ceil(120 / 3.0) = 40, extension = 40 - 12 = 28, clamped to max=13
    ext = calculate_extension(CARD_TYPE_SENIOR_RTC, 120, 12, _cfg())
    assert ext == 13


def test_standard_card_no_extension():
    ext = calculate_extension(CARD_TYPE_STANDARD, 60, 12, _cfg())
    assert ext == 0


def test_extension_rounds_up():
    # ceil(50 / 3.0) = ceil(16.667) = 17, extension = 17 - 12 = 5
    ext = calculate_extension(CARD_TYPE_SENIOR_RTC, 50, 12, _cfg())
    assert ext == 5
