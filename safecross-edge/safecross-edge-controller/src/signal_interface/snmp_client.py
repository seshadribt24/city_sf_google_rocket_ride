"""Async SNMP client for traffic signal controller communication.

Uses ``pysnmp-lextudio`` (v6+) for SNMPv2c GET / GET-BULK / SET
operations against the signal controller's NTCIP 1202 MIB.
"""

from __future__ import annotations

import logging
from typing import Any

from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
    setCmd,
)
from pysnmp.proto.rfc1902 import Integer32, OctetString

from src.signal_interface.ntcip_objects import CONTROLLER_DESCRIPTION, CONTROLLER_VERSION

logger = logging.getLogger(__name__)

# Number of consecutive failures before we consider the controller unreachable
_UNREACHABLE_THRESHOLD: int = 3


class SNMPClient:
    """Async SNMPv2c client for a single traffic signal controller.

    Attributes:
        host: IP address or hostname of the controller.
        port: SNMP UDP port (usually 161).
        community_read: SNMPv2c read community string.
        community_write: SNMPv2c write community string.
        timeout_sec: Per-request timeout in seconds.
        retries: Number of automatic retries per request.
    """

    def __init__(
        self,
        host: str,
        port: int,
        community_read: str,
        community_write: str,
        snmp_version: str = "v2c",
        timeout_sec: float = 2.0,
        retries: int = 1,
    ) -> None:
        if snmp_version != "v2c":
            raise NotImplementedError(
                # TODO: implement SNMPv3 with auth (MD5/SHA) and privacy
                # (DES/AES) when SFMTA provides credentials
                f"Only SNMPv2c is supported; got {snmp_version!r}"
            )

        self.host = host
        self.port = port
        self.community_read = community_read
        self.community_write = community_write
        self.timeout_sec = timeout_sec
        self.retries = retries

        self._engine: SnmpEngine | None = None
        self._transport: UdpTransportTarget | None = None
        self._consecutive_failures: int = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Create the SNMP engine / transport and verify connectivity.

        Performs a test ``GET`` on ``CONTROLLER_DESCRIPTION`` and
        ``CONTROLLER_VERSION``.  Logs the returned strings on success.

        Raises:
            RuntimeError: If the connectivity check fails.
        """
        self._engine = SnmpEngine()
        self._transport = UdpTransportTarget(
            (self.host, self.port),
            timeout=self.timeout_sec,
            retries=self.retries,
        )

        desc = await self.snmp_get(CONTROLLER_DESCRIPTION)
        ver = await self.snmp_get(CONTROLLER_VERSION)

        if desc is None and ver is None:
            raise RuntimeError(
                f"Cannot reach signal controller at {self.host}:{self.port}"
            )

        logger.info(
            "Connected to signal controller %s:%d — %s (version %s)",
            self.host, self.port, desc, ver,
        )

    async def close(self) -> None:
        """Release SNMP engine resources."""
        if self._engine is not None:
            self._engine.closeDispatcher()
            self._engine = None
        self._transport = None
        logger.info("SNMP client closed")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_reachable(self) -> bool:
        """``True`` if fewer than 3 consecutive failures have occurred."""
        return self._consecutive_failures < _UNREACHABLE_THRESHOLD

    @property
    def consecutive_failures(self) -> int:
        """Current consecutive-failure count (exposed for testing)."""
        return self._consecutive_failures

    # ------------------------------------------------------------------
    # SNMP operations
    # ------------------------------------------------------------------

    async def snmp_get(self, oid: str) -> Any | None:
        """Perform an SNMP GET and return the value.

        Args:
            oid: Fully-qualified OID string.

        Returns:
            The value on success, or ``None`` on timeout / error.
        """
        if self._engine is None or self._transport is None:
            logger.error("snmp_get called before connect()")
            return None

        logger.debug("SNMP GET %s", oid)

        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                self._engine,
                CommunityData(self.community_read),
                self._transport,
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
            )
        except Exception as exc:
            self._record_failure()
            logger.warning("SNMP GET %s exception: %s", oid, exc)
            return None

        if error_indication:
            self._record_failure()
            logger.warning("SNMP GET %s timeout/error: %s", oid, error_indication)
            return None

        if error_status:
            self._record_failure()
            logger.warning(
                "SNMP GET %s error-status at %s: %s",
                oid, error_index, error_status.prettyPrint(),
            )
            return None

        self._record_success()
        value = var_binds[0][1]
        logger.debug("SNMP GET %s → %s", oid, value)
        return value

    async def snmp_get_bulk(self, oids: list[str]) -> dict[str, Any]:
        """GET multiple OIDs, returning a dict mapping OID → value.

        Each OID is fetched with an individual GET (pysnmp v2c does not
        expose a true GetBulk for arbitrary OID lists).  OIDs that fail
        map to ``None``.

        Args:
            oids: List of fully-qualified OID strings.

        Returns:
            Dict of ``{oid: value_or_None}``.
        """
        results: dict[str, Any] = {}
        for oid in oids:
            results[oid] = await self.snmp_get(oid)
        return results

    async def snmp_set(
        self,
        oid: str,
        value: int,
        value_type: str = "Integer",
    ) -> bool:
        """Perform an SNMP SET.

        Args:
            oid: Fully-qualified OID string.
            value: Value to write.
            value_type: ``"Integer"`` (default) or ``"OctetString"``.

        Returns:
            ``True`` on success, ``False`` on error.
        """
        if self._engine is None or self._transport is None:
            logger.error("snmp_set called before connect()")
            return False

        logger.info("SNMP SET %s = %s (%s)", oid, value, value_type)

        if value_type == "OctetString":
            snmp_value = OctetString(value)
        else:
            snmp_value = Integer32(value)

        try:
            error_indication, error_status, error_index, var_binds = await setCmd(
                self._engine,
                CommunityData(self.community_write),
                self._transport,
                ContextData(),
                ObjectType(ObjectIdentity(oid), snmp_value),
            )
        except Exception as exc:
            self._record_failure()
            logger.error("SNMP SET %s exception: %s", oid, exc)
            return False

        if error_indication:
            self._record_failure()
            logger.error("SNMP SET %s timeout/error: %s", oid, error_indication)
            return False

        if error_status:
            self._record_failure()
            logger.error(
                "SNMP SET %s error-status at %s: %s",
                oid, error_index, error_status.prettyPrint(),
            )
            return False

        self._record_success()
        logger.info("SNMP SET %s = %s OK", oid, value)
        return True

    # ------------------------------------------------------------------
    # Failure tracking
    # ------------------------------------------------------------------

    def _record_failure(self) -> None:
        self._consecutive_failures += 1

    def _record_success(self) -> None:
        self._consecutive_failures = 0
