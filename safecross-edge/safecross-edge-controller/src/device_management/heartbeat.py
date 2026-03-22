"""Periodic device heartbeat reporter to the SafeCross cloud API."""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import shutil
import time
from datetime import datetime, timezone
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

_SOFTWARE_VERSION = "0.1.0-dev"


class HeartbeatReporter:
    """Posts device health heartbeats to the cloud API.

    Args:
        config: Full intersection config dict.
        phase_manager: The ``PhaseManager`` instance (for state).
        reader_listener: The ``ReaderListener`` instance (for reader status).
        event_store: The ``EventStore`` instance (for pending event count).
    """

    def __init__(
        self,
        config: dict[str, Any],
        phase_manager: Any,
        reader_listener: Any,
        event_store: Any,
    ) -> None:
        self._config = config
        self._phase_manager = phase_manager
        self._reader_listener = reader_listener
        self._event_store = event_store

        cloud = config.get("cloud", {})
        self._api_url: str = cloud.get("api_url", "").rstrip("/")
        self._api_key: str = cloud.get("api_key", "")
        self._interval: int = cloud.get("heartbeat_interval_sec", 60)
        self._device_id: str = config.get("intersection_id", "unknown")
        self._boot_time: float = time.monotonic()

    async def run(self) -> None:
        """Background loop — posts heartbeat every *interval* seconds."""
        while True:
            await asyncio.sleep(self._interval)
            try:
                payload = await self._build_payload()
                await self._post(payload)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Heartbeat post failed (will retry): %s", exc)

    # ------------------------------------------------------------------
    # Payload
    # ------------------------------------------------------------------

    async def _build_payload(self) -> dict[str, Any]:
        uptime = time.monotonic() - self._boot_time

        pending = 0
        if self._event_store is not None:
            try:
                pending = await self._event_store.count_pending()
            except Exception:  # noqa: BLE001
                pass

        return {
            "device_id": self._device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_sec": round(uptime, 1),
            "software_version": _SOFTWARE_VERSION,
            "state_machine_state": (
                self._phase_manager.state.value
                if self._phase_manager is not None
                else "unknown"
            ),
            "reader_status": self._reader_status(),
            "signal_controller_reachable": self._controller_reachable(),
            "events_pending": pending,
            "system": self._system_metrics(),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _reader_status(self) -> str:
        if self._reader_listener is None:
            return "unknown"
        try:
            return "online" if self._reader_listener.reader_online else "offline"
        except Exception:  # noqa: BLE001
            return "unknown"

    def _controller_reachable(self) -> bool:
        if self._phase_manager is None:
            return False
        try:
            return self._phase_manager._snmp.is_reachable
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _system_metrics() -> dict[str, Any]:
        metrics: dict[str, Any] = {}

        # CPU temperature (Linux thermal zone)
        try:
            temp_path = "/sys/class/thermal/thermal_zone0/temp"
            if os.path.exists(temp_path):
                with open(temp_path) as f:
                    metrics["cpu_temp_c"] = int(f.read().strip()) / 1000.0
        except Exception:  # noqa: BLE001
            pass

        # Disk usage
        try:
            usage = shutil.disk_usage("/")
            metrics["disk_total_mb"] = usage.total // (1024 * 1024)
            metrics["disk_free_mb"] = usage.free // (1024 * 1024)
            metrics["disk_used_pct"] = round(
                (usage.used / usage.total) * 100, 1,
            )
        except Exception:  # noqa: BLE001
            pass

        # Memory (Linux /proc/meminfo)
        try:
            if os.path.exists("/proc/meminfo"):
                info: dict[str, int] = {}
                with open("/proc/meminfo") as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) >= 2:
                            info[parts[0].rstrip(":")] = int(parts[1])
                total = info.get("MemTotal", 0)
                avail = info.get("MemAvailable", 0)
                if total > 0:
                    metrics["mem_total_mb"] = total // 1024
                    metrics["mem_available_mb"] = avail // 1024
                    metrics["mem_used_pct"] = round(
                        ((total - avail) / total) * 100, 1,
                    )
        except Exception:  # noqa: BLE001
            pass

        return metrics

    # ------------------------------------------------------------------
    # Network
    # ------------------------------------------------------------------

    async def _post(self, payload: dict[str, Any]) -> None:
        url = f"{self._api_url}/v1/devices/{self._device_id}/heartbeat"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                logger.debug("Heartbeat posted (%d)", resp.status)
