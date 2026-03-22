#!/usr/bin/env python3
"""Simulated NFC reader — sends card-tap and heartbeat frames over RS-485.

Standalone script that does NOT import from the safecross package.
Protocol constants and CRC logic are inlined for portability.

Usage examples:
    # Basic: send senior taps every 15-60s on /dev/ttyUSB0
    python scripts/simulate_reader.py --port /dev/ttyUSB0

    # Burst test: 5 rapid taps 1s apart with same UID (dedup testing)
    python scripts/simulate_reader.py --port COM3 --burst 5 --same-uid

    # Specific card type, fixed interval
    python scripts/simulate_reader.py --port /dev/ttyS1 --card-type disabled --interval 30
"""

from __future__ import annotations

import argparse
import os
import random
import struct
import sys
import threading
import time
from datetime import datetime

import serial

# ---------------------------------------------------------------------------
# Protocol constants (inlined — no safecross dependency)
# ---------------------------------------------------------------------------

SYNC = b"\xAA\x55"

MSG_CARD_TAP: int = 0x01
MSG_HEARTBEAT: int = 0x02

CARD_TYPE_SENIOR_RTC: int = 0x01
CARD_TYPE_DISABLED_RTC: int = 0x02
CARD_TYPE_STANDARD: int = 0x03
CARD_TYPE_YOUTH: int = 0x04
CARD_TYPE_DESFIRE_DETECTED: int = 0x05

CARD_TYPE_MAP: dict[str, int] = {
    "senior": CARD_TYPE_SENIOR_RTC,
    "disabled": CARD_TYPE_DISABLED_RTC,
    "standard": CARD_TYPE_STANDARD,
    "youth": CARD_TYPE_YOUTH,
    "desfire": CARD_TYPE_DESFIRE_DETECTED,
}

CARD_TYPE_NAMES: dict[int, str] = {v: k.upper() for k, v in CARD_TYPE_MAP.items()}

READ_METHOD_ANY_DESFIRE: int = 3  # default read method


# ---------------------------------------------------------------------------
# CRC-16/MODBUS (inlined)
# ---------------------------------------------------------------------------

def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


# ---------------------------------------------------------------------------
# Frame builder
# ---------------------------------------------------------------------------

def build_frame(msg_type: int, payload: bytes) -> bytes:
    """Build a complete RS-485 frame.

    Format: SYNC(2) | LENGTH(1) | MSG_TYPE(1) | PAYLOAD(N) | CRC16(2)
    LENGTH = len(payload) + 2  (MSG_TYPE byte + LENGTH byte itself)
    CRC covers: LENGTH + MSG_TYPE + PAYLOAD
    """
    length = len(payload) + 2
    body = bytes([length, msg_type]) + payload
    crc = crc16_modbus(body)
    return SYNC + body + struct.pack("<H", crc)


def build_card_tap(
    card_type: int,
    uid: bytes,
    timestamp_ms: int,
    read_method: int = READ_METHOD_ANY_DESFIRE,
) -> bytes:
    """Build a card-tap frame payload."""
    payload = struct.pack(
        "<BB",
        card_type,
        len(uid),
    ) + uid + struct.pack("<IB", timestamp_ms, read_method)
    return build_frame(MSG_CARD_TAP, payload)


def build_heartbeat(
    status: int,
    uptime_sec: int,
    tap_count: int,
    temperature_c: float,
) -> bytes:
    """Build a reader heartbeat frame payload."""
    temp_raw = int(temperature_c * 10)  # 0.1°C units, int16
    payload = struct.pack("<BIIH", status, uptime_sec, tap_count, temp_raw & 0xFFFF)
    return build_frame(MSG_HEARTBEAT, payload)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_str() -> str:
    return datetime.now().strftime("%H:%M:%S")


def random_uid(length: int = 7) -> bytes:
    return os.urandom(length)


# ---------------------------------------------------------------------------
# Heartbeat background thread
# ---------------------------------------------------------------------------

