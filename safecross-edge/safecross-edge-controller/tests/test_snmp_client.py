"""Tests for NTCIP OID helpers and SNMP client failure tracking.

Covers:
- get_oid() phase appending
- get_oid_with_overrides() with and without overrides
- Consecutive failure counter / is_reachable behaviour
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.signal_interface.ntcip_objects import (
    CONTROLLER_DESCRIPTION,
    PED_CALL,
    PED_WALK_TIME,
    PREEMPT_STATUS,
    get_oid,
    get_oid_with_overrides,
)
from src.signal_interface.snmp_client import SNMPClient


# ===================================================================
# get_oid
# ===================================================================


class TestGetOid:
    """Test bare OID + phase concatenation."""

    def test_phase_4(self) -> None:
        assert get_oid(PED_WALK_TIME, 4) == f"{PED_WALK_TIME}.4"

    def test_phase_8(self) -> None:
        assert get_oid(PED_CALL, 8) == f"{PED_CALL}.8"

    def test_phase_1(self) -> None:
        assert get_oid(PREEMPT_STATUS, 1) == f"{PREEMPT_STATUS}.1"

    def test_scalar_oid_phase_0(self) -> None:
        """Phase 0 is valid (some OIDs use .0 for scalar access)."""
        assert get_oid(CONTROLLER_DESCRIPTION, 0) == f"{CONTROLLER_DESCRIPTION}.0"


# ===================================================================
# get_oid_with_overrides
# ===================================================================


class TestGetOidWithOverrides:
    """Test OID resolution with per-intersection overrides."""

    def test_no_overrides_uses_default(self) -> None:
        config: dict = {"signal_controller": {}}
        result = get_oid_with_overrides("PED_WALK_TIME", 4, config)
        assert result == f"{PED_WALK_TIME}.4"

    def test_override_replaces_base(self) -> None:
        custom = "1.3.6.1.4.1.9999.1.2.3"
        config: dict = {
            "signal_controller": {
                "oid_overrides": {"PED_WALK_TIME": custom},
            },
        }
        result = get_oid_with_overrides("PED_WALK_TIME", 4, config)
        assert result == f"{custom}.4"

    def test_override_only_affects_named_oid(self) -> None:
        """An override on one name must not bleed to another."""
        config: dict = {
            "signal_controller": {
                "oid_overrides": {"PED_WALK_TIME": "1.2.3"},
            },
        }
        # PED_CALL should still use its default
        result = get_oid_with_overrides("PED_CALL", 8, config)
        assert result == f"{PED_CALL}.8"

    def test_missing_signal_controller_key(self) -> None:
        """Config with no signal_controller section falls back to default."""
        result = get_oid_with_overrides("PED_WALK_TIME", 4, {})
        assert result == f"{PED_WALK_TIME}.4"

    def test_unknown_name_raises(self) -> None:
        with pytest.raises(KeyError):
            get_oid_with_overrides("DOES_NOT_EXIST", 1, {})


# ===================================================================
# SNMPClient — consecutive failure tracking & is_reachable
# ===================================================================


class TestSNMPClientFailureTracking:
    """Test the failure counter and is_reachable property."""

    def _make_client(self) -> SNMPClient:
        return SNMPClient(
            host="10.0.1.100",
            port=161,
            community_read="public",
            community_write="private",
        )

    def test_initial_state_reachable(self) -> None:
        client = self._make_client()
        assert client.is_reachable is True
        assert client.consecutive_failures == 0

    def test_failures_increment(self) -> None:
        client = self._make_client()
        client._record_failure()
        assert client.consecutive_failures == 1
        assert client.is_reachable is True

        client._record_failure()
        assert client.consecutive_failures == 2
        assert client.is_reachable is True

    def test_unreachable_after_3_failures(self) -> None:
        client = self._make_client()
        for _ in range(3):
            client._record_failure()
        assert client.consecutive_failures == 3
        assert client.is_reachable is False

    def test_success_resets_counter(self) -> None:
        client = self._make_client()
        for _ in range(3):
            client._record_failure()
        assert client.is_reachable is False

        client._record_success()
        assert client.consecutive_failures == 0
        assert client.is_reachable is True

    def test_interleaved_success_resets(self) -> None:
        """A single success in the middle resets the counter."""
        client = self._make_client()
        client._record_failure()
        client._record_failure()
        client._record_success()
        assert client.consecutive_failures == 0
        client._record_failure()
        assert client.consecutive_failures == 1
        assert client.is_reachable is True


class TestSNMPClientGetWithMock:
    """Test snmp_get failure tracking with a mocked transport."""

    @pytest.fixture
    def client(self) -> SNMPClient:
        c = SNMPClient(
            host="10.0.1.100",
            port=161,
            community_read="public",
            community_write="private",
        )
        # Pretend we're connected (set internals so snmp_get doesn't bail)
        from pysnmp.hlapi.asyncio import SnmpEngine
        c._engine = SnmpEngine()
        c._transport = AsyncMock()
        return c

    @pytest.mark.asyncio
    async def test_get_timeout_increments_failures(self, client: SNMPClient) -> None:
        """A GET that returns an error_indication counts as a failure."""
        with patch("src.signal_interface.snmp_client.getCmd", new_callable=AsyncMock) as mock_get:
            # Simulate timeout: error_indication is truthy
            mock_get.return_value = ("requestTimedOut", None, None, [])
            result = await client.snmp_get("1.3.6.1.2.1.1.1.0")
            assert result is None
            assert client.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_get_success_resets_failures(self, client: SNMPClient) -> None:
        """A successful GET resets the consecutive failure counter."""
        # Seed some failures
        client._record_failure()
        client._record_failure()

        with patch("src.signal_interface.snmp_client.getCmd", new_callable=AsyncMock) as mock_get:
            mock_bind = ("1.3.6.1.2.1.1.1.0", "TestController")
            mock_get.return_value = (None, None, None, [mock_bind])
            result = await client.snmp_get("1.3.6.1.2.1.1.1.0")
            assert result == "TestController"
            assert client.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_three_timeouts_makes_unreachable(self, client: SNMPClient) -> None:
        with patch("src.signal_interface.snmp_client.getCmd", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = ("requestTimedOut", None, None, [])
            for _ in range(3):
                await client.snmp_get("1.3.6.1.2.1.1.1.0")
            assert client.is_reachable is False


class TestSNMPv3Stub:
    """SNMPv3 raises NotImplementedError."""

    def test_v3_raises(self) -> None:
        with pytest.raises(NotImplementedError, match="Only SNMPv2c"):
            SNMPClient(
                host="10.0.1.100",
                port=161,
                community_read="public",
                community_write="private",
                snmp_version="v3",
            )
