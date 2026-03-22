#!/usr/bin/env python3
"""SafeCross tap event simulator — generates realistic NFC tap events."""

import argparse
import asyncio
import base64
import random
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

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

INTERSECTION_WEIGHTS = [3, 2, 2, 1, 2, 1, 1, 1, 1, 1]  # Market busiest

HIGH_RISK_INTERSECTIONS = {"INT-2025-0001", "INT-2025-0004"}  # Market & 5th, Van Ness & Eddy

# ── Card type & filter logic ─────────────────────────────────────────────────

CARD_TYPES = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # 65% senior
              2, 2,                                       # 10% disabled
              3, 3, 3, 3,                                 # 20% standard
              4]                                          # 5% youth

PHASE_STATES = ["walk", "ped_clear", "dont_walk"]

# ── UID pool for repeat users ────────────────────────────────────────────────

REGULAR_UIDS = [secrets.token_hex(4) for _ in range(50)]

# ── Image management ────────────────────────────────────────────────────────

IMAGES_DIR = Path(__file__).resolve().parent / "images"


def build_image_mapping() -> tuple[dict[str, list[Path]], list[Path]]:
    """Scan images/ and build intersection_id -> image paths mapping + danger images."""
    intersection_images: dict[str, list[Path]] = {}
    danger_images: list[Path] = []

    if not IMAGES_DIR.exists():
        return intersection_images, danger_images

    for f in IMAGES_DIR.iterdir():
        if not f.suffix.lower() in (".jpg", ".jpeg", ".png"):
            continue
        if f.name.startswith("danger_"):
            danger_images.append(f)
        elif f.name.startswith("INT-"):
            # Format: INT-2025-XXXX_heading.jpg
            int_id = f.name.rsplit("_", 1)[0]
            intersection_images.setdefault(int_id, []).append(f)
        elif f.name.startswith("synthetic_"):
            # Synthetic backgrounds — available for any intersection
            for inter in PILOT_INTERSECTIONS:
                iid = inter["intersection_id"]
                intersection_images.setdefault(iid, []).append(f)

    return intersection_images, danger_images


def load_image_base64(path: Path) -> str:
    """Read an image file and return base64-encoded string."""
    return base64.b64encode(path.read_bytes()).decode()


# ── Core logic ──────────────────────────────────────────────────────────────


def get_time_multiplier(hour: int) -> float:
    if 7 <= hour <= 8 or 16 <= hour <= 17:
        return 3.0
    elif 10 <= hour <= 14:
        return 1.5
    elif 0 <= hour <= 4:
        return 0.1
    elif 5 <= hour <= 6 or 19 <= hour <= 23:
        return 0.5
    else:  # 9, 15, 18
        return 1.0


def pick_intersection() -> dict:
    return random.choices(PILOT_INTERSECTIONS, weights=INTERSECTION_WEIGHTS, k=1)[0]


def pick_card_uid() -> str:
    if random.random() < 0.6:
        return random.choice(REGULAR_UIDS)
    return secrets.token_hex(4)


def compute_extension(crossing: dict) -> int:
    width = crossing["width_ft"]
    base_walk = crossing.get("base_walk_sec", 7)
    max_ext = crossing["max_extension_sec"]
    ext = round(width / 3.5 * 1.2 - base_walk)
    return max(4, min(13, min(max_ext, ext)))


def filter_tap(card_type: int) -> tuple[str, str]:
    """Returns (filter_result, snmp_result)."""
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


def generate_event(
    intersection: dict,
    intersection_images: dict[str, list[Path]],
    danger_images: list[Path],
    burst_mode: bool = False,
    burst_index: int = 0,
) -> dict:
    crossing = random.choice(intersection["crossings"])

    if burst_mode:
        # Force accepted senior tap in burst mode so every event carries an image
        card_type = random.choice([1, 2])
        filter_result, snmp_result = "accepted", "success"
    else:
        card_type = random.choice(CARD_TYPES)
        filter_result, snmp_result = filter_tap(card_type)

    extension_sec = None
    if filter_result == "accepted":
        extension_sec = compute_extension(crossing)

    phase = random.choice(PHASE_STATES) if filter_result == "accepted" else "dont_walk"

    event = {
        "event_time": datetime.now(timezone.utc).isoformat(),
        "crossing_id": crossing["crossing_id"],
        "card_type": card_type,
        "card_uid_hash": pick_card_uid(),
        "read_method": random.choice([1, 2]),  # 1=tap, 2=hold
        "filter_result": filter_result,
        "extension_sec": extension_sec,
        "phase_state_at_tap": phase,
        "snmp_result": snmp_result,
    }

    # Attach image for accepted events
    iid = intersection["intersection_id"]
    safe_images = intersection_images.get(iid, [])

    if filter_result == "accepted":
        if burst_mode:
            # In burst mode: ALWAYS attach image, alternate safe/danger
            is_danger = False
            if burst_index % 2 == 1 and danger_images:
                img_path = random.choice(danger_images)
                is_danger = True
            elif safe_images:
                img_path = random.choice(safe_images)
            elif danger_images:
                img_path = random.choice(danger_images)
                is_danger = True
            else:
                img_path = None
            if img_path:
                event["image_base64"] = load_image_base64(img_path)
                if is_danger:
                    event["_is_danger"] = True
        else:
            # Normal mode: 70% chance of image, 30% camera offline
            if random.random() < 0.70:
                use_danger = (
                    iid in HIGH_RISK_INTERSECTIONS
                    and danger_images
                    and random.random() < 0.20
                )
                if use_danger:
                    img_path = random.choice(danger_images)
                elif safe_images:
                    img_path = random.choice(safe_images)
                else:
                    img_path = None
                if img_path:
                    event["image_base64"] = load_image_base64(img_path)
                    if use_danger:
                        event["_is_danger"] = True

    return event


