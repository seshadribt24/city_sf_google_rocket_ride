# SafeCross Edge Controller

DIN-rail-mounted ARM edge controller software for the SafeCross accessible pedestrian signal extension system. It receives NFC card events from a reader over RS-485, decides whether to extend the pedestrian walk phase, sends NTCIP/SNMP commands to the traffic signal controller, and **always restores baseline timing** afterward. The system is additive-only: its absence means no extensions, not broken signals.

## Architecture

```
NFC Reader ──RS-485──► reader_interface/ ──► decision/ ──► signal_interface/ ──► Signal Controller
                        (protocol, listener)   (timing,     (safety, phase_manager,   (SNMP SET)
                                                cooldown)    snmp_client)
                                                     │
                                              logging_events/ ──► Cloud API
                                              device_management/ (config, heartbeat, OTA)
```

| Package | Responsibility |
|---|---|
| `src/reader_interface/` | RS-485 serial I/O, frame protocol (CRC-16/MODBUS), message parsing |
| `src/signal_interface/` | NTCIP 1202 OIDs, SNMP client, safety validation, **PhaseManager state machine** |
| `src/decision/` | Walk-time extension calculation, cooldown/dedup/rate-limiting |
| `src/logging_events/` | SQLite event store, cloud forwarder |
| `src/device_management/` | Config loading/validation, heartbeat reporting, OTA updates |
| `src/main.py` | Orchestrator — wires everything together, handles shutdown |

## Prerequisites

- Python 3.10+
- Linux (target: ARM SBC with DIN-rail mount) or Windows for development
- Serial port access (RS-485 to NFC reader)
- Network access to traffic signal controller (SNMP UDP/161)
- `pyserial`, `pysnmp-lextudio`, `aiosqlite`, `aiohttp`, `jsonschema` (see `requirements.txt`)

## Installation

### Development

```bash
pip install -r requirements.txt
pytest tests/ -v
```

### Production

```bash
sudo bash scripts/install.sh
```

This creates the `safecross` system user, installs dependencies into a venv at `/opt/safecross/venv`, copies the example config, installs the systemd service, and enables it. It does **not** start the service — you must edit the config first.

## Configuration

Copy `config/intersection.example.json` to `/etc/safecross/intersection.json` and edit for your intersection.

### Key sections

| Section | Description |
|---|---|
| `intersection_id` | Unique ID for this intersection (e.g., `INT-2025-0042`) |
| `location` | Name, latitude, longitude |
| `crossings[]` | Per-crosswalk: width, signal phase, base walk/clearance times, extension bounds |
| `signal_controller` | IP address, SNMP port, community strings, controller model |
| `nfc_reader` | Serial port path, baud rate, reader ID |
| `timing_rules` | Cooldown between extensions, eligible card types, max per cycle |
| `cloud` | API URL, mTLS cert paths, heartbeat/event flush intervals |
| `ota` | Update manifest URL, check interval, auto-apply flag |

**signal_controller**: Set `ip_address` to the controller's management IP. Community strings (`snmp_community_read`/`snmp_community_write`) must match the controller's SNMP configuration. The `controller_model` determines OID mappings (`econolite_cobalt` or `mccain`).

**timing_rules**: `cooldown_sec` (default 120) prevents rapid re-extensions at the same crossing. `eligible_card_types` controls which NFC cards trigger extensions (default: `SENIOR_RTC`, `DISABLED_RTC`).

## Development

### Running tests

```bash
pytest tests/ -v
```

153 tests covering protocol parsing, safety validation, state machine lifecycle, timing calculations, cooldown logic, and event storage.

### Type checking

```bash
mypy src/ --ignore-missing-imports
```

### Reader simulator

For testing without physical NFC hardware:

```bash
# Basic: send senior card taps over a loopback serial port
python scripts/simulate_reader.py --port loop:// --card-type senior --count 5

# Burst test for cooldown/dedup
python scripts/simulate_reader.py --port /dev/ttyUSB0 --burst 10 --same-uid

# Random card types at fixed intervals
python scripts/simulate_reader.py --port /dev/ttyUSB0 --card-type random --interval 20
```

### Running the controller (development)

```bash
python src/main.py --config config/intersection.example.json --debug
```

This will log errors for missing serial port and unreachable SNMP host, but won't crash — the system is designed to start degraded and recover when hardware becomes available.

## Deployment

```bash
# Start
sudo systemctl start safecross-edge

# Status
sudo systemctl status safecross-edge

# Logs (live)
journalctl -u safecross-edge -f

# Reload config (without restart)
sudo systemctl reload safecross-edge   # sends SIGHUP

# Restart
sudo systemctl restart safecross-edge
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `RS-485 open failed` | Serial port not found or no permission | Check `serial_port` in config; add user to `dialout` group: `sudo usermod -aG dialout safecross` |
| `Cannot reach signal controller` | Wrong IP, SNMP not enabled, or firewall | Verify with `snmpget -v2c -c public 10.0.1.100 1.3.6.1.4.1.1206.4.2.1.1.1.0` |
| `SNMP SET error-status` | Wrong write community string | Check `snmp_community_write` matches controller config |
| `Config validation failed` | Invalid intersection.json | Compare against `config/schema.json`; check required fields |
| `PhaseManager stuck in ERROR` | Controller unresponsive during restore | Controller will auto-recover when SNMP responds; check physical connection |
| `rate_limited` in logs | Extension requested too soon after previous | Expected behavior — `cooldown_sec` enforces minimum interval |

## Safety Guarantees

1. **Baseline always restored**: After every extension (success, timeout, preemption, or error), the original walk time is restored via SNMP SET with verification and 3 retries.

2. **Fail-safe ERROR state**: If baseline restoration fails after 3 retries, the system enters ERROR state and probes the controller every 30 seconds until it can confirm the baseline is correct.

3. **Preemption respected**: Emergency vehicle preemption is polled every 1 second. If preemption activates during an extension, the system immediately transitions to RESTORING.

4. **Additive-only**: The edge controller only extends walk times, never shortens them. Its absence (power loss, crash, network failure) means pedestrians get standard timing — the signal controller's conflict monitor is never bypassed.

5. **Safety validation layer**: Every SNMP SET passes through `safety.check_safety()` which enforces: OID allowlist, preemption check, baseline floor, absolute maximum, and rate limiting.

6. **Graceful shutdown**: On SIGTERM, the controller waits up to 30 seconds for any in-progress extension to be restored before exiting.
