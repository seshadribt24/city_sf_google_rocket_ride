"""Background task that forwards local events to the SafeCross cloud API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from src.logging_events.event_store import EventStore
from src.logging_events.models import TapEvent

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Raised when the cloud API rejects our credentials."""


class NetworkError(Exception):
    """Raised on transient network failures."""


class CloudForwarder:
    """Periodically posts unforwarded events to the cloud API.

    Args:
        event_store: The local ``EventStore`` to drain.
        config: Cloud config dict with keys ``api_url`` and ``api_key``.
        interval_sec: Seconds between forwarding attempts (default 30).
    """

    def __init__(
        self,
        event_store: EventStore,
        config: dict[str, Any],
        interval_sec: float = 30.0,
    ) -> None:
        self._event_store = event_store
        self._api_url: str = config["api_url"].rstrip("/")
        self._api_key: str = config.get("api_key", "")
        self._interval = interval_sec
        self._running = True

    async def run(self) -> None:
        """Main loop — runs until ``stop()`` is called."""
        while self._running:
            await asyncio.sleep(self._interval)
            events = await self._event_store.get_unforwarded(limit=100)
            if not events:
                continue
            try:
                accepted_ids = await self._post_events(events)
                if accepted_ids:
                    await self._event_store.mark_forwarded(accepted_ids)
                    logger.info("Forwarded %d events to cloud", len(accepted_ids))
            except AuthError:
                logger.critical(
                    "Cloud API authentication failed — stopping forwarder",
                )
                self._running = False
            except NetworkError as exc:
                logger.warning("Cloud API network error: %s — will retry", exc)

    def stop(self) -> None:
        """Signal the run loop to exit."""
        self._running = False

    async def _post_events(self, events: list[TapEvent]) -> list[str]:
        """POST events to the cloud API and return accepted event IDs."""
        url = f"{self._api_url}/v1/events"
        payload = [e.to_dict() for e in events]
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status == 401 or resp.status == 403:
                        raise AuthError(f"HTTP {resp.status}")
                    if resp.status >= 500:
                        raise NetworkError(f"HTTP {resp.status}")
                    resp.raise_for_status()
                    body = await resp.json()
                    return body.get("accepted_ids", [e.event_id for e in events])
        except aiohttp.ClientError as exc:
            raise NetworkError(str(exc)) from exc
