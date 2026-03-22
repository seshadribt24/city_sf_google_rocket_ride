#!/usr/bin/env python3
"""Generate danger scenario images using Gemini image generation."""

import base64
import io
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types

load_dotenv()
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

IMAGES_DIR = Path(__file__).resolve().parent / "images"

INTERSECTIONS = [
    "Market St & 5th St",
    "Geary Blvd & Masonic Ave",
    "Mission St & 16th St",
    "Van Ness Ave & Eddy St",
    "Stockton St & Clay St",
    "3rd St & Evans Ave",
    "Taraval St & 19th Ave",
    "Polk St & Turk St",
    "Ocean Ave & Geneva Ave",
    "Sutter St & Larkin St",
]

WIDTH, HEIGHT = 640, 480
ROAD_COLOR = (0x55, 0x55, 0x55)
SIDEWALK_COLOR = (0x99, 0x99, 0x99)
STRIPE_COLOR = (255, 255, 255)

DANGER_SCENARIOS = [
    {
        "filename": "danger_vehicle_close.jpg",
        "prompt": (
            "Edit this crosswalk camera image to add a realistic silver sedan "
            "approaching the crosswalk from the right side, about 15 feet away. "
            "The car should look like it's moving toward the crosswalk at moderate "
            "speed. Keep the rest of the scene unchanged. Make it look like a real "
            "traffic camera capture."
        ),
    },
    {
        "filename": "danger_vehicle_in_crosswalk.jpg",
        "prompt": (
            "Edit this crosswalk camera image to add a realistic white SUV that "
            "is stopped directly inside the crosswalk, blocking pedestrian passage. "
            "The vehicle should be overlapping the crosswalk markings. Keep the "
            "rest of the scene unchanged. Make it look like a real traffic camera capture."
        ),
    },
    {
        "filename": "danger_turning.jpg",
        "prompt": (
            "Edit this crosswalk camera image to add a realistic dark pickup truck "
            "making a right turn at the intersection corner, cutting close to the "
            "crosswalk. The truck should be at an angle, mid-turn. Keep the rest "
            "of the scene unchanged. Make it look like a real traffic camera capture."
        ),
    },
    {
        "filename": "danger_double_parked.jpg",
        "prompt": (
            "Edit this crosswalk camera image to add a realistic delivery van "
            "double-parked very close to the crosswalk on the right side of the "
            "road, partially blocking the view of the crosswalk. Keep the rest "
            "of the scene unchanged. Make it look like a real traffic camera capture."
        ),
    },
]


def create_synthetic_background(name: str) -> Image.Image:
    """Create a synthetic crosswalk background image (fallback)."""
    img = Image.new("RGB", (WIDTH, HEIGHT), ROAD_COLOR)
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, WIDTH, 80], fill=SIDEWALK_COLOR)
    draw.rectangle([0, HEIGHT - 80, WIDTH, HEIGHT], fill=SIDEWALK_COLOR)

    stripe_x = (WIDTH - 80) // 2
    stripe_y_start = 100
    for i in range(6):
        y = stripe_y_start + i * (10 + 15)
        draw.rectangle([stripe_x, y, stripe_x + 80, y + 10], fill=STRIPE_COLOR)

    try:
        font_small = ImageFont.truetype("arial.ttf", 14)
    except (OSError, IOError):
        font_small = ImageFont.load_default()
    draw.text((10, HEIGHT - 25), name, fill=(255, 255, 255), font=font_small)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cam_text = f"SafeCross CAM  {timestamp}"
    try:
        font_cam = ImageFont.truetype("arial.ttf", 12)
    except (OSError, IOError):
        font_cam = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), cam_text, font=font_cam)
    text_w = bbox[2] - bbox[0]
    draw.text((WIDTH - text_w - 10, 10), cam_text, fill=(255, 255, 255), font=font_cam)

    return img


