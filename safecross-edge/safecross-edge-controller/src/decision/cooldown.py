"""Cooldown, deduplication, and rate-limiting for extension requests."""

from __future__ import annotations

from typing import Any


class CooldownManager:
    """Tracks per-intersection cooldowns, duplicate UIDs, and hourly caps.

    All time values use ``time.monotonic``-style floats passed in by the
    caller (for testability).

    Args:
        config: Dict with keys ``cooldown_sec``, ``dedup_window_sec``,
            ``max_extensions_per_hour``.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._cooldown_sec: float = config["cooldown_sec"]
        self._dedup_window_sec: float = config["dedup_window_sec"]
        self._max_per_hour: int = config["max_extensions_per_hour"]

        self._last_extension_time: dict[str, float] = {}
        self._recent_uids: dict[str, list[tuple[str, float]]] = {}
        self._hourly_counts: dict[str, list[float]] = {}

    def can_extend(
        self,
        intersection_id: str,
        card_uid_hash: str,
        now: float,
    ) -> tuple[bool, str | None]:
        """Check whether an extension is permitted.

        Returns ``(True, None)`` if allowed, or ``(False, reason)`` if
        blocked by dedup / cooldown / rate limit.
        """
        # 1. Dedup: same UID within dedup window
        uid_list = self._recent_uids.get(intersection_id, [])
        for uid, ts in uid_list:
            if uid == card_uid_hash and now - ts < self._dedup_window_sec:
                return False, "duplicate_card"

        # 2. Cooldown: last extension too recent
        last = self._last_extension_time.get(intersection_id)
        if last is not None and now - last < self._cooldown_sec:
            return False, "cooldown_active"

        # 3. Hourly rate limit
        hour_list = self._hourly_counts.get(intersection_id, [])
        recent = [t for t in hour_list if now - t < 3600.0]
        if len(recent) >= self._max_per_hour:
            return False, "hourly_rate_limit"

        return True, None

    def record_extension(
        self,
        intersection_id: str,
        card_uid_hash: str,
        now: float,
    ) -> None:
        """Record a granted extension and prune stale entries."""
        self._last_extension_time[intersection_id] = now

        # Recent UIDs — add and prune
        uid_list = self._recent_uids.setdefault(intersection_id, [])
        uid_list.append((card_uid_hash, now))
        self._recent_uids[intersection_id] = [
            (u, t) for u, t in uid_list if now - t < self._dedup_window_sec
        ]

        # Hourly counts — add and prune
        hour_list = self._hourly_counts.setdefault(intersection_id, [])
        hour_list.append(now)
        self._hourly_counts[intersection_id] = [
            t for t in hour_list if now - t < 3600.0
        ]

    def reset(self, intersection_id: str) -> None:
        """Clear all state for an intersection."""
        self._last_extension_time.pop(intersection_id, None)
        self._recent_uids.pop(intersection_id, None)
        self._hourly_counts.pop(intersection_id, None)
