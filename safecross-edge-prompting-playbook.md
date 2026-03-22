# SafeCross Edge Controller — Claude Code Prompting Playbook

## How to use this document

This is a step-by-step prompting guide for building the SafeCross edge controller software using Claude Code. The edge controller is the DIN-rail ARM SBC that sits inside the traffic signal cabinet. It receives card tap events from the NFC reader, decides whether to extend the pedestrian walk phase, sends NTCIP/SNMP commands to the traffic signal controller, and logs everything.

This is the hardest software component in the SafeCross system. The prompts are ordered to build complexity incrementally — each step is testable before moving to the next.

**Prerequisites:**
- You have `safecross-edge-controller-spec.md` (the full technical spec) in your project directory as `SPEC.md`
- Python 3.10+ installed
- Claude Code installed and configured

**Setup:**
```bash
mkdir safecross-edge
cd safecross-edge
cp /path/to/safecross-edge-controller-spec.md ./SPEC.md
```

---

## Step 1 — Project skeleton

**What this does:** Creates every file and directory with proper structure, type hints, and docstrings — but no implementation yet. This gives Claude Code a map of the full system before it starts filling in details.

**Prompt:**
```
Read SPEC.md completely. Create the full project skeleton exactly as defined 
in the "Project structure" section:
- All directories and __init__.py files
- requirements.txt with all dependencies listed in the spec
- setup.py for the safecross package
- config/default.json with the example config from the spec
- config/schema.json — a JSON Schema that validates the config structure
- systemd/safecross-edge.service exactly as shown in the spec
- Every .py module file with the class/function signatures stubbed out, 
  full docstrings, and TODO comments in the bodies
- conftest.py with the shared test fixtures described in the spec

Do not implement any function bodies yet — just the skeleton with type hints 
and docstrings.
```

**Verify before moving on:**
- All directories exist
- Every `.py` file has proper imports, class/function stubs, and type hints
- `config/schema.json` validates `config/default.json`
- `pip install -r requirements.txt` succeeds

---

## Step 2 — CRC utility and message protocol

**What this does:** Builds the RS-485 message parsing layer — the interface contract between the NFC reader firmware (Layer 1) and this edge controller. This must match the reader firmware protocol byte-for-byte.

**Prompt:**
```
Implement src/utils/crc.py and src/reader_interface/protocol.py.

crc.py:
- Implement CRC-16/MODBUS: polynomial 0xA001 (reflected), initial value 0xFFFF
- Function: crc16_modbus(data: bytes) -> int
- Include test vectors in a docstring

protocol.py:
- Implement the frame format exactly as defined in SPEC.md under 
  "RS-485 message protocol":
  | SYNC (0xAA 0x55) | LENGTH (1 byte) | MSG_TYPE (1 byte) | PAYLOAD | CRC16 (2 bytes) |

- Define all constants:
  MSG_CARD_TAP = 0x01
  MSG_HEARTBEAT = 0x02
  MSG_CONFIG_UPDATE = 0x80
  MSG_CONFIG_ACK = 0x81
  CARD_TYPE_NONE = 0x00
  CARD_TYPE_SENIOR_RTC = 0x01
  CARD_TYPE_DISABLED_RTC = 0x02
  CARD_TYPE_STANDARD = 0x03
  CARD_TYPE_YOUTH = 0x04
  CARD_TYPE_DESFIRE_DETECTED = 0x05
  CARD_TYPE_UNKNOWN = 0xFF
  EXTENSION_ELIGIBLE = {0x01, 0x02}

- Define dataclasses:
  CardTapEvent: card_type (int), uid (bytes), timestamp_ms (int), read_method (int)
  ReaderHeartbeat: status (int), uptime_sec (int), tap_count (int), temperature_c (float)

- Implement parse_frame(buffer: bytes) -> tuple[int, dict, int] | None
  - Scans for SYNC bytes 0xAA 0x55
  - Extracts LENGTH, MSG_TYPE, PAYLOAD, CRC
  - Validates CRC — reject if mismatch
  - Parses PAYLOAD into the appropriate dataclass based on MSG_TYPE
  - Returns (msg_type, parsed_payload_as_dict, total_bytes_consumed) or None
  - Must handle: partial frames (return None), corrupt CRC (discard + return None),
    multiple frames in one buffer (return first valid, caller re-calls for next)

- Implement build_config_message(config_key: int, config_data: bytes) -> bytes
  - Constructs a complete frame for MSG_TYPE 0x80
  - Returns raw bytes ready to send over serial

Then write tests/test_protocol.py:
- Test parse_frame with a valid card tap frame (construct bytes manually)
- Test parse_frame with a valid heartbeat frame
- Test parse_frame with truncated frame (only SYNC + partial LENGTH) → returns None
- Test parse_frame with corrupt CRC → returns None
- Test parse_frame with two complete frames concatenated → returns first, 
  caller can parse remainder
- Test parse_frame when SYNC bytes appear in middle of payload (shouldn't 
  false-trigger)
- Test build_config_message produces a frame that parse_frame can round-trip
- Test CRC-16/MODBUS against known vectors:
  - crc16_modbus(b"") should return a known value
  - crc16_modbus(b"\x01\x02\x03\x04") against a reference
  - crc16_modbus of a full message payload matches manual calculation
- Test little-endian byte ordering: construct a CardTapEvent with timestamp_ms=0x12345678,
  verify the bytes in the frame are 0x78, 0x56, 0x34, 0x12

Run: pytest tests/test_protocol.py -v
All tests must pass before moving on.
```

**Verify before moving on:**
- `pytest tests/test_protocol.py -v` — all green
- Round-trip test passes (build → parse → compare)

