import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { useApi } from "../hooks/useApi";
import type { IntersectionInfo, TapEvent } from "../types";
import type { NearMissAlertData } from "../hooks/useWebSocket";

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN as string | undefined;

interface Props {
  wsEvents: TapEvent[];
  nearMissAlerts: NearMissAlertData[];
  onSelectIntersection?: (id: string | null) => void;
}

export function MapView({ wsEvents, nearMissAlerts, onSelectIntersection }: Props) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markersRef = useRef<Map<string, { marker: mapboxgl.Marker; el: HTMLDivElement }>>(new Map());
  const [ready, setReady] = useState(false);

  const { data: intersections } = useApi<IntersectionInfo[]>("/api/v1/analytics/intersections", 15000);

  // Init map
  useEffect(() => {
    if (!MAPBOX_TOKEN || !mapContainer.current || mapRef.current) return;
    mapboxgl.accessToken = MAPBOX_TOKEN;

    const map = new mapboxgl.Map({
      container: mapContainer.current,
      style: "mapbox://styles/mapbox/dark-v11",
      center: [-122.44, 37.76],
      zoom: 12,
    });

    map.on("load", () => setReady(true));
    mapRef.current = map;

    return () => { map.remove(); mapRef.current = null; };
  }, []);

  // Create/update markers
  useEffect(() => {
    if (!ready || !mapRef.current || !intersections) return;

    intersections.forEach((inter) => {
      const id = inter.intersection_id;
      const taps = inter.taps_today ?? 0;
      const size = Math.max(12, Math.min(28, 12 + taps * 0.8));

      let entry = markersRef.current.get(id);

      if (!entry) {
        const el = document.createElement("div");
        el.className = "sc-marker";
        el.style.cssText = `
          width: ${size}px; height: ${size}px; border-radius: 50%;
          background: #0D9488; border: 2px solid #0D9488;
          cursor: pointer; position: relative; transition: width 0.3s, height 0.3s;
          display: flex; align-items: center; justify-content: center;
        `;
        const dot = document.createElement("div");
        dot.style.cssText = "width: 4px; height: 4px; border-radius: 50%; background: white;";
        el.appendChild(dot);

        el.addEventListener("click", () => onSelectIntersection?.(id));

        const marker = new mapboxgl.Marker({ element: el })
          .setLngLat([inter.lng, inter.lat])
          .setPopup(new mapboxgl.Popup({ offset: 10, closeButton: false })
            .setHTML(`<strong style="color:#0F172A">${inter.name}</strong><br/><span style="color:#64748B">${taps} taps today</span>`))
          .addTo(mapRef.current!);

        entry = { marker, el };
        markersRef.current.set(id, entry);
      } else {
        entry.el.style.width = `${size}px`;
        entry.el.style.height = `${size}px`;
        entry.marker.getPopup()?.setHTML(
          `<strong style="color:#0F172A">${inter.name}</strong><br/><span style="color:#64748B">${taps} taps today</span>`
        );
      }
    });
  }, [ready, intersections, onSelectIntersection]);

  // Pulse markers on new WS events
  const lastEventRef = useRef<string>("");

  useEffect(() => {
    if (wsEvents.length === 0) return;
    const latest = wsEvents[0];
    const key = `${latest.event_time}-${latest.card_uid_hash}`;
    if (key === lastEventRef.current) return;
    lastEventRef.current = key;

    const id = latest.intersection_id;
    if (!id) return;
    const entry = markersRef.current.get(id);
    if (!entry) return;

    entry.el.style.background = "#F59E0B";
    entry.el.style.borderColor = "#F59E0B";
    entry.el.style.boxShadow = "0 0 16px #F59E0B88";

    setTimeout(() => {
      entry.el.style.background = "#0D9488";
      entry.el.style.borderColor = "#0D9488";
      entry.el.style.boxShadow = "none";
    }, 3000);
  }, [wsEvents]);

  // Flash RED on near-miss alerts
  const lastAlertRef = useRef<string>("");

  useEffect(() => {
    if (nearMissAlerts.length === 0) return;
    const latest = nearMissAlerts[0];
    const key = `${latest.event_time}-${latest.intersection_id}`;
    if (key === lastAlertRef.current) return;
    lastAlertRef.current = key;

    const entry = markersRef.current.get(latest.intersection_id);
    if (!entry) return;

    // Create pulse ring element
    const ring = document.createElement("div");
    ring.className = "near-miss-pulse-ring";
    entry.el.appendChild(ring);

    entry.el.style.background = "#DC2626";
    entry.el.style.borderColor = "#DC2626";
    entry.el.style.boxShadow = "0 0 24px #DC262688";

    setTimeout(() => {
      entry.el.style.background = "#0D9488";
      entry.el.style.borderColor = "#0D9488";
      entry.el.style.boxShadow = "none";
      ring.remove();
    }, 5000);
  }, [nearMissAlerts]);

  if (!MAPBOX_TOKEN) {
    return (
      <div
        style={{
          background: "#1E293B",
          borderRadius: 12,
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#94A3B8",
          fontSize: 14,
        }}
      >
        Set VITE_MAPBOX_TOKEN to enable the map
      </div>
    );
  }

  return (
    <div
      ref={mapContainer}
      style={{ width: "100%", height: "100%", borderRadius: 12, overflow: "hidden" }}
    />
  );
}