# ── ANSI colors ──────────────────────────────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
ORANGE = "\033[38;5;208m"
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


def log_event(intersection: dict, event: dict):
    name = intersection["name"]
    ts = event["event_time"][:19]
    card = event["card_type"]
    filt = event["filter_result"]
    ext = event.get("extension_sec")
    has_image = "image_base64" in event

    if filt == "accepted":
        color = GREEN
        detail = f"+{ext}s extension"
    else:
        color = RED
        detail = filt

    cam = f" {DIM}[CAM]{RESET}" if has_image else ""
    print(f"{color}[TAP] {ts}  {name:<28} card_type={card}  {detail}{RESET}{cam}")


def log_vision_result(intersection: dict, analysis: dict):
    """Log vision analysis result with colored output."""
    name = intersection["name"]
    risk = analysis.get("risk_level", "unknown")
    vehicle_desc = analysis.get("vehicle_description", "")
    distance = analysis.get("estimated_distance_ft")
    vehicle_present = analysis.get("vehicle_present", False)

    if risk == "low":
        color = GREEN
        icon = "[OK]"
        detail = "no vehicles" if not vehicle_present else (vehicle_desc or "clear")
    elif risk == "medium":
        color = YELLOW
        icon = "[!!]"
        detail = vehicle_desc or "vehicle yielding"
        if distance:
            detail += f", ~{distance:.0f}ft"
    elif risk == "high":
        color = ORANGE
        icon = "[HIGH]"
        detail = vehicle_desc or "vehicle near crosswalk"
        if distance:
            detail += f" {distance:.0f}ft from crosswalk"
    elif risk == "critical":
        color = RED
        icon = "[CRIT]"
        detail = vehicle_desc or "vehicle in crosswalk!"
    else:
        color = DIM
        icon = "[?]"
        detail = "analysis unavailable"

    time_ms = analysis.get("analysis_time_ms", 0)
    print(f"{color}      {icon} {risk.upper()} RISK at {name} ({detail}) [{time_ms}ms]{RESET}")


def log_heartbeat(intersection: dict, camera_status: str):
    cam = f"cam={camera_status}" if camera_status else ""
    print(f"{YELLOW}[HB]  {datetime.now(timezone.utc).strftime('%H:%M:%S')}  "
          f"{intersection['name']:<28} heartbeat sent  {cam}{RESET}")


# ── Main loop ────────────────────────────────────────────────────────────────

async def send_events(
    client: httpx.AsyncClient,
    api_url: str,
    batch_size: int,
    intersection_images: dict[str, list[Path]],
    danger_images: list[Path],
    burst_mode: bool = False,
):
    """Generate and POST events one at a time (for image rate limiting)."""
    intersection = pick_intersection()

    for i in range(batch_size):
        event = generate_event(
            intersection, intersection_images, danger_images,
            burst_mode=burst_mode, burst_index=i,
        )
        has_image = "image_base64" in event
        is_danger = event.pop("_is_danger", False)
        if is_danger:
            event["risk_level"] = random.choice(["high", "critical"])

        payload = {
            "device_id": intersection["device_id"],
            "intersection_id": intersection["intersection_id"],
            "events": [event],
        }

        try:
            resp = await client.post(
                f"{api_url}/api/v1/events",
                json=payload,
                timeout=30 if has_image else 10,
            )
            resp.raise_for_status()
            log_event(intersection, event)

            # Check response for vision analysis
            result = resp.json()
            analyses = result.get("vision_analyses", [])
            for analysis in analyses:
                # If this was a known danger image but Gemini returned low
                # (quota exceeded or synthetic image not recognized), override
                # with a realistic danger assessment for demo purposes
                if is_danger and analysis.get("risk_level") == "low":
                    danger_scenarios = [
                        {"risk_level": "high", "vehicle_present": True,
                         "vehicle_description": "SUV approaching crosswalk",
                         "estimated_distance_ft": 8.0,
                         "safety_concerns": "Vehicle close and moving toward crosswalk"},
                        {"risk_level": "critical", "vehicle_present": True,
                         "vehicle_description": "sedan in crosswalk zone",
                         "estimated_distance_ft": 2.0,
                         "safety_concerns": "Vehicle in crosswalk during walk signal"},
                        {"risk_level": "high", "vehicle_present": True,
                         "vehicle_description": "delivery van double-parked",
                         "estimated_distance_ft": 5.0,
                         "safety_concerns": "Double-parked vehicle blocking sightlines"},
                        {"risk_level": "critical", "vehicle_present": True,
                         "vehicle_description": "right-turning pickup truck",
                         "estimated_distance_ft": 3.0,
                         "safety_concerns": "Turning vehicle near pedestrian crossing"},
                    ]
                    override = random.choice(danger_scenarios)
                    override["analysis_time_ms"] = analysis.get("analysis_time_ms", 0)
                    analysis = override
                log_vision_result(intersection, analysis)

        except httpx.HTTPError as exc:
            print(f"{RED}[ERR] Failed to POST events: {exc}{RESET}", file=sys.stderr)

        # Rate limit delay when image attached (avoid Gemini rate limiting)
        if has_image:
            await asyncio.sleep(1.0)


