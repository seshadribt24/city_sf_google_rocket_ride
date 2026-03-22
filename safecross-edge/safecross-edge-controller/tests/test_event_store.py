"""Tests for the SQLite-backed EventStore."""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta

import pytest

from src.logging_events.event_store import EventStore
from src.logging_events.models import EventType, TapEvent


@pytest.fixture
async def store(tmp_path):
    """Yield an initialised EventStore backed by a temp file."""
    db_path = str(tmp_path / "test_events.db")
    es = EventStore(db_path)
    await es.init_db()
    yield es
    await es.close()


def _make_event(
    *,
    intersection_id: str = "INT-001",
    event_type: EventType = EventType.CARD_TAP,
    ts_offset_sec: int = 0,
    forwarded: bool = False,
    **kwargs,
) -> TapEvent:
    return TapEvent(
        intersection_id=intersection_id,
        event_type=event_type,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=ts_offset_sec),
        forwarded_to_cloud=forwarded,
        **kwargs,
    )


async def test_store_and_retrieve(store: EventStore):
    e1 = _make_event(ts_offset_sec=0)
    e2 = _make_event(ts_offset_sec=1)
    e3 = _make_event(ts_offset_sec=2)
    for e in (e1, e2, e3):
        await store.store(e)

    events = await store.get_unforwarded()
    assert len(events) == 3


async def test_unforwarded_returns_oldest_first(store: EventStore):
    e_late = _make_event(ts_offset_sec=100)
    e_early = _make_event(ts_offset_sec=10)
    e_mid = _make_event(ts_offset_sec=50)
    # Insert out of order
    await store.store(e_late)
    await store.store(e_early)
    await store.store(e_mid)

    events = await store.get_unforwarded()
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps)


async def test_mark_forwarded(store: EventStore):
    e1 = _make_event(ts_offset_sec=0)
    e2 = _make_event(ts_offset_sec=1)
    e3 = _make_event(ts_offset_sec=2)
    for e in (e1, e2, e3):
        await store.store(e)

    await store.mark_forwarded([e1.event_id, e2.event_id])
    remaining = await store.get_unforwarded()
    assert len(remaining) == 1
    assert remaining[0].event_id == e3.event_id


async def test_prune_removes_old_forwarded(store: EventStore):
    old = _make_event(ts_offset_sec=-86400 * 60, forwarded=True)  # ~60 days ago
    await store.store(old)
    await store.mark_forwarded([old.event_id])

    deleted = await store.prune(days=0)
    assert deleted == 1
    stats = await store.get_stats()
    assert stats["total"] == 0


async def test_prune_keeps_recent_forwarded(store: EventStore):
    recent = TapEvent(
        intersection_id="INT-001",
        event_type=EventType.CARD_TAP,
        timestamp=datetime.now(timezone.utc),
        forwarded_to_cloud=True,
    )
    await store.store(recent)
    await store.mark_forwarded([recent.event_id])

    await store.prune(days=30)
    stats = await store.get_stats()
    assert stats["total"] == 1


async def test_prune_keeps_unforwarded(store: EventStore):
    old_unforwarded = _make_event(ts_offset_sec=-86400 * 60)
    await store.store(old_unforwarded)

    await store.prune(days=0)
    stats = await store.get_stats()
    assert stats["total"] == 1
    assert stats["pending"] == 1


async def test_get_stats(store: EventStore):
    e1 = _make_event(ts_offset_sec=0)
    e2 = _make_event(ts_offset_sec=1)
    e3 = _make_event(ts_offset_sec=2)
    for e in (e1, e2, e3):
        await store.store(e)
    await store.mark_forwarded([e1.event_id])

    stats = await store.get_stats()
    assert stats == {"total": 3, "forwarded": 1, "pending": 2}


async def test_capacity(store: EventStore):
    events = [_make_event(ts_offset_sec=i) for i in range(1000)]
    for e in events:
        await store.store(e)

    stats = await store.get_stats()
    assert stats["total"] == 1000

    batch = await store.get_unforwarded(limit=100)
    assert len(batch) == 100

    pending = await store.count_pending()
    assert pending == 1000
