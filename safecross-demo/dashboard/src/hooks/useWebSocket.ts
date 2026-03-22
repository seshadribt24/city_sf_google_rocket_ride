import { useState, useEffect, useRef, useCallback } from "react";
import type { TapEvent } from "../types";

const MAX_EVENTS = 50;
const MAX_RETRIES = 10;

export interface NearMissAlertData {
  type: "near_miss_alert";
  intersection_id: string;
  intersection_name: string;
  risk_level: string;
  vehicle_description?: string;
  estimated_distance_ft?: number;
  image_path?: string;
  event_time: string;
  vision_analysis?: {
    risk_level: string;
    vehicle_description?: string;
    estimated_distance_ft?: number;
    safety_concerns?: string;
    analysis_time_ms?: number;
  };
}

export function useWebSocket(url: string) {
  const [events, setEvents] = useState<TapEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [nearMissAlerts, setNearMissAlerts] = useState<NearMissAlertData[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const timerRef = useRef<number | null>(null);

  const dismissAlert = useCallback((index: number) => {
    setNearMissAlerts((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      retriesRef.current = 0;
    };

    ws.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data);
        if (data.type === "near_miss_alert") {
          setNearMissAlerts((prev) => [data as NearMissAlertData, ...prev].slice(0, 3));
          // Also add to the main event feed so it persists in the scrollable list
          const alertAsEvent: TapEvent = {
            event_time: data.event_time,
            crossing_id: "",
            card_type: 0,
            card_uid_hash: "",
            read_method: 0,
            filter_result: "near_miss",
            extension_sec: null,
            phase_state_at_tap: "",
            snmp_result: "",
            intersection_id: data.intersection_id,
            intersection_name: data.intersection_name,
            risk_level: data.risk_level,
            image_path: data.image_path,
            vision_analysis: data.vision_analysis,
          };
          setEvents((prev) => [alertAsEvent, ...prev].slice(0, MAX_EVENTS));
        } else {
          const event: TapEvent = data;
          setEvents((prev) => [event, ...prev].slice(0, MAX_EVENTS));
        }
      } catch { /* ignore bad messages */ }
    };

    ws.onclose = () => {
      setIsConnected(false);
      if (retriesRef.current < MAX_RETRIES) {
        const delay = Math.min(1000 * 2 ** retriesRef.current, 30000);
        retriesRef.current++;
        timerRef.current = window.setTimeout(connect, delay);
      }
    };

    ws.onerror = () => ws.close();
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { events, isConnected, nearMissAlerts, dismissAlert };
}
