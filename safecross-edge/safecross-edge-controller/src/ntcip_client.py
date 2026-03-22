"""NTCIP/SNMP client for traffic signal controller communication.

Communicates with the traffic signal controller using SNMP v2c to read
signal phase state and write pedestrian timing parameters per NTCIP 1202.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from .config_manager import SignalControllerConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NTCIP 1202 OID constants
# ---------------------------------------------------------------------------

NTCIP_BASE = "1.3.6.1.4.1.1206.4.2.1"

# Phase status group — read current phase state
PHASE_STATUS_GROUP_GREENS = f"{NTCIP_BASE}.1.4.1.4"
PHASE_STATUS_GROUP_YELLOWS = f"{NTCIP_BASE}.1.4.1.5"
PHASE_STATUS_GROUP_REDS = f"{NTCIP_BASE}.1.4.1.6"

# Pedestrian phase status
PED_STATUS_WALK = f"{NTCIP_BASE}.1.4.1.7"
PED_STATUS_PED_CLEAR = f"{NTCIP_BASE}.1.4.1.8"
PED_STATUS_DONT_WALK = f"{NTCIP_BASE}.1.4.1.9"

# Pedestrian timing parameters (per phase) — writable
PED_WALK_TIME = f"{NTCIP_BASE}.1.2.1.7"
PED_CLEAR_TIME = f"{NTCIP_BASE}.1.2.1.8"

# Pedestrian call control
PED_CALL = f"{NTCIP_BASE}.1.3.1.3"

# Preemption status
PREEMPT_STATE = f"{NTCIP_BASE}.6.5.1.4"

# Coordination status
COORD_PATTERN_STATUS = f"{NTCIP_BASE}.3.6.1.3"

# Unit control
UNIT_CONTROL_STATUS = f"{NTCIP_BASE}.6.1"

# Hard-coded safety ceiling
MAX_TOTAL_WALK_SEC = 45


class PhaseState(Enum):
    """Current state of a traffic signal phase."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    PED_WALK = "ped_walk"
    PED_CLEAR = "ped_clear"
    PED_DONT_WALK = "ped_dont_walk"
    PREEMPTED = "preempted"
    UNKNOWN = "unknown"


class ControllerMode(Enum):
    """Operating mode of the traffic signal controller."""

    AUTO = "auto"
    MANUAL = "manual"
    FLASH = "flash"
    PREEMPT = "preempt"


@dataclass
class PedTiming:
    """Pedestrian timing parameters for a signal phase.

    Attributes:
        walk_sec: Current walk time in seconds.
        clearance_sec: Current pedestrian clearance time in seconds.
    """

    walk_sec: int
    clearance_sec: int


@dataclass
class ControllerStatus:
    """Overall traffic signal controller status.

    Attributes:
        mode: Current operating mode.
        coordination_pattern: Active coordination pattern number.
        comm_ok: True if SNMP communication is healthy.
    """

    mode: ControllerMode
    coordination_pattern: int
    comm_ok: bool


class SNMPError(Exception):
    """Raised when an SNMP operation fails."""

    pass


# ---------------------------------------------------------------------------
# Vendor OID profiles
# ---------------------------------------------------------------------------


class VendorOIDProfile:
    """Base OID profile using standard NTCIP 1202 v02 OIDs.

    Subclass to override OIDs for specific controller manufacturers.
    """

    def ped_walk_time_oid(self, phase: int) -> str:
        """Return the OID for pedestrian walk time for a given phase."""
        return f"{NTCIP_BASE}.1.2.1.7.{phase}"

    def ped_clear_time_oid(self, phase: int) -> str:
        """Return the OID for pedestrian clearance time for a given phase."""
        return f"{NTCIP_BASE}.1.2.1.8.{phase}"

    def ped_call_oid(self, phase: int) -> str:
        """Return the OID for placing a pedestrian call for a given phase."""
        return f"{NTCIP_BASE}.1.3.1.3.{phase}"

    def ped_walk_status_oid(self) -> str:
        """Return the OID for pedestrian walk status bitmap."""
        return f"{NTCIP_BASE}.1.4.1.7.0"

    def ped_clear_status_oid(self) -> str:
        """Return the OID for pedestrian clearance status bitmap."""
        return f"{NTCIP_BASE}.1.4.1.8.0"

    def ped_dont_walk_status_oid(self) -> str:
        """Return the OID for pedestrian don't-walk status bitmap."""
        return f"{NTCIP_BASE}.1.4.1.9.0"

    def preempt_state_oid(self, preempt_num: int = 1) -> str:
        """Return the OID for preemption state."""
        return f"{NTCIP_BASE}.6.5.1.4.{preempt_num}"


class EconoliteCobaltProfile(VendorOIDProfile):
    """Econolite Cobalt controller — uses standard OIDs."""

    pass


class McCainProfile(VendorOIDProfile):
    """McCain controller — may need OID adjustments."""

    pass


