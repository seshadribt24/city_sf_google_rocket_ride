import { useEffect, useState } from "react";
import type { NearMissAlertData } from "../hooks/useWebSocket";

const API_BASE = "";

interface Props {
  alerts: NearMissAlertData[];
  onDismiss: (index: number) => void;
  onClickAlert?: (alert: NearMissAlertData) => void;
}

export function NearMissAlert({ alerts, onDismiss, onClickAlert }: Props) {
  return (
    <div
      style={{
        position: "fixed",
        top: 80,
        right: 20,
        zIndex: 9999,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        maxWidth: 380,
      }}
    >
      {alerts.map((alert, i) => (
        <AlertToast
          key={`${alert.event_time}-${alert.intersection_id}-${i}`}
          alert={alert}
          onDismiss={() => onDismiss(i)}
          onClick={() => onClickAlert?.(alert)}
        />
      ))}
    </div>
  );
}

function AlertToast({
  alert,
  onDismiss,
  onClick,
}: {
  alert: NearMissAlertData;
  onDismiss: () => void;
  onClick: () => void;
}) {
  const [fading, setFading] = useState(false);

  useEffect(() => {
    const fadeTimer = setTimeout(() => setFading(true), 7000);
    const removeTimer = setTimeout(onDismiss, 8000);
    return () => {
      clearTimeout(fadeTimer);
      clearTimeout(removeTimer);
    };
  }, [onDismiss]);

  const isCritical = alert.risk_level === "critical";

  return (
    <div
      onClick={onClick}
      className={isCritical ? "near-miss-toast-critical" : ""}
      style={{
        background: isCritical
          ? "linear-gradient(135deg, #DC2626, #B91C1C)"
          : "linear-gradient(135deg, #EA580C, #C2410C)",
        borderRadius: 12,
        padding: "12px 14px",
        cursor: "pointer",
        display: "flex",
        gap: 12,
        alignItems: "center",
        opacity: fading ? 0 : 1,
        transform: fading ? "translateX(100px)" : "translateX(0)",
        transition: "opacity 0.8s ease, transform 0.8s ease",
        animation: "slideInRight 0.4s ease-out",
        boxShadow: "0 8px 32px rgba(220, 38, 38, 0.4)",
      }}
    >
      {alert.image_path && (
        <img
          src={`${API_BASE}/images/${alert.image_path.split("/").pop()}`}
          alt="Crosswalk"
          style={{
            width: 56,
            height: 42,
            borderRadius: 6,
            objectFit: "cover",
            flexShrink: 0,
          }}
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = "none";
          }}
        />
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            color: "white",
            fontWeight: 700,
            fontSize: 13,
            marginBottom: 2,
          }}
        >
          {isCritical ? "\u{1F6A8}" : "\u{1F536}"}{" "}
          {isCritical ? "CRITICAL" : "HIGH RISK"} — {alert.intersection_name}
        </div>
        <div
          style={{
            color: "rgba(255,255,255,0.85)",
            fontSize: 11,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {alert.vehicle_description || "Vehicle detected"}
          {alert.estimated_distance_ft != null &&
            ` \u2022 ${alert.estimated_distance_ft}ft from crosswalk`}
        </div>
      </div>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDismiss();
        }}
        style={{
          background: "none",
          border: "none",
          color: "rgba(255,255,255,0.6)",
          cursor: "pointer",
          fontSize: 16,
          padding: 4,
          lineHeight: 1,
          flexShrink: 0,
        }}
      >
        \u00D7
      </button>
    </div>
  );
}
