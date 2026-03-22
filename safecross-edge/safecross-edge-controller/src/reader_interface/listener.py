"""Reader listener — dispatches parsed RS-485 messages to callbacks.

Consumes ``(msg_type, payload_dict)`` tuples from the
:class:`RS485Connection` queue, converts them to typed dataclasses,
and invokes registered callbacks.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from src.reader_interface.protocol import (
    MSG_CARD_TAP,
    MSG_CONFIG_ACK,
    MSG_HEARTBEAT,
    CardTapEvent,
    ReaderHeartbeat,
    build_config_message,
)
from src.reader_interface.rs485 import RS485Connection

logger = logging.getLogger(__name__)

# A heartbeat older than this many seconds means the reader is offline.
_HEARTBEAT_TIMEOUT_SEC: float = 30.0


class ReaderListener:
    """Dispatches parsed NFC-reader messages to application callbacks.

    Attributes:
        conn: The underlying RS-485 connection.
        on_card_tap: Async callback invoked for every card-tap event.
        on_reader_health_update: Optional sync callback for heartbeats.
    """

    def __init__(
        self,
        conn: RS485Connection,
        on_card_tap: Callable[[CardTapEvent], Awaitable[None]],
        on_reader_health_update: Callable[[ReaderHeartbeat], None] | None = None,
    ) -> None:
        self.conn = conn
        self.on_card_tap = on_card_tap
        self.on_reader_health_update = on_reader_health_update

        self._last_heartbeat: ReaderHeartbeat | None = None
        self._last_heartbeat_time: float | None = None

        # Pending config-update futures keyed by config_key
        self._pending_acks: dict[int, asyncio.Future[bool]] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def reader_online(self) -> bool:
        """``True`` if a heartbeat was received within the last 30 s."""
        if self._last_heartbeat_time is None:
            return False
        return (time.monotonic() - self._last_heartbeat_time) < _HEARTBEAT_TIMEOUT_SEC

    @property
    def reader_last_heartbeat(self) -> ReaderHeartbeat | None:
        """The most recent :class:`ReaderHeartbeat`, or ``None``."""
        return self._last_heartbeat

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Consume messages from the RS-485 queue and dispatch them.

        This coroutine runs until cancelled.  It should be launched as a
        background task alongside :meth:`RS485Connection.open`.

        - ``MSG_CARD_TAP``   → :pyattr:`on_card_tap`
        - ``MSG_HEARTBEAT``  → internal health state +
          :pyattr:`on_reader_health_update`
        - ``MSG_CONFIG_ACK`` → resolve pending :meth:`send_config` future
        """
        while True:
            msg_type, payload = await self.conn.queue.get()

            try:
                if msg_type == MSG_CARD_TAP:
                    await self._handle_card_tap(payload)
                elif msg_type == MSG_HEARTBEAT:
                    self._handle_heartbeat(payload)
                elif msg_type == MSG_CONFIG_ACK:
                    self._handle_config_ack(payload)
                else:
                    logger.debug("Ignoring unknown msg_type 0x%02X", msg_type)
            except Exception:
                logger.exception("Error handling msg_type 0x%02X", msg_type)

    # ------------------------------------------------------------------
    # Config sending with ACK
    # ------------------------------------------------------------------

    async def send_config(
        self,
        config_key: int,
        config_data: bytes,
        timeout: float = 5.0,
    ) -> bool:
        """Send a config-update frame and wait for ACK.

        Args:
            config_key: 1-byte config key identifier.
            config_data: Variable-length config payload.
            timeout: Seconds to wait for an ACK before giving up.

        Returns:
            ``True`` if an ACK was received within *timeout*, ``False``
            otherwise.
        """
        frame = build_config_message(config_key, config_data)

        loop = asyncio.get_running_loop()
        fut: asyncio.Future[bool] = loop.create_future()
        self._pending_acks[config_key] = fut

        try:
            await self.conn.send(frame)
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("Config ACK timeout for key 0x%02X", config_key)
            return False
        finally:
            self._pending_acks.pop(config_key, None)

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    async def _handle_card_tap(self, payload: dict[str, Any]) -> None:
        event = CardTapEvent(
            card_type=payload["card_type"],
            uid=payload["uid"],
            timestamp_ms=payload["timestamp_ms"],
            read_method=payload["read_method"],
        )
        logger.info(
            "Card tap: type=0x%02X uid=%s ts=%d method=%d",
            event.card_type,
            event.uid.hex(),
            event.timestamp_ms,
            event.read_method,
        )
        await self.on_card_tap(event)

    def _handle_heartbeat(self, payload: dict[str, Any]) -> None:
        hb = ReaderHeartbeat(
            status=payload["status"],
            uptime_sec=payload["uptime_sec"],
            tap_count=payload["tap_count"],
            temperature_c=payload["temperature_c"],
        )
        self._last_heartbeat = hb
        self._last_heartbeat_time = time.monotonic()
        logger.debug(
            "Reader heartbeat: status=%d uptime=%ds taps=%d temp=%.1f°C",
            hb.status, hb.uptime_sec, hb.tap_count, hb.temperature_c,
        )
        if self.on_reader_health_update is not None:
            self.on_reader_health_update(hb)

    def _handle_config_ack(self, payload: dict[str, Any]) -> None:
        raw: bytes = payload.get("raw", b"")
        if not raw:
            logger.warning("Config ACK with empty payload")
            return
        acked_key = raw[0]
        fut = self._pending_acks.get(acked_key)
        if fut is not None and not fut.done():
            fut.set_result(True)
            logger.info("Config ACK received for key 0x%02X", acked_key)
        else:
            logger.debug("Unexpected config ACK for key 0x%02X (no pending future)", acked_key)