def get_vendor_profile(model: str) -> VendorOIDProfile:
    """Return the appropriate VendorOIDProfile for the given controller model.

    Args:
        model: Controller model identifier from config.

    Returns:
        VendorOIDProfile instance (defaults to base profile for unknown models).
    """
    profiles: dict[str, VendorOIDProfile] = {
        "econolite_cobalt": EconoliteCobaltProfile(),
        "mccain": McCainProfile(),
    }
    return profiles.get(model, VendorOIDProfile())


# ---------------------------------------------------------------------------
# NTCIP Client
# ---------------------------------------------------------------------------


class NTCIPClient:
    """Async SNMP client for traffic signal controller communication.

    All operations use SNMP v2c (the version supported by most deployed
    signal controllers). Uses community strings for authentication.

    Attributes:
        config: Signal controller connection configuration.
        vendor_profile: OID profile for the target controller model.
    """

    def __init__(self, config: SignalControllerConfig) -> None:
        """Initialize the NTCIP client.

        Args:
            config: Signal controller connection configuration.
        """
        self.config = config
        self.vendor_profile = get_vendor_profile(config.controller_model)

    async def connect(self, config: SignalControllerConfig) -> None:
        """Initialize SNMP transport to the signal controller.

        Args:
            config: Signal controller connection configuration.
        """
        # TODO: Set up pysnmp-lextudio SNMP engine and transport
        raise NotImplementedError

    async def get_phase_state(self, phase: int) -> PhaseState:
        """Read current state of a signal phase.

        Reads the phase status bitmaps and checks which bit is set
        for the given phase number.

        Args:
            phase: Signal phase number (1-indexed).

        Returns:
            PhaseState enum value for the current phase state.
        """
        # TODO: SNMP GET phase status bitmaps, decode bit for phase
        raise NotImplementedError

    async def get_ped_timing(self, phase: int) -> PedTiming:
        """Read current pedestrian timing parameters for a phase.

        Args:
            phase: Signal phase number.

        Returns:
            PedTiming with walk_sec and clearance_sec.
        """
        # TODO: SNMP GET phaseWalk and phasePedClear OIDs
        raise NotImplementedError

    async def set_ped_walk_time(self, phase: int, seconds: int) -> bool:
        """Write a new pedestrian walk time for a phase.

        This is the core extension operation. Sends an SNMP SET on
        phaseWalk.{phase} with the new value.

        Safety constraints:
            - MUST reject any value > (base_walk_sec + max_extension_sec)
            - Hard-coded upper bound: never exceed 45 seconds

        Args:
            phase: Signal phase number.
            seconds: New walk time in seconds (base + extension).

        Returns:
            True if SNMP SET was acknowledged, False on error.
        """
        # TODO: Validate seconds against safety ceiling
        # TODO: SNMP SET phaseWalk.{phase} = seconds
        raise NotImplementedError

    async def place_ped_call(self, phase: int) -> bool:
        """Place a pedestrian call for a phase.

        Equivalent to pressing the pedestrian push button. Sends SNMP SET
        to phasePedCall with the appropriate bit set.

        Args:
            phase: Signal phase number.

        Returns:
            True if acknowledged, False on error.
        """
        # TODO: SNMP SET phasePedCall.{phase} with appropriate bit
        raise NotImplementedError

    async def check_preemption_active(self) -> bool:
        """Check if any preemption is currently active on the controller.

        Checks for emergency vehicle preemption or transit priority.

        Returns:
            True if preemption is active (we should NOT extend).
        """
        # TODO: SNMP GET preemptState OID, check for active preemption
        raise NotImplementedError

    async def restore_base_timing(self, phase: int, base_walk_sec: int) -> bool:
        """Restore the pedestrian walk time to its base value.

        Called after the extended walk phase completes.

        Args:
            phase: Signal phase number.
            base_walk_sec: Original base walk time to restore.

        Returns:
            True if acknowledged, False on error.
        """
        # TODO: SNMP SET phaseWalk.{phase} = base_walk_sec
        raise NotImplementedError

    async def get_controller_status(self) -> ControllerStatus:
        """Read overall controller status for health monitoring.

        Returns:
            ControllerStatus with mode, coordination_pattern, and comm_ok.
        """
        # TODO: SNMP GET unit control status and coordination pattern
        raise NotImplementedError

    async def snmp_get(self, oid: str) -> Any:
        """Execute an SNMP GET and return the value.

        Args:
            oid: The SNMP OID to read.

        Returns:
            The value returned by the SNMP agent.

        Raises:
            SNMPError: If the SNMP operation fails.
        """
        # TODO: Use pysnmp-lextudio hlapi async get_cmd
        raise NotImplementedError

    async def snmp_set(self, oid: str, value: int) -> bool:
        """Execute an SNMP SET with an integer value.

        Args:
            oid: The SNMP OID to write.
            value: Integer value to set.

        Returns:
            True if acknowledged, False on error.
        """
        # TODO: Use pysnmp-lextudio hlapi async set_cmd
        raise NotImplementedError
