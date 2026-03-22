#!/usr/bin/env python3
"""Seed 30 days of historical tap events directly into SQLite."""

import json
import random
import secrets
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Resolve DB path (same as backend) ────────────────────────────────────────

DB_PATH = Path(__file__).resolve().parent.parent / "safecross.db"

# ── Seed data (mirrored from backend) ────────────────────────────────────────

PILOT_INTERSECTIONS = [
    {"intersection_id": "INT-2025-0001", "device_id": "EDGE-0001", "name": "Market St & 5th St", "crossings": [{"crossing_id": "NS", "width_ft": 72, "base_walk_sec": 7, "max_extension_sec": 13}, {"crossing_id": "EW", "width_ft": 48, "base_walk_sec": 7, "max_extension_sec": 8}]},
    {"intersection_id": "INT-2025-0002", "device_id": "EDGE-0002", "name": "Geary Blvd & Masonic Ave", "crossings": [{"crossing_id": "NS", "width_ft": 80, "max_extension_sec": 13}, {"crossing_id": "EW", "width_ft": 60, "max_extension_sec": 10}]},
    {"intersection_id": "INT-2025-0003", "device_id": "EDGE-0003", "name": "Mission St & 16th St", "crossings": [{"crossing_id": "NS", "width_ft": 65, "max_extension_sec": 11}, {"crossing_id": "EW", "width_ft": 50, "max_extension_sec": 8}]},
    {"intersection_id": "INT-2025-0004", "device_id": "EDGE-0004", "name": "Van Ness Ave & Eddy St", "crossings": [{"crossing_id": "NS", "width_ft": 95, "max_extension_sec": 13}, {"crossing_id": "EW", "width_ft": 45, "max_extension_sec": 8}]},
    {"intersection_id": "INT-2025-0005", "device_id": "EDGE-0005", "name": "Stockton St & Clay St", "crossings": [{"crossing_id": "NS", "width_ft": 50, "max_extension_sec": 8}, {"crossing_id": "EW", "width_ft": 50, "max_extension_sec": 8}]},
    {"intersection_id": "INT-2025-0006", "device_id": "EDGE-0006", "name": "3rd St & Evans Ave", "crossings": [{"crossing_id": "NS", "width_ft": 70, "max_extension_sec": 12}, {"crossing_id": "EW", "width_ft": 55, "max_extension_sec": 9}]},
    {"intersection_id": "INT-2025-0007", "device_id": "EDGE-0007", "name": "Taraval St & 19th Ave", "crossings": [{"crossing_id": "NS", "width_ft": 90, "max_extension_sec": 13}, {"crossing_id": "EW", "width_ft": 45, "max_extension_sec": 7}]},
    {"intersection_id": "INT-2025-0008", "device_id": "EDGE-0008", "name": "Polk St & Turk St", "crossings": [{"crossing_id": "NS", "width_ft": 55, "max_extension_sec": 9}, {"crossing_id": "EW", "width_ft": 50, "max_extension_sec": 8}]},
    {"intersection_id": "INT-2025-0009", "device_id": "EDGE-0009", "name": "Ocean Ave & Geneva Ave", "crossings": [{"crossing_id": "NS", "width_ft": 75, "max_extension_sec": 12}, {"crossing_id": "EW", "width_ft": 60, "max_extension_sec": 10}]},
    {"intersection_id": "INT-2025-0010", "device_id": "EDGE-0010", "name": "Sutter St & Larkin St", "crossings": [{"crossing_id": "NS", "width_ft": 55, "max_extension_sec": 9}, {"crossing_id": "EW", "width_ft": 50, "max_extension_sec": 8}]},
]

INTERSECTION_WEIGHTS = [3, 2, 2, 1, 2, 1, 1, 1, 1, 1]

# High-risk intersections get weighted toward high/critical
HIGH_RISK_INTERSECTIONS = {"INT-2025-0004", "INT-2025-0001"}  # Van Ness & Eddy, Market & 5th

