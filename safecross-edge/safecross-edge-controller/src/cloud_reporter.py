"""Cloud reporter — forwards events to the backend API.

Batches unsent events from the local SQLite store and forwards them
to the cloud backend over HTTPS with mTLS authentication.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .config_manager import CloudConfig
    from .event_logger import EventLogger, TapEventRecord

logger = logging.getLogger(__name__)

# HTTP request timeout (seconds)
REQUEST_TIMEOUT_SEC = 10

# Retry backoff intervals (seconds)
RETRY_BACKOFF = [1, 4, 16]

# Software version reported in heartbeats
SOFTWARE_VERSION = "1.0.0"


class CloudReporter:
    """Batches and forwards events to the SafeCross cloud API.

    Events are batched up to event_batch_size or flushed every
    event_flush_interval_sec, whichever comes first. Uses mTLS
    with per-device certificates for authentication.

    If the cloud API is unreachable, events remain in the local
    SQLite buffer and are replayed on reconnection.

    Attributes:
        config: Cloud API connection configuration.
        db: Event logger for reading unreported events.
    """

    def __init__(self, config: CloudConfig, db: EventLogger) -> None:
        """Initialize the cloud reporter.

        Args:
            config: Cloud API connection configuration.
            db: Event logger for reading/marking reported events.
        """
        self.config = config
        self.db = db
        self._last_flush_time: float = time.monotonic()
        self._session = None  # aiohttp.ClientSession, created lazily

    async def maybe_flush(self) -> None:
        """Flush events to the cloud if batch size or time threshold reached.

        Called by the main loop on every iteration. Checks if enough
        events have accumulated or enough time has passed to trigger
        a flush.
        """
        # TODO: Check batch size and flush interval
        # TODO: Call _send_events if threshold met
        raise NotImplementedError

    async def _send_events(self, events: list[TapEventRecord]) -> bool:
        """Send a batch of events to POST /api/v1/events.

        Hashes card UIDs before sending (privacy measure). Retries
        with exponential backoff on failure.

        Args:
            events: List of tap event records to send.

        Returns:
            True if all events were sent and acknowledged.
        """
        # TODO: Build JSON payload with card_uid_hash (truncated SHA-256)
        # TODO: POST to {api_url}/api/v1/events with mTLS
        # TODO: Retry with exponential backoff on failure
        # TODO: Mark events as reported on success
        raise NotImplementedError

    async def send_heartbeat(
        self,
        device_id: str,
        intersection_id: str,
        edge_status: str,
        reader_status: str,
        signal_controller_status: str,
        uptime_sec: int,
        last_extension_time: Optional[str],
    ) -> bool:
        """Send a heartbeat to POST /api/v1/heartbeat.

        Args:
            device_id: Edge controller device identifier.
            intersection_id: Intersection identifier.
            edge_status: Overall edge controller status.
            reader_status: NFC reader status.
            signal_controller_status: Signal controller communication status.
            uptime_sec: Seconds since edge controller boot.
            last_extension_time: ISO timestamp of last extension, or None.

        Returns:
            True if heartbeat was acknowledged.
        """
        # TODO: Build heartbeat JSON payload
        # TODO: POST to {api_url}/api/v1/heartbeat with mTLS
        raise NotImplementedError

    async def _get_session(self) -> object:
        """Get or create the aiohttp ClientSession with mTLS.

        Returns:
            aiohttp.ClientSession configured with device certificates.
        """
        # TODO: Create SSL context with device cert and key
        # TODO: Create aiohttp.ClientSession with SSL context
        raise NotImplementedError

    async def close(self) -> None:
        """Close the HTTP session."""
        # TODO: Close aiohttp session if open
        raise NotImplementedError

    @staticmethod
    def _hash_uid(raw_uid: str) -> str:
        """Hash a card UID for privacy-safe cloud reporting.

        Returns the first 8 hex characters of the SHA-256 hash.
        The raw UID is never transmitted to the cloud.

        Args:
            raw_uid: Raw card UID hex string.

        Returns:
            Truncated SHA-256 hash (8 hex chars).
        """
        # TODO: SHA-256 hash, truncate to first 8 hex chars
        raise NotImplementedError
