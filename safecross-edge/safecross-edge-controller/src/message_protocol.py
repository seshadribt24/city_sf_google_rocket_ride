"""RS-485 message protocol — frame parsing and construction.

Implements the Layer 1 binary frame format for communication between the
NFC reader and the edge controller over RS-485.

Frame format:
    | SYNC (2B) | LENGTH (1B) | MSG_TYPE (1B) | PAYLOAD (NB) | CRC16 (2B) |
    | 0xAA 0x55 | N + 2       | see below     | varies       | CRC-16/MODBUS |
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, IntEnum, auto
from typing import Optional

logger = logging.getLogger(__name__)

# Sync bytes
SYNC_BYTE_1 = 0xAA
SYNC_BYTE_2 = 0x55


class FrameState(Enum):
    """State machine states for incremental frame parsing."""

    WAITING_SYNC1 = auto()
    WAITING_SYNC2 = auto()
    WAITING_LENGTH = auto()
    READING_BODY = auto()
    WAITING_CRC = auto()


class MessageType(IntEnum):
    """RS-485 message type identifiers."""

    CARD_TAP = 0x01
    HEARTBEAT = 0x02
    CONFIG_UPDATE = 0x80


class CardType(IntEnum):
    """NFC card classification types."""

    SENIOR_RTC = 0x01
    DISABLED_RTC = 0x02
    STANDARD = 0x03
    YOUTH = 0x04
    DESFIRE_DETECTED = 0x05
    UNKNOWN = 0xFF


class ReadMethod(IntEnum):
    """NFC read method used to classify the card."""

    APPDIR = 1
    UID_PREFIX = 2
    ANY_DESFIRE = 3


@dataclass
class CardTapEvent:
    """Parsed card tap event from the NFC reader.

    Attributes:
        card_type: Classification of the NFC card.
        uid: Raw UID bytes of the card.
        timestamp_ms: Milliseconds since reader boot (little-endian uint32).
        read_method: Method used to classify the card.
    """

    card_type: CardType
    uid: bytes
    timestamp_ms: int
    read_method: ReadMethod


@dataclass
class ReaderHeartbeat:
    """Parsed heartbeat message from the NFC reader.

    Attributes:
        status: Reader status byte (0x00=OK, 0x01=NFC_CHIP_ERROR, 0x02=LED_ERROR).
        uptime_sec: Seconds since reader boot.
        tap_count: Total taps since reader boot.
        temperature_c: Reader temperature in degrees Celsius.
    """

    status: int
    uptime_sec: int
    tap_count: int
    temperature_c: float


@dataclass
class ConfigUpdate:
    """Config update message to send to the NFC reader.

    Attributes:
        config_key: Configuration key identifier.
        config_data: Variable-length configuration data.
    """

    config_key: int
    config_data: bytes


@dataclass
class ParsedFrame:
    """A fully parsed and CRC-validated RS-485 frame.

    Attributes:
        msg_type: The message type byte.
        payload: Raw payload bytes.
    """

    msg_type: MessageType
    payload: bytes


class FrameParser:
    """Incremental RS-485 frame parser using a state machine.

    Feed raw bytes from the serial port into this parser. It scans for
    sync bytes, reads the length, body, and CRC, validates the CRC, and
    yields complete parsed frames.

    Usage:
        parser = FrameParser()
        for frame in parser.feed(raw_bytes):
            handle_frame(frame)
    """

    def __init__(self) -> None:
        """Initialize parser in WAITING_SYNC1 state."""
        # TODO: Initialize state machine fields
        raise NotImplementedError

    def feed(self, data: bytes) -> list[ParsedFrame]:
        """Feed raw bytes into the parser and return any complete frames.

        Args:
            data: Raw bytes received from the serial port.

        Returns:
            List of successfully parsed and CRC-validated frames.
            Invalid frames (bad CRC, truncated) are logged and discarded.
        """
        # TODO: Implement state machine byte-by-byte parsing
        raise NotImplementedError

    def reset(self) -> None:
        """Reset the parser state machine to WAITING_SYNC1."""
        # TODO: Reset all internal state
        raise NotImplementedError


def compute_crc16(data: bytes) -> int:
    """Compute CRC-16/MODBUS checksum over the given data.

    Args:
        data: Bytes to checksum (LENGTH + MSG_TYPE + PAYLOAD).

    Returns:
        16-bit CRC value.
    """
    # TODO: Implement CRC-16/MODBUS algorithm
    raise NotImplementedError


def build_frame(msg_type: MessageType, payload: bytes) -> bytes:
    """Build a complete RS-485 frame with sync, length, CRC.

    Args:
        msg_type: The message type byte.
        payload: The payload bytes.

    Returns:
        Complete frame bytes ready to send over serial.
    """
    # TODO: Assemble SYNC + LENGTH + MSG_TYPE + PAYLOAD + CRC16
    raise NotImplementedError


def parse_card_tap(payload: bytes) -> CardTapEvent:
    """Parse a card tap event payload into a CardTapEvent.

    Args:
        payload: Raw payload bytes from a MSG_TYPE=0x01 frame.

    Returns:
        Parsed CardTapEvent.

    Raises:
        ValueError: If payload is malformed.
    """
    # TODO: Unpack card_type, uid_length, uid, timestamp_ms, read_method
    raise NotImplementedError


def parse_reader_heartbeat(payload: bytes) -> ReaderHeartbeat:
    """Parse a reader heartbeat payload into a ReaderHeartbeat.

    Args:
        payload: Raw payload bytes from a MSG_TYPE=0x02 frame.

    Returns:
        Parsed ReaderHeartbeat.

    Raises:
        ValueError: If payload is malformed.
    """
    # TODO: Unpack status, uptime_sec, tap_count, temperature
    raise NotImplementedError


def build_config_update(update: ConfigUpdate) -> bytes:
    """Build a config update payload for sending to the reader.

    Args:
        update: The ConfigUpdate to serialize.

    Returns:
        Payload bytes for a MSG_TYPE=0x80 frame.
    """
    # TODO: Pack config_key + config_data
    raise NotImplementedError
