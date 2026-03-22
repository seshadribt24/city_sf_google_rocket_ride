"""RS-485 serial connection manager.

Wraps pyserial to provide an async interface for reading/writing to the
NFC reader over RS-485.  Raw bytes are fed into ``protocol.parse_frame``
and complete messages are placed on an :class:`asyncio.Queue` for the
:class:`ReaderListener` to consume.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import serial  # pyserial

from src.reader_interface.protocol import parse_frame

logger = logging.getLogger(__name__)

# Reconnection back-off parameters
_RECONNECT_BASE_SEC: float = 5.0
_RECONNECT_CAP_SEC: float = 60.0

# How many bytes to request per serial read
_READ_CHUNK: int = 256


class RS485Connection:
    """Async RS-485 serial connection to the NFC reader.

    Reads raw bytes from the serial port in a background task, parses
    frames via :func:`protocol.parse_frame`, and enqueues complete
    ``(msg_type, payload_dict)`` tuples for downstream consumers.

    Attributes:
        port: Serial port device path (e.g. ``/dev/ttyS1``).
        baud_rate: Baud rate (default 115 200).
        queue: Asyncio queue of parsed ``(msg_type, payload_dict)`` tuples.
    """

    def __init__(self, port: str, baud_rate: int = 115200) -> None:
        self.port = port
        self.baud_rate = baud_rate
        self.queue: asyncio.Queue[tuple[int, dict[str, Any]]] = asyncio.Queue()

        self._serial: serial.Serial | None = None
        self._read_task: asyncio.Task[None] | None = None
        self._buffer: bytes = b""
        self._closing: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def open(self) -> None:
        """Open the serial port and start the background read loop.

        Configures 8N1 (8 data bits, no parity, 1 stop bit) and attempts
        to enable hardware RS-485 mode via ``ioctl(SER_RS485_ENABLED)``
        where supported.  Logs success or a warning on RS-485 ioctl
        failure (falls back to normal serial).
        """
        self._closing = False
        self._open_port()
        self._read_task = asyncio.get_running_loop().create_task(
            self._read_loop(), name="rs485-read-loop",
        )
        logger.info("RS-485 connection opened on %s @ %d baud", self.port, self.baud_rate)

    async def close(self) -> None:
        """Cancel the read loop and close the serial port."""
        self._closing = True
        if self._read_task is not None:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None
        self._close_port()
        logger.info("RS-485 connection closed on %s", self.port)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        """Return ``True`` if the serial port is currently open."""
        return self._serial is not None and self._serial.is_open

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    async def send(self, data: bytes) -> None:
        """Write *data* to the serial port.

        Used to send config messages to the NFC reader.  Handles RS-485
        direction control if the transceiver requires it (most USB-485
        adapters auto-switch; discrete transceivers may need RTS toggling
        which pyserial handles when ``rs485_mode`` is configured).

        Raises:
            serial.SerialException: If the port is closed or write fails.
        """
        if self._serial is None or not self._serial.is_open:
            raise serial.SerialException("Port not open")
        # Run blocking write in the default executor so we don't stall
        # the event loop.
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._serial.write, data)
        logger.debug("TX %d bytes on %s", len(data), self.port)

    # ------------------------------------------------------------------
    # Internal — port helpers
    # ------------------------------------------------------------------

    def _open_port(self) -> None:
        """Open and configure the pyserial port (blocking)."""
        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baud_rate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,  # short timeout so reads are non-blocking-ish
        )
        self._try_enable_rs485()

    def _close_port(self) -> None:
        """Close the pyserial port if open."""
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None

    def _try_enable_rs485(self) -> None:
        """Attempt to enable kernel RS-485 mode via ioctl.

        This is Linux-specific (``SER_RS485_ENABLED`` flag via
        ``TIOCSRS485``).  If the platform or driver doesn't support it
        we log a warning and fall back to normal serial — most
        USB-to-485 adapters handle direction switching in hardware.
        """
        try:
            import fcntl
            import struct as _struct

            SER_RS485_ENABLED = 1
            TIOCSRS485 = 0x542F
            # struct serial_rs485 — first u32 is flags
            flags = _struct.pack("IIIIIIII", SER_RS485_ENABLED, 0, 0, 0, 0, 0, 0, 0)
            fcntl.ioctl(self._serial.fileno(), TIOCSRS485, flags)  # type: ignore[union-attr,attr-defined]
            logger.info("RS-485 mode enabled via ioctl on %s", self.port)
        except (ImportError, OSError) as exc:
            logger.warning(
                "Could not enable RS-485 ioctl on %s (%s) — using normal serial",
                self.port, exc,
            )

    # ------------------------------------------------------------------
    # Internal — read loop with reconnection
    # ------------------------------------------------------------------

    async def _read_loop(self) -> None:
        """Continuously read from serial, parse frames, enqueue results.

        On serial errors the loop waits with exponential back-off
        (5 s → 10 s → 20 s … capped at 60 s) and retries indefinitely
        until the port reopens or :meth:`close` is called.
        """
        backoff = _RECONNECT_BASE_SEC
        loop = asyncio.get_running_loop()

        while not self._closing:
            try:
                if not self.is_connected:
                    self._open_port()
                    self._buffer = b""
                    backoff = _RECONNECT_BASE_SEC
                    logger.info("Reconnected to %s", self.port)

                # Blocking read in executor — returns b"" on timeout
                raw = await loop.run_in_executor(
                    None, self._serial.read, _READ_CHUNK,  # type: ignore[union-attr]
                )
                if raw:
                    self._buffer += raw
                    self._drain_frames()

            except serial.SerialException as exc:
                if self._closing:
                    break
                logger.warning("Serial error on %s: %s — reconnecting in %.0fs", self.port, exc, backoff)
                self._close_port()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _RECONNECT_CAP_SEC)

            except asyncio.CancelledError:
                raise

            except Exception as exc:
                if self._closing:
                    break
                logger.error("Unexpected error in read loop: %s", exc, exc_info=True)
                self._close_port()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _RECONNECT_CAP_SEC)

    def _drain_frames(self) -> None:
        """Parse as many complete frames as possible from ``_buffer``."""
        while self._buffer:
            result = parse_frame(self._buffer)
            if result is None:
                break
            msg_type, payload_dict, consumed = result
            self._buffer = self._buffer[consumed:]
            self.queue.put_nowait((msg_type, payload_dict))
            logger.debug("Parsed msg_type=0x%02X, %d bytes consumed", msg_type, consumed)