def pick_risk_level(intersection_id: str) -> str:
    """75% low, 15% medium, 8% high, 2% critical — weighted higher for risky intersections."""
    r = random.random()
    if intersection_id in HIGH_RISK_INTERSECTIONS:
        # Double the high/critical rates
        if r < 0.55:
            return "low"
        elif r < 0.75:
            return "medium"
        elif r < 0.91:
            return "high"
        else:
            return "critical"
    else:
        if r < 0.75:
            return "low"
        elif r < 0.90:
            return "medium"
        elif r < 0.98:
            return "high"
        else:
            return "critical"

CARD_TYPES = [1]*13 + [2]*2 + [3]*4 + [4]*1  # 65/10/20/5

PHASE_STATES = ["walk", "ped_clear", "dont_walk"]

REGULAR_UIDS = [secrets.token_hex(4) for _ in range(50)]


def get_time_multiplier(hour: int) -> float:
    if 7 <= hour <= 8 or 16 <= hour <= 17:
        return 3.0
    elif 10 <= hour <= 14:
        return 1.5
    elif 0 <= hour <= 4:
        return 0.1
    elif 5 <= hour <= 6 or 19 <= hour <= 23:
        return 0.5
    else:
        return 1.0


def compute_extension(crossing: dict) -> int:
    width = crossing["width_ft"]
    base_walk = crossing.get("base_walk_sec", 7)
    max_ext = crossing["max_extension_sec"]
    ext = round(width / 3.5 * 1.2 - base_walk)
    return max(4, min(13, min(max_ext, ext)))


def filter_tap(card_type: int) -> tuple[str, str]:
    if card_type in (3, 4):
        return "rejected_card_type", "not_sent"
    roll = random.random()
    if roll < 0.90:
        return "accepted", "success"
    elif roll < 0.95:
        return "rejected_cooldown", "not_sent"
    elif roll < 0.98:
        return "rejected_clearance", "not_sent"
    else:
        return "rejected_duplicate", "not_sent"


def pick_card_uid() -> str:
    if random.random() < 0.6:
        return random.choice(REGULAR_UIDS)
    return secrets.token_hex(4)


def generate_events_for_day(day: datetime) -> list[tuple]:
    """Generate events for a single day, returning DB rows."""
    rows = []

    # Distribute events across hours based on time multiplier
    # Target: ~50-80 events/day → base ~3 per hour, scaled by multiplier
    for hour in range(24):
        mult = get_time_multiplier(hour)
        # Base 2.5 events/hour * multiplier, with some randomness
        n_events = max(0, int(random.gauss(2.5 * mult, 0.8 * mult)))

        for _ in range(n_events):
            intersection = random.choices(
                PILOT_INTERSECTIONS, weights=INTERSECTION_WEIGHTS, k=1
            )[0]
            crossing = random.choice(intersection["crossings"])
            card_type = random.choice(CARD_TYPES)
            filter_result, snmp_result = filter_tap(card_type)

            extension_sec = None
            if filter_result == "accepted":
                extension_sec = compute_extension(crossing)

            phase = (random.choice(PHASE_STATES)
                     if filter_result == "accepted" else "dont_walk")

            # Random minute/second within the hour
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            event_time = day.replace(
                hour=hour, minute=minute, second=second, microsecond=0,
                tzinfo=timezone.utc,
            )

            risk_level = pick_risk_level(intersection["intersection_id"])

            rows.append((
                intersection["intersection_id"],
                intersection["device_id"],
                event_time.isoformat(),
                crossing["crossing_id"],
                card_type,
                pick_card_uid(),
                random.choice([1, 2]),
                filter_result,
                extension_sec,
                phase,
                snmp_result,
                risk_level,
            ))

    return rows


