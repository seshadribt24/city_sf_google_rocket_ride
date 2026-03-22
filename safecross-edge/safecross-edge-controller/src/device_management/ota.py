"""Over-the-air update checker — downloads and stages updates without restarting."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

_STAGING_DIR = "/opt/safecross-staging"
_DOWNLOAD_DIR = "/tmp/safecross-update"


class OTAChecker:
    """Periodically checks for and stages OTA updates.

    Updates are downloaded and verified but **never auto-applied**.
    An operator or separate process must restart the service to apply.

    Args:
        config: Full intersection config dict.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        ota = config.get("ota", {})
        cloud = config.get("cloud", {})
        self._device_id: str = config.get("intersection_id", "unknown")
        self._api_url: str = cloud.get("api_url", "").rstrip("/")
        self._api_key: str = cloud.get("api_key", "")
        self._base_interval: int = ota.get("check_interval_sec", 21600)  # 6 hours
        self._auto_apply: bool = ota.get("auto_apply", False)

        # Deterministic jitter: hash device_id mod 3600 → 0-60 min offset
        jitter_hash = int(hashlib.sha256(self._device_id.encode()).hexdigest(), 16)
        self._jitter_sec: int = jitter_hash % 3600

    @property
    def interval_sec(self) -> int:
        """Effective check interval including per-device jitter."""
        return self._base_interval + self._jitter_sec

    async def run(self) -> None:
        """Background loop — checks for updates on a jittered schedule."""
        while True:
            await asyncio.sleep(self.interval_sec)
            try:
                await self._check_and_stage()
            except Exception as exc:  # noqa: BLE001
                logger.warning("OTA check failed: %s", exc)

    async def _check_and_stage(self) -> None:
        update = await self._fetch_update_info()
        if update is None:
            logger.debug("No update available")
            return

        version = update["version"]
        sha256 = update["sha256"]
        download_url = update["download_url"]
        release_notes = update.get("release_notes", "")

        logger.info(
            "Update available: v%s — %s", version, release_notes,
        )

        local_path = await self._download(download_url, version)
        if not self._verify_hash(local_path, sha256):
            logger.error(
                "SHA-256 mismatch for v%s — discarding download", version,
            )
            os.remove(local_path)
            return

        self._extract(local_path, version)
        logger.info(
            "Update v%s staged at %s. Restart service to apply.",
            version, _STAGING_DIR,
        )

    async def _fetch_update_info(self) -> dict[str, Any] | None:
        """GET the update manifest for this device."""
        url = f"{self._api_url}/v1/devices/{self._device_id}/updates"
        headers: dict[str, str] = {}
        if self._api_key:
            headers["X-API-Key"] = self._api_key

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 204 or resp.status == 404:
                    return None
                resp.raise_for_status()
                data = await resp.json()
                if not data.get("update_available", False):
                    return None
                return data

    async def _download(self, url: str, version: str) -> str:
        """Download the update archive to a temp location."""
        os.makedirs(_DOWNLOAD_DIR, exist_ok=True)
        dest = os.path.join(_DOWNLOAD_DIR, f"safecross-{version}.tar.gz")

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                with open(dest, "wb") as f:
                    async for chunk in resp.content.iter_chunked(8192):
                        f.write(chunk)

        logger.info("Downloaded update v%s to %s", version, dest)
        return dest

    @staticmethod
    def _verify_hash(path: str, expected_sha256: str) -> bool:
        """Verify the SHA-256 hash of a downloaded file."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        actual = h.hexdigest()
        if actual != expected_sha256:
            logger.error(
                "Hash mismatch: expected %s, got %s", expected_sha256, actual,
            )
            return False
        return True

    @staticmethod
    def _extract(archive_path: str, version: str) -> None:
        """Extract the update tarball into the staging directory."""
        staging = os.path.join(_STAGING_DIR, version)
        if os.path.exists(staging):
            shutil.rmtree(staging)
        os.makedirs(staging, exist_ok=True)

        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(path=staging)  # noqa: S202

        logger.info("Extracted update v%s to %s", version, staging)
