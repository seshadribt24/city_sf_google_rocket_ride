# SafeCross Edge Controller — Claude Code Spec

## What you are building

The edge controller software for SafeCross — a DIN-rail-mounted ARM single-board computer that lives inside a traffic signal cabinet. It receives card classification events from the NFC reader (Layer 1) over RS-485, decides whether and how long to extend the pedestrian walk phase, sends NTCIP/SNMP commands to the existing traffic signal controller to execute that extension, logs every event, and reports to a cloud backend.

This is the most safety-critical and protocol-intensive component in the system. It is the only device that communicates directly with the traffic signal controller.

## Target hardware

- **SBC:** Industrial DIN-rail ARM board (e.g., Axiomtek IFB122 or equivalent)
  - ARM Cortex-A7+, ~500 MHz, 256MB+ RAM, 4GB+ eMMC
  - Running embedded Linux (Debian-based or Yocto — assume Debian 12 minimal for this spec)
  - 2x RS-232/485 serial ports
  - 1x Ethernet (10/100 Mbps)
  - USB port (for Phase 2 thermal sensor — not used in this spec)
  - Operating range: -40°C to +70°C
  - DIN-rail mounted inside traffic signal cabinet
  - Powered by 12/24VDC DIN-rail power supply from cabinet 120VAC

- **Connections:**
  - RS-485 Port 1 (input): Connected to NFC reader on the signal pole
  - Ethernet (output 1): Connected to traffic signal controller (NTCIP/SNMP)
  - Ethernet or LTE Cat-M1 modem (output 2): Connected to cloud backend
  - The signal controller's IP address is configured per intersection (see config file)

## Project structure

Create the following file structure:

```
safecross-edge-controller/
├── README.md                          # Setup, deployment, config guide
├── requirements.txt                   # Python dependencies
├── pyproject.toml                     # Project metadata and build config
├── config/
│   └── intersection.example.json      # Example per-intersection config
├── src/
│   ├── main.py                        # Entry point, service lifecycle
│   ├── rs485_listener.py              # Serial listener for NFC reader messages
│   ├── message_protocol.py            # Parse/build RS-485 message frames
│   ├── classifier_filter.py           # Validate and filter tap events
│   ├── timing_engine.py               # Decide extension duration
│   ├── ntcip_client.py                # SNMP client for signal controller
│   ├── signal_state.py                # Signal controller state machine
│   ├── event_logger.py                # Local SQLite event store
│   ├── cloud_reporter.py              # Forward events to cloud API
│   ├── config_manager.py              # Load/validate/update intersection config
│   ├── health_monitor.py              # Heartbeat, self-diagnostics, alerting
│   └── ota_updater.py                 # Over-the-air firmware update client
├── scripts/
│   ├── install.sh                     # Install dependencies, create systemd service
│   ├── safecross-edge.service         # systemd unit file
│   └── logrotate.conf                 # Log rotation config
├── tests/
│   ├── test_message_protocol.py       # Frame parsing + CRC tests
│   ├── test_timing_engine.py          # Extension duration logic tests
│   ├── test_signal_state.py           # State machine transition tests
│   ├── test_ntcip_client.py           # SNMP command construction tests (mocked)
│   ├── test_classifier_filter.py      # Tap validation + dedup tests
│   └── conftest.py                    # Shared fixtures
└── docs/
    ├── NTCIP_INTEGRATION.md           # Signal controller integration notes
    └── RS485_PROTOCOL.md              # Link to/copy of Layer 1 protocol spec
```

## Language and dependencies

- **Python 3.11+** (available on Debian 12)
- Key libraries:
  - `pysnmp-lextudio` (v6+) — SNMP v2c client for NTCIP communication
  - `pyserial` — RS-485 serial communication
  - `aiohttp` — async HTTP client for cloud API reporting
  - `aiosqlite` — async SQLite for local event buffer
  - `pydantic` — config validation and message models
- Use `asyncio` for the main event loop — the system needs to concurrently:
  - Listen for RS-485 messages from the reader
  - Manage SNMP sessions with the signal controller
  - Forward events to the cloud
  - Send periodic heartbeats
  - Check for OTA updates
- Do NOT use threads except for the RS-485 serial listener (pyserial is synchronous — wrap it in a thread that posts to an asyncio queue)

## Per-intersection configuration

Each edge controller is configured with a JSON file specifying the intersection's physical characteristics and operational parameters. This file is loaded at startup and can be updated via the cloud API.

