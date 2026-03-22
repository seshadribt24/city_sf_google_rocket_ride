from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class VisionAnalysis(BaseModel):
    vehicle_present: bool
    risk_level: str  # "low", "medium", "high", "critical"
    vehicle_description: Optional[str] = None
    estimated_distance_ft: Optional[float] = None
    safety_concerns: str = ""
    analysis_time_ms: int = 0


class TapEvent(BaseModel):
    event_time: datetime
    crossing_id: str
    card_type: int  # 0-4
    card_uid_hash: str
    read_method: int
    filter_result: str
    extension_sec: Optional[int] = None
    phase_state_at_tap: str
    snmp_result: str
    image_base64: Optional[str] = None
    vision_analysis: Optional[VisionAnalysis] = None
    risk_level: Optional[str] = None
    image_path: Optional[str] = None


class EventBatch(BaseModel):
    device_id: str
    intersection_id: str
    events: list[TapEvent]


class Heartbeat(BaseModel):
    device_id: str
    intersection_id: str
    timestamp: datetime
    edge_status: str
    reader_status: str
    signal_controller_status: str
    uptime_sec: int
    events_pending: int
    last_extension_time: Optional[datetime] = None
    software_version: str


class IntersectionInfo(BaseModel):
    intersection_id: str
    device_id: str
    name: str
    lat: float
    lng: float
    crossings: list[dict]
