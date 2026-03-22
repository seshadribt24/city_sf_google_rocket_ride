"""Health monitor — heartbeat and self-diagnostics.

Runs periodic health checks on all subsystems and sends heartbeat
reports to the cloud API. Monitors reader communication, signal
controller connectivity, disk usage, event backlog, and temperature.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .cloud_reporter import CloudReporter
    from .config_manager import IntersectionConfig
    from .event_logger import EventLogger
    from .ntcip_client import NTCIPClient
    from .rs485_listener import RS485Listener

logger = logging.getLogger(__name__)

# Alert thresholds
READER_OFFLINE_ALERT_SEC = 300  # 5 minutes
SIGNAL_UNREACHABLE_ALERT_SEC = 120  # 2 minutes
DISK_USAGE_ALERT_PERCENT = 90
EVENT_BACKLOG_ALERT_COUNT = 1000
TEMPERATURE_WARN_C = 65.0
TEMPERATURE_ALERT_C = 70.0


class HealthMonitor:
    """Periodic health checks and heartbeat reporting.

    Checks are run every heartbeat_interval_sec (default 300s):
    1. Reader communication (heartbeat within 30s)
    2. Signal controller SNMP connectivity
    3. Disk usage (eMMC < 90%)
    4. Event backlog (< 1000 unreported)
    5. SBC temperature (< 65C warn, < 70C alert)

    Attributes:
        config: Full intersection configuration.
        ntcip: NTCIP client for signal controller checks.
        rs485: RS-485 listener for reader status.
        db: Event logger for backlog checks.
    """

    def __init__(
        self,
        config: IntersectionConfig,
        ntcip: NTCIPClient,
        rs485: RS485Listener,
        db: EventLogger,
    ) -> None:
        """Initialize the health monitor.

        Args:
            config: Full intersection configuration.
            ntcip: NTCIP client instance.
            rs485: RS-485 listener instance.
            db: Event logger instance.
        """
        self.config = config
        self.ntcip = ntcip
        self.rs485 = rs485
        self.db = db
        self._last_heartbeat_time: float = 0.0
        self._reader_status: str = "unknown"
        self._signal_status: str = "unknown"

    async def maybe_send_heartbeat(self) -> None:
        """Send a heartbeat if the interval has elapsed.

        Called by the main loop on every iteration. Runs all health
        checks and sends a heartbeat to the cloud if the configured
        interval has passed.
        """
        # TODO: Check if heartbeat_interval_sec has elapsed
        # TODO: Run all health checks
        # TODO: Send heartbeat via cloud reporter
        raise NotImplementedError

    async def check_reader(self) -> str:
        """Check NFC reader communication status.

        Returns 'ok' if a heartbeat was received within the last 30
        seconds, 'offline' otherwise.

        Returns:
            Reader status string.
        """
        # TODO: Check rs485.last_heartbeat_time
        raise NotImplementedError

    async def check_signal_controller(self) -> str:
        """Check signal controller SNMP connectivity.

        Performs an SNMP GET on the controller status OID.

        Returns:
            Controller status string ('auto', 'manual', 'flash', 'unreachable').
        """
        # TODO: SNMP GET controller status via ntcip
        raise NotImplementedError

    async def check_disk(self) -> bool:
        """Check if eMMC storage is below 90% capacity.

        Returns:
            True if disk usage is acceptable, False if above threshold.
        """
        # TODO: Read disk usage, trigger early cleanup if > 90%
        raise NotImplementedError

    async def check_backlog(self) -> bool:
        """Check if event backlog exceeds threshold.

        Returns:
            True if backlog is acceptable (< 1000), False otherwise.
        """
        # TODO: Query db.get_unreported_count()
        raise NotImplementedError

    async def check_temperature(self) -> Optional[float]:
        """Read SBC die temperature.

        Reads from /sys/class/thermal/thermal_zone0/temp on Linux.

        Returns:
            Temperature in degrees Celsius, or None if unavailable.
        """
        # TODO: Read thermal zone sysfs file
        # TODO: Log warning if > 65C, error if > 70C
        raise NotImplementedError
