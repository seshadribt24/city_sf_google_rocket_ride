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

INTERSECTIONS = [
    ("INT-2025-0001", "Market St & 5th St", 37.7837, -122.4073),
    ("INT-2025-0002", "Geary Blvd & Masonic Ave", 37.7842, -122.4462),
    ("INT-2025-0003", "Mission St & 16th St", 37.7650, -122.4194),
    ("INT-2025-0004", "Van Ness Ave & Eddy St", 37.7836, -122.4213),
    ("INT-2025-0005", "Stockton St & Clay St", 37.7934, -122.4082),
    ("INT-2025-0006", "3rd St & Evans Ave", 37.7432, -122.3872),
    ("INT-2025-0007", "Taraval St & 19th Ave", 37.7434, -122.4756),
    ("INT-2025-0008", "Polk St & Turk St", 37.7824, -122.4186),
    ("INT-2025-0009", "Ocean Ave & Geneva Ave", 37.7235, -122.4419),
    ("INT-2025-0010", "Sutter St & Larkin St", 37.7876, -122.4182),
]

HEADINGS = [0, 90, 180, 270]

BASE_URL = (
    "https://maps.googleapis.com/maps/api/streetview"
    "?size=640x480&location={lat},{lng}&heading={heading}"
    "&pitch=-10&fov=90&key={key}"
)


def main():
    api_key = os.environ.get("GEMINI_API_KEY")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    total = len(INTERSECTIONS) * len(HEADINGS)
    downloaded = 0

    for int_id, name, lat, lng in INTERSECTIONS:
        for heading in HEADINGS:
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
