"""Shared test fixtures for SafeCross Edge Controller tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config_manager import (
    CloudConfig,
    CrossingConfig,
    IntersectionConfig,
    LocationConfig,
    NFCReaderConfig,
    OTAConfig,
    SignalControllerConfig,
    TimingRulesConfig,
)
from src.message_protocol import CardTapEvent, CardType, ReadMethod


@pytest.fixture
def sample_crossing_ns() -> CrossingConfig:
    """North-south crossing config (72-foot, phase 4)."""
    return CrossingConfig(
        crossing_id="NS",
        description="North-south crosswalk (Market St)",
        width_ft=72,
        signal_phase=4,
        base_walk_sec=7,
        base_clearance_sec=18,
        max_extension_sec=13,
        min_extension_sec=6,
        ped_detector_phase_bit=4,
    )


@pytest.fixture
def sample_crossing_ew() -> CrossingConfig:
    """East-west crossing config (48-foot, phase 8)."""
    return CrossingConfig(
        crossing_id="EW",
        description="East-west crosswalk (5th St)",
        width_ft=48,
        signal_phase=8,
        base_walk_sec=7,
        base_clearance_sec=12,
        max_extension_sec=8,
        min_extension_sec=4,
        ped_detector_phase_bit=8,
    )


@pytest.fixture
def sample_config(sample_crossing_ns, sample_crossing_ew) -> IntersectionConfig:
    """Complete intersection configuration for testing."""
    return IntersectionConfig(
        intersection_id="INT-2025-0042",
        location=LocationConfig(
            name="Market St & 5th St",
            latitude=37.7837,
            longitude=-122.4073,
        ),
        crossings=[sample_crossing_ns, sample_crossing_ew],
        signal_controller=SignalControllerConfig(
            ip_address="10.0.1.100",
            snmp_port=161,
            snmp_community_read="public",
            snmp_community_write="private",
            protocol_version="ntcip1202v02",
            controller_model="econolite_cobalt",
            supports_scp=False,
        ),
        nfc_reader=NFCReaderConfig(
            serial_port="/dev/ttyS1",
            baud_rate=115200,
            reader_id="RDR-0042-A",
        ),
        timing_rules=TimingRulesConfig(
            cooldown_sec=120,
            max_extensions_per_cycle=1,
            extension_formula="linear_by_width",
            eligible_card_types=["SENIOR_RTC", "DISABLED_RTC"],
            extend_during_active_walk=True,
            block_during_preemption=True,
        ),
        cloud=CloudConfig(
            api_url="https://safecross-api.sfmta.example.com",
            device_cert_path="/etc/safecross/device.pem",
            device_key_path="/etc/safecross/device.key",
            heartbeat_interval_sec=300,
            event_batch_size=10,
            event_flush_interval_sec=60,
        ),
        ota=OTAConfig(
            manifest_url="https://safecross-api.sfmta.example.com/ota/manifest",
            check_interval_sec=86400,
            auto_apply=False,
        ),
    )


@pytest.fixture
def sample_tap_event() -> CardTapEvent:
    """Sample SENIOR_RTC card tap event."""
    return CardTapEvent(
        card_type=CardType.SENIOR_RTC,
        uid=b"\x01\x02\x03\x04\x05\x06\x07",
        timestamp_ms=123456,
        read_method=ReadMethod.APPDIR,
    )


@pytest.fixture
def sample_frame_bytes() -> bytes:
    """Valid RS-485 frame for a SENIOR_RTC card tap (7-byte UID)."""
    from src.reader_interface.protocol import build_config_message
    from src.utils.crc import crc16_modbus
    import struct

    uid = b"\x01\x02\x03\x04\x05\x06\x07"
    payload = struct.pack("<BB", 0x01, len(uid)) + uid + struct.pack("<IB", 123456, 1)
    length = len(payload) + 2
    body = bytes([length, 0x01]) + payload
    crc = crc16_modbus(body)
    return b"\xAA\x55" + body + struct.pack("<H", crc)


class MockSNMPClient:
    """In-memory SNMP client for deterministic testing.

    Mirrors the ``SNMPClient`` interface but stores OID values in a plain
    dict.  Provides helpers to simulate failures and inspect SET history.
    """

    def __init__(self, initial_values: dict[str, Any] | None = None) -> None:
        self._store: dict[str, Any] = dict(initial_values or {})
        self.set_log: list[tuple[str, int]] = []
        self._fail_gets: bool = False
        self._fail_sets: bool = False
        self._remaining_set_failures: int = 0
        self._consecutive_failures: int = 0

    # -- SNMPClient interface --------------------------------------------------

    @property
    def is_reachable(self) -> bool:
        return self._consecutive_failures < 3

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    async def snmp_get(self, oid: str) -> Any | None:
        if self._fail_gets:
            self._consecutive_failures += 1
            return None
        self._consecutive_failures = 0
        return self._store.get(oid)

    async def snmp_set(
        self, oid: str, value: int, value_type: str = "Integer",
    ) -> bool:
        self.set_log.append((oid, value))
        if self._fail_sets:
            self._consecutive_failures += 1
            return False
        if self._remaining_set_failures > 0:
            self._remaining_set_failures -= 1
            self._consecutive_failures += 1
            return False
        self._consecutive_failures = 0
        self._store[oid] = value
        return True

    # -- Test control ----------------------------------------------------------

    def simulate_failure(
        self, *, gets: bool = False, sets: bool = False,
    ) -> None:
        self._fail_gets = gets
        self._fail_sets = sets

    def fail_next_n_sets(self, n: int) -> None:
        """Make the next *n* SET calls fail, then revert to normal."""
        self._remaining_set_failures = n

    def clear_failures(self) -> None:
        self._fail_gets = False
        self._fail_sets = False
        self._remaining_set_failures = 0
        self._consecutive_failures = 0

    def set_value(self, oid: str, value: Any) -> None:
        self._store[oid] = value

    def get_value(self, oid: str) -> Any | None:
        return self._store.get(oid)


@pytest.fixture
def mock_snmp_client() -> MockSNMPClient:
    """MockSNMPClient with empty store."""
    return MockSNMPClient()


@pytest.fixture
def mock_ntcip_client() -> AsyncMock:
    """Mocked NTCIPClient for testing without SNMP hardware."""
    from src.ntcip_client import ControllerMode, ControllerStatus, NTCIPClient, PedTiming, PhaseState

    mock = AsyncMock(spec=NTCIPClient)
    mock.get_phase_state.return_value = PhaseState.PED_DONT_WALK
    mock.get_ped_timing.return_value = PedTiming(walk_sec=7, clearance_sec=18)
    mock.set_ped_walk_time.return_value = True
    mock.place_ped_call.return_value = True
    mock.check_preemption_active.return_value = False
    mock.restore_base_timing.return_value = True
    mock.get_controller_status.return_value = ControllerStatus(
        mode=ControllerMode.AUTO,
        coordination_pattern=1,
        comm_ok=True,
    )
    return mock


@pytest.fixture
async def event_db(tmp_path):
    """Yield an initialised EventStore backed by a temporary SQLite file."""
    from src.logging_events.event_store import EventStore

    db_path = str(tmp_path / "test_events.db")
    store = EventStore(db_path)
    await store.init_db()
    yield store
    await store.close()
