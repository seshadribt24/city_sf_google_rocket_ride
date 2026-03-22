#!/usr/bin/env python3
"""Download Google Street View images for SF intersections."""

import os
import sys
import requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
    # Also try loading from project root .env
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

IMAGES_DIR = Path(__file__).resolve().parent / "images"

# Each intersection has curated headings that face the actual crosswalks
# (looking down the street toward the crossing) instead of blind cardinal directions.
# Format: (id, name, lat, lng, [headings])
INTERSECTIONS = [
    # Market runs SW-NE (~65°); 5th runs N-S. Crosswalks at ~155° and ~335° (across Market), ~65° and ~245° (across 5th)
    ("INT-2025-0001", "Market St & 5th St", 37.7837, -122.4073, [155, 335]),
    # Geary runs E-W; Masonic runs N-S. Look across Geary (~0°, ~180°) and across Masonic (~90°, ~270°)
    ("INT-2025-0002", "Geary Blvd & Masonic Ave", 37.7842, -122.4462, [0, 180]),
    # Mission runs NW-SE (~145°); 16th runs E-W. Look across Mission (~55°, ~235°)
    ("INT-2025-0003", "Mission St & 16th St", 37.7650, -122.4194, [55, 235]),
    # Van Ness runs N-S; Eddy runs E-W. Look across Van Ness (~90°, ~270°)
    ("INT-2025-0004", "Van Ness Ave & Eddy St", 37.7836, -122.4213, [90, 270]),
    # Stockton runs N-S; Clay runs E-W. Look across Stockton (~90°, ~270°)
    ("INT-2025-0005", "Stockton St & Clay St", 37.7934, -122.4082, [90, 270]),
    # 3rd runs N-S; Evans runs E-W. Look across 3rd (~90°, ~270°)
    ("INT-2025-0006", "3rd St & Evans Ave", 37.7432, -122.3872, [90, 270]),
    # Taraval runs E-W; 19th Ave runs N-S. Look across 19th Ave (~90°, ~270°)
    ("INT-2025-0007", "Taraval St & 19th Ave", 37.7434, -122.4756, [90, 270]),
    # Polk runs N-S; Turk runs E-W. Look across Polk (~90°, ~270°)
    ("INT-2025-0008", "Polk St & Turk St", 37.7824, -122.4186, [90, 270]),
    # Ocean runs E-W; Geneva runs SE (~135°). Look across the intersection (~45°, ~225°)
    ("INT-2025-0009", "Ocean Ave & Geneva Ave", 37.7235, -122.4419, [45, 225]),
    # Sutter runs E-W; Larkin runs N-S. Look across Larkin (~90°, ~270°)
    ("INT-2025-0010", "Sutter St & Larkin St", 37.7876, -122.4182, [90, 270]),
]

BASE_URL = (
    "https://maps.googleapis.com/maps/api/streetview"
    "?size=640x480&location={lat},{lng}&heading={heading}"
    "&pitch=-10&fov=90&source=outdoor&key={key}"
)


def main():
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    total = sum(len(headings) for *_, headings in INTERSECTIONS)
    downloaded = 0

    for int_id, name, lat, lng, headings in INTERSECTIONS:
        for heading in headings:
            filename = f"{int_id}_{heading}.jpg"
            filepath = IMAGES_DIR / filename

            url = BASE_URL.format(lat=lat, lng=lng, heading=heading, key=api_key)

            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()

                if resp.headers.get("Content-Type", "").startswith("image/"):
                    filepath.write_bytes(resp.content)
                    downloaded += 1
                    print(f"[{downloaded}/{total}] {filename} ({name}, heading={heading})")
                else:
                    print(f"  SKIP {filename} — not an image response")
            except requests.RequestException as e:
                print(f"  FAIL {filename} — {e}")

    print(f"\nDone: {downloaded}/{total} images saved to {IMAGES_DIR}")


if __name__ == "__main__":
    main()