---

## Step 3 — RS-485 serial listener

**What this does:** Connects the protocol parser to an actual serial port, with async I/O, reconnection logic, and event dispatching.

**Prompt:**
```
Implement src/reader_interface/rs485.py and src/reader_interface/listener.py.

rs485.py — class RS485Connection:
- Constructor takes port path (str) and baud rate (int, default 115200)
- Uses pyserial for serial I/O
- async open() — open the serial port, configure 8N1, set RS-485 mode 
  via ioctl if supported (SER_RS485_ENABLED), log success
- async close() — close the port cleanly
- async read_loop() — continuously read available bytes from serial port
  in a background asyncio task. Feed raw bytes into an internal buffer.
  Call protocol.parse_frame() on the buffer after each read. When a 
  complete frame is parsed, put the (msg_type, payload_dict) onto an 
  asyncio.Queue for the listener to consume.
- async send(data: bytes) — write bytes to serial port (for config messages 
  to the reader). Handle RS-485 direction control if needed.
- Reconnection: if serial port raises an exception (device disconnected, 
  permission error), log WARNING, wait 5 seconds, attempt to reopen. 
  Keep retrying indefinitely with exponential backoff capped at 60 seconds.
- Property: is_connected -> bool

listener.py — class ReaderListener:
- Constructor takes RS485Connection and callback functions:
  on_card_tap: Callable[[CardTapEvent], Awaitable[None]]
  on_reader_health_update: Callable[[ReaderHeartbeat], None] (optional)
- async run() — consume messages from the RS485Connection queue:
  - MSG_CARD_TAP → parse into CardTapEvent, call on_card_tap callback
  - MSG_HEARTBEAT → parse into ReaderHeartbeat, update internal reader 
    health state, call on_reader_health_update if registered
  - MSG_CONFIG_ACK → resolve a pending config update Future
- Property: reader_online -> bool (True if heartbeat received within last 30 sec)
- Property: reader_last_heartbeat -> ReaderHeartbeat | None
- async send_config(config_key: int, config_data: bytes, timeout: float = 5.0) -> bool
  — send config message to reader and wait for ACK with timeout

No unit tests for this step — these are I/O-heavy modules that will be 
tested via the simulation script later. But make sure the code is clean 
and the types are correct.
```

**Verify before moving on:**
- No import errors: `python -c "from safecross.reader_interface.listener import ReaderListener"`
- Code passes `mypy src/reader_interface/ --ignore-missing-imports`

---

## Step 4 — NTCIP object definitions and SNMP client

**What this does:** Builds the interface to the traffic signal controller. The SNMP client wraps pysnmp for async GET/SET operations. The NTCIP objects module defines what we can read and write.

**Prompt:**
```
Implement src/signal_interface/ntcip_objects.py and src/signal_interface/snmp_client.py.

ntcip_objects.py:
- Define all OID string constants from SPEC.md:
  PHASE_STATUS_GROUP = "1.3.6.1.4.1.1206.4.2.1.1.4.1.2"
  PED_PHASE_STATUS = "1.3.6.1.4.1.1206.4.2.1.1.4.1.4"
  PED_WALK_TIME = "1.3.6.1.4.1.1206.4.2.1.1.2.1.7"
  PED_CLEAR_TIME = "1.3.6.1.4.1.1206.4.2.1.1.2.1.8"
  PED_CALL = "1.3.6.1.4.1.1206.4.2.1.1.6.1.8"
  PREEMPT_STATUS = "1.3.6.1.4.1.1206.4.2.1.6.5.1.2"
  CONTROLLER_DESCRIPTION = "1.3.6.1.4.1.1206.4.2.1.1.1.0"
  CONTROLLER_VERSION = "1.3.6.1.4.1.1206.4.2.1.1.3.0"

- Function: get_oid(base_oid: str, phase: int) -> str
  Returns "{base_oid}.{phase}" — appends the phase number as a sub-OID

- Function: get_oid_with_overrides(name: str, phase: int, config: dict) -> str
  Check config["signal_controller"]["oid_overrides"] for a name match.
  If override exists, use that OID. Otherwise use the default.
  This allows per-intersection OID customization for controllers with 
  non-standard MIB layouts.

- Document each OID with a comment explaining:
  - What it represents
  - Its NTCIP 1202 section reference
  - Read-only or read-write
  - Value type and valid range

snmp_client.py — class SNMPClient:
- Constructor takes host (str), port (int), community_read (str), 
  community_write (str), snmp_version (str = "v2c"), 
  timeout_sec (float = 2.0), retries (int = 1)
- Uses pysnmp (or pysnmp-lextudio if using the maintained fork)
- async connect() — create SNMP engine and transport target. 
  Do a test GET on CONTROLLER_DESCRIPTION to verify connectivity.
  Log the controller description and version on success.
- async snmp_get(oid: str) -> Any | None
  Perform SNMP GET. Return the value on success, None on timeout/error.
  Log at DEBUG level for every request/response.
  Log at WARNING level for timeouts.
- async snmp_get_bulk(oids: list[str]) -> dict[str, Any]
  GET multiple OIDs in one request. Return dict mapping OID→value.
  Missing/failed OIDs map to None.
- async snmp_set(oid: str, value: int, value_type: str = "Integer") -> bool
  Perform SNMP SET. Return True on success, False on error.
  Log at INFO level for every SET (these are state-changing operations).
  Log at ERROR level for failures.
- Track consecutive failures: _consecutive_failures counter
  Increment on any timeout/error, reset to 0 on any success.
- Property: is_reachable -> bool (True if _consecutive_failures < 3)
- async close() — clean up SNMP engine

For SNMPv3 support: add a stub that raises NotImplementedError with 
a comment "TODO: implement SNMPv3 with auth (MD5/SHA) and privacy 
(DES/AES) when SFMTA provides credentials". The v2c path should be 
fully functional.

Write a basic test in tests/test_snmp_client.py:
- Test get_oid() and get_oid_with_overrides() with various inputs
- Test that consecutive failure tracking works correctly
  (mock the transport to simulate timeouts)
- Test that is_reachable flips to False after 3 failures and back 
  to True after one success

Run: pytest tests/test_snmp_client.py -v
```

