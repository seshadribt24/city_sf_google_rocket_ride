"""RS-485 serial listener for NFC reader messages.

Runs a dedicated thread that reads raw bytes from the RS-485 serial port,
assembles frames using the FrameParser state machine, and posts parsed
messages to an asyncio.Queue for the main event loop.

pyserial is blocking, so this MUST run in a thread — not in the async loop.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Optional

from .config_manager import NFCReaderConfig
from .message_protocol import (
    CardTapEvent,
    FrameParser,
    MessageType,
    ParsedFrame,
    ReaderHeartbeat,
    parse_card_tap,
    parse_reader_heartbeat,
)

logger = logging.getLogger(__name__)


class RS485Listener(threading.Thread):
    """Thread-based RS-485 serial listener for NFC reader communication.

    Reads raw bytes from the serial port, parses frames, and posts
    validated messages to an asyncio.Queue.

    Attributes:
        config: NFC reader serial configuration.
        queue: Asyncio queue for passing parsed messages to the main loop.
        running: Flag to signal the thread to stop.
    """

    def __init__(
        self,
        config: NFCReaderConfig,
        queue: asyncio.Queue,
    ) -> None:
        """Initialize the RS-485 listener thread.

        Args:
            config: NFC reader serial port configuration.
            queue: Asyncio queue to post parsed messages into.
        """
        super().__init__(daemon=True, name="rs485-listener")
        self.config = config
        self.queue = queue
        self.running = threading.Event()
        self._parser = FrameParser()
        self._serial = None  # type: ignore[assignment]

    def run(self) -> None:
        """Main thread loop: read serial bytes, parse frames, post to queue.

        Opens the serial port, reads continuously, feeds bytes to the
        FrameParser, and posts complete messages to the asyncio queue.
        Handles serial errors gracefully with reconnection logic.
        """
        # TODO: Open serial port with pyserial using self.config
        # TODO: Read bytes in a loop while self.running is set
        # TODO: Feed bytes to self._parser
        # TODO: For each complete frame, parse payload and put on self.queue
        # TODO: Handle serial.SerialException with reconnection backoff
        raise NotImplementedError

    def stop(self) -> None:
        """Signal the listener thread to stop and close the serial port."""
        # TODO: Clear self.running event
        # TODO: Close serial port if open
        raise NotImplementedError

    @property
    def is_connected(self) -> bool:
        """Return True if the serial port is currently open and readable."""
        # TODO: Check serial port status
        raise NotImplementedError

    @property
    def last_heartbeat_time(self) -> Optional[float]:
        """Return the timestamp of the last reader heartbeat, or None."""
        # TODO: Track and return last heartbeat time
        raise NotImplementedError