```json
{
  "intersection_id": "INT-2025-0042",
  "location": {
    "name": "Market St & 5th St",
    "latitude": 37.7837,
    "longitude": -122.4073
  },
  "crossings": [
    {
      "crossing_id": "NS",
      "description": "North-south crosswalk (Market St)",
      "width_ft": 72,
      "signal_phase": 4,
      "base_walk_sec": 7,
      "base_clearance_sec": 18,
      "max_extension_sec": 13,
      "min_extension_sec": 6,
      "ped_detector_phase_bit": 4
    },
    {
      "crossing_id": "EW",
      "description": "East-west crosswalk (5th St)",
      "width_ft": 48,
      "signal_phase": 8,
      "base_walk_sec": 7,
      "base_clearance_sec": 12,
      "max_extension_sec": 8,
      "min_extension_sec": 4,
      "ped_detector_phase_bit": 8
    }
  ],
  "signal_controller": {
    "ip_address": "10.0.1.100",
    "snmp_port": 161,
    "snmp_community_read": "public",
    "snmp_community_write": "private",
    "protocol_version": "ntcip1202v02",
    "controller_model": "econolite_cobalt",
    "supports_scp": false
  },
  "nfc_reader": {
    "serial_port": "/dev/ttyS1",
    "baud_rate": 115200,
    "reader_id": "RDR-0042-A"
  },
  "timing_rules": {
    "cooldown_sec": 120,
    "max_extensions_per_cycle": 1,
    "extension_formula": "linear_by_width",
    "eligible_card_types": ["SENIOR_RTC", "DISABLED_RTC"],
    "extend_during_active_walk": true,
    "block_during_preemption": true
  },
  "cloud": {
    "api_url": "https://safecross-api.sfmta.example.com",
    "device_cert_path": "/etc/safecross/device.pem",
    "device_key_path": "/etc/safecross/device.key",
    "heartbeat_interval_sec": 300,
    "event_batch_size": 10,
    "event_flush_interval_sec": 60
  },
  "ota": {
    "manifest_url": "https://safecross-api.sfmta.example.com/ota/manifest",
    "check_interval_sec": 86400,
    "auto_apply": false
  }
}
```

Create a Pydantic model (`config_manager.py`) that validates this structure on load and provides typed access throughout the application. The `intersection.example.json` file should contain the above with comments explaining each field.

## RS-485 listener — receiving NFC reader messages

The NFC reader sends messages using the frame format defined in the Layer 1 spec. Implement the receiver side:

### Frame format (from Layer 1 spec)

```
| SYNC (2 bytes) | LENGTH (1 byte) | MSG_TYPE (1 byte) | PAYLOAD (N bytes) | CRC16 (2 bytes) |
| 0xAA 0x55      | N + 2            | see below         | varies             | CRC-16/MODBUS   |
```

### Message types to handle

**0x01 — Card tap event (from reader)**
```
PAYLOAD:
  card_type:     1 byte (0x01=SENIOR_RTC, 0x02=DISABLED_RTC, 0x03=STANDARD,
                          0x04=YOUTH, 0x05=DESFIRE_DETECTED, 0xFF=UNKNOWN)
  uid_length:    1 byte (4 or 7)
  uid:           4 or 7 bytes
  timestamp_ms:  4 bytes (uint32, ms since reader boot, little-endian)
  read_method:   1 byte (1=APPDIR, 2=UID_PREFIX, 3=ANY_DESFIRE)
```

**0x02 — Heartbeat (from reader)**
```
PAYLOAD:
  status:        1 byte (0x00=OK, 0x01=NFC_CHIP_ERROR, 0x02=LED_ERROR)
  uptime_sec:    4 bytes (uint32, little-endian)
  tap_count:     4 bytes (uint32, little-endian)
  temperature:   2 bytes (int16, 0.1°C units, little-endian)
```

### Messages to send

**0x80 — Config update (to reader)**
```
PAYLOAD:
  config_key:    1 byte (0x01=UID_TABLE, 0x02=CLASSIFY_MODE, 0x03=COOLDOWN)
  config_data:   variable
```

### Implementation notes

- Run the serial listener in a dedicated thread (pyserial is blocking)
- Thread reads raw bytes, assembles frames by scanning for SYNC bytes, validates CRC
- Successfully parsed messages are posted to an `asyncio.Queue` for the main event loop
- Invalid frames (bad CRC, truncated, unexpected length) are counted and logged but not fatal
- Implement a frame parser as a state machine:

```python
class FrameState(Enum):
    WAITING_SYNC1 = auto()    # Looking for 0xAA
    WAITING_SYNC2 = auto()    # Looking for 0x55
    WAITING_LENGTH = auto()   # Next byte is LENGTH
    READING_BODY = auto()     # Reading LENGTH bytes
    WAITING_CRC = auto()      # Reading 2 CRC bytes
```

## Classifier filter — validating and deduplicating tap events