**Verify before moving on:**
- Tests pass
- `get_oid("1.3.6.1.4.1.1206.4.2.1.1.2.1.7", 4)` returns `"1.3.6.1.4.1.1206.4.2.1.1.2.1.7.4"`

---

## Step 5 — Safety boundaries

**What this does:** Builds the safety validation layer that sits between the phase manager and the SNMP client. Every write to the signal controller passes through this module first. This is safety-critical code — 100% test coverage required.

**Prompt:**
```
Implement src/signal_interface/safety.py.

This module enforces safety boundaries on all signal controller writes.
It is a pure validation module — no side effects, no I/O, no state mutation.
Every function takes inputs and returns (allowed: bool, reason: str).

Implement:

WRITABLE_OID_ALLOWLIST = {"PED_WALK_TIME", "PED_CALL"}

def check_safety(
    oid_name: str,
    proposed_value: int,
    current_value: int,
    baseline_value: int,
    config: dict,  # intersection config timing section
    preemption_active: bool,
    last_write_timestamp: float | None,  # time.monotonic() of last SET
    cycle_length_sec: float = 90.0,  # typical signal cycle
) -> tuple[bool, str]:
    """
    Validate a proposed SNMP SET operation against all safety rules.
    Returns (True, "ok") if allowed, or (False, "reason") if blocked.
    
    Rules enforced (check in this order, return on first failure):
    1. oid_name must be in WRITABLE_OID_ALLOWLIST
       → (False, "oid_not_in_allowlist: {oid_name}")
    2. preemption_active must be False
       → (False, "preemption_active")
    3. proposed_value must be >= baseline_value (never decrease walk time)
       → (False, "below_baseline: proposed={proposed} baseline={baseline}")
    4. proposed_value must be <= config["max_walk_time_sec"] (absolute cap)
       → (False, "exceeds_max: proposed={proposed} max={max}")
    5. Rate limit: if last_write_timestamp is not None, 
       time since last write must be >= cycle_length_sec * 0.8
       → (False, "rate_limited: {seconds_since_last:.1f}s < {min_interval:.1f}s")
    """

def validate_extension_request(
    extension_sec: int,
    baseline_walk_sec: int,
    config: dict,
) -> tuple[int, list[str]]:
    """
    Clamp an extension request to configured bounds.
    Returns (clamped_value, warnings_list).
    
    Logic:
    - If extension_sec < config["min_extension_sec"]: 
      clamp up, warn "clamped_to_minimum"
    - If extension_sec > config["max_extension_sec"]: 
      clamp down, warn "clamped_to_maximum"
    - If baseline + extension > config["max_walk_time_sec"]: 
      reduce extension to fit, warn "clamped_to_absolute_max"
    - If extension_sec <= 0: return (0, ["no_extension_needed"])
    """

Write tests/test_safety.py with comprehensive coverage:

- test_allowlist_blocks_unknown_oid: 
  oid_name="VEHICLE_GREEN_TIME" → (False, "oid_not_in_allowlist...")
- test_allowlist_allows_ped_walk_time:
  oid_name="PED_WALK_TIME" with all other params valid → (True, "ok")
- test_allowlist_allows_ped_call:
  oid_name="PED_CALL" → (True, "ok")
- test_preemption_blocks_write:
  preemption_active=True → (False, "preemption_active")
- test_below_baseline_blocked:
  proposed=8, baseline=12 → (False, "below_baseline...")
- test_equal_to_baseline_allowed:
  proposed=12, baseline=12 → (True, "ok")
- test_exceeds_max_blocked:
  proposed=50, max_walk_time_sec=45 → (False, "exceeds_max...")
- test_within_max_allowed:
  proposed=25, max_walk_time_sec=45 → (True, "ok")
- test_rate_limit_blocks_rapid_writes:
  last_write 30 seconds ago, cycle_length=90 → (False, "rate_limited...")
- test_rate_limit_allows_after_cycle:
  last_write 80 seconds ago, cycle_length=90 → (True, "ok")
- test_rate_limit_allows_first_write:
  last_write_timestamp=None → (True, "ok")
- test_all_rules_pass:
  All valid params → (True, "ok")
- test_validate_clamps_to_minimum:
  extension=1, min=3 → (3, ["clamped_to_minimum"])
- test_validate_clamps_to_maximum:
  extension=20, max=13 → (13, ["clamped_to_maximum"])
- test_validate_clamps_to_absolute_max:
  extension=13, baseline=38, absolute_max=45 → (7, ["clamped_to_absolute_max"])
- test_validate_zero_extension:
  extension=0 → (0, ["no_extension_needed"])
- test_validate_negative_extension:
  extension=-3 → (0, ["no_extension_needed"])

Run: pytest tests/test_safety.py -v
Every test must pass. This is safety-critical code.
```

**Verify before moving on:**
- All 16+ tests pass
- `mypy src/signal_interface/safety.py` — no errors

---

## Step 6 — Phase manager state machine (THE CRITICAL PIECE)

