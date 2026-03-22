"""RS-485 frame protocol for NFC reader ↔ edge controller communication.

Frame format (from SPEC.md):
    | SYNC (2 B) | LENGTH (1 B) | MSG_TYPE (1 B) | PAYLOAD (N B) | CRC16 (2 B) |
    | 0xAA 0x55  | N + 2        | see below      | varies        | CRC-16/MODBUS|

LENGTH = len(payload) + 2  (accounts for MSG_TYPE byte and LENGTH byte itself).
CRC-16/MODBUS is computed over the bytes: LENGTH + MSG_TYPE + PAYLOAD.
CRC is stored little-endian (low byte first).
All multi-byte integers inside payloads are little-endian.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any

from src.utils.crc import crc16_modbus

# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------
SYNC = b"\xAA\x55"

# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------
MSG_CARD_TAP: int = 0x01
MSG_HEARTBEAT: int = 0x02
MSG_CONFIG_UPDATE: int = 0x80
MSG_CONFIG_ACK: int = 0x81

# ---------------------------------------------------------------------------
# Card-type constants
# ---------------------------------------------------------------------------
CARD_TYPE_NONE: int = 0x00
CARD_TYPE_SENIOR_RTC: int = 0x01
CARD_TYPE_DISABLED_RTC: int = 0x02
CARD_TYPE_STANDARD: int = 0x03
CARD_TYPE_YOUTH: int = 0x04
CARD_TYPE_DESFIRE_DETECTED: int = 0x05
CARD_TYPE_UNKNOWN: int = 0xFF

EXTENSION_ELIGIBLE: set[int] = {CARD_TYPE_SENIOR_RTC, CARD_TYPE_DISABLED_RTC}

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CardTapEvent:
    """Parsed card-tap event from the NFC reader.

    Attributes:
        card_type: One of the CARD_TYPE_* constants.
        uid: Raw UID bytes (4 or 7 bytes).
        timestamp_ms: Milliseconds since reader boot (uint32 LE).
        read_method: Classification method (1=APPDIR, 2=UID_PREFIX, 3=ANY_DESFIRE).
    """

    card_type: int
    uid: bytes
    timestamp_ms: int
    read_method: int


@dataclass
class ReaderHeartbeat:
    """Parsed heartbeat from the NFC reader.

    Attributes:
        status: 0x00=OK, 0x01=NFC_CHIP_ERROR, 0x02=LED_ERROR.
        uptime_sec: Seconds since reader boot (uint32 LE).
        tap_count: Total taps since boot (uint32 LE).
        temperature_c: Temperature in °C (from int16 in 0.1 °C units).
    """

    status: int
    uptime_sec: int
    tap_count: int
    temperature_c: float


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_card_tap_payload(payload: bytes) -> dict[str, Any]:
    """Decode a card-tap payload into a dict matching CardTapEvent fields.

    Payload layout:
        card_type    1 B
        uid_length   1 B  (4 or 7)
        uid          uid_length B
        timestamp_ms 4 B  uint32 LE
        read_method  1 B
    """
    if len(payload) < 2:
        raise ValueError("Card-tap payload too short")
    card_type = payload[0]
    uid_length = payload[1]
    if uid_length not in (4, 7):
        raise ValueError(f"Invalid uid_length: {uid_length}")
    expected = 2 + uid_length + 4 + 1  # header + uid + timestamp + read_method
    if len(payload) < expected:
        raise ValueError("Card-tap payload truncated")
    uid = payload[2 : 2 + uid_length]
    offset = 2 + uid_length
    timestamp_ms = struct.unpack_from("<I", payload, offset)[0]
    read_method = payload[offset + 4]
    return {
        "card_type": card_type,
        "uid": uid,
        "timestamp_ms": timestamp_ms,
        "read_method": read_method,
    }


def _parse_heartbeat_payload(payload: bytes) -> dict[str, Any]:
    """Decode a heartbeat payload into a dict matching ReaderHeartbeat fields.

    Payload layout:
        status       1 B
        uptime_sec   4 B  uint32 LE
        tap_count    4 B  uint32 LE
        temperature  2 B  int16  LE  (0.1 °C units)
    """
    if len(payload) < 11:
        raise ValueError("Heartbeat payload too short")
    status = payload[0]
    uptime_sec = struct.unpack_from("<I", payload, 1)[0]
    tap_count = struct.unpack_from("<I", payload, 5)[0]
    raw_temp = struct.unpack_from("<h", payload, 9)[0]
    return {
        "status": status,
        "uptime_sec": uptime_sec,
        "tap_count": tap_count,
        "temperature_c": raw_temp / 10.0,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_frame(buffer: bytes) -> tuple[int, dict[str, Any], int] | None:
    """Parse the first valid frame from *buffer*.

    Scans for the SYNC bytes (0xAA 0x55), reads LENGTH, MSG_TYPE,
    PAYLOAD, and CRC.  Validates CRC-16/MODBUS over
    ``LENGTH + MSG_TYPE + PAYLOAD``.

    Returns:
        ``(msg_type, parsed_payload_dict, total_bytes_consumed)`` for the
        first valid frame, or ``None`` if the buffer contains no complete
        valid frame (partial data or CRC mismatch).
    """
    buf_len = len(buffer)
    pos = 0

    while pos <= buf_len - 2:
        # --- scan for SYNC ---------------------------------------------------
        sync_idx = buffer.find(SYNC, pos)
        if sync_idx == -1:
            return None

        start = sync_idx  # first byte of the frame

        # --- LENGTH -----------------------------------------------------------
        length_offset = start + 2
        if length_offset >= buf_len:
            return None  # need at least the LENGTH byte

        length_val = buffer[length_offset]

        # Sanity: LENGTH must be >= 2 (MSG_TYPE + at least 0-byte payload, but
        # the "+2" in the spec accounts for MSG_TYPE and LENGTH-byte-self).
        # payload_size = LENGTH - 2.  Minimum LENGTH is 3 (1 msg_type byte +
        # 0-byte payload + the 2 counted by the formula... actually minimum
        # meaningful LENGTH = 2+0 = 2 when there is no payload).
        if length_val < 2:
            # Not a real frame; skip past this SYNC and keep scanning.
            pos = sync_idx + 1
            continue

        payload_size = length_val - 2  # N = LENGTH - 2

        # Total frame bytes: SYNC(2) + LENGTH(1) + MSG_TYPE(1) + PAYLOAD(N) + CRC(2)
        frame_len = 2 + 1 + 1 + payload_size + 2
        if start + frame_len > buf_len:
            return None  # incomplete frame

        # --- extract parts ----------------------------------------------------
        msg_type = buffer[start + 3]
        payload = buffer[start + 4 : start + 4 + payload_size]
        crc_bytes = buffer[start + 4 + payload_size : start + 4 + payload_size + 2]
        received_crc = struct.unpack_from("<H", crc_bytes, 0)[0]

        # CRC is over LENGTH + MSG_TYPE + PAYLOAD
        crc_data = buffer[start + 2 : start + 4 + payload_size]  # length_byte + msg_type + payload
        computed_crc = crc16_modbus(crc_data)

        if received_crc != computed_crc:
            # Bad CRC — skip past this SYNC and keep scanning.
            pos = sync_idx + 1
            continue

        # --- decode payload ---------------------------------------------------
        parsed: dict[str, Any]
        if msg_type == MSG_CARD_TAP:
            try:
                parsed = _parse_card_tap_payload(payload)
            except ValueError:
                pos = sync_idx + 1
                continue
        elif msg_type == MSG_HEARTBEAT:
            try:
                parsed = _parse_heartbeat_payload(payload)
            except ValueError:
                pos = sync_idx + 1
                continue
        else:
            # Unknown or config-ack — return raw payload as dict
            parsed = {"raw": payload}

        bytes_consumed = (start - 0) + frame_len  # bytes from buffer[0] through end of frame
        # Actually we want bytes consumed from the START of the buffer
        # so the caller can slice buffer[bytes_consumed:] for the next call.
        bytes_consumed = start + frame_len

        return (msg_type, parsed, bytes_consumed)

    return None


def build_config_message(config_key: int, config_data: bytes) -> bytes:
    """Build a complete frame for MSG_TYPE 0x80 (config update to reader).

    Args:
        config_key: 1-byte configuration key identifier.
        config_data: Variable-length configuration data.

    Returns:
        Raw frame bytes ready to send over serial.
    """
    payload = bytes([config_key]) + config_data
    return _build_frame(MSG_CONFIG_UPDATE, payload)


def _build_frame(msg_type: int, payload: bytes) -> bytes:
    """Assemble a complete RS-485 frame.

    Frame: SYNC(2) + LENGTH(1) + MSG_TYPE(1) + PAYLOAD(N) + CRC16(2)
    LENGTH = len(payload) + 2
    CRC covers LENGTH + MSG_TYPE + PAYLOAD.
    """
    length_val = len(payload) + 2  # N + 2
    # Bytes that the CRC covers
    crc_data = bytes([length_val, msg_type]) + payload
    crc = crc16_modbus(crc_data)
    return SYNC + crc_data + struct.pack("<H", crc)