def get_base_images() -> list[Image.Image]:
    """Load existing downloaded images, or generate synthetic backgrounds."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    existing = [
        f for f in IMAGES_DIR.iterdir()
        if f.suffix.lower() in (".jpg", ".jpeg", ".png")
        and not f.name.startswith("danger_")
    ]

    if existing:
        print(f"Found {len(existing)} existing images, using as backgrounds.")
        return [
            Image.open(f).convert("RGB")
            for f in random.sample(existing, min(4, len(existing)))
        ]

    print("No downloaded images found. Generating synthetic crosswalk backgrounds.")
    return [create_synthetic_background(name) for name in random.sample(INTERSECTIONS, 4)]


def generate_with_gemini(
    client: genai.Client, base_image: Image.Image, scenario: dict
) -> Image.Image | None:
    """Use Gemini to generate a danger scenario image from a base crosswalk image."""
    try:
        # Convert PIL image to bytes for the API
        buf = io.BytesIO()
        base_image.save(buf, format="JPEG", quality=90)
        image_bytes = buf.getvalue()

        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[
                scenario["prompt"],
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            ],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        # Extract image from response
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                return Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")

        print(f"    No image in Gemini response for {scenario['filename']}")
        return None

    except Exception as exc:
        print(f"    Gemini generation failed for {scenario['filename']}: {exc}")
        return None


def generate_with_pil_fallback(
    base_image: Image.Image, scenario_index: int
) -> Image.Image:
    """PIL fallback: draw simple car rectangles on the image."""
    img = base_image.copy()
    draw = ImageDraw.Draw(img)
    car_fill = (192, 192, 192)
    car_outline = (40, 40, 40)
    stripe_x = (WIDTH - 80) // 2

    if scenario_index == 0:  # vehicle_close
        gap = random.randint(15, 25)
        draw.rectangle(
            [stripe_x + 80 + gap, 150, stripe_x + 80 + gap + 120, 210],
            fill=car_fill, outline=car_outline, width=2,
        )
    elif scenario_index == 1:  # vehicle_in_crosswalk
        draw.rectangle(
            [stripe_x - 30, 130, stripe_x - 30 + 120, 190],
            fill=car_fill, outline=car_outline, width=2,
        )
    elif scenario_index == 2:  # turning
        import math
        cx, cy = 140, 115
        w, h = 120, 60
        rad = math.radians(30)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        corners = [(-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2)]
        rotated = [(cx + px*cos_a - py*sin_a, cy + px*sin_a + py*cos_a) for px, py in corners]
        draw.polygon(rotated, fill=car_fill, outline=car_outline)
    elif scenario_index == 3:  # double_parked
        stripe_y_end = 100 + 5 * 25 + 10
        draw.rectangle(
            [WIDTH - 140, stripe_y_end - 30, WIDTH - 20, stripe_y_end + 30],
            fill=car_fill, outline=car_outline, width=2,
        )

    return img


def main():
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    bases = get_base_images()

    # Check for Gemini API key
    api_key = os.getenv("GEMINI_API_KEY", "")
    use_gemini = bool(api_key)
    client = None

    if use_gemini:
        client = genai.Client(api_key=api_key)
        print("Using Gemini image generation for danger scenarios.")
    else:
        print("No GEMINI_API_KEY found. Using PIL fallback.")

    for i, scenario in enumerate(DANGER_SCENARIOS):
        base = bases[i % len(bases)]
        result = None

        if use_gemini and client:
            print(f"  Generating {scenario['filename']} with Gemini...")
            result = generate_with_gemini(client, base, scenario)
            # Rate limit: wait between Gemini calls
            if i < len(DANGER_SCENARIOS) - 1:
                time.sleep(2)

        if result is None:
            print(f"  Generating {scenario['filename']} with PIL fallback...")
            result = generate_with_pil_fallback(base, i)

        # Resize to 640x480 if Gemini returned a different size
        if result.size != (WIDTH, HEIGHT):
            result = result.resize((WIDTH, HEIGHT), Image.LANCZOS)

        result.save(IMAGES_DIR / scenario["filename"], "JPEG", quality=90)
        print(f"  Created {scenario['filename']}")

    # Generate synthetic backgrounds if no downloaded images exist
    if not any(
        f.name.startswith("INT-") for f in IMAGES_DIR.iterdir()
        if f.suffix.lower() in (".jpg", ".jpeg")
    ):
        print("\nGenerating additional synthetic backgrounds...")
        for i, name in enumerate(INTERSECTIONS):
            bg = create_synthetic_background(name)
            bg.save(IMAGES_DIR / f"synthetic_{i+1:02d}.jpg", "JPEG", quality=90)
            print(f"  Created synthetic_{i+1:02d}.jpg - {name}")

    total = len(list(IMAGES_DIR.glob("*.jpg")))
    print(f"\nTotal images in {IMAGES_DIR}: {total}")


if __name__ == "__main__":
    main()