**What this does:** The central state machine that orchestrates everything — reading signal state, requesting extensions, monitoring for preemption, restoring baseline timing. This is the most complex module and the one most likely to need iteration.

**Prompt:**
```
Implement src/signal_interface/phase_manager.py.

Read the full state machine specification in SPEC.md under "phase_manager.py — 
THE STATE MACHINE". Implement it exactly as described.

class PhaseState(Enum):
    IDLE = "idle"
    EXTENSION_REQUESTED = "extension_requested"
    WALK_EXTENDED = "walk_extended"
    RESTORING = "restoring"
    COOLDOWN = "cooldown"
    ERROR = "error"

class PhaseManager:
    def __init__(self, snmp_client: SNMPClient, safety: module, config: dict):
        self._snmp = snmp_client
        self._safety = safety
        self._config = config
        self._state = PhaseState.IDLE
        self._baseline_walk_times: dict[int, int] = {}  # phase -> saved baseline
        self._last_write_time: float | None = None
        self._extension_request_time: float | None = None
        self._current_extension_phase: int | None = None

    @property
    def state(self) -> PhaseState:
        return self._state

    async def process_tap(self, phase: int, extension_sec: int) -> bool:
        """
        Main entry point. Called when decision engine determines an extension 
        should be attempted.
        
        Returns True if extension was successfully requested, False if denied.
        
        Logic:
        1. If state is not IDLE → return False (log "extension already in progress"
           or "in cooldown" or "in error state")
        2. Check preemption via SNMP GET → if active, return False
        3. Read current PED_WALK_TIME for this phase → save as baseline
        4. Calculate target: baseline + extension_sec
        5. Pass through safety.check_safety() → if blocked, return False
        6. SNMP SET PED_WALK_TIME to target value
        7. SNMP GET PED_WALK_TIME to verify write took effect
           - If verification fails: try SNMP SET PED_CALL as fallback 
             (at least place a ped call with standard timing)
        8. Transition to EXTENSION_REQUESTED
        9. Record _extension_request_time and _current_extension_phase
        10. Return True
        """

    async def monitor_loop(self):
        """
        Background task that runs continuously while the service is alive.
        Polls signal state and manages state transitions.
        
        Loop (every 500ms):
        
        If state == EXTENSION_REQUESTED:
          - Read PED_PHASE_STATUS for current phase
          - If ped is in WALK state → transition to WALK_EXTENDED, log event
          - If 60 seconds elapsed since request → walk phase never started,
            transition to RESTORING (the signal cycle passed without serving 
            our ped call — timing will be restored)
            
        If state == WALK_EXTENDED:
          - Read PED_PHASE_STATUS for current phase
          - If ped is no longer in WALK (changed to CLEARANCE or DONT_WALK) →
            transition to RESTORING
            
        If state == RESTORING:
          - Call _restore_baseline()
          - If successful → transition to COOLDOWN, start cooldown timer
          - If failed after 3 retries → transition to ERROR, log CRITICAL
          
        If state == COOLDOWN:
          - If cooldown timer expired (cooldown_sec from config, default 120) →
            transition to IDLE
            
        If state == ERROR:
          - Every 30 seconds: attempt SNMP GET on controller description
          - If responsive: check if baseline is already correct (maybe restored 
            by another mechanism)
          - If responsive AND baseline confirmed → transition to IDLE, log recovery
        
        In ALL states except IDLE:
          - Poll PREEMPT_STATUS every 1 second
          - If preemption becomes active AND state is EXTENSION_REQUESTED or 
            WALK_EXTENDED → immediately transition to RESTORING
        """

    async def _restore_baseline(self, phase: int) -> bool:
        """
        Restore the original pedestrian walk time.
        
        1. Get saved baseline from self._baseline_walk_times[phase]
        2. SNMP SET PED_WALK_TIME to baseline value
        3. SNMP GET to verify
        4. If success: delete saved baseline, return True
        5. If fail: retry up to 3 times with 2-second delays between
        6. If all retries fail: return False (caller transitions to ERROR)
        """

    def _transition(self, new_state: PhaseState, reason: str):
        """
        Perform a state transition with logging.
        Log at INFO: "PhaseManager: {old_state} → {new_state} ({reason})"
        """

Now write tests/test_phase_manager.py. This needs thorough coverage because 
it's the most safety-sensitive module.

Create a MockSNMPClient in conftest.py that:
- Stores a dict of OID → value (simulating the signal controller's state)
- snmp_get returns the stored value
- snmp_set updates the stored value and returns True
- Can be configured to simulate: timeouts (return None/False), 
  preemption active (set preempt status OID to non-zero)
- Tracks all SET operations in a list for assertions

Test cases:

test_happy_path_full_lifecycle:
  1. Start in IDLE
  2. process_tap(phase=4, extension=8) → returns True, state=EXTENSION_REQUESTED
  3. Verify SNMP SET was called with correct OID and value
  4. Verify baseline was saved
  5. Simulate ped phase going to WALK → state=WALK_EXTENDED
  6. Simulate ped phase going to CLEARANCE → state=RESTORING
  7. Verify _restore_baseline is called → SNMP SET back to baseline
  8. State should reach COOLDOWN, then after cooldown expires → IDLE
  9. Verify saved baseline dict is empty (cleaned up)

test_preemption_during_extension_requested:
  1. process_tap → EXTENSION_REQUESTED
  2. Set preemption status to active in mock
  3. Run one monitor_loop iteration
  4. State should be RESTORING
  5. Verify baseline is restored

test_preemption_during_walk_extended:
  1. Get to WALK_EXTENDED state
  2. Set preemption active
  3. Run monitor_loop → RESTORING → baseline restored

test_extension_timeout:
  1. process_tap → EXTENSION_REQUESTED
  2. Do NOT set ped phase to WALK (simulate signal cycle passing)
  3. Advance time by 61 seconds
  4. Run monitor_loop → RESTORING → baseline restored

test_snmp_timeout_goes_to_error:
  1. process_tap → EXTENSION_REQUESTED
  2. Configure mock to start timing out (return None on all GETs)
  3. State should eventually reach ERROR
  4. Verify new process_tap calls return False while in ERROR

test_error_recovery:
  1. Get to ERROR state
  2. Re-enable mock SNMP responses
  3. Ensure baseline was restored (either by recovery or was already correct)
  4. State should return to IDLE

test_restore_baseline_retries:
  1. Get to RESTORING state
  2. Configure mock to fail SET twice then succeed on third attempt
  3. Verify 3 SET attempts were made
  4. State reaches COOLDOWN (not ERROR)

test_restore_baseline_all_retries_fail:
  1. Get to RESTORING state
  2. Configure mock to fail all SETs
  3. After 3 failures → state is ERROR
  4. Verify CRITICAL log was emitted

test_tap_rejected_during_cooldown:
  1. Complete full lifecycle → reach COOLDOWN
  2. process_tap → returns False
  3. State stays COOLDOWN

test_tap_rejected_during_error:
  1. Get to ERROR state
  2. process_tap → returns False

test_safety_check_blocks_extension:
  1. Configure config with max_walk_time_sec=15, baseline=14, extension=10
  2. process_tap should still work but extension is clamped by safety module
  3. Verify the SET value respects the safety bounds

test_baseline_always_restored:
  Run 5 different scenarios (happy path, preemption, timeout, error+recovery, 
  rapid back-to-back). After each scenario completes and returns to IDLE, 
  verify that the mock signal controller's PED_WALK_TIME matches the 
  original baseline value. This is THE critical safety assertion.

Run: pytest tests/test_phase_manager.py -v
All tests must pass.
```