def ensure_tables(db: sqlite3.Connection):
    """Create tables if they don't exist (mirrors backend init_db)."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS tap_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intersection_id TEXT NOT NULL,
            device_id TEXT NOT NULL,
            event_time TEXT NOT NULL,
            crossing_id TEXT NOT NULL,
            card_type INTEGER NOT NULL,
            card_uid_hash TEXT NOT NULL,
            read_method INTEGER NOT NULL,
            filter_result TEXT NOT NULL,
            extension_sec INTEGER,
            phase_state_at_tap TEXT NOT NULL,
            snmp_result TEXT NOT NULL,
            risk_level TEXT DEFAULT 'unknown',
            vision_analysis TEXT,
            image_path TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS heartbeats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            intersection_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            edge_status TEXT NOT NULL,
            reader_status TEXT NOT NULL,
            signal_controller_status TEXT NOT NULL,
            uptime_sec INTEGER NOT NULL,
            events_pending INTEGER NOT NULL,
            last_extension_time TEXT,
            software_version TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS intersections (
            intersection_id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            name TEXT NOT NULL,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            crossings TEXT NOT NULL
        )
    """)
    # Migrate: add vision columns if missing
    existing_cols = {row[1] for row in db.execute("PRAGMA table_info(tap_events)").fetchall()}
    for col, typedef in [
        ("risk_level", "TEXT DEFAULT 'unknown'"),
        ("vision_analysis", "TEXT"),
        ("image_path", "TEXT"),
    ]:
        if col not in existing_cols:
            db.execute(f"ALTER TABLE tap_events ADD COLUMN {col} {typedef}")

    # Seed intersections if empty
    count = db.execute("SELECT COUNT(*) FROM intersections").fetchone()[0]
    if count == 0:
        for i in PILOT_INTERSECTIONS:
            # Need lat/lng from the full seed data
            FULL_DATA = {
                "INT-2025-0001": (37.7837, -122.4073),
                "INT-2025-0002": (37.7842, -122.4462),
                "INT-2025-0003": (37.7650, -122.4194),
                "INT-2025-0004": (37.7836, -122.4213),
                "INT-2025-0005": (37.7934, -122.4082),
                "INT-2025-0006": (37.7432, -122.3872),
                "INT-2025-0007": (37.7434, -122.4756),
                "INT-2025-0008": (37.7824, -122.4186),
                "INT-2025-0009": (37.7235, -122.4419),
                "INT-2025-0010": (37.7876, -122.4182),
            }
            lat, lng = FULL_DATA[i["intersection_id"]]
            db.execute(
                "INSERT INTO intersections VALUES (?, ?, ?, ?, ?, ?)",
                (i["intersection_id"], i["device_id"], i["name"],
                 lat, lng, json.dumps(i["crossings"])),
            )
    db.commit()


def main():
    print(f"Database: {DB_PATH}")

    db = sqlite3.connect(str(DB_PATH))
    ensure_tables(db)

    # Check existing event count
    existing = db.execute("SELECT COUNT(*) FROM tap_events").fetchone()[0]
    print(f"Existing events: {existing}")

    now = datetime.now(timezone.utc)
    total_inserted = 0
    all_rows = []

    for days_ago in range(30, 0, -1):
        day = now - timedelta(days=days_ago)
        day_rows = generate_events_for_day(day)
        all_rows.extend(day_rows)

    # Bulk insert
    db.executemany(
        """INSERT INTO tap_events
           (intersection_id, device_id, event_time, crossing_id, card_type,
            card_uid_hash, read_method, filter_result, extension_sec,
            phase_state_at_tap, snmp_result, risk_level)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        all_rows,
    )
    db.commit()
    total_inserted = len(all_rows)

    # Stats
    total = db.execute("SELECT COUNT(*) FROM tap_events").fetchone()[0]
    accepted = db.execute(
        "SELECT COUNT(*) FROM tap_events WHERE filter_result = 'accepted'"
    ).fetchone()[0]
    distinct_days = db.execute(
        "SELECT COUNT(DISTINCT DATE(event_time)) FROM tap_events"
    ).fetchone()[0]

    db.close()

    print(f"\nInserted {total_inserted} historical events across 30 days")
    print(f"Total events in DB: {total}")
    print(f"Accepted taps: {accepted} ({accepted/total*100:.1f}%)")
    print(f"Distinct days: {distinct_days}")
    print("Done!")


if __name__ == "__main__":
    main()
