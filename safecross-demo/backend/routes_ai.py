"""AI-powered analytics endpoints."""

import json
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .database import DB_PATH, get_intersection_stats, get_near_misses, get_risk_summary, get_summary
from .gemini_client import ai_client
from .routes_analytics import list_intersections

router = APIRouter(prefix="/api/v1/ai")

# ── Simple in-memory cache ───────────────────────────────────────────────────

_insights_cache: dict = {"text": None, "ts": 0}
CACHE_TTL = 300  # 5 minutes


class AskRequest(BaseModel):
    question: str


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/insights")
async def ai_insights():
    now = time.time()
    if _insights_cache["text"] and now - _insights_cache["ts"] < CACHE_TTL:
        return {"insights": _insights_cache["text"], "cached": True}

    summary = await get_summary()
    intersections = await list_intersections()

    # Gather near-miss stats for the AI prompt
    near_miss_stats = await _build_near_miss_stats()

    context = {
        "summary": summary,
        "intersections": [
            {
                "name": i["name"],
                "intersection_id": i["intersection_id"],
                "taps_today": i["taps_today"],
                "has_heartbeat": i["latest_heartbeat"] is not None,
            }
            for i in intersections
        ],
        "near_miss_stats": near_miss_stats,
    }

    text = await ai_client.generate_insights(context)
    _insights_cache["text"] = text
    _insights_cache["ts"] = now
    return {"insights": text, "cached": False}


@router.get("/recommendation/{intersection_id}")
async def ai_recommendation(intersection_id: str):
    stats = await get_intersection_stats(intersection_id)
    if stats is None:
        raise HTTPException(status_code=404, detail="Intersection not found")

    recommendation = await ai_client.generate_recommendation(stats)
    return recommendation


@router.post("/ask")
async def ai_ask(req: AskRequest):
    summary = await get_summary()
    intersections = await list_intersections()
    near_miss_stats = await _build_near_miss_stats()

    context = {
        "summary": summary,
        "intersections": [
            {
                "name": i["name"],
                "intersection_id": i["intersection_id"],
                "taps_today": i["taps_today"],
                "has_heartbeat": i["latest_heartbeat"] is not None,
            }
            for i in intersections
        ],
        "near_miss_stats": near_miss_stats,
    }

    answer = await ai_client.answer_question(req.question, context)
    return {"question": req.question, "answer": answer}


async def _build_near_miss_stats() -> dict:
    """Build near-miss statistics for AI context."""
    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    events = await get_near_misses(since=since_24h, limit=100)
    risk_summary = await get_risk_summary()

    by_intersection: dict[str, int] = {}
    vehicle_descriptions: list[str] = []
    hour_counts: Counter = Counter()

    for ev in events:
        name = ev.get("intersection_name", "Unknown")
        by_intersection[name] = by_intersection.get(name, 0) + 1
        va = ev.get("vision_analysis")
        if isinstance(va, dict) and va.get("vehicle_description"):
            vehicle_descriptions.append(va["vehicle_description"])
        try:
            et = ev.get("event_time", "")
            if "T" in str(et):
                h = int(str(et).split("T")[1][:2])
            else:
                h = int(str(et).split(" ")[1][:2])
            hour_counts[h] += 1
        except (ValueError, IndexError):
            pass

    # Top 5 most common vehicle descriptions
    vc = Counter(vehicle_descriptions)
    common_vehicles = [desc for desc, _ in vc.most_common(5)]

    # Peak hours sorted by count
    peak_hours = [{"hour": h, "count": c} for h, c in hour_counts.most_common(5)]

    return {
        "total_near_misses": len(events),
        "by_intersection": by_intersection,
        "common_vehicles": common_vehicles,
        "peak_hours": peak_hours,
        "risk_summary": risk_summary,
    }