Before a tap event triggers a signal extension, it must pass several checks:

```python
class TapFilterResult(Enum):
    ACCEPTED = "accepted"
    REJECTED_CARD_TYPE = "rejected_card_type"
    REJECTED_COOLDOWN = "rejected_cooldown"
    REJECTED_DUPLICATE = "rejected_duplicate"
    REJECTED_PREEMPTION = "rejected_preemption"
    REJECTED_MAX_EXTENSIONS = "rejected_max_ext"
```

Implement these checks in order:

1. **Card type check:** Is `card_type` in the `eligible_card_types` list from config? Default: only `SENIOR_RTC` and `DISABLED_RTC`. In test mode, `DESFIRE_DETECTED` is also eligible.

2. **Duplicate tap detection:** Has the same card UID been seen in the last 5 seconds? Maintain a small TTL cache of recent UIDs. Prevents double-counting if someone taps multiple times.

3. **Cooldown check:** Has this crossing had an extension granted within the last `cooldown_sec` (default 120 seconds)? Track per-crossing last-extension timestamp.

4. **Max extensions per cycle:** Has this signal cycle already received `max_extensions_per_cycle` extensions? Prevents stacking.

5. **Preemption check:** Query signal controller (via SNMP) for active preemption. If emergency vehicle preemption or transit priority is active, reject. (This check is async — the NTCIP client handles it.)

Every tap event is logged regardless of filter result — the rejection reason is recorded for analytics.

## Timing engine — calculating extension duration

When a tap passes all filters, the timing engine determines how many extra seconds to grant.

### Extension calculation

```python
def calculate_extension(crossing_config: CrossingConfig) -> int:
    """
    Calculate pedestrian walk phase extension in seconds.

    The extension is based on crossing width, using a target walking speed
    of 2.5 ft/sec (slower than the MUTCD standard of 3.5 ft/sec, to
    accommodate elderly and disabled pedestrians).

    Formula:
      needed_total = crossing_width_ft / 2.5
      already_provided = base_walk_sec + base_clearance_sec
      raw_extension = needed_total - already_provided
      extension = clamp(raw_extension, min_extension_sec, max_extension_sec)

    Example for a 72-foot crossing:
      needed_total = 72 / 2.5 = 28.8 sec
      already_provided = 7 + 18 = 25 sec
      raw_extension = 3.8 -> rounds up to 4
      clamped = clamp(4, 6, 13) = 6 sec (minimum floor applies)

    Returns: integer seconds of extension
    """
```

The formula above is the `linear_by_width` mode. Implement it as the default. Leave room for alternative formulas (the `extension_formula` config field) but only implement this one for now.

**Important constraint:** The extension must ALWAYS respect `max_extension_sec` from the config. This is a safety cap that prevents the software from ever requesting an unreasonably long walk phase.

### When to apply the extension

The timing engine must also decide HOW to apply the extension based on the current signal state:

| Current state | Action |
|---------------|--------|
| Pedestrian phase NOT yet called | Place a ped call AND set extended walk time |
| Walk phase currently active | Extend the walk timer if `extend_during_active_walk` is true |
| Clearance (flashing don't walk) active | Too late — log as `MISSED_PHASE`, do not extend |
| Don't walk (solid red) | Place a ped call for the NEXT cycle with extended time |
| Preemption active | Reject (handled by classifier filter) |

## NTCIP/SNMP client — the hardest piece

This module communicates with the traffic signal controller using SNMP (Simple Network Management Protocol) to read signal state and write pedestrian timing parameters. The signal controller exposes its data as an SNMP MIB (Management Information Base) defined by the NTCIP 1202 standard.

### SNMP library

Use `pysnmp-lextudio` (v6+, the actively maintained fork). All SNMP operations should be async.

```
pip install pysnmp-lextudio
```

### NTCIP 1202 OID reference

The following SNMP Object Identifiers (OIDs) are used. The base OID for NTCIP 1202 objects is:

```
1.3.6.1.4.1.1206.4.2.1  (ntcipSignalControl)
```

Key OID paths (the trailing `.N` is the phase number, 1-indexed):

```python
# Base OID prefix for NTCIP 1202
NTCIP_BASE = "1.3.6.1.4.1.1206.4.2.1"

# Phase status group — read current phase state
PHASE_STATUS_GROUP_GREENS    = f"{NTCIP_BASE}.1.4.1.4"    # phaseStatusGroupGreens (bitmap)
PHASE_STATUS_GROUP_YELLOWS   = f"{NTCIP_BASE}.1.4.1.5"    # phaseStatusGroupYellows (bitmap)
PHASE_STATUS_GROUP_REDS      = f"{NTCIP_BASE}.1.4.1.6"    # phaseStatusGroupReds (bitmap)

# Pedestrian phase status
PED_STATUS_WALK              = f"{NTCIP_BASE}.1.4.1.7"    # phaseStatusGroupWalk (bitmap)
PED_STATUS_PED_CLEAR         = f"{NTCIP_BASE}.1.4.1.8"    # phaseStatusGroupPedClear (bitmap)
PED_STATUS_DONT_WALK         = f"{NTCIP_BASE}.1.4.1.9"    # phaseStatusGroupDontWalk (bitmap)

# Pedestrian timing parameters (per phase) — these are what we WRITE to extend
PED_WALK_TIME                = f"{NTCIP_BASE}.1.2.1.7"    # phaseWalk.{phase} (seconds)
PED_CLEAR_TIME               = f"{NTCIP_BASE}.1.2.1.8"    # phasePedClear.{phase} (seconds)

# Pedestrian call control — place a ped call
PED_CALL                     = f"{NTCIP_BASE}.1.3.1.3"    # phasePedCall.{phase} (set bit)

# Preemption status
PREEMPT_STATE                = f"{NTCIP_BASE}.6.5.1.4"    # preemptState (per preempt number)

# Coordination status
COORD_PATTERN_STATUS         = f"{NTCIP_BASE}.3.6.1.3"    # coordPatternStatus

# Unit control
UNIT_CONTROL_STATUS          = f"{NTCIP_BASE}.6.1"        # unitControlStatus
```

> **Important note on OID accuracy:** The OIDs above are based on the NTCIP 1202 v02 standard. Different signal controller manufacturers (Econolite, McCain, Siemens, Intelight/Q-Free) may implement slightly different OID trees or have vendor-specific extensions. The `controller_model` field in the config exists to allow vendor-specific OID overrides. For the initial implementation, target the standard OIDs above and add a `VendorOIDProfile` abstraction that can be extended later.

### SNMP operations to implement

```python
class NTCIPClient:
    """
    Async SNMP client for traffic signal controller communication.

    All operations use SNMP v2c (the version supported by most deployed
    signal controllers in SF). Uses community strings for auth.
    """

    async def connect(self, config: SignalControllerConfig) -> None:
        """Initialize SNMP transport to the signal controller."""

    async def get_phase_state(self, phase: int) -> PhaseState:
        """
        Read current state of a signal phase.

        Returns PhaseState enum:
          - GREEN, YELLOW, RED (vehicle phases)
          - PED_WALK, PED_CLEAR, PED_DONT_WALK (pedestrian phases)
          - PREEMPTED, UNKNOWN

        Reads the phase status bitmaps and checks which bit is set
        for the given phase number.
        """

    async def get_ped_timing(self, phase: int) -> PedTiming:
        """
        Read current pedestrian timing parameters for a phase.

        Returns PedTiming(walk_sec: int, clearance_sec: int)
        """

    async def set_ped_walk_time(self, phase: int, seconds: int) -> bool:
        """
        Write a new pedestrian walk time for a phase.

        This is the core extension operation. Sends an SNMP SET on
        phaseWalk.{phase} with the new value.

        Args:
            phase: Signal phase number (from crossing config)
            seconds: New walk time in seconds (base + extension)

        Returns: True if SNMP SET was acknowledged, False on error

        Safety constraint: This method MUST reject any value greater
        than (base_walk_sec + max_extension_sec) from the config.
        Hard-coded upper bound: never exceed 45 seconds regardless
        of config.
        """

    async def place_ped_call(self, phase: int) -> bool:
        """
        Place a pedestrian call for a phase.

        Sends SNMP SET to phasePedCall with the appropriate bit set.
        Equivalent to someone pressing the pedestrian push button.

        Returns: True if acknowledged, False on error
        """

    async def check_preemption_active(self) -> bool:
        """
        Check if any preemption (emergency vehicle, transit priority)
        is currently active on the controller.

        Returns: True if preemption is active (we should NOT extend)
        """

    async def restore_base_timing(self, phase: int, base_walk_sec: int) -> bool:
        """
        Restore the pedestrian walk time to its base value.

        Called after the extended walk phase completes.

        Returns: True if acknowledged, False on error
        """

    async def get_controller_status(self) -> ControllerStatus:
        """
        Read overall controller status for health monitoring.

        Returns ControllerStatus with fields:
          - mode: AUTO, MANUAL, FLASH, PREEMPT
          - coordination_pattern: int
          - comm_ok: bool
        """
```

### SNMP implementation details

Using `pysnmp-lextudio`, a typical SNMP GET looks like:

```python
from pysnmp.hlapi.v3arch.asyncio import *

async def snmp_get(self, oid: str) -> Any:
    """Execute an SNMP GET and return the value."""
    error_indication, error_status, error_index, var_binds = await get_cmd(
        SnmpEngine(),
        CommunityData(self.community_read),
        await UdpTransportTarget.create((self.ip_address, self.snmp_port)),
        ContextData(),
        ObjectType(ObjectIdentity(oid))
    )

    if error_indication:
        raise SNMPError(f"SNMP error: {error_indication}")
    if error_status:
        raise SNMPError(
            f"SNMP error at {error_index}: {error_status.prettyPrint()}"
        )

    for var_bind in var_binds:
        return var_bind[1]
```

And an SNMP SET:

```python
async def snmp_set(self, oid: str, value: int) -> bool:
    """Execute an SNMP SET with an integer value."""
    error_indication, error_status, error_index, var_binds = await set_cmd(
        SnmpEngine(),
        CommunityData(self.community_write),
        await UdpTransportTarget.create((self.ip_address, self.snmp_port)),
        ContextData(),
        ObjectType(ObjectIdentity(oid), Integer32(value))
    )

    if error_indication or error_status:
        return False
    return True
```

> **Note to Claude Code:** The `pysnmp` API has changed across versions. Use the `pysnmp-lextudio` package (v6+) and its `pysnmp.hlapi.v3arch.asyncio` module for async operations. Check the current pysnmp-lextudio docs if the above import paths don't resolve — the async API surface has moved between v5 and v6.

### Vendor OID profile abstraction

Implement a base class that can be subclassed per controller manufacturer:

```python
class VendorOIDProfile:
    """Base OID profile using standard NTCIP 1202 v02 OIDs."""

    def ped_walk_time_oid(self, phase: int) -> str:
        return f"{NTCIP_BASE}.1.2.1.7.{phase}"

    def ped_clear_time_oid(self, phase: int) -> str:
        return f"{NTCIP_BASE}.1.2.1.8.{phase}"

    def ped_call_oid(self, phase: int) -> str:
        return f"{NTCIP_BASE}.1.3.1.3.{phase}"

    def ped_walk_status_oid(self) -> str:
        return f"{NTCIP_BASE}.1.4.1.7.0"

    def ped_clear_status_oid(self) -> str:
        return f"{NTCIP_BASE}.1.4.1.8.0"

    def ped_dont_walk_status_oid(self) -> str:
        return f"{NTCIP_BASE}.1.4.1.9.0"

    def preempt_state_oid(self, preempt_num: int = 1) -> str:
        return f"{NTCIP_BASE}.6.5.1.4.{preempt_num}"


class EconoliteCobaltProfile(VendorOIDProfile):
    """Econolite Cobalt controller — uses standard OIDs."""
    pass  # No overrides needed for Cobalt


class McCainProfile(VendorOIDProfile):
    """McCain controller — may need OID adjustments."""
    pass  # Add overrides as discovered during testing


def get_vendor_profile(model: str) -> VendorOIDProfile:
    profiles = {
        "econolite_cobalt": EconoliteCobaltProfile(),
        "mccain": McCainProfile(),
    }
    return profiles.get(model, VendorOIDProfile())
```

## Signal state machine

The edge controller maintains a state machine per crossing representing the extension lifecycle:

```python
class ExtensionState(Enum):
    IDLE = "idle"
    EXTENSION_REQUESTED = "extension_requested"
    WALK_EXTENDED = "walk_extended"
    RESTORING = "restoring"
    COOLDOWN = "cooldown"
    ERROR = "error"
```

### State transitions

```
IDLE
  -> EXTENSION_REQUESTED  (valid tap received, SNMP SET sent)

EXTENSION_REQUESTED
  -> WALK_EXTENDED        (SNMP SET acknowledged, phase is now PED_WALK)
  -> ERROR                (SNMP timeout or error response)
  -> IDLE                 (phase changed before we could extend — missed it)

WALK_EXTENDED
  -> RESTORING            (phase transitioned to PED_CLEAR — walk ended)
  -> ERROR                (lost SNMP communication)

RESTORING
  -> COOLDOWN             (base timing restored successfully)
  -> ERROR                (SNMP SET to restore timing failed — retry)

COOLDOWN
  -> IDLE                 (cooldown_sec elapsed)

ERROR
  -> IDLE                 (after 3 retries or 30 seconds, reset to IDLE)
```

Implement the state machine with:
- A `tick()` method called every 500ms by the main loop
- Each tick reads the current signal phase state via SNMP and advances the state machine
- All state transitions are logged with timestamps to the `state_transitions` table

### Phase monitoring during extension

While in `WALK_EXTENDED` state, the controller must poll the signal phase every 500ms to detect when the walk phase ends (transitions from PED_WALK to PED_CLEAR). This is how it knows to restore the base timing.

**Do NOT rely on timers alone** to detect phase end — the signal controller may shorten or cancel the walk phase due to preemption, manual override, or coordination changes. Always read the actual phase state.

## Event logger — local SQLite store

Every event is persisted to a local SQLite database before any cloud reporting. This ensures no data is lost during network outages.

### Database schema

```sql
CREATE TABLE IF NOT EXISTS tap_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time TEXT NOT NULL,
    intersection_id TEXT NOT NULL,
    crossing_id TEXT NOT NULL,
    card_type INTEGER NOT NULL,
    card_uid TEXT NOT NULL,
    read_method INTEGER NOT NULL,
    filter_result TEXT NOT NULL,
    extension_sec INTEGER,
    phase_state_at_tap TEXT,
    snmp_result TEXT,
    reported_to_cloud INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS reader_heartbeats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time TEXT NOT NULL,
    reader_id TEXT NOT NULL,
    status INTEGER NOT NULL,
    uptime_sec INTEGER NOT NULL,
    tap_count INTEGER NOT NULL,
    temperature_c REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS state_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time TEXT NOT NULL,
    crossing_id TEXT NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    trigger TEXT NOT NULL
);

CREATE INDEX idx_tap_events_reported ON tap_events(reported_to_cloud);
CREATE INDEX idx_tap_events_time ON tap_events(event_time);
```

### Retention policy

Keep local data for 30 days. Run a daily cleanup:

```sql
DELETE FROM tap_events WHERE event_time < datetime('now', '-30 days');
DELETE FROM reader_heartbeats WHERE event_time < datetime('now', '-7 days');
DELETE FROM state_transitions WHERE event_time < datetime('now', '-7 days');
```

## Cloud reporter — forwarding events to the backend API

The cloud reporter batches unsent events and forwards them to the cloud backend over HTTPS.

### API contract (the cloud API that Layer 3 will implement)

**POST `/api/v1/events`**
```json
{
  "device_id": "EDGE-0042",
  "intersection_id": "INT-2025-0042",
  "events": [
    {
      "event_time": "2026-03-20T14:32:05.123Z",
      "crossing_id": "NS",
      "card_type": 1,
      "card_uid_hash": "a1b2c3d4",
      "read_method": 2,
      "filter_result": "accepted",
      "extension_sec": 8,
      "phase_state_at_tap": "PED_DONT_WALK",
      "snmp_result": "ok"
    }
  ]
}
```

**Important:** The `card_uid_hash` field is a truncated SHA-256 hash of the raw UID (first 8 hex chars). Do NOT send the raw UID to the cloud — this is a privacy measure. The raw UID is stored locally for deduplication but never transmitted.

**POST `/api/v1/heartbeat`**
```json
{
  "device_id": "EDGE-0042",
  "intersection_id": "INT-2025-0042",
  "timestamp": "2026-03-20T14:35:00Z",
  "edge_status": "ok",
  "reader_status": "ok",
  "signal_controller_status": "auto",
  "uptime_sec": 86420,
  "events_pending": 3,
  "last_extension_time": "2026-03-20T14:32:05Z",
  "software_version": "1.2.0"
}
```

**GET `/api/v1/config/{intersection_id}`**
Returns the latest intersection config JSON. The edge controller checks this on startup and periodically (every hour) to pick up config changes without redeployment.

**GET `/api/v1/ota/manifest`**
Returns available firmware version and download URL. See OTA updater section.

### Reporting behavior

- Batch up to `event_batch_size` (default 10) events, or flush every `event_flush_interval_sec` (default 60 seconds), whichever comes first
- If the cloud API is unreachable, events stay in the local SQLite buffer (marked `reported_to_cloud = 0`)
- On reconnection, replay all unreported events in chronological order
- Use mTLS (mutual TLS) with per-device certificates for authentication
- Timeout: 10 seconds per request, 3 retries with exponential backoff (1s, 4s, 16s)

## Health monitor

### Checks (run every `heartbeat_interval_sec`, default 300 seconds)

1. **Reader communication:** Has a heartbeat been received from the NFC reader in the last 30 seconds? If not, set `reader_status = "offline"`.

2. **Signal controller communication:** Can we SNMP GET the controller status? If not, set `signal_controller_status = "unreachable"`.

3. **Disk usage:** Is the eMMC storage below 90% capacity? If not, trigger early log cleanup.

4. **Event backlog:** Are there more than 1000 unreported events? If so, set `events_backlogged = true` in heartbeat.

5. **Temperature:** Read SBC die temperature from `/sys/class/thermal/thermal_zone0/temp`. Log if above 65°C.

### Alert conditions

- NFC reader offline for > 5 minutes
- Signal controller unreachable for > 2 minutes
- SNMP SET failure rate > 50% over last 10 attempts
- Disk usage > 90%
- Temperature > 70°C

## OTA updater

### Update flow

1. Every `check_interval_sec` (default 86400 = daily), GET the OTA manifest:
   ```json
   {
     "latest_version": "1.3.0",
     "download_url": "https://safecross-api.sfmta.example.com/ota/edge-1.3.0.tar.gz",
     "sha256": "abcdef1234567890...",
     "release_notes": "Added support for thermal sensor input",
     "min_current_version": "1.0.0"
   }
   ```

2. If `latest_version` > current version AND current >= `min_current_version`:
   - Download the tarball to `/tmp/safecross-update/`
   - Verify SHA-256 checksum
   - If `auto_apply` is true: extract, replace `/opt/safecross/`, restart service
   - If `auto_apply` is false: log that update is available, report in heartbeat

3. **Rollback:** Before applying, copy current install to `/opt/safecross.bak/`. If the new version fails to start (systemd detects 3 failures in 60 sec), the `OnFailure=` handler restores the backup.

## systemd service

```ini
[Unit]
Description=SafeCross Edge Controller
After=network.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/safecross/src/main.py --config /etc/safecross/intersection.json
WorkingDirectory=/opt/safecross
Restart=on-failure
RestartSec=5
StartLimitBurst=3
StartLimitIntervalSec=60
WatchdogSec=30
NotifyAccess=all
Environment=PYTHONUNBUFFERED=1
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/var/lib/safecross /tmp/safecross-update
ProtectHome=true

[Install]
WantedBy=multi-user.target
```

The application must send `sd_notify("WATCHDOG=1")` at least every 15 seconds (half of WatchdogSec). Use the `sdnotify` package or write directly to `$NOTIFY_SOCKET`.

## main.py — entry point and orchestration

```python
"""
SafeCross Edge Controller — main entry point.

Orchestrates all async components:
1. Config loading and validation
2. RS-485 listener thread -> asyncio queue
3. Main async loop processing tap events, managing state machines,
   logging, reporting, heartbeats, OTA checks, and watchdog kicks.
"""

async def main():
    config = ConfigManager.load("/etc/safecross/intersection.json")

    db = await EventLogger.create("/var/lib/safecross/events.db")
    ntcip = NTCIPClient(config.signal_controller)
    rs485_queue = asyncio.Queue()
    rs485_thread = RS485Listener(config.nfc_reader, rs485_queue)
    cloud = CloudReporter(config.cloud, db)
    health = HealthMonitor(config, ntcip, rs485_thread, db)
    ota = OTAUpdater(config.ota)

    state_machines = {
        c.crossing_id: SignalStateMachine(c, ntcip, db)
        for c in config.crossings
    }
    filters = {
        c.crossing_id: ClassifierFilter(c, config.timing_rules)
        for c in config.crossings
    }
    timing = TimingEngine(config.crossings)

    rs485_thread.start()

    while True:
        sd_notify("WATCHDOG=1")

        while not rs485_queue.empty():
            msg = rs485_queue.get_nowait()
            if msg.type == MSG_TYPE_TAP:
                await handle_tap(msg, filters, timing, state_machines, ntcip, db)
            elif msg.type == MSG_TYPE_HEARTBEAT:
                await db.log_reader_heartbeat(msg)

        for sm in state_machines.values():
            await sm.tick()

        await cloud.maybe_flush()
        await health.maybe_send_heartbeat()
        await ota.maybe_check()

        await asyncio.sleep(0.25)
```

### handle_tap implementation outline

```python
async def handle_tap(msg, filters, timing, state_machines, ntcip, db):
    """Process a single tap event from the NFC reader."""

    # 1. Determine which crossing this tap is for.
    #    For Phase 1 with a single reader, use the first crossing in config.
    #    Future: use reader_id to map to specific crossing.
    crossing_id = determine_crossing(msg)

    # 2. Run classifier filter
    filter_result = await filters[crossing_id].check(msg, ntcip)

    # 3. Log the event regardless of filter outcome
    event_record = build_event_record(msg, crossing_id, filter_result)

    if filter_result != TapFilterResult.ACCEPTED:
        event_record.extension_sec = None
        event_record.snmp_result = None
        await db.log_tap_event(event_record)
        return

    # 4. Calculate extension
    extension_sec = timing.calculate_extension(crossing_id)

    # 5. Get current phase state
    phase = get_phase_for_crossing(crossing_id)
    phase_state = await ntcip.get_phase_state(phase)
    event_record.phase_state_at_tap = phase_state.value

    # 6. Apply extension via state machine
    sm = state_machines[crossing_id]
    if phase_state in (PhaseState.PED_CLEAR, PhaseState.PREEMPTED):
        event_record.extension_sec = None
        event_record.snmp_result = "missed_phase"
    else:
        new_walk_time = timing.get_base_walk(crossing_id) + extension_sec
        success = await ntcip.set_ped_walk_time(phase, new_walk_time)
        if success and phase_state == PhaseState.PED_DONT_WALK:
            await ntcip.place_ped_call(phase)
        event_record.extension_sec = extension_sec if success else None
        event_record.snmp_result = "ok" if success else "snmp_error"
        if success:
            sm.transition_to(ExtensionState.EXTENSION_REQUESTED)

    await db.log_tap_event(event_record)
```

## Unit tests

Write tests using `pytest` + `pytest-asyncio`. Mock all hardware interfaces.

### test_message_protocol.py
- Correct SYNC, LENGTH, CRC-16/MODBUS construction
- Valid frame decoding
- Corrupted frame rejection (bad CRC)
- Truncated frame handling
- Back-to-back frame parsing
- Known CRC-16/MODBUS test vectors

### test_timing_engine.py
- 72-foot crossing -> correct extension seconds
- 48-foot crossing -> correct extension seconds
- Extension respects max_extension_sec cap
- Extension respects min_extension_sec floor
- Extension never exceeds 45-second hard ceiling
- Negative raw_extension -> min_extension_sec floor applies

### test_signal_state.py
- IDLE -> EXTENSION_REQUESTED on valid tap
- EXTENSION_REQUESTED -> WALK_EXTENDED on SNMP ack
- EXTENSION_REQUESTED -> ERROR on SNMP timeout
- WALK_EXTENDED -> RESTORING on PED_CLEAR detection
- RESTORING -> COOLDOWN on base timing restore
- COOLDOWN -> IDLE after elapsed time
- ERROR -> IDLE after retry exhaustion
- No transition from IDLE on rejected tap
- Preemption during any state handled correctly

### test_ntcip_client.py
- Correct OID construction for each phase number
- SNMP SET value within safety bounds
- SET value above 45-second ceiling rejected
- SET value above config max rejected
- Preemption check reads correct OIDs
- Mock responses: success, timeout, error
- Vendor profile OID override works correctly

### test_classifier_filter.py
- Senior RTC card -> accepted
- Disabled RTC card -> accepted
- Standard adult card -> rejected_card_type
- Same UID within 5 sec -> rejected_duplicate
- Same UID after 6 sec -> accepted (dedup expired)
- Tap during cooldown -> rejected_cooldown
- Tap after cooldown -> accepted
- Tap during preemption -> rejected_preemption

## Code style

- Python 3.11+, type hints on all function signatures
- `black` formatting (line length 100)
- `ruff` for linting
- Google-style docstrings on all public functions and classes
- Logging via Python `logging` module:
  - DEBUG: SNMP request/response, frame bytes
  - INFO: Tap events, state transitions, extensions granted
  - WARNING: SNMP timeouts, reader offline, config issues
  - ERROR: SNMP failures, unrecoverable states
  - CRITICAL: Signal controller unreachable, system errors
- All times in UTC (`datetime.timezone.utc`)
- No global mutable state — dependency injection via constructors
- Async where possible, threads only for blocking serial I/O

## Safety invariants — these must NEVER be violated

1. **The edge controller must never send a walk time value greater than (base_walk_sec + max_extension_sec) for any crossing.** Enforce with a bounds check in `set_ped_walk_time()` independent of the timing engine — defense in depth.

2. **Hard-coded ceiling: 45 seconds total walk time must never be exceeded**, regardless of config values. Fail-safe against misconfiguration.

3. **If SNMP communication is lost, do NOT cache or queue timing changes.** When communication resumes, re-read current phase state before any action.

4. **Never interfere with emergency vehicle preemption.** Always check preemption before extending. If preemption activates during an extension, do not attempt to override or restore timing until preemption clears.

5. **If the edge controller crashes or restarts, the signal controller continues on base timing.** The edge controller is additive only — its absence means "no extensions," not "broken signal."

## What NOT to build

- Do not implement the cloud API server (Layer 3) — only the client that calls it
- Do not implement the dashboard frontend (Layer 5)
- Do not implement Phase 2 thermal sensor input (USB port reserved for future)
- Do not implement NTCIP 1211 SCP priority requests — use direct NTCIP 1202 phaseWalk SET
- Do not implement SNMPv3 — use SNMPv2c with community strings
- Do not implement multi-reader support (one reader per edge controller in Phase 1)