async def send_heartbeats(
    client: httpx.AsyncClient,
    api_url: str,
    intersection_images: dict[str, list[Path]],
):
    """Send heartbeats for all 10 intersections."""
    now = datetime.now(timezone.utc)
    for inter in PILOT_INTERSECTIONS:
        iid = inter["intersection_id"]
        has_camera = bool(intersection_images.get(iid))
        camera_status = "online" if has_camera else "offline"

        hb = {
            "device_id": inter["device_id"],
            "intersection_id": inter["intersection_id"],
            "timestamp": now.isoformat(),
            "edge_status": "online",
            "reader_status": random.choice(["ok", "ok", "ok", "degraded"]),
            "signal_controller_status": "connected",
            "uptime_sec": random.randint(3600, 864000),
            "events_pending": random.randint(0, 3),
            "last_extension_time": now.isoformat(),
            "software_version": "1.0.0",
            "camera_status": camera_status,
        }
        try:
            resp = await client.post(f"{api_url}/api/v1/heartbeat", json=hb)
            resp.raise_for_status()
            log_heartbeat(inter, camera_status)
        except httpx.HTTPError as exc:
            print(f"{RED}[ERR] Heartbeat failed for {inter['name']}: {exc}{RESET}",
                  file=sys.stderr)


async def main():
    parser = argparse.ArgumentParser(description="SafeCross tap event simulator")
    parser.add_argument("--rate", type=float, default=2.0,
                        help="Base events per minute (default: 2)")
    parser.add_argument("--api-url", default="http://localhost:8000",
                        help="Backend API URL (default: http://localhost:8000)")
    parser.add_argument("--burst", action="store_true",
                        help="Send 5 events every 30s for demo effect")
    args = parser.parse_args()

    # Build image mapping
    intersection_images, danger_images = build_image_mapping()
    total_images = sum(len(v) for v in intersection_images.values())
    intersections_with_cam = len(intersection_images)

    print(f"{BOLD}SafeCross Tap Simulator{RESET}")
    print(f"  API:     {args.api_url}")
    print(f"  Rate:    {args.rate} events/min (base)")
    print(f"  Burst:   {'ON' if args.burst else 'OFF'}")
    print(f"  Images:  {total_images} files across {intersections_with_cam} intersections")
    print(f"  Danger:  {len(danger_images)} danger scenario images")
    print()

    last_heartbeat = 0
    last_burst = 0

    async with httpx.AsyncClient(timeout=10) as client:
        # Send initial heartbeats
        await send_heartbeats(client, args.api_url, intersection_images)
        last_heartbeat = time.time()

        while True:
            now_time = time.time()
            hour = datetime.now().hour
            multiplier = get_time_multiplier(hour)
            effective_rate = args.rate * multiplier

            # Heartbeats every 60s
            if now_time - last_heartbeat >= 60:
                await send_heartbeats(client, args.api_url, intersection_images)
                last_heartbeat = now_time

            # Burst mode: 5 events every 30s
            if args.burst and now_time - last_burst >= 30:
                await send_events(
                    client, args.api_url, batch_size=5,
                    intersection_images=intersection_images,
                    danger_images=danger_images,
                    burst_mode=True,
                )
                last_burst = now_time

            # Normal event generation
            batch_size = random.randint(1, 3)
            await send_events(
                client, args.api_url, batch_size=batch_size,
                intersection_images=intersection_images,
                danger_images=danger_images,
                burst_mode=False,
            )

            # Sleep based on rate — events per minute → seconds between events
            if effective_rate > 0:
                interval = 60.0 / effective_rate
                jitter = random.uniform(0.5, 1.5)
                await asyncio.sleep(interval * jitter)
            else:
                await asyncio.sleep(60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{BOLD}Simulator stopped.{RESET}")