**Verify before moving on:** (paused here)
- All 12+ tests pass
- The "baseline always restored" test is the most important — if it fails, do not proceed
- `mypy src/signal_interface/phase_manager.py` — clean

---

## Step 7 — Decision engine (timing + cooldown)

**What this does:** Calculates how much extension to grant and manages cooldown/dedup rules.

**Prompt:**
```
Implement src/decision/timing.py and src/decision/cooldown.py.

timing.py:
- Function: calculate_extension(
    card_type: int,
    crossing_width_ft: float,
    base_walk_time_sec: int,
    config: dict  # timing section of intersection config
  ) -> int

- Logic:
  walk_speed = config["senior_walk_speed_ft_per_sec"] if card_type == SENIOR_RTC
               else config["disabled_walk_speed_ft_per_sec"] if card_type == DISABLED_RTC
               else return 0 (not eligible)
  required_time = math.ceil(crossing_width_ft / walk_speed)
  extension = max(0, required_time - base_walk_time_sec)
  # Clamp to bounds
  extension = max(extension, config["min_extension_sec"]) if extension > 0 else 0
  extension = min(extension, config["max_extension_sec"])
  return extension

cooldown.py — class CooldownManager:
- __init__(self, config: dict):
    self._cooldown_sec = config["cooldown_sec"]  # default 120
    self._dedup_window_sec = config["dedup_window_sec"]  # default 10
    self._max_per_hour = config["max_extensions_per_hour"]  # default 20
    self._last_extension_time: dict[str, float] = {}  # intersection_id → monotonic time
    self._recent_uids: dict[str, list[tuple[str, float]]] = {}  # intersection → [(uid_hash, time)]
    self._hourly_counts: dict[str, list[float]] = {}  # intersection → [timestamps]

- can_extend(self, intersection_id: str, card_uid_hash: str, now: float) -> tuple[bool, str | None]:
    Check in order:
    1. Dedup: if same uid_hash seen for this intersection within dedup_window_sec
       → (False, "duplicate_card")
    2. Cooldown: if last extension for this intersection within cooldown_sec
       → (False, "cooldown_active")
    3. Rate limit: if extensions this hour >= max_per_hour
       → (False, "hourly_rate_limit")
    4. All clear → (True, None)

- record_extension(self, intersection_id: str, card_uid_hash: str, now: float):
    Record the extension in all tracking structures.
    Prune old entries from _recent_uids and _hourly_counts.

- reset(self, intersection_id: str):
    Clear all state for an intersection (for testing).

Write tests/test_timing.py:
- test_senior_60ft_crossing: width=60, base_walk=12, speed=3.0 → extension=8
- test_disabled_60ft_crossing: width=60, base_walk=12, speed=2.5 → extension=12
- test_narrow_crossing_no_extension: width=30, base_walk=12, speed=3.0 → 
  required=10, extension=0 (base time is sufficient, but min_extension applies 
  only if extension > 0, so this should return 0)
- test_wide_crossing_clamped: width=120, base_walk=12, speed=3.0 → 
  required=40, extension=28, clamped to max_extension=13
- test_standard_card_no_extension: card_type=STANDARD → extension=0
- test_extension_rounds_up: width=50, speed=3.0 → ceil(16.67)=17, extension=5

Write tests/test_cooldown.py:
- test_first_tap_allowed: no history → (True, None)
- test_duplicate_uid_blocked: same uid within 10 sec → (False, "duplicate_card")
- test_different_uid_during_cooldown: different uid within 120 sec → (False, "cooldown_active")
- test_after_cooldown_allowed: same intersection after 121 sec → (True, None)
- test_hourly_rate_limit: 20 extensions in one hour → 21st blocked
- test_rate_limit_resets_after_hour: oldest extension ages out → allowed again
- test_reset_clears_state: after reset, next tap is allowed

Run: pytest tests/test_timing.py tests/test_cooldown.py -v
```

