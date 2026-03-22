"""Gemini AI integration for SafeCross analytics."""

import asyncio
import base64
import io
import json
import logging
import os
import time

from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image

load_dotenv()

log = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-2.5-flash"
VISION_TIMEOUT_SEC = 15
VISION_MAX_CONCURRENT = 3
VISION_MAX_QUEUE = 10
VISION_MAX_WIDTH = 640

SYSTEM_CONTEXT = (
    "You are an AI traffic safety analyst for SafeCross SF, an adaptive "
    "pedestrian crossing system deployed at 10 pilot intersections on San "
    "Francisco's High Injury Network. The system uses NFC card readers to "
    "detect seniors and disabled pedestrians, then extends walk signal times "
    "via SNMP commands to the signal controller. Card types: 1=senior RTC, "
    "2=disabled RTC, 3=standard adult (rejected), 4=youth (rejected). "
    "Filter results: accepted (extension granted), rejected_cooldown, "
    "rejected_clearance, rejected_duplicate, rejected_card_type."
)


class SafeCrossAI:
    def __init__(self):
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel(MODEL_NAME)
        self._vision_semaphore = asyncio.Semaphore(VISION_MAX_CONCURRENT)
        self._vision_queue_count = 0

    def _resize_image(self, image: Image.Image) -> Image.Image:
        """Resize image to max VISION_MAX_WIDTH wide to reduce API payload."""
        if image.width > VISION_MAX_WIDTH:
            ratio = VISION_MAX_WIDTH / image.width
            new_h = int(image.height * ratio)
            image = image.resize((VISION_MAX_WIDTH, new_h), Image.LANCZOS)
        return image

    async def analyze_crosswalk_image(
        self, image_base64: str, intersection_name: str, crossing_id: str
    ) -> dict:
        """Analyze a crosswalk camera image for vehicle threats using Gemini vision."""
        # Queue overflow protection
        if self._vision_queue_count >= VISION_MAX_QUEUE:
            log.warning("Vision analysis queue full (%d), dropping request", self._vision_queue_count)
            return {
                "vehicle_present": False,
                "risk_level": "unknown",
                "vehicle_description": None,
                "estimated_distance_ft": None,
                "safety_concerns": "Analysis skipped: queue full",
                "analysis_time_ms": 0,
            }

        self._vision_queue_count += 1
        try:
            async with self._vision_semaphore:
                return await self._analyze_image_inner(
                    image_base64, intersection_name, crossing_id
                )
        finally:
            self._vision_queue_count -= 1

    async def _analyze_image_inner(
        self, image_base64: str, intersection_name: str, crossing_id: str
    ) -> dict:
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_bytes))
        image = self._resize_image(image)

        prompt = (
            f"You are a traffic safety AI analyzing a crosswalk camera image "
            f"from {intersection_name} ({crossing_id} crossing) in San Francisco. "
            f"A senior pedestrian has just activated an extended crossing signal.\n\n"
            f"Assess:\n"
            f"1. Is a vehicle within dangerous proximity of the crosswalk? (yes/no)\n"
            f"2. Risk level: low (no vehicles nearby), medium (vehicle present but "
            f"yielding), high (vehicle close and moving toward crosswalk), "
            f"critical (vehicle in or about to enter crosswalk)\n"
            f"3. Vehicle type and estimated distance from crosswalk if present\n"
            f"4. Any other safety concerns (blocked sightlines, double-parked cars, "
            f"construction, poor lighting)\n\n"
            f'Respond with ONLY valid JSON, no markdown:\n'
            f'{{"vehicle_present": true/false, "risk_level": "low|medium|high|critical", '
            f'"vehicle_description": "description or null", '
            f'"estimated_distance_ft": number or null, '
            f'"safety_concerns": "description or empty string"}}'
        )

        for attempt in range(2):
            try:
                start = time.time()
                model = genai.GenerativeModel(MODEL_NAME)
                response = await asyncio.wait_for(
                    model.generate_content_async([prompt, image]),
                    timeout=VISION_TIMEOUT_SEC,
                )
                elapsed_ms = int((time.time() - start) * 1000)

                text = response.text.strip()
                # Strip markdown fences if present
                if text.startswith("```"):
                    text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

                result = json.loads(text)
                result["analysis_time_ms"] = elapsed_ms
                return result
            except asyncio.TimeoutError:
                elapsed_ms = int((time.time() - start) * 1000)
                log.warning("Vision analysis timed out after %dms", elapsed_ms)
                return {
                    "vehicle_present": False,
                    "risk_level": "unknown",
                    "vehicle_description": None,
                    "estimated_distance_ft": None,
                    "safety_concerns": "Analysis timed out",
                    "analysis_time_ms": elapsed_ms,
                }
            except json.JSONDecodeError:
                elapsed_ms = int((time.time() - start) * 1000)
                log.warning("Gemini returned invalid JSON, falling back to low")
                return {
                    "vehicle_present": False,
                    "risk_level": "low",
                    "vehicle_description": None,
                    "estimated_distance_ft": None,
                    "safety_concerns": "Could not parse Gemini response",
                    "analysis_time_ms": elapsed_ms,
                }
            except Exception as exc:
                if attempt == 0:
                    await asyncio.sleep(2)
                    continue
                elapsed_ms = int((time.time() - start) * 1000) if 'start' in dir() else 0
                return {
                    "vehicle_present": False,
                    "risk_level": "low",
                    "vehicle_description": None,
                    "estimated_distance_ft": None,
                    "safety_concerns": f"Analysis failed: {exc}",
                    "analysis_time_ms": elapsed_ms,
                }

    async def generate_insights(self, events_summary: dict) -> str:
        json_summary = json.dumps(events_summary, indent=2, default=str)

        # Build near-miss context section
        near_miss_section = ""
        nm = events_summary.get("near_miss_stats")
        if nm:
            near_miss_section = f"""
Near-miss / vehicle conflict data (last 24 hours):
- Total near-miss events (high+critical risk): {nm.get('total_near_misses', 0)}
- Per-intersection counts: {json.dumps(nm.get('by_intersection', {}), default=str)}
- Most common vehicle descriptions: {json.dumps(nm.get('common_vehicles', []), default=str)}
- Peak near-miss hours: {json.dumps(nm.get('peak_hours', []), default=str)}
"""

        prompt = f"""\
You are an AI traffic safety analyst for SafeCross SF, an adaptive \
pedestrian crossing system that extends walk signals for seniors.

Analyze this crossing data and provide 3-4 actionable insights for \
SFMTA traffic engineers. Focus on:
- Which intersections have the highest senior crossing demand
- Time-of-day patterns that suggest permanent timing changes
- Any intersections where rejection rates suggest a problem
- Vehicle conflict / near-miss patterns from vision analysis
- Which intersections have the most dangerous vehicle conflicts
- Specific recommendations with numbers (e.g., "increase baseline \
walk time by 8 seconds at Market & 5th during 8-9am")

Data:
{json_summary}
{near_miss_section}
Respond in 3-4 concise bullet points. Be specific with intersection \
names, times, and recommended seconds. No hedging language."""

        try:
            response = await self.model.generate_content_async(prompt)
            return response.text
        except Exception as exc:
            return f"AI analysis temporarily unavailable: {exc}"

    async def generate_recommendation(self, intersection_data: dict) -> dict:
        json_data = json.dumps(intersection_data, indent=2, default=str)
        prompt = f"""\
{SYSTEM_CONTEXT}

Analyze the following intersection data and generate a timing recommendation.
Return ONLY valid JSON matching this exact schema (no markdown, no code fences):
{{
  "intersection": "<intersection name>",
  "recommendation": "<specific timing change>",
  "peak_hours": "<peak demand hours>",
  "confidence": "high|medium|low",
  "reasoning": "<data-driven reasoning with specific numbers>",
  "estimated_impact": "<quantified expected improvement>"
}}

Intersection data:
{json_data}"""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                ),
            )
            return json.loads(response.text)
        except json.JSONDecodeError:
            # Gemini returned non-JSON despite JSON mode — parse best-effort
            try:
                text = response.text.strip()
                # Strip markdown fences if present
                if text.startswith("```"):
                    text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                return json.loads(text)
            except Exception:
                return {
                    "intersection": intersection_data.get("name", "Unknown"),
                    "recommendation": "AI analysis temporarily unavailable",
                    "peak_hours": "N/A",
                    "confidence": "low",
                    "reasoning": "Could not parse AI response",
                    "estimated_impact": "N/A",
                }
        except Exception as exc:
            return {
                "intersection": intersection_data.get("name", "Unknown"),
                "recommendation": "AI analysis temporarily unavailable",
                "peak_hours": "N/A",
                "confidence": "low",
                "reasoning": str(exc),
                "estimated_impact": "N/A",
            }

    async def answer_question(self, question: str, context: dict) -> str:
        json_context = json.dumps(context, indent=2, default=str)
        prompt = f"""\
{SYSTEM_CONTEXT}

Current system data:
{json_context}

A traffic engineer asks: "{question}"

Answer concisely with specific data from the system. Reference intersection \
names, times, and numbers. If the data doesn't support a confident answer, \
say so clearly."""

        try:
            response = await self.model.generate_content_async(prompt)
            return response.text
        except Exception as exc:
            return f"AI analysis temporarily unavailable: {exc}"


# Singleton
ai_client = SafeCrossAI()
