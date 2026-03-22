"""Event data models for SafeCross logging and cloud reporting."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventType(Enum):
    """All event types emitted by the edge controller."""

    CARD_TAP = "card_tap"
    EXTENSION_GRANTED = "extension_granted"
    EXTENSION_DENIED = "extension_denied"
    EXTENSION_COMPLETED = "extension_completed"
    BASELINE_RESTORED = "baseline_restored"
    BASELINE_RESTORE_FAILED = "baseline_restore_failed"
    PREEMPTION_DETECTED = "preemption_detected"
    SNMP_ERROR = "snmp_error"
    READER_OFFLINE = "reader_offline"
    READER_ONLINE = "reader_online"
    SYSTEM_STARTUP = "system_startup"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


@dataclass
class TapEvent:
    """A single logged event with all context needed for cloud reporting.

    Attributes:
        event_id: Unique UUID for this event.
        intersection_id: Intersection where the event occurred.
        timestamp: UTC time of the event.
        event_type: Category of the event.
        card_type: NFC card type constant (nullable for non-tap events).
        card_uid_hash: SHA-256 hex digest of the raw card UID.
        extension_seconds: Walk-time extension granted (0 if denied).
        denial_reason: Reason string if the extension was denied.
        phase_number: Signal phase associated with the event.
        signal_state_at_tap: Human-readable signal state at tap time.
        read_method: NFC read method constant.
        reader_uptime_sec: Reader uptime in seconds at event time.
        forwarded_to_cloud: Whether this event has been sent to the API.
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    intersection_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: EventType = EventType.CARD_TAP
    card_type: int | None = None
    card_uid_hash: str = ""
    extension_seconds: int = 0
    denial_reason: str | None = None
    phase_number: int | None = None
    signal_state_at_tap: str | None = None
    read_method: int | None = None
    reader_uptime_sec: int | None = None
    forwarded_to_cloud: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict for the cloud API."""
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        d["event_type"] = self.event_type.value
        d["forwarded_to_cloud"] = int(self.forwarded_to_cloud)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TapEvent:
        """Reconstruct from a dict (e.g. a SQLite row mapping)."""
        d = dict(d)  # don't mutate the original
        if isinstance(d.get("timestamp"), str):
            d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        if isinstance(d.get("event_type"), str):
            d["event_type"] = EventType(d["event_type"])
        if "forwarded_to_cloud" in d:
            d["forwarded_to_cloud"] = bool(d["forwarded_to_cloud"])
        return cls(**d)
