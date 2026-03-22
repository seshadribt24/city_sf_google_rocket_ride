"""Tests for the timing engine — extension duration calculation.

Covers:
- 72-foot crossing -> correct extension seconds
- 48-foot crossing -> correct extension seconds
- Extension respects max_extension_sec cap
- Extension respects min_extension_sec floor
- Extension never exceeds 45-second hard ceiling
- Negative raw_extension -> min_extension_sec floor applies
"""

from __future__ import annotations

import pytest

from src.config_manager import CrossingConfig
from src.timing_engine import MAX_TOTAL_WALK_SEC, TimingEngine


class TestLinearByWidthFormula:
    """Tests for the linear_by_width extension formula."""

    def test_72ft_crossing_extension(self, sample_crossing_ns: CrossingConfig) -> None:
        """72-ft crossing: needed=28.8, provided=25, raw=3.8 -> ceil=4 -> clamped to min=6."""
        # TODO: engine = TimingEngine([sample_crossing_ns])
        # TODO: assert engine.calculate_extension("NS") == 6
        pass

    def test_48ft_crossing_extension(self, sample_crossing_ew: CrossingConfig) -> None:
        """48-ft crossing: needed=19.2, provided=19, raw=0.2 -> ceil=1 -> clamped to min=4."""
        # TODO: engine = TimingEngine([sample_crossing_ew])
        # TODO: assert engine.calculate_extension("EW") == 4
        pass

    def test_max_extension_cap(self) -> None:
        """Extension must not exceed max_extension_sec from config."""
        # TODO: Create a very wide crossing where raw extension > max
        # TODO: assert result <= crossing.max_extension_sec
        pass

    def test_min_extension_floor(self) -> None:
        """Extension must not fall below min_extension_sec from config."""
        # TODO: Create a narrow crossing where raw extension < min
        # TODO: assert result >= crossing.min_extension_sec
        pass

    def test_hard_ceiling_45_seconds(self) -> None:
        """Total walk time (base + extension) must never exceed 45 seconds."""
        # TODO: Create config where base + max_extension > 45
        # TODO: Verify total walk time is capped at MAX_TOTAL_WALK_SEC
        pass

    def test_negative_raw_extension_floors_to_min(self) -> None:
        """When already_provided > needed_total, min_extension_sec applies."""
        # TODO: Create config where base + clearance > width/2.5
        # TODO: assert result == crossing.min_extension_sec
        pass


class TestGetBaseWalk:
    """Tests for base walk time lookup."""

    def test_returns_base_walk_sec(self, sample_crossing_ns: CrossingConfig) -> None:
        """get_base_walk returns the configured base_walk_sec."""
        # TODO: engine = TimingEngine([sample_crossing_ns])
        # TODO: assert engine.get_base_walk("NS") == 7
        pass

    def test_unknown_crossing_raises(self, sample_crossing_ns: CrossingConfig) -> None:
        """get_base_walk raises KeyError for unknown crossing_id."""
        # TODO: engine = TimingEngine([sample_crossing_ns])
        # TODO: with pytest.raises(KeyError): engine.get_base_walk("UNKNOWN")
        pass


class TestGetTotalWalkTime:
    """Tests for total walk time calculation with safety cap."""

    def test_total_within_ceiling(self, sample_crossing_ns: CrossingConfig) -> None:
        """Total walk time within ceiling is returned as-is."""
        # TODO: assert engine.get_total_walk_time("NS", 6) == 13
        pass

    def test_total_capped_at_ceiling(self, sample_crossing_ns: CrossingConfig) -> None:
        """Total exceeding ceiling is capped at MAX_TOTAL_WALK_SEC."""
        # TODO: assert engine.get_total_walk_time("NS", 50) == MAX_TOTAL_WALK_SEC
        pass