**Verify before moving on:**
- All tests pass
- Edge cases (zero extension, negative values) handled correctly

---

## Step 8 — Event logging and cloud forwarding

**What this does:** Local event persistence and async forwarding to the cloud API.

**Prompt:**
```
Implement src/logging_events/models.py, event_store.py, and cloud_forwarder.py.

models.py:
- EventType enum with all types from SPEC.md: CARD_TAP, EXTENSION_GRANTED, 
  EXTENSION_DENIED, EXTENSION_COMPLETED, BASELINE_RESTORED, 
  BASELINE_RESTORE_FAILED, PREEMPTION_DETECTED, SNMP_ERROR, 
  READER_OFFLINE, READER_ONLINE, SYSTEM_STARTUP, RATE_LIMIT_EXCEEDED
- TapEvent dataclass with all fields from SPEC.md
  Include: event_id (UUID), intersection_id, timestamp (UTC datetime), 
  event_type, card_type, card_uid_hash (SHA-256 of raw UID), 
  extension_seconds, denial_reason (nullable), phase_number, 
  signal_state_at_tap, read_method, reader_uptime_sec, 
  forwarded_to_cloud (bool, default False)
- to_dict() → dict (for JSON serialization to cloud API)
- from_dict(d: dict) → TapEvent (for loading from SQLite)

event_store.py — class EventStore:
- __init__(self, db_path: str = "/var/lib/safecross/events.db")
- async init_db() — create table if not exists:
  CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    intersection_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    card_type INTEGER,
    card_uid_hash TEXT,
    extension_seconds INTEGER DEFAULT 0,
    denial_reason TEXT,
    phase_number INTEGER,
    signal_state_at_tap TEXT,
    read_method INTEGER,
    reader_uptime_sec INTEGER,
    forwarded_to_cloud INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
  );
  CREATE INDEX IF NOT EXISTS idx_events_forward ON events(forwarded_to_cloud, timestamp);
  CREATE INDEX IF NOT EXISTS idx_events_intersection ON events(intersection_id, timestamp);

- async store(event: TapEvent) -> str — insert, return event_id
- async get_unforwarded(limit: int = 100) -> list[TapEvent] — oldest first
- async mark_forwarded(event_ids: list[str]) — bulk update
- async get_stats() -> dict — {"total": N, "forwarded": N, "pending": N}
- async prune(days: int = 30) — delete forwarded events older than N days
- async count_pending() -> int — quick count for health monitoring

cloud_forwarder.py — class CloudForwarder:
- __init__(self, event_store: EventStore, config: dict)
- async run() — background task:
  while True:
    await asyncio.sleep(30)
    events = await self._event_store.get_unforwarded(limit=100)
    if not events: continue
    try:
      accepted_ids = await self._post_events(events)
      await self._event_store.mark_forwarded(accepted_ids)
    except AuthError: log CRITICAL, stop forwarding
    except NetworkError: log WARNING, continue (retry next cycle)
    
- async _post_events(events: list[TapEvent]) -> list[str]:
  POST to {api_base_url}/v1/events
  Body: JSON array of event dicts
  Auth: API key header (dev) or mTLS (production)
  Return list of accepted event_ids

Write tests/test_event_store.py using a temp SQLite db (conftest fixture):
- test_store_and_retrieve: store 3 events, get_unforwarded returns all 3
- test_unforwarded_returns_oldest_first: store events with different timestamps
- test_mark_forwarded: mark 2 of 3, get_unforwarded returns only the 1 remaining
- test_prune_removes_old_forwarded: store old forwarded event, prune(days=0), verify gone
- test_prune_keeps_recent_forwarded: store recent forwarded event, prune(days=30), verify kept
- test_prune_keeps_unforwarded: store old unforwarded event, prune, verify still there
- test_get_stats: verify counts are correct after mixed operations
- test_capacity: store 1000 events, verify no performance issues

Run: pytest tests/test_event_store.py -v
```

**Verify before moving on:**
- All tests pass
- SQLite database is created and accessible

---

## Step 9 — Device management

**What this does:** Config loading, health reporting, and OTA update checking.

**Prompt:**
```
Implement src/device_management/config_manager.py, heartbeat.py, and ota.py.

config_manager.py — class ConfigManager:
- __init__(self, config_path: str = "/etc/safecross/intersection.json")
- load() -> dict: read JSON file, validate against config/schema.json 
  using jsonschema library, return parsed config. Raise ValueError on 
  invalid config with a clear error message.
- get_crosswalk(direction: str) -> dict | None: return the crosswalk 
  config entry matching the direction name
- get_crosswalk_for_phase(phase: int) -> dict | None: return the 
  crosswalk config entry for the given ped phase number
- Log all config values at INFO on load. Mask sensitive values:
  community_write → "****", api_key → "****"
- Support hot-reload: reload() re-reads the file and replaces the 
  config atomically. Register as SIGHUP handler in main.py.

heartbeat.py — class HeartbeatReporter:
- __init__(self, config: dict, phase_manager: PhaseManager, 
  reader_listener: ReaderListener, event_store: EventStore)
- async run(): every 60 seconds, POST heartbeat to cloud API
  Payload matches SPEC.md heartbeat format: device_id, timestamp, uptime, 
  software_version, state_machine_state, reader_status, 
  signal_controller_reachable, events_pending, extensions_granted_today, 
  errors_today, system metrics (CPU temp, disk, memory).
  Use /proc/thermal_zone0/temp for CPU temp, shutil.disk_usage for disk, 
  and /proc/meminfo for memory.
  If cloud unreachable: log DEBUG and skip (don't buffer heartbeats).

ota.py — class OTAChecker:
- __init__(self, config: dict)
- async run(): check for updates periodically
  Interval: 6 hours + jitter (hash device_id, mod 3600 → 0-60min offset)
  GET {api_base_url}/v1/devices/{device_id}/updates
  If update available: log INFO with version and release notes
  Download update to /tmp/safecross-update/
  Verify SHA-256 hash
  Extract to /opt/safecross-staging/
  Log: "Update v{version} staged. Restart service to apply."
  Do NOT auto-restart — just stage. The operator or a separate process 
  triggers the restart. (This is a safety precaution — we don't want 
  auto-restarts during active extensions.)

No tests needed for these modules.
```

