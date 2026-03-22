"""Safety validation for signal controller SNMP writes.

Pure validation module — no side effects, no I/O, no state mutation.
Every public function takes inputs and returns a result tuple.

This is the last line of defence before any value is written to the
traffic signal controller.  All rules are deliberately conservative:
a false rejection is always safer than a false acceptance.
"""

from __future__ import annotations

from typing import Any

# Only these OID names may ever be the target of an SNMP SET.
WRITABLE_OID_ALLOWLIST: set[str] = {"PED_WALK_TIME", "PED_CALL"}


def check_safety(
    oid_name: str,
    proposed_value: int,
    current_value: int,
    baseline_value: int,
    config: dict[str, Any],
    preemption_active: bool,
    last_write_timestamp: float | None,
    now: float | None = None,
    cycle_length_sec: float = 90.0,
) -> tuple[bool, str]:
    """Validate a proposed SNMP SET against all safety rules.

    Rules are checked in order; the first failure short-circuits.

    1. *oid_name* must be in :data:`WRITABLE_OID_ALLOWLIST`.
    2. *preemption_active* must be ``False``.
    3. *proposed_value* must be ``>=`` *baseline_value*
       (never shorten the walk phase below its original duration).
    4. *proposed_value* must be ``<=`` ``config["max_walk_time_sec"]``.
    5. Rate limit: if *last_write_timestamp* is not ``None``, the
       elapsed time since the last write must be at least
       ``cycle_length_sec * 0.8``.

    Args:
        oid_name: Logical OID name (e.g. ``"PED_WALK_TIME"``).
        proposed_value: Integer value to be written.
        current_value: Current value read from the controller.
        baseline_value: Original/default value from config.
        config: Timing section of the intersection config.  Must
            contain ``"max_walk_time_sec"``.
        preemption_active: Whether emergency preemption is active.
        last_write_timestamp: ``time.monotonic()`` of the last SET,
            or ``None`` if no prior write this session.
        now: Current ``time.monotonic()`` value.  If ``None`` the
            caller must not be using the rate-limit check (provided
            for testability so callers can inject a clock).
        cycle_length_sec: Typical signal cycle length in seconds
            (default 90).

    Returns:
        ``(True, "ok")`` if the write is allowed, or
        ``(False, reason_string)`` on the first rule violation.
    """
    # 1. OID allowlist
    if oid_name not in WRITABLE_OID_ALLOWLIST:
        return False, f"oid_not_in_allowlist: {oid_name}"

    # 2. Preemption
    if preemption_active:
        return False, "preemption_active"

    # 3. Never decrease below baseline
    if proposed_value < baseline_value:
        return False, f"below_baseline: proposed={proposed_value} baseline={baseline_value}"

    # 4. Absolute maximum
    max_walk = config["max_walk_time_sec"]
    if proposed_value > max_walk:
        return False, f"exceeds_max: proposed={proposed_value} max={max_walk}"

    # 5. Rate limit
    if last_write_timestamp is not None and now is not None:
        min_interval = cycle_length_sec * 0.8
        elapsed = now - last_write_timestamp
        if elapsed < min_interval:
            return False, f"rate_limited: {elapsed:.1f}s < {min_interval:.1f}s"

    return True, "ok"


def validate_extension_request(
    extension_sec: int,
    baseline_walk_sec: int,
    config: dict[str, Any],
) -> tuple[int, list[str]]:
    """Clamp an extension request to configured safety bounds.

    Args:
        extension_sec: Requested extension in seconds.
        baseline_walk_sec: Base walk time from intersection config.
        config: Timing section; must contain ``"min_extension_sec"``,
            ``"max_extension_sec"``, and ``"max_walk_time_sec"``.

    Returns:
        ``(clamped_extension, warnings)`` where *clamped_extension*
        is the safe value and *warnings* lists any adjustments made.
    """
    warnings: list[str] = []

    # Non-positive → nothing to do
    if extension_sec <= 0:
        return 0, ["no_extension_needed"]

    clamped = extension_sec

    # Floor
    min_ext = config["min_extension_sec"]
    if clamped < min_ext:
        clamped = min_ext
        warnings.append("clamped_to_minimum")

    # Ceiling
    max_ext = config["max_extension_sec"]
    if clamped > max_ext:
        clamped = max_ext
        warnings.append("clamped_to_maximum")

    # Absolute maximum (baseline + extension must not exceed cap)
    max_walk = config["max_walk_time_sec"]
    if baseline_walk_sec + clamped > max_walk:
        clamped = max_walk - baseline_walk_sec
        if clamped < 0:
            clamped = 0
        warnings.append("clamped_to_absolute_max")

    return clamped, warnings
