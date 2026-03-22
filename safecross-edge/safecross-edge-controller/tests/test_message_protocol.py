"""Tests for RS-485 message protocol — frame parsing and CRC.

Covers:
- Correct SYNC, LENGTH, CRC-16/MODBUS construction
- Valid frame decoding
- Corrupted frame rejection (bad CRC)
- Truncated frame handling
- Back-to-back frame parsing
- Known CRC-16/MODBUS test vectors
"""

from __future__ import annotations

import pytest

from src.message_protocol import (
    CardTapEvent,
    CardType,
    FrameParser,
    MessageType,
    ReadMethod,
    ReaderHeartbeat,
    build_frame,
    compute_crc16,
    parse_card_tap,
    parse_reader_heartbeat,
)


class TestCRC16Modbus:
    """CRC-16/MODBUS computation tests."""

    def test_known_vector_empty(self) -> None:
        """CRC-16/MODBUS of empty data should return 0xFFFF."""
        # TODO: assert compute_crc16(b"") == 0xFFFF
        pass

    def test_known_vector_123456789(self) -> None:
        """CRC-16/MODBUS of '123456789' should return 0x4B37."""
        # TODO: assert compute_crc16(b"123456789") == 0x4B37
        pass

    def test_deterministic(self) -> None:
        """Same input always produces same CRC."""
        # TODO: Call compute_crc16 twice, assert equal
        pass


class TestFrameConstruction:
    """Frame building tests."""

    def test_build_frame_sync_bytes(self) -> None:
        """Built frame starts with 0xAA 0x55."""
        # TODO: Build a frame, check first two bytes
        pass

    def test_build_frame_length_field(self) -> None:
        """LENGTH byte equals len(payload) + 2 (msg_type + payload)."""
        # TODO: Build a frame, verify LENGTH byte
        pass

    def test_build_frame_crc_valid(self) -> None:
        """CRC in built frame matches recomputed CRC."""
        # TODO: Build a frame, extract CRC, recompute and compare
        pass


class TestFrameParser:
    """Incremental frame parser state machine tests."""

    def test_valid_frame_decoded(self) -> None:
        """A correctly built frame is parsed successfully."""
        # TODO: Build a frame, feed to parser, check output
        pass

    def test_corrupted_crc_rejected(self) -> None:
        """A frame with corrupted CRC is discarded."""
        # TODO: Build a frame, flip a CRC bit, feed to parser, check empty
        pass

    def test_truncated_frame_handled(self) -> None:
        """A truncated frame does not crash the parser."""
        # TODO: Feed partial frame bytes, verify no output and no exception
        pass

    def test_back_to_back_frames(self) -> None:
        """Two valid frames concatenated are both parsed."""
        # TODO: Build two frames, concatenate, feed to parser, check two outputs
        pass

    def test_garbage_before_sync_skipped(self) -> None:
        """Random bytes before a valid frame are skipped."""
        # TODO: Prepend garbage bytes, feed to parser, check valid frame parsed
        pass


class TestCardTapParsing:
    """Card tap event payload parsing tests."""

    def test_parse_senior_rtc_7byte_uid(self) -> None:
        """Parse a SENIOR_RTC tap with 7-byte UID."""
        # TODO: Construct payload, call parse_card_tap, verify fields
        pass

    def test_parse_disabled_rtc_4byte_uid(self) -> None:
        """Parse a DISABLED_RTC tap with 4-byte UID."""
        # TODO: Construct payload, call parse_card_tap, verify fields
        pass

    def test_malformed_payload_raises(self) -> None:
        """Malformed payload raises ValueError."""
        # TODO: Feed truncated payload, expect ValueError
        pass


class TestReaderHeartbeatParsing:
    """Reader heartbeat payload parsing tests."""

    def test_parse_ok_heartbeat(self) -> None:
        """Parse a healthy heartbeat message."""
        # TODO: Construct payload, call parse_reader_heartbeat, verify fields
        pass

    def test_temperature_conversion(self) -> None:
        """Temperature is correctly converted from 0.1C units."""
        # TODO: Verify int16 -> float conversion
        pass