**Verify before moving on:**
- `python -c "from safecross.device_management.config_manager import ConfigManager; cm = ConfigManager('config/default.json'); cm.load()"` succeeds
- Config validation rejects invalid JSON (test manually with a bad file)

---

## Step 10 — Wire everything together in main.py

**What this does:** The entry point that initializes all components, connects them, and runs the async event loop.

**Prompt:**
```
Implement src/main.py — the orchestrator that wires everything together.

1. Parse CLI args: --config (default /etc/safecross/intersection.json)
   For development, also support --config config/default.json

2. Setup logging:
   format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
   level = DEBUG if --debug flag, else INFO
   Log to stdout (systemd captures it via journal)

3. Load and validate config via ConfigManager

4. Initialize components in order:
   a. event_store = EventStore(db_path) → call await init_db()
   b. snmp_client = SNMPClient(**config["signal_controller"])
      → call await connect(), log controller description
      → if connection fails: log ERROR but continue (phase manager 
        will start in ERROR state and attempt recovery)
   c. phase_manager = PhaseManager(snmp_client, safety, config)
   d. timing module (just import, it's stateless functions)
   e. cooldown_manager = CooldownManager(config["timing"])
   f. rs485 = RS485Connection(config["reader"]["serial_port"], ...)
      → call await open()
   g. cloud_forwarder = CloudForwarder(event_store, config)
   h. heartbeat = HeartbeatReporter(config, phase_manager, listener, event_store)
   i. ota = OTAChecker(config)

5. Define the card tap callback:
   async def on_card_tap(event: CardTapEvent):
       log INFO: "Card tap: type={event.card_type}, uid_hash={sha256(event.uid)[:12]}"
       
       # Check eligibility
       if event.card_type not in EXTENSION_ELIGIBLE:
           await event_store.store(TapEvent(
               event_type=EventType.EXTENSION_DENIED,
               denial_reason="not_eligible",
               ...
           ))
           return
       
       # Determine which crosswalk/phase this tap is for
       # For Phase 1: use the first crosswalk in config (single reader per intersection)
       crosswalk = config["crosswalks"][0]
       
       # Check cooldown
       uid_hash = hashlib.sha256(event.uid).hexdigest()
       allowed, denial_reason = cooldown_manager.can_extend(
           config["intersection_id"], uid_hash, time.monotonic()
       )
       if not allowed:
           await event_store.store(TapEvent(
               event_type=EventType.EXTENSION_DENIED,
               denial_reason=denial_reason,
               ...
           ))
           return
       
       # Calculate extension
       extension_sec = calculate_extension(
           event.card_type,
           crosswalk["crossing_width_ft"],
           crosswalk["base_walk_time_sec"],
           config["timing"]
       )
       if extension_sec == 0:
           log INFO: "No extension needed (base time sufficient)"
           return
       
       # Request extension from phase manager
       success = await phase_manager.process_tap(
           phase=crosswalk["ped_phase"],
           extension_sec=extension_sec
       )
       
       # Record
       cooldown_manager.record_extension(config["intersection_id"], uid_hash, time.monotonic())
       await event_store.store(TapEvent(
           event_type=EventType.EXTENSION_GRANTED if success else EventType.EXTENSION_DENIED,
           extension_seconds=extension_sec if success else 0,
           denial_reason=None if success else "phase_manager_rejected",
           ...
       ))

6. Create ReaderListener with on_card_tap callback

7. Start all background tasks with asyncio.gather:
   - rs485.read_loop()
   - listener.run()
   - phase_manager.monitor_loop()
   - cloud_forwarder.run()
   - heartbeat.run()
   - ota.run()
   - systemd_watchdog_loop() — kick systemd watchdog every 15 sec

8. Handle shutdown:
   Register signal handlers for SIGTERM and SIGINT.
   On shutdown signal:
   - Log INFO: "Shutdown requested, cleaning up..."
   - Cancel all background tasks
   - If phase_manager.state in (EXTENSION_REQUESTED, WALK_EXTENDED, RESTORING):
     log WARNING: "Extension in progress, waiting for restoration..."
     Wait up to 30 seconds for state to reach IDLE or COOLDOWN
   - Close rs485 connection
   - Close snmp_client
   - Close event_store
   - Log INFO: "Shutdown complete"

9. Handle SIGHUP: call config_manager.reload(), log new config values

10. Entry point:
    if __name__ == "__main__":
        asyncio.run(main())

Log each startup step at INFO so the operator can see initialization progress 
in journalctl.
```

**Verify before moving on:**
- `python -m safecross.main --config config/default.json --debug` starts without errors
  (it will fail to open the serial port and SNMP connection, but should log those failures 
  gracefully and continue)
