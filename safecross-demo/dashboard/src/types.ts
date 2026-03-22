export interface VisionAnalysis {
  vehicle_present: boolean;
  risk_level: 'low' | 'medium' | 'high' | 'critical' | 'unknown';
  vehicle_description: string | null;
  estimated_distance_ft: number | null;
  safety_concerns: string;
  analysis_time_ms: number;
}

export interface TapEvent {
  event_time: string;
  crossing_id: string;
  card_type: number;
  card_uid_hash: string;
  read_method: number;
  filter_result: string;
  extension_sec: number | null;
  phase_state_at_tap: string;
  snmp_result: string;
  // Added by WebSocket broadcast
  intersection_id?: string;
  device_id?: string;
  intersection_name?: string;
  lat?: number;
  lng?: number;
  // Vision analysis
  risk_level?: string;
  vision_analysis?: VisionAnalysis;
  image_path?: string;
}

export interface NearMissEvent {
  id: number;
  intersection_id: string;
  intersection_name: string;
  event_time: string;
  risk_level: string;
  vehicle_description?: string;
  estimated_distance_ft?: number;
  image_path?: string;
  vision_analysis?: VisionAnalysis;
}

export interface RiskSummaryItem {
  intersection_id: string;
  name: string;
  total_analyzed: number;
  high_count: number;
  critical_count: number;
  risk_rate: number;
}

export interface EventBatch {
  device_id: string;
  intersection_id: string;
  events: TapEvent[];
}

export interface Heartbeat {
  device_id: string;
  intersection_id: string;
  timestamp: string;
  edge_status: string;
  reader_status: string;
  signal_controller_status: string;
  uptime_sec: number;
  events_pending: number;
  last_extension_time: string | null;
  software_version: string;
}

export interface IntersectionInfo {
  intersection_id: string;
  device_id: string;
  name: string;
  lat: number;
  lng: number;
  crossings: {
    crossing_id: string;
    width_ft: number;
    base_walk_sec?: number;
    max_extension_sec: number;
  }[];
  taps_today?: number;
  latest_heartbeat?: Heartbeat | null;
}

export interface AnalyticsSummary {
  total_taps_today: number;
  total_extensions_today: number;
  avg_extension_sec: number;
  unique_intersections_active: number;
  acceptance_rate: number;
}

export interface HeatmapPoint {
  lat: number;
  lng: number;
  weight: number;
}

export interface AIInsights {
  insights: string;
  cached: boolean;
}

export interface AIRecommendation {
  intersection: string;
  recommendation: string;
  peak_hours: string;
  confidence: string;
  reasoning: string;
  estimated_impact: string;
}
