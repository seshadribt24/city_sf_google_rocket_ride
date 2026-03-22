"""SQLite-backed event store for durable, local-first logging."""

from __future__ import annotations

import aiosqlite
import logging
from typing import Any

from src.logging_events.models import TapEvent, EventType

logger = logging.getLogger(__name__)

_CREATE_TABLE = """\
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    intersection_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    card_type INTEGER,
    card_uid_hash TEXT,
    extension_seconds INTEGER DEFAULT 0,
    denial_reason TEXT,
    phase_number INTEGER,
    signal_state_at_tap TEXT,
    read_method INTEGER,
    reader_uptime_sec INTEGER,
    forwarded_to_cloud INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

_CREATE_IDX_FORWARD = (
    "CREATE INDEX IF NOT EXISTS idx_events_forward "
    "ON events(forwarded_to_cloud, timestamp);"
)
_CREATE_IDX_INTERSECTION = (
    "CREATE INDEX IF NOT EXISTS idx_events_intersection "
    "ON events(intersection_id, timestamp);"
)


class EventStore:
    """Async SQLite event store.

    Args:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: str = "/var/lib/safecross/events.db") -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def init_db(self) -> None:
        """Open the database and create the schema if needed."""
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute(_CREATE_TABLE)
        await self._db.execute(_CREATE_IDX_FORWARD)
        await self._db.execute(_CREATE_IDX_INTERSECTION)
        await self._db.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def store(self, event: TapEvent) -> str:
        """Insert an event and return its ``event_id``."""
        assert self._db is not None
        await self._db.execute(
            "INSERT INTO events "
            "(event_id, intersection_id, timestamp, event_type, card_type, "
            "card_uid_hash, extension_seconds, denial_reason, phase_number, "
            "signal_state_at_tap, read_method, reader_uptime_sec, forwarded_to_cloud) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.event_id,
                event.intersection_id,
                event.timestamp.isoformat(),
                event.event_type.value,
                event.card_type,
                event.card_uid_hash,
                event.extension_seconds,
                event.denial_reason,
                event.phase_number,
                event.signal_state_at_tap,
                event.read_method,
                event.reader_uptime_sec,
                int(event.forwarded_to_cloud),
            ),
        )
        await self._db.commit()
        return event.event_id

    async def get_unforwarded(self, limit: int = 100) -> list[TapEvent]:
        """Return the oldest unforwarded events."""
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT event_id, intersection_id, timestamp, event_type, "
            "card_type, card_uid_hash, extension_seconds, denial_reason, "
            "phase_number, signal_state_at_tap, read_method, reader_uptime_sec, "
            "forwarded_to_cloud "
            "FROM events WHERE forwarded_to_cloud = 0 "
            "ORDER BY timestamp ASC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [TapEvent.from_dict(dict(row)) for row in rows]

    async def mark_forwarded(self, event_ids: list[str]) -> None:
        """Mark events as successfully forwarded to cloud."""
        if not event_ids:
            return
        assert self._db is not None
        placeholders = ",".join("?" for _ in event_ids)
        await self._db.execute(
            f"UPDATE events SET forwarded_to_cloud = 1 "
            f"WHERE event_id IN ({placeholders})",
            event_ids,
        )
        await self._db.commit()

    async def get_stats(self) -> dict[str, int]:
        """Return event count statistics."""
        assert self._db is not None
        cursor = await self._db.execute("SELECT COUNT(*) FROM events")
        row = await cursor.fetchone()
        total: int = row[0] if row else 0
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM events WHERE forwarded_to_cloud = 1",
        )
        row = await cursor.fetchone()
        forwarded: int = row[0] if row else 0
        return {"total": total, "forwarded": forwarded, "pending": total - forwarded}

    async def prune(self, days: int = 30) -> int:
        """Delete forwarded events older than *days*. Returns rows deleted."""
        assert self._db is not None
        cursor = await self._db.execute(
            "DELETE FROM events WHERE forwarded_to_cloud = 1 "
            "AND timestamp < datetime('now', ?)",
            (f"-{days} days",),
        )
        await self._db.commit()
        return cursor.rowcount

    async def count_pending(self) -> int:
        """Quick count of unforwarded events."""
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM events WHERE forwarded_to_cloud = 0",
        )
        row = await cursor.fetchone()
        return row[0] if row else 0
