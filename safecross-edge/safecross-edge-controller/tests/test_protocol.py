"""Tests for CRC-16/MODBUS and RS-485 frame protocol.

Covers:
- CRC-16/MODBUS known test vectors
- parse_frame with valid card-tap and heartbeat frames
- parse_frame with truncated / corrupt / concatenated frames
- SYNC bytes inside payload (no false trigger)
- build_config_message round-trip through parse_frame
- Little-endian byte ordering of multi-byte fields
"""

from __future__ import annotations

import struct

import pytest

from src.utils.crc import crc16_modbus
from src.reader_interface.protocol import (
    CARD_TYPE_DISABLED_RTC,
    CARD_TYPE_SENIOR_RTC,
    MSG_CARD_TAP,
    MSG_CONFIG_UPDATE,
    MSG_HEARTBEAT,
    SYNC,
    build_config_message,
    parse_frame,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_frame(msg_type: int, payload: bytes) -> bytes:
    """Build a raw frame (duplicates internal helper for test clarity)."""
    length_val = len(payload) + 2
    crc_data = bytes([length_val, msg_type]) + payload
    crc = crc16_modbus(crc_data)
    return SYNC + crc_data + struct.pack("<H", crc)


def _make_card_tap_payload(
    card_type: int = CARD_TYPE_SENIOR_RTC,
    uid: bytes = b"\x01\x02\x03\x04\x05\x06\x07",
    timestamp_ms: int = 100_000,
    read_method: int = 1,
) -> bytes:
    """Build a card-tap payload with the given values."""
    uid_length = len(uid)
    return (
        bytes([card_type, uid_length])
        + uid
        + struct.pack("<I", timestamp_ms)
        + bytes([read_method])
    )


def _make_heartbeat_payload(
    status: int = 0x00,
    uptime_sec: int = 3600,
    tap_count: int = 42,
    temperature_raw: int = 253,  # 25.3 °C in 0.1 °C units
) -> bytes:
    return (
        bytes([status])
        + struct.pack("<I", uptime_sec)
        + struct.pack("<I", tap_count)
        + struct.pack("<h", temperature_raw)
    )


# ===================================================================
# CRC-16/MODBUS tests
# ===================================================================


class TestCRC16Modbus:
    """CRC-16/MODBUS known-vector tests."""

    def test_empty_data(self) -> None:
        assert crc16_modbus(b"") == 0xFFFF

    def test_123456789(self) -> None:
        assert crc16_modbus(b"123456789") == 0x4B37

    def test_01020304(self) -> None:
        assert crc16_modbus(b"\x01\x02\x03\x04") == 0x2BA1

    def test_full_message_payload(self) -> None:
        """CRC of a manually-constructed LENGTH+MSG_TYPE+PAYLOAD matches."""
        payload = _make_card_tap_payload()
        length_val = len(payload) + 2
        crc_data = bytes([length_val, MSG_CARD_TAP]) + payload
        crc = crc16_modbus(crc_data)
        # Re-compute must be identical
        assert crc == crc16_modbus(crc_data)
        # And it must be a 16-bit value
        assert 0 <= crc <= 0xFFFF


# ===================================================================
# parse_frame — valid frames
# ===================================================================


class TestParseFrameValid:
    """parse_frame correctly decodes well-formed frames."""

    def test_valid_card_tap(self) -> None:
        uid = b"\xAB\xCD\xEF\x01\x02\x03\x04"
        payload = _make_card_tap_payload(
            card_type=CARD_TYPE_SENIOR_RTC,
            uid=uid,
            timestamp_ms=500_000,
            read_method=2,
        )
        frame = _build_frame(MSG_CARD_TAP, payload)

        result = parse_frame(frame)
        assert result is not None
        msg_type, data, consumed = result
        assert msg_type == MSG_CARD_TAP
        assert data["card_type"] == CARD_TYPE_SENIOR_RTC
        assert data["uid"] == uid
        assert data["timestamp_ms"] == 500_000
        assert data["read_method"] == 2
        assert consumed == len(frame)

    def test_valid_heartbeat(self) -> None:
        payload = _make_heartbeat_payload(
            status=0x00, uptime_sec=7200, tap_count=99, temperature_raw=312,
        )
        frame = _build_frame(MSG_HEARTBEAT, payload)

        result = parse_frame(frame)
        assert result is not None
        msg_type, data, consumed = result
        assert msg_type == MSG_HEARTBEAT
        assert data["status"] == 0x00
        assert data["uptime_sec"] == 7200
        assert data["tap_count"] == 99
        assert data["temperature_c"] == pytest.approx(31.2)
        assert consumed == len(frame)


# ===================================================================
# parse_frame — error / edge cases
# ===================================================================


class TestParseFrameErrors:
    """parse_frame handles partial, corrupt, and concatenated data."""

    def test_truncated_frame_returns_none(self) -> None:
        """Only SYNC + partial LENGTH → None."""
        assert parse_frame(b"\xAA\x55") is None
        assert parse_frame(b"\xAA\x55\x04") is None  # not enough body

    def test_corrupt_crc_returns_none(self) -> None:
        payload = _make_card_tap_payload()
        frame = bytearray(_build_frame(MSG_CARD_TAP, payload))
        # Flip a bit in the CRC (last two bytes)
        frame[-1] ^= 0x01
        assert parse_frame(bytes(frame)) is None

    def test_two_concatenated_frames(self) -> None:
        """Two valid frames back-to-back: first call returns frame 1."""
        tap_payload = _make_card_tap_payload()
        hb_payload = _make_heartbeat_payload()
        frame1 = _build_frame(MSG_CARD_TAP, tap_payload)
        frame2 = _build_frame(MSG_HEARTBEAT, hb_payload)
        combined = frame1 + frame2

        result1 = parse_frame(combined)
        assert result1 is not None
        msg1, data1, consumed1 = result1
        assert msg1 == MSG_CARD_TAP
        assert consumed1 == len(frame1)

        # Second call on the remainder
        result2 = parse_frame(combined[consumed1:])
        assert result2 is not None
        msg2, data2, consumed2 = result2
        assert msg2 == MSG_HEARTBEAT
        assert consumed2 == len(frame2)

    def test_sync_inside_payload_no_false_trigger(self) -> None:
        """SYNC bytes (0xAA 0x55) embedded in a UID must not confuse parser."""
        # UID contains the sync pattern
        uid = b"\xAA\x55\xAA\x55\xDE\xAD\xBE"
        payload = _make_card_tap_payload(uid=uid, timestamp_ms=1)
        frame = _build_frame(MSG_CARD_TAP, payload)

        result = parse_frame(frame)
        assert result is not None
        msg_type, data, consumed = result
        assert data["uid"] == uid
        assert consumed == len(frame)


# ===================================================================
# build_config_message round-trip
# ===================================================================


class TestBuildConfigMessage:
    """build_config_message produces a frame that parse_frame can read."""

    def test_round_trip(self) -> None:
        config_key = 0x02
        config_data = b"\x10\x20\x30"
        frame = build_config_message(config_key, config_data)

        result = parse_frame(frame)
        assert result is not None
        msg_type, data, consumed = result
        assert msg_type == MSG_CONFIG_UPDATE
        # For non-tap/heartbeat types, parse_frame returns {"raw": payload}
        assert data["raw"] == bytes([config_key]) + config_data
        assert consumed == len(frame)


# ===================================================================
# Little-endian byte ordering
# ===================================================================


class TestLittleEndianOrdering:
    """Verify little-endian encoding of multi-byte fields."""

    def test_timestamp_bytes_in_frame(self) -> None:
        """timestamp_ms=0x12345678 encodes as 78 56 34 12 in the frame."""
        ts = 0x12345678
        uid = b"\x01\x02\x03\x04"  # 4-byte UID for easy offset math
        payload = _make_card_tap_payload(uid=uid, timestamp_ms=ts)
        frame = _build_frame(MSG_CARD_TAP, payload)

        # payload starts at frame[4] (after SYNC+LENGTH+MSG_TYPE)
        # inside payload: card_type(1) + uid_len(1) + uid(4) + timestamp(4)
        ts_offset = 4 + 1 + 1 + 4  # frame offset to timestamp bytes
        ts_bytes = frame[ts_offset : ts_offset + 4]
        assert ts_bytes == b"\x78\x56\x34\x12"

        # And parse_frame should decode it back correctly
        result = parse_frame(frame)
        assert result is not None
        _, data, _ = result
        assert data["timestamp_ms"] == 0x12345678
