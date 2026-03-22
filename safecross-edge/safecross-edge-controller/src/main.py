"""SafeCross Edge Controller — main orchestrator.

Wires together all subsystems and runs the async event loop:
  RS-485 reader → decision engine → SNMP signal control
  with local event logging, cloud forwarding, heartbeat, and OTA.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import os
import signal
import socket
import sys
import time
from typing import Any

# -- Project imports ---------------------------------------------------------

from src.device_management.config_manager import ConfigManager
from src.device_management.heartbeat import HeartbeatReporter
from src.device_management.ota import OTAChecker

from src.decision.cooldown import CooldownManager
from src.decision.timing import calculate_extension

from src.logging_events.event_store import EventStore
from src.logging_events.cloud_forwarder import CloudForwarder
from src.logging_events.models import EventType, TapEvent

from src.reader_interface.protocol import (
    CardTapEvent,
    EXTENSION_ELIGIBLE,
)
from src.reader_interface.rs485 import RS485Connection
from src.reader_interface.listener import ReaderListener

from src.signal_interface import safety
from src.signal_interface.phase_manager import PhaseManager, PhaseState
from src.signal_interface.snmp_client import SNMPClient

logger = logging.getLogger("safecross")

# ---------------------------------------------------------------------------
# Systemd helpers
# ---------------------------------------------------------------------------

def sd_notify(state: str) -> None:
    """Send a notification to systemd via ``$NOTIFY_SOCKET``."""
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return
    if addr.startswith("@"):
        addr = "\0" + addr[1:]
    try:
        sock = socket.socket(
            getattr(socket, "AF_UNIX", socket.AF_INET), socket.SOCK_DGRAM,
        )
        sock.sendto(state.encode(), addr)
        sock.close()
    except OSError as exc:
        logger.debug("sd_notify failed: %s", exc)


async def watchdog_loop() -> None:
    """Kick the systemd watchdog every 15 seconds."""
    while True:
        sd_notify("WATCHDOG=1")
        await asyncio.sleep(15)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SafeCross Edge Controller")
    parser.add_argument(
        "--config",
        default="/etc/safecross/intersection.json",
        help="Path to intersection config JSON",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG logging",
    )
    parser.add_argument(
        "--db-path",
        default="/var/lib/safecross/events.db",
        help="Path to the SQLite event database",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    """Initialise all components and run the event loop."""

    args = parse_args()

    # -- Logging -----------------------------------------------------------
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    logger.info("SafeCross Edge Controller starting")

    # -- Config ------------------------------------------------------------
    logger.info("Loading config from %s", args.config)
    config_mgr = ConfigManager(args.config)
    try:
        config = config_mgr.load()
    except (FileNotFoundError, ValueError) as exc:
        logger.critical("Config load failed: %s", exc)
        sys.exit(1)

    intersection_id: str = config["intersection_id"]
    logger.info("Intersection: %s", intersection_id)

    # -- Event store -------------------------------------------------------
    logger.info("Initialising event store at %s", args.db_path)
    event_store = EventStore(args.db_path)
    await event_store.init_db()

    # -- SNMP client -------------------------------------------------------
    sc = config["signal_controller"]
    snmp_client = SNMPClient(
        host=sc["ip_address"],
        port=sc["snmp_port"],
        community_read=sc["snmp_community_read"],
        community_write=sc["snmp_community_write"],
    )
    try:
        logger.info("Connecting to signal controller at %s:%d", sc["ip_address"], sc["snmp_port"])
        await snmp_client.connect()
    except Exception as exc:
        logger.error(
            "Signal controller connection failed: %s — will retry via phase manager",
            exc,
        )

    # -- Phase manager -----------------------------------------------------
    first_crossing = config["crossings"][0]
    phase_config: dict[str, Any] = {
        "max_walk_time_sec": first_crossing["base_walk_sec"] + first_crossing["max_extension_sec"],
        "min_extension_sec": first_crossing["min_extension_sec"],
        "max_extension_sec": first_crossing["max_extension_sec"],
        "cooldown_sec": config["timing_rules"]["cooldown_sec"],
    }
    phase_manager = PhaseManager(snmp_client, phase_config)
    logger.info("Phase manager initialised (state=%s)", phase_manager.state.value)

    # -- Cooldown manager --------------------------------------------------
    cooldown_config: dict[str, Any] = {
        "cooldown_sec": config["timing_rules"]["cooldown_sec"],
        "dedup_window_sec": 10,
        "max_extensions_per_hour": 20,
    }
    cooldown_mgr = CooldownManager(cooldown_config)

    # -- Timing config (for calculate_extension) ---------------------------
    timing_config: dict[str, Any] = {
        "senior_walk_speed_ft_per_sec": 3.0,
        "disabled_walk_speed_ft_per_sec": 2.5,
        "min_extension_sec": first_crossing["min_extension_sec"],
        "max_extension_sec": first_crossing["max_extension_sec"],
    }

    # -- RS-485 reader connection ------------------------------------------
    reader_cfg = config["nfc_reader"]
    rs485 = RS485Connection(reader_cfg["serial_port"], reader_cfg["baud_rate"])
    try:
        logger.info("Opening RS-485 on %s @ %d baud", reader_cfg["serial_port"], reader_cfg["baud_rate"])
        await rs485.open()
    except Exception as exc:
        logger.error("RS-485 open failed: %s — listener will retry", exc)

    # -- Card tap callback -------------------------------------------------
    async def on_card_tap(event: CardTapEvent) -> None:
        uid_hash = hashlib.sha256(event.uid).hexdigest()
        logger.info(
            "Card tap: type=0x%02X uid_hash=%s",
            event.card_type, uid_hash[:12],
        )

        crosswalk = config["crossings"][0]
        phase = crosswalk["signal_phase"]
        now = time.monotonic()

        # Eligibility check
        if event.card_type not in EXTENSION_ELIGIBLE:
            logger.info("Card type 0x%02X not eligible for extension", event.card_type)
            await event_store.store(TapEvent(
                intersection_id=intersection_id,
                event_type=EventType.EXTENSION_DENIED,
                card_type=event.card_type,
                card_uid_hash=uid_hash,
                denial_reason="not_eligible",
                phase_number=phase,
                read_method=event.read_method,
            ))
            return

        # Cooldown / dedup / rate limit
        allowed, denial_reason = cooldown_mgr.can_extend(
            intersection_id, uid_hash, now,
        )
        if not allowed:
            logger.info("Extension denied: %s", denial_reason)
            await event_store.store(TapEvent(
                intersection_id=intersection_id,
                event_type=EventType.EXTENSION_DENIED,
                card_type=event.card_type,
                card_uid_hash=uid_hash,
                denial_reason=denial_reason,
                phase_number=phase,
                read_method=event.read_method,
            ))
            return

        # Calculate extension
        extension_sec = calculate_extension(
            event.card_type,
            crosswalk["width_ft"],
            crosswalk["base_walk_sec"],
            timing_config,
        )
        if extension_sec == 0:
            logger.info("No extension needed (base time sufficient)")
            return

        # Request extension
        logger.info(
            "Requesting %ds extension for phase %d", extension_sec, phase,
        )
        success = await phase_manager.process_tap(phase, extension_sec)

        # Record
        cooldown_mgr.record_extension(intersection_id, uid_hash, now)
        await event_store.store(TapEvent(
            intersection_id=intersection_id,
            event_type=(
                EventType.EXTENSION_GRANTED if success
                else EventType.EXTENSION_DENIED
            ),
            card_type=event.card_type,
            card_uid_hash=uid_hash,
            extension_seconds=extension_sec if success else 0,
            denial_reason=None if success else "phase_manager_rejected",
            phase_number=phase,
            read_method=event.read_method,
        ))

        if success:
            logger.info("Extension granted: %ds on phase %d", extension_sec, phase)
        else:
            logger.info("Extension denied by phase manager for phase %d", phase)

    # -- Listener ----------------------------------------------------------
    listener = ReaderListener(rs485, on_card_tap=on_card_tap)
    logger.info("Reader listener created")

    # -- Cloud forwarder ---------------------------------------------------
    cloud_config: dict[str, Any] = {
        "api_url": config["cloud"]["api_url"],
        "api_key": config["cloud"].get("api_key", ""),
    }
    cloud_forwarder = CloudForwarder(event_store, cloud_config)

    # -- Heartbeat ---------------------------------------------------------
    heartbeat = HeartbeatReporter(config, phase_manager, listener, event_store)

    # -- OTA ---------------------------------------------------------------
    ota = OTAChecker(config)

    # -- SIGHUP handler (config hot-reload) --------------------------------
    def _sighup_handler() -> None:
        logger.info("SIGHUP received — reloading config")
        try:
            config_mgr.reload()
        except Exception as exc:
            logger.error("Config reload failed: %s", exc)

    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGHUP, _sighup_handler)

    # -- Gather background tasks -------------------------------------------
    tasks: list[asyncio.Task[None]] = []

    async def _start_tasks() -> None:
        # rs485._read_loop is auto-started by open(), no task needed here
        tasks.extend([
            asyncio.create_task(listener.run(), name="listener"),
            asyncio.create_task(phase_manager.monitor_loop(), name="phase_monitor"),
            asyncio.create_task(cloud_forwarder.run(), name="cloud_forwarder"),
            asyncio.create_task(heartbeat.run(), name="heartbeat"),
            asyncio.create_task(ota.run(), name="ota"),
            asyncio.create_task(watchdog_loop(), name="watchdog"),
        ])

    await _start_tasks()
    sd_notify("READY=1")
    logger.info("All subsystems started — serving")

    # -- Shutdown handler --------------------------------------------------
    shutdown_event = asyncio.Event()

    def _shutdown_signal() -> None:
        logger.info("Shutdown requested, cleaning up...")
        shutdown_event.set()

    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _shutdown_signal)
    else:
        # On Windows, Ctrl+C raises KeyboardInterrupt
        pass

    try:
        await shutdown_event.wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Interrupted, shutting down...")

    # -- Graceful shutdown -------------------------------------------------

    # Wait for active extension to finish
    if phase_manager.state in (
        PhaseState.EXTENSION_REQUESTED,
        PhaseState.WALK_EXTENDED,
        PhaseState.RESTORING,
    ):
        logger.warning("Extension in progress, waiting for restoration...")
        deadline = time.monotonic() + 30
        while (
            phase_manager.state not in (PhaseState.IDLE, PhaseState.COOLDOWN)
            and time.monotonic() < deadline
        ):
            await asyncio.sleep(0.5)
        if phase_manager.state not in (PhaseState.IDLE, PhaseState.COOLDOWN):
            logger.warning("Timed out waiting for extension restoration")

    # Cancel all background tasks
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    # Close resources
    try:
        await rs485.close()
    except Exception:
        pass
    try:
        await snmp_client.close()
    except Exception:
        pass
    try:
        await event_store.close()
    except Exception:
        pass

    logger.info("Shutdown complete")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(main())
