"""Over-the-air firmware update client.

Periodically checks for new firmware versions, downloads and verifies
update packages, and optionally applies them with rollback support.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .config_manager import OTAConfig

logger = logging.getLogger(__name__)

# Current software version
CURRENT_VERSION = "1.0.0"

# Paths for OTA operations
UPDATE_DOWNLOAD_DIR = "/tmp/safecross-update"
INSTALL_DIR = "/opt/safecross"
BACKUP_DIR = "/opt/safecross.bak"


@dataclass
class OTAManifest:
    """OTA update manifest from the cloud API.

    Attributes:
        latest_version: Available version string.
        download_url: URL to download the update tarball.
        sha256: Expected SHA-256 checksum of the tarball.
        release_notes: Human-readable release notes.
        min_current_version: Minimum current version required to apply.
    """

    latest_version: str
    download_url: str
    sha256: str
    release_notes: str
    min_current_version: str


class OTAUpdater:
    """Over-the-air update client for the edge controller.

    Update flow:
    1. GET OTA manifest from cloud API (daily by default)
    2. Compare latest_version > current AND current >= min_current_version
    3. Download tarball, verify SHA-256 checksum
    4. If auto_apply: backup current, extract, restart service
    5. If not auto_apply: log availability, report in heartbeat
    6. Rollback: if new version fails to start (3 failures in 60s),
       systemd OnFailure handler restores backup

    Attributes:
        config: OTA configuration from intersection config.
    """

    def __init__(self, config: OTAConfig) -> None:
        """Initialize the OTA updater.

        Args:
            config: OTA configuration settings.
        """
        self.config = config
        self._last_check_time: float = 0.0
        self._update_available: Optional[OTAManifest] = None

    async def maybe_check(self) -> None:
        """Check for updates if the check interval has elapsed.

        Called by the main loop on every iteration. Fetches the OTA
        manifest if check_interval_sec has passed since the last check.
        """
        # TODO: Check if check_interval_sec has elapsed
        # TODO: GET manifest from config.manifest_url
        # TODO: Compare versions
        # TODO: If auto_apply, trigger download + apply
        raise NotImplementedError

    async def _fetch_manifest(self) -> Optional[OTAManifest]:
        """Fetch the OTA manifest from the cloud API.

        Returns:
            OTAManifest if successfully fetched, None on error.
        """
        # TODO: GET {manifest_url}, parse JSON into OTAManifest
        raise NotImplementedError

    async def _download(self, manifest: OTAManifest) -> Optional[str]:
        """Download the update tarball to the staging directory.

        Args:
            manifest: OTA manifest with download URL.

        Returns:
            Path to the downloaded file, or None on error.
        """
        # TODO: Download tarball to UPDATE_DOWNLOAD_DIR
        # TODO: Return file path
        raise NotImplementedError

    def _verify(self, file_path: str, expected_sha256: str) -> bool:
        """Verify SHA-256 checksum of a downloaded file.

        Args:
            file_path: Path to the downloaded tarball.
            expected_sha256: Expected SHA-256 hex digest.

        Returns:
            True if checksum matches, False otherwise.
        """
        # TODO: Compute SHA-256 of file, compare to expected
        raise NotImplementedError

    async def _apply(self, file_path: str) -> bool:
        """Apply the update: backup current, extract new, restart service.

        Args:
            file_path: Path to the verified update tarball.

        Returns:
            True if update was applied successfully.
        """
        # TODO: Backup current install to BACKUP_DIR
        # TODO: Extract tarball to INSTALL_DIR
        # TODO: Restart systemd service
        raise NotImplementedError

    def _backup(self) -> bool:
        """Backup the current installation for rollback.

        Copies INSTALL_DIR to BACKUP_DIR.

        Returns:
            True if backup was successful.
        """
        # TODO: Copy /opt/safecross/ to /opt/safecross.bak/
        raise NotImplementedError

    @staticmethod
    def _version_compare(v1: str, v2: str) -> int:
        """Compare two semantic version strings.

        Args:
            v1: First version string (e.g., '1.2.3').
            v2: Second version string (e.g., '1.3.0').

        Returns:
            -1 if v1 < v2, 0 if equal, 1 if v1 > v2.
        """
        # TODO: Parse and compare semantic version components
        raise NotImplementedError

    @property
    def update_available(self) -> Optional[OTAManifest]:
        """Return the pending update manifest, if any."""
        return self._update_available
