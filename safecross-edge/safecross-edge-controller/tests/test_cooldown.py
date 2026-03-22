"""Tests for CooldownManager dedup / cooldown / rate limiting."""

from __future__ import annotations

import pytest

from src.decision.cooldown import CooldownManager


def _cfg(**overrides) -> dict:
    defaults = {
        "cooldown_sec": 120,
        "dedup_window_sec": 10,
        "max_extensions_per_hour": 20,
    }
    defaults.update(overrides)
    return defaults


INT_ID = "INT-001"
UID_A = "aabbccdd"
UID_B = "11223344"


def test_first_tap_allowed():
    cm = CooldownManager(_cfg())
    ok, reason = cm.can_extend(INT_ID, UID_A, now=1000.0)
    assert ok is True
    assert reason is None


def test_duplicate_uid_blocked():
    cm = CooldownManager(_cfg())
    cm.record_extension(INT_ID, UID_A, now=1000.0)
    ok, reason = cm.can_extend(INT_ID, UID_A, now=1005.0)
    assert ok is False
    assert reason == "duplicate_card"


def test_different_uid_during_cooldown():
    cm = CooldownManager(_cfg())
    cm.record_extension(INT_ID, UID_A, now=1000.0)
    ok, reason = cm.can_extend(INT_ID, UID_B, now=1050.0)
    assert ok is False
    assert reason == "cooldown_active"


def test_after_cooldown_allowed():
    cm = CooldownManager(_cfg())
    cm.record_extension(INT_ID, UID_A, now=1000.0)
    ok, reason = cm.can_extend(INT_ID, UID_B, now=1121.0)
    assert ok is True
    assert reason is None


def test_hourly_rate_limit():
    cm = CooldownManager(_cfg(cooldown_sec=0, dedup_window_sec=0))
    base = 1000.0
    for i in range(20):
        cm.record_extension(INT_ID, f"uid-{i}", now=base + i)
    ok, reason = cm.can_extend(INT_ID, "uid-new", now=base + 21)
    assert ok is False
    assert reason == "hourly_rate_limit"


def test_rate_limit_resets_after_hour():
    cm = CooldownManager(_cfg(cooldown_sec=0, dedup_window_sec=0))
    base = 1000.0
    for i in range(20):
        cm.record_extension(INT_ID, f"uid-{i}", now=base + i)
    # Oldest entry at base=1000 ages out after 3600s
    ok, reason = cm.can_extend(INT_ID, "uid-new", now=base + 3601)
    assert ok is True
    assert reason is None


def test_reset_clears_state():
    cm = CooldownManager(_cfg())
    cm.record_extension(INT_ID, UID_A, now=1000.0)
    cm.reset(INT_ID)
    ok, reason = cm.can_extend(INT_ID, UID_A, now=1001.0)
    assert ok is True
    assert reason is None
