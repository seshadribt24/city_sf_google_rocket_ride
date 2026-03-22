import json

from fastapi import APIRouter, HTTPException

from .database import (
    get_events,
    get_heatmap_data,
    get_intersection_stats,
    get_near_misses,
    get_risk_summary,
    get_summary,
)
from .seed_data import PILOT_INTERSECTIONS

import aiosqlite
from .database import DB_PATH

from datetime import datetime, timezone

router = APIRouter(prefix="/api/v1/analytics")


@router.get("/summary")
async def summary():
    return await get_summary()


@router.get("/intersections")
async def list_intersections():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    results = []
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        for i in PILOT_INTERSECTIONS:
            iid = i["intersection_id"]

            # Tap count today
            cursor = await db.execute(
                "SELECT COUNT(*) FROM tap_events WHERE intersection_id = ? AND event_time >= ?",
                (iid, today),
            )
            taps_today = (await cursor.fetchone())[0]

            # Latest heartbeat
            cursor = await db.execute(
                "SELECT * FROM heartbeats WHERE intersection_id = ? ORDER BY timestamp DESC LIMIT 1",
                (iid,),
            )
            hb_row = await cursor.fetchone()
            latest_heartbeat = dict(hb_row) if hb_row else None

            results.append({
                **i,
                "taps_today": taps_today,
                "latest_heartbeat": latest_heartbeat,
            })
    return results


@router.get("/intersection/{intersection_id}")
async def intersection_detail(intersection_id: str):
    stats = await get_intersection_stats(intersection_id)
    if stats is None:
        raise HTTPException(status_code=404, detail="Intersection not found")
    return stats


@router.get("/heatmap")
async def heatmap():
    return await get_heatmap_data()


@router.get("/near-misses")
async def near_misses():
    return await get_near_misses(limit=20)


@router.get("/risk-summary")
async def risk_summary():
    return await get_risk_summary()
