import base64
import json
import os
from pathlib import Path

from fastapi import APIRouter

from .database import insert_events
from .gemini_client import ai_client
from .models import EventBatch, Heartbeat
from .seed_data import INTERSECTIONS_BY_ID
from .websocket_manager import manager
from .database import insert_heartbeat

router = APIRouter(prefix="/api/v1")

IMAGES_DIR = Path("data/images")


@router.post("/events")
async def receive_events(batch: EventBatch):
    events_dicts = [e.model_dump() for e in batch.events]
    info = INTERSECTIONS_BY_ID.get(batch.intersection_id, {})
    intersection_name = info.get("name", "Unknown")

    for e_dict, e_model in zip(events_dicts, batch.events):
        # Vision analysis if image is included
        if e_model.image_base64:
            try:
                analysis = await ai_client.analyze_crosswalk_image(
                    e_model.image_base64,
                    intersection_name,
                    e_dict["crossing_id"],
                )
                e_dict["vision_analysis"] = analysis
                gemini_risk = analysis.get("risk_level", "low")
                # If Gemini failed (quota/error) and client provided a risk hint, use it
                client_risk = e_model.risk_level
                if (gemini_risk == "low"
                        and "Analysis failed" in analysis.get("safety_concerns", "")
                        and client_risk in ("medium", "high", "critical")):
                    e_dict["risk_level"] = client_risk
                    analysis["risk_level"] = client_risk
                else:
                    e_dict["risk_level"] = gemini_risk

                # Save image to disk
                IMAGES_DIR.mkdir(parents=True, exist_ok=True)
                event_id = f"{batch.intersection_id}_{e_dict['crossing_id']}_{e_dict['event_time']}"
                # Sanitize filename
                safe_id = event_id.replace(":", "-").replace(" ", "_")
                img_filename = f"{safe_id}.jpg"
                img_path = IMAGES_DIR / img_filename
                img_path.write_bytes(base64.b64decode(e_model.image_base64))
                e_dict["image_path"] = f"/images/{img_filename}"
            except Exception as exc:
                import traceback
                traceback.print_exc()
                e_dict["risk_level"] = "unknown"
                e_dict["vision_analysis"] = {
                    "vehicle_present": False,
                    "risk_level": "unknown",
                    "safety_concerns": str(exc),
                    "analysis_time_ms": 0,
                }

        # Remove base64 before DB insert (too large to store)
        e_dict.pop("image_base64", None)

    await insert_events(batch.intersection_id, batch.device_id, events_dicts)

    # Broadcast each event via WebSocket with intersection metadata
    for e_dict in events_dicts:
        ws_payload = {
            **e_dict,
            "intersection_id": batch.intersection_id,
            "device_id": batch.device_id,
            "intersection_name": intersection_name,
            "lat": info.get("lat"),
            "lng": info.get("lng"),
        }

        # Near-miss alert for high/critical risk
        if e_dict.get("risk_level") in ("high", "critical"):
            ws_payload["type"] = "near_miss_alert"
            ws_payload["vision_analysis"] = e_dict.get("vision_analysis")
            ws_payload["image_path"] = e_dict.get("image_path")
            # Don't send base64 over WebSocket

        await manager.broadcast(ws_payload)

    # Build response with vision analysis results
    response: dict = {"status": "ok", "events_received": len(batch.events)}
    analyses = [
        e.get("vision_analysis") for e in events_dicts if e.get("vision_analysis")
    ]
    if analyses:
        response["vision_analyses"] = analyses
    return response


@router.post("/heartbeat")
async def receive_heartbeat(hb: Heartbeat):
    await insert_heartbeat(hb.model_dump())
    return {"status": "ok"}
