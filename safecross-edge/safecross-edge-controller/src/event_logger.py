"""Event logger — local SQLite event store.

Persists every event to a local SQLite database before any cloud
reporting. Ensures no data is lost during network outages. Uses
aiosqlite for async database operations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQL schema
# ---------------------------------------------------------------------------

CREATE_TAP_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS tap_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time TEXT NOT NULL,
    intersection_id TEXT NOT NULL,
    crossing_id TEXT NOT NULL,
    card_type INTEGER NOT NULL,
    card_uid TEXT NOT NULL,
    read_method INTEGER NOT NULL,
    filter_result TEXT NOT NULL,
    extension_sec INTEGER,
    phase_state_at_tap TEXT,
    snmp_result TEXT,
    reported_to_cloud INTEGER DEFAULT 0
);
"""

CREATE_READER_HEARTBEATS_TABLE = """
CREATE TABLE IF NOT EXISTS reader_heartbeats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time TEXT NOT NULL,
    reader_id TEXT NOT NULL,
    status INTEGER NOT NULL,
    uptime_sec INTEGER NOT NULL,
    tap_count INTEGER NOT NULL,
    temperature_c REAL NOT NULL
);
"""

CREATE_STATE_TRANSITIONS_TABLE = """
CREATE TABLE IF NOT EXISTS state_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time TEXT NOT NULL,
    crossing_id TEXT NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    trigger TEXT NOT NULL
);
"""

CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_tap_events_reported ON tap_events(reported_to_cloud);
CREATE INDEX IF NOT EXISTS idx_tap_events_time ON tap_events(event_time);
"""

# Retention cleanup queries
CLEANUP_TAP_EVENTS = "DELETE FROM tap_events WHERE event_time < datetime('now', '-30 days');"
CLEANUP_HEARTBEATS = "DELETE FROM reader_heartbeats WHERE event_time < datetime('now', '-7 days');"
CLEANUP_TRANSITIONS = "DELETE FROM state_transitions WHERE event_time < datetime('now', '-7 days');"


# ---------------------------------------------------------------------------
# Data classes for event records
# ---------------------------------------------------------------------------


@dataclass
class TapEventRecord:
    """A tap event record for storage in the local database.

    Attributes:
        event_time: UTC timestamp of the event.
        intersection_id: Intersection identifier.
        crossing_id: Crossing identifier.
        card_type: NFC card type code.
        card_uid: Raw card UID (hex string, stored locally only).
        read_method: NFC read method code.
        filter_result: Result of the classifier filter.
        extension_sec: Extension granted in seconds, or None if rejected.
        phase_state_at_tap: Signal phase state at time of tap.
        snmp_result: Result of SNMP operation, or None.
    """

    event_time: datetime
    intersection_id: str
    crossing_id: str
    card_type: int
    card_uid: str
    read_method: int
    filter_result: str
    extension_sec: Optional[int] = None
    phase_state_at_tap: Optional[str] = None
    snmp_result: Optional[str] = None


# ---------------------------------------------------------------------------
# EventLogger class
# ---------------------------------------------------------------------------


class EventLogger:
    """Async SQLite event store for local persistence.

    All events are persisted locally before cloud reporting to ensure
    no data loss during network outages.

    Attributes:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db: object) -> None:
        """Initialize the event logger with an open database connection.

        Args:
            db: An aiosqlite connection object.
        """
        self._db = db

    @classmethod
    async def create(cls, db_path: str) -> EventLogger:
        """Create and initialize the event logger with database schema.

        Opens the SQLite database, creates tables if they don't exist,
        and returns an initialized EventLogger.

        Args:
            db_path: Filesystem path for the SQLite database.

        Returns:
            Initialized EventLogger instance.
        """
        # TODO: Open aiosqlite connection
        # TODO: Execute CREATE TABLE statements
        # TODO: Execute CREATE INDEX statements
        # TODO: Return EventLogger instance
        raise NotImplementedError

    async def log_tap_event(self, record: TapEventRecord) -> int:
        """Insert a tap event into the database.

        Args:
            record: The tap event record to store.

        Returns:
            The row ID of the inserted record.
        """
        # TODO: INSERT INTO tap_events
        raise NotImplementedError

    async def log_reader_heartbeat(self, heartbeat: object) -> int:
        """Insert a reader heartbeat into the database.

        Args:
            heartbeat: Parsed ReaderHeartbeat message.

        Returns:
            The row ID of the inserted record.
        """
        # TODO: INSERT INTO reader_heartbeats
        raise NotImplementedError

    async def log_state_transition(
        self,
        crossing_id: str,
        from_state: str,
        to_state: str,
        trigger: str,
    ) -> int:
        """Insert a state transition record.

        Args:
            crossing_id: The crossing identifier.
            from_state: State transitioned from.
            to_state: State transitioned to.
            trigger: Description of transition cause.

        Returns:
            The row ID of the inserted record.
        """
        # TODO: INSERT INTO state_transitions
        raise NotImplementedError

    async def get_unreported_events(self, limit: int = 10) -> list[TapEventRecord]:
        """Retrieve tap events not yet reported to the cloud.

        Args:
            limit: Maximum number of events to return (batch size).

        Returns:
            List of unreported TapEventRecord instances.
        """
        # TODO: SELECT from tap_events WHERE reported_to_cloud = 0
        raise NotImplementedError

    async def mark_reported(self, event_ids: list[int]) -> None:
        """Mark events as successfully reported to the cloud.

        Args:
            event_ids: List of tap_events row IDs to mark.
        """
        # TODO: UPDATE tap_events SET reported_to_cloud = 1
        raise NotImplementedError

    async def get_unreported_count(self) -> int:
        """Return the count of unreported events in the backlog.

        Returns:
            Number of events with reported_to_cloud = 0.
        """
        # TODO: SELECT COUNT(*) from tap_events WHERE reported_to_cloud = 0
        raise NotImplementedError

    async def cleanup_old(self) -> None:
        """Delete records older than the retention policy.

        Tap events: 30 days. Heartbeats and transitions: 7 days.
        """
        # TODO: Execute retention DELETE queries
        raise NotImplementedError

    async def close(self) -> None:
        """Close the database connection."""
        # TODO: Close aiosqlite connection
        raise NotImplementedError