class HeartbeatSender:
    def __init__(self, ser: serial.Serial, interval: float = 10.0) -> None:
        self._ser = ser
        self._interval = interval
        self._start = time.monotonic()
        self._tap_count = 0
        self._running = True

    def increment_taps(self) -> None:
        self._tap_count += 1

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        while self._running:
            time.sleep(self._interval)
            if not self._running:
                break
            uptime = int(time.monotonic() - self._start)
            frame = build_heartbeat(
                status=0x00,
                uptime_sec=uptime,
                tap_count=self._tap_count,
                temperature_c=42.5,
            )
            try:
                self._ser.write(frame)
                print(
                    f"[{now_str()}] TX heartbeat: status=OK "
                    f"uptime={uptime}s taps={self._tap_count}"
                )
            except Exception as exc:
                print(f"[{now_str()}] Heartbeat send error: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Simulated NFC reader for SafeCross testing",
    )
    p.add_argument("--port", required=True, help="Serial port path")
    p.add_argument("--baud", type=int, default=115200, help="Baud rate")
    p.add_argument(
        "--card-type",
        choices=["senior", "disabled", "standard", "youth", "desfire", "random"],
        default="senior",
        help="Card type to simulate (default: senior)",
    )
    p.add_argument(
        "--interval", type=float, default=0,
        help="Seconds between taps (0 = random 15-60, default: 0)",
    )
    p.add_argument(
        "--burst", type=int, default=0,
        help="Send N rapid taps 1s apart, then exit",
    )
    p.add_argument(
        "--same-uid", action="store_true",
        help="Reuse the same UID for all taps (dedup testing)",
    )
    p.add_argument(
        "--count", type=int, default=0,
        help="Total taps to send (0 = infinite, default: 0)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    print(f"=== SafeCross Reader Simulator ===")
    print(f"  Port:      {args.port}")
    print(f"  Baud:      {args.baud}")
    print(f"  Card type: {args.card_type}")
    if args.burst:
        print(f"  Mode:      burst ({args.burst} taps, 1s apart)")
    elif args.interval:
        print(f"  Interval:  {args.interval}s")
    else:
        print(f"  Interval:  random 15-60s")
    if args.same_uid:
        print(f"  UID mode:  fixed (same UID for all taps)")
    if args.count:
        print(f"  Count:     {args.count}")
    print()

    # Open serial port (serial_for_url supports loop://, spy://, etc.)
    ser = serial.serial_for_url(args.port, baudrate=args.baud, timeout=1)
    print(f"[{now_str()}] Serial port opened: {args.port} @ {args.baud}")

    # Start heartbeat thread
    hb = HeartbeatSender(ser)
    hb_thread = threading.Thread(target=hb.run, daemon=True)
    hb_thread.start()

    # Fixed UID if requested
    fixed_uid = random_uid() if args.same_uid else None

    tap_num = 0
    boot_time = time.monotonic()

    try:
        total = args.burst if args.burst else args.count

        while True:
            # Pick card type
            if args.card_type == "random":
                card_type = random.choice(list(CARD_TYPE_MAP.values()))
            else:
                card_type = CARD_TYPE_MAP[args.card_type]

            # Pick UID
            uid = fixed_uid if fixed_uid else random_uid()

            # Timestamp (ms since boot)
            ts_ms = int((time.monotonic() - boot_time) * 1000)

            # Build and send
            frame = build_card_tap(card_type, uid, ts_ms)
            ser.write(frame)
            tap_num += 1
            hb.increment_taps()

            type_name = CARD_TYPE_NAMES.get(card_type, f"0x{card_type:02X}")
            uid_hex = uid.hex().upper()
            print(
                f"[{now_str()}] TX tap #{tap_num}: "
                f"type={type_name} uid={uid_hex[:8]}... method={READ_METHOD_ANY_DESFIRE}"
            )

            # Check if done
            if total and tap_num >= total:
                print(f"\n[{now_str()}] Sent {tap_num} taps, exiting")
                break

            # Wait
            if args.burst:
                time.sleep(1.0)
            elif args.interval:
                time.sleep(args.interval)
            else:
                delay = random.uniform(15, 60)
                time.sleep(delay)

    except KeyboardInterrupt:
        print(f"\n[{now_str()}] Interrupted — sent {tap_num} taps total")
    finally:
        hb.stop()
        ser.close()
        print(f"[{now_str()}] Serial port closed")


if __name__ == "__main__":
    main()
