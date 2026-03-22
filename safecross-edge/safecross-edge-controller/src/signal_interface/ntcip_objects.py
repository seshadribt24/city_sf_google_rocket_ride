"""NTCIP 1202 OID constants and helpers for traffic signal controllers.

All OIDs reference the NTCIP 1202 v02 standard.  The base enterprise
prefix is ``1.3.6.1.4.1.1206.4.2.1`` (ntcipSignalControl).

Per-intersection OID overrides are supported via the optional
``oid_overrides`` dict in the signal controller config, allowing
non-standard MIB layouts to be accommodated without code changes.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Phase status group — read current phase state
# NTCIP 1202 §5.4  phaseStatusTable
# Read-only — OctetString bitmap (1 byte per group of 8 phases)
# Bit N set = phase N+1 is in the corresponding state
# ---------------------------------------------------------------------------

# phaseStatusGroupPhaseOn — bitmap of phases currently active (green/walk)
# Value: OctetString; each bit = one phase (bit 0 = phase 1)
PHASE_STATUS_GROUP: str = "1.3.6.1.4.1.1206.4.2.1.1.4.1.2"

# ---------------------------------------------------------------------------
# Pedestrian phase status
# NTCIP 1202 §5.4  phaseStatusTable
# Read-only — OctetString bitmap
# ---------------------------------------------------------------------------

# phaseStatusGroupPedPhase — bitmap of ped phases currently active
# Value: OctetString; bit N = ped phase N+1 active
PED_PHASE_STATUS: str = "1.3.6.1.4.1.1206.4.2.1.1.4.1.4"

# ---------------------------------------------------------------------------
# Pedestrian timing parameters (per phase)
# NTCIP 1202 §5.2  phaseTable
# Read-write — INTEGER (seconds)
# ---------------------------------------------------------------------------

# phaseWalk — pedestrian walk interval duration
# Value: INTEGER (0..255), seconds
# Setting this extends or shortens the walk phase for the given phase
PED_WALK_TIME: str = "1.3.6.1.4.1.1206.4.2.1.1.2.1.7"

# phasePedClear — pedestrian clearance (flashing don't walk) duration
# Value: INTEGER (0..255), seconds
PED_CLEAR_TIME: str = "1.3.6.1.4.1.1206.4.2.1.1.2.1.8"

# ---------------------------------------------------------------------------
# Pedestrian call control
# NTCIP 1202 §5.6  phaseControlTable
# Read-write — INTEGER (bitmap)
# ---------------------------------------------------------------------------

# phaseControlPedOmit / phasePedCall — place a pedestrian call
# Writing the appropriate bit is equivalent to pressing the ped button
# Value: INTEGER (bitmap, set bit N for phase N)
PED_CALL: str = "1.3.6.1.4.1.1206.4.2.1.1.6.1.8"

# ---------------------------------------------------------------------------
# Preemption status
# NTCIP 1202 §5.14  preemptTable
# Read-only — INTEGER
# ---------------------------------------------------------------------------

# preemptStatus — current preemption state per preempt number
# Value: INTEGER; 0 = not active, >0 = active preemption
# When any preempt is active, ped extensions must be blocked
PREEMPT_STATUS: str = "1.3.6.1.4.1.1206.4.2.1.6.5.1.2"

# ---------------------------------------------------------------------------
# Controller identification (scalar OIDs)
# NTCIP 1202 §5.1
# Read-only — DisplayString / OctetString
# ---------------------------------------------------------------------------

# moduleDescription — human-readable controller description
# Value: DisplayString (up to 255 chars)
CONTROLLER_DESCRIPTION: str = "1.3.6.1.4.1.1206.4.2.1.1.1.0"

# moduleVersion — firmware / software version string
# Value: DisplayString
CONTROLLER_VERSION: str = "1.3.6.1.4.1.1206.4.2.1.1.3.0"


# ---------------------------------------------------------------------------
# Mapping of logical names → default OIDs (used by get_oid_with_overrides)
# ---------------------------------------------------------------------------

_DEFAULT_OIDS: dict[str, str] = {
    "PHASE_STATUS_GROUP": PHASE_STATUS_GROUP,
    "PED_PHASE_STATUS": PED_PHASE_STATUS,
    "PED_WALK_TIME": PED_WALK_TIME,
    "PED_CLEAR_TIME": PED_CLEAR_TIME,
    "PED_CALL": PED_CALL,
    "PREEMPT_STATUS": PREEMPT_STATUS,
    "CONTROLLER_DESCRIPTION": CONTROLLER_DESCRIPTION,
    "CONTROLLER_VERSION": CONTROLLER_VERSION,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_oid(base_oid: str, phase: int) -> str:
    """Append a phase number as a sub-OID index.

    Args:
        base_oid: The table-row OID prefix (e.g. ``PED_WALK_TIME``).
        phase: 1-based signal phase number.

    Returns:
        ``"{base_oid}.{phase}"``
    """
    return f"{base_oid}.{phase}"


def get_oid_with_overrides(name: str, phase: int, config: dict[str, Any]) -> str:
    """Resolve an OID by logical *name*, applying per-intersection overrides.

    Checks ``config["signal_controller"]["oid_overrides"]`` for a key
    matching *name*.  If found the override value is used as the base OID;
    otherwise the built-in default is used.  The *phase* index is appended
    in either case.

    Args:
        name: Logical OID name (e.g. ``"PED_WALK_TIME"``).
        phase: 1-based signal phase number.
        config: Full intersection config dict.

    Returns:
        Fully-qualified OID string with phase suffix.

    Raises:
        KeyError: If *name* is not a recognised OID name and no override
            is provided.
    """
    overrides: dict[str, str] = (
        config.get("signal_controller", {}).get("oid_overrides", {})
    )
    base = overrides.get(name, _DEFAULT_OIDS[name])
    return f"{base}.{phase}"