- Ctrl+C triggers clean shutdown with log messages

---

## Step 11 — Simulation script and install script

**What this does:** Tools for testing without hardware and for deploying to a real device.

**Prompt:**
```
Create scripts/simulate_reader.py and scripts/install.sh.

simulate_reader.py:
- Standalone script (does not import from safecross package — copy the 
  protocol and CRC logic inline, or add safecross to PYTHONPATH)
- Uses pyserial to send messages over a serial port
- Command line args:
  --port PORT: serial port path (required)
  --baud 115200: baud rate
  --card-type TYPE: senior|disabled|standard|youth|desfire|random (default: senior)
  --interval SEC: seconds between taps (default: random 15-60)
  --burst N: send N rapid taps 1 second apart (for testing cooldown)
  --same-uid: reuse the same UID for all taps (for testing dedup)
  --count N: total number of taps to send (default: infinite)
  
- Behavior:
  - On start: print config summary
  - Send reader heartbeat every 10 seconds (in a background thread)
  - At each interval: construct a CardTapEvent frame with random UID 
    (or fixed UID if --same-uid), send over serial, print summary line
  - Generate UIDs as random 7 bytes
  - Print each sent message in human-readable format:
    "[14:30:05] TX tap: type=SENIOR_RTC uid=04A2B3... method=3"
    "[14:30:10] TX heartbeat: status=OK uptime=45s taps=3"

install.sh:
- #!/bin/bash
- set -e
- Check for root (required for systemd and user creation)
- Create safecross system user and group
- Create directories: /var/lib/safecross, /etc/safecross, /opt/safecross
- Set ownership to safecross:safecross
- Copy config/default.json → /etc/safecross/intersection.json 
  (if not already present — don't overwrite existing config)
- Create Python venv at /opt/safecross/venv
- Install requirements into venv
- Install safecross package into venv (pip install -e .)
- Copy systemd service file → /etc/systemd/system/safecross-edge.service
- systemctl daemon-reload
- systemctl enable safecross-edge (but don't start)
- Print: "Installation complete. Edit /etc/safecross/intersection.json 
  then run: systemctl start safecross-edge"
```

**Verify before moving on:**
- `python scripts/simulate_reader.py --port /dev/null --card-type senior --count 1` 
  runs without import errors (the write will fail on /dev/null, but protocol 
  construction should work)

---

## Step 12 — Full test suite, type checking, and README

**What this does:** Final quality pass across the entire project.

**Prompt:**
```
Final review and quality pass for the entire safecross-edge project.

1. Review conftest.py — ensure all shared fixtures are complete:
   - mock_snmp_client: returns configurable responses, tracks all SETs
   - sample_config: returns a valid config dict based on config/default.json
   - sample_tap_event: factory for CardTapEvent with sensible defaults 
     (card_type=SENIOR_RTC, random uid, timestamp=now)
   - temp_event_db: creates a temporary SQLite path, yields it, 
     cleans up after test

2. Run the full test suite:
   pytest -v --tb=short
   Fix any failures.

3. Run type checking:
   mypy src/ --ignore-missing-imports
   Fix any type errors.

4. Check that every module has:
   - Module-level docstring
   - All public functions have docstrings with param descriptions
   - Type hints on all function signatures
   - No unused imports

5. Update README.md with:
   - Project overview: what the edge controller does (3-4 sentences)
   - Architecture: which module handles what (brief list)
   - Prerequisites: Python 3.10+, Linux, serial port access
   - Installation: reference install.sh
   - Configuration: explain each section of intersection.json, 
     especially the signal_controller and timing sections
   - Development: how to run tests (pytest), how to use the simulator
   - Deployment: systemctl commands, log viewing (journalctl -u safecross-edge -f)
   - Troubleshooting: common issues (serial port permissions, SNMP 
     community string wrong, signal controller unreachable)
   - Safety: explain the safety guarantees (baseline always restored, 
     conflict monitor independence, ERROR state behavior)

6. Verify the full dependency chain works:
   pip install -r requirements.txt
   pytest -v
   mypy src/ --ignore-missing-imports
   python -m safecross.main --config config/default.json --debug
   (should start, log errors for missing serial port and SNMP host, 
   but not crash)
```

---

## Troubleshooting tips for Claude Code

If Claude Code produces code that doesn't work at a particular step:

**Protocol parsing issues (Step 2):**
> "The test_parse_two_frames test is failing — parse_frame is consuming the 
> entire buffer instead of returning bytes_consumed for just the first frame. 
> Fix parse_frame to return the exact number of bytes consumed including 
> SYNC + LENGTH + MSG_TYPE + PAYLOAD + CRC, so the caller can slice the 
> buffer and call again for the next frame."

**State machine issues (Step 6):**
> "test_baseline_always_restored is failing — after the preemption scenario, 
> the mock signal controller's PED_WALK_TIME is still at the extended value 
> instead of the baseline. Trace through _restore_baseline and make sure it's 
> called when transitioning from WALK_EXTENDED to RESTORING due to preemption."

**Async issues (Step 10):**
> "The main.py is hanging on startup. The phase_manager.monitor_loop is 
> blocking because it's doing synchronous SNMP calls inside an async function. 
> Make sure all pysnmp calls use the async transport (hlapi.v2c.asyncio or 
> equivalent) and are properly awaited."

**pysnmp API confusion:**
> "pysnmp's API is confusing you. For SNMPv2c with the maintained fork 
> (pysnmp-lextudio), use:
> from pysnmp.hlapi.v3arch.asyncio import *
> The key functions are get_cmd() and set_cmd(). Show me the snmp_get 
> implementation and I'll help debug it."
