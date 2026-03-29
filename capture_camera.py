#!/usr/bin/env python3
"""Periodically capture still images from a 511NY traffic camera."""

import time
from datetime import datetime
from pathlib import Path

import httpx

CAMERA_ID = 5021
CAMERA_NAME = "ontario_st"
IMAGE_URL = f"https://511ny.org/map/Cctv/{CAMERA_ID}"
INTERVAL_SECONDS = 10
CAPTURES_DIR = Path(__file__).resolve().parent / "captures"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://511ny.org/cctv",
}


def capture_once(client: httpx.Client) -> Path | None:
    """Fetch a single camera snapshot and save it. Returns the saved path or None."""
    resp = client.get(IMAGE_URL, headers=HEADERS, timeout=10)
    resp.raise_for_status()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{CAMERA_NAME}_{timestamp}.jpg"
    filepath = CAPTURES_DIR / filename
    filepath.write_bytes(resp.content)
    return filepath


def main():
    CAPTURES_DIR.mkdir(exist_ok=True)
    print(f"Capturing camera {CAMERA_ID} ({CAMERA_NAME}) every {INTERVAL_SECONDS}s")
    print(f"Saving to: {CAPTURES_DIR}")
    print("Press Ctrl+C to stop.\n")

    with httpx.Client() as client:
        count = 0
        while True:
            try:
                path = capture_once(client)
                count += 1
                size_kb = path.stat().st_size / 1024
                print(f"[{count}] Saved {path.name} ({size_kb:.1f} KB)")
            except (httpx.HTTPError, OSError) as e:
                print(f"[!] Error: {e}")

            time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
