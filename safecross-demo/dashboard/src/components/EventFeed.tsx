import { useEffect, useState } from "react";
import type { TapEvent, VisionAnalysis } from "../types";

interface Props {
  events: TapEvent[];
}

const CARD_ICONS: Record<number, string> = {
  1: "\u{1F474}",  // 👴 senior
  2: "\u267F",     // ♿ disabled
  3: "\u{1F6B6}",  // 🚶 adult
  4: "\u{1F9D2}",  // 🧒 youth
};

const API_BASE = "";

function timeAgo(iso: string): string {
  const diff = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

function RiskBadge({ level }: { level: string }) {
  const config: Record<string, { bg: string; color: string; text: string; pulse?: boolean }> = {
    low: { bg: "#22C55E22", color: "#22C55E", text: "\u2713" },
    medium: { bg: "#F59E0B22", color: "#F59E0B", text: "\u26A0" },
    high: { bg: "#EA580C22", color: "#EA580C", text: "\u26A0 Vehicle nearby" },
    critical: { bg: "#DC262633", color: "#DC2626", text: "\u{1F6A8} Near miss", pulse: true },
  };
  const c = config[level] || { bg: "#64748B22", color: "#64748B", text: level };
  return (
    <span
      className={c.pulse ? "pulse-risk" : ""}
      style={{
        fontSize: 10,
        fontWeight: 600,
        padding: "2px 6px",
        borderRadius: 4,
        background: c.bg,
        color: c.color,
        whiteSpace: "nowrap",
        flexShrink: 0,
      }}
    >
      {c.text}
    </span>
  );
}

function VisionModal({
  event,
  onClose,
}: {
  event: TapEvent;
  onClose: () => void;
}) {
  const va = event.vision_analysis as VisionAnalysis;
  const imageSrc = event.image_path
    ? `${API_BASE}/images/${event.image_path.split("/").pop()}`
    : null;
  const [aiAnalysis, setAiAnalysis] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  useEffect(() => {
    if (!va) {
      setAiLoading(true);
      fetch("/api/v1/ai/analyze-event", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event }),
      })
        .then((r) => r.json())
        .then((data) => setAiAnalysis(data.analysis))
        .catch(() => setAiAnalysis("AI analysis unavailable."))
        .finally(() => setAiLoading(false));
    }
  }, [event, va]);

  const cardLabels: Record<number, string> = {
    1: "Senior RTC",
    2: "Disabled RTC",
    3: "Standard Adult",
    4: "Youth",
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.7)",
        zIndex: 10000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        animation: "fadeIn 0.2s ease",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "#1E293B",
          borderRadius: 16,
          padding: 24,
          maxWidth: 520,
          width: "90%",
          boxShadow: "0 24px 64px rgba(0,0,0,0.5)",
        }}
      >
        {imageSrc && (
          <img
            src={imageSrc}
            alt="Crosswalk camera"
            style={{
              width: "100%",
              borderRadius: 10,
              marginBottom: 16,
              maxHeight: 320,
              objectFit: "cover",
            }}
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
        )}

        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: "#F1F5F9" }}>
            {event.intersection_name || event.intersection_id}
          </span>
          <RiskBadge level={va?.risk_level || event.risk_level || "unknown"} />
        </div>

        {/* Event details for non-vision events */}
        {!va && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 12 }}>
            <div style={{ fontSize: 13, color: "#CBD5E1" }}>
              <strong style={{ color: "#F1F5F9" }}>Card Type:</strong>{" "}
              {cardLabels[event.card_type] ?? "Unknown"}
            </div>
            <div style={{ fontSize: 13, color: "#CBD5E1" }}>
              <strong style={{ color: "#F1F5F9" }}>Status:</strong>{" "}
              {event.filter_result === "accepted" ? (
                <span style={{ color: "#0D9488" }}>Extended +{event.extension_sec}s</span>
              ) : (
                <span style={{ color: "#EF4444" }}>
                  Rejected ({event.filter_result.replace("rejected_", "")})
                </span>
              )}
            </div>
            <div style={{ fontSize: 13, color: "#CBD5E1" }}>
              <strong style={{ color: "#F1F5F9" }}>Time:</strong>{" "}
              {new Date(event.event_time).toLocaleTimeString()}
            </div>
          </div>
        )}

        {va && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {va.vehicle_description && (
              <div style={{ fontSize: 13, color: "#CBD5E1" }}>
                <strong style={{ color: "#F1F5F9" }}>Vehicle:</strong> {va.vehicle_description}
              </div>
            )}
            {va.estimated_distance_ft != null && (
              <div style={{ fontSize: 13, color: "#CBD5E1" }}>
                <strong style={{ color: "#F1F5F9" }}>Distance:</strong> {va.estimated_distance_ft} ft from crosswalk
              </div>
            )}
            {va.safety_concerns && (
              <div style={{ fontSize: 13, color: "#CBD5E1" }}>
                <strong style={{ color: "#F1F5F9" }}>Concerns:</strong> {va.safety_concerns}
              </div>
            )}
            <div
              style={{
                fontSize: 11,
                color: "#64748B",
                marginTop: 8,
                paddingTop: 8,
                borderTop: "1px solid #334155",
              }}
            >
              Analyzed in {va.analysis_time_ms}ms by Gemini Vision
            </div>
          </div>
        )}

        {/* AI analysis for non-vision events */}
        {!va && (
          <div
            style={{
              marginTop: 8,
              padding: 12,
              background: "#1a1a2e",
              borderRadius: 10,
              border: "1px solid #334155",
            }}
          >
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "#A78BFA",
                marginBottom: 6,
                textTransform: "uppercase",
                letterSpacing: 0.5,
              }}
            >
              Gemini Analysis
            </div>
            {aiLoading ? (
              <div style={{ fontSize: 12, color: "#94A3B8", fontStyle: "italic" }}>
                Analyzing event...
              </div>
            ) : (
              <div style={{ fontSize: 13, color: "#CBD5E1", lineHeight: 1.5 }}>
                {aiAnalysis}
              </div>
            )}
            <div
              style={{
                fontSize: 10,
                color: "#64748B",
                marginTop: 8,
                paddingTop: 6,
                borderTop: "1px solid #334155",
              }}
            >
              Powered by Google Gemini
            </div>
          </div>
        )}

        <button
          onClick={onClose}
          style={{
            marginTop: 16,
            width: "100%",
            padding: "8px 0",
            background: "#334155",
            border: "none",
            borderRadius: 8,
            color: "#94A3B8",
            fontSize: 12,
            cursor: "pointer",
          }}
        >
          Close
        </button>
      </div>
    </div>
  );
}

export function EventFeed({ events }: Props) {
  const [, setTick] = useState(0);
  const [selectedEvent, setSelectedEvent] = useState<TapEvent | null>(null);

  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 5000);
    return () => clearInterval(id);
  }, []);

  const displayed = events.slice(0, 15);

  return (
    <>
      <div
        style={{
          background: "#1E293B",
          borderRadius: 12,
          padding: 16,
          maxHeight: 380,
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <h3 style={{ color: "#F1F5F9", fontSize: 14, margin: "0 0 12px", fontWeight: 600 }}>
          Live Event Feed
        </h3>
        <div style={{ flex: 1, overflowY: "auto" }}>
          {displayed.length === 0 && (
            <div style={{ textAlign: "center", marginTop: 40 }}>
              <span className="pulse-dot" />
              <p style={{ color: "#64748B", fontSize: 13, marginTop: 12 }}>
                Waiting for events...
              </p>
            </div>
          )}
          {displayed.map((e, i) => {
            const accepted = e.filter_result === "accepted";
            const isHighRisk =
              e.risk_level === "high" || e.risk_level === "critical";
            return (
              <div
                key={`${e.event_time}-${e.card_uid_hash}-${i}`}
                className={i === 0 ? "slide-in" : undefined}
                onClick={() => setSelectedEvent(e)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "8px 10px",
                  marginBottom: 4,
                  borderRadius: 8,
                  borderLeft: `3px solid ${
                    isHighRisk ? "#EA580C" : accepted ? "#0D9488" : "#EF4444"
                  }`,
                  background: isHighRisk
                    ? "rgba(220, 38, 38, 0.06)"
                    : "#0F172A",
                  cursor: "pointer",
                  transition: "background 0.2s",
                }}
              >
                <span style={{ fontSize: 18, lineHeight: 1, flexShrink: 0 }}>
                  {CARD_ICONS[e.card_type] ?? "\u{1F6B6}"}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      color: "#F1F5F9",
                      fontSize: 13,
                      fontWeight: 500,
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
                      {e.intersection_name ?? e.intersection_id}
                    </span>
                    <span style={{ color: "#64748B", fontWeight: 400 }}>
                      &middot; {e.crossing_id}
                    </span>
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      marginTop: 2,
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    {accepted ? (
                      <span style={{ color: "#0D9488", fontWeight: 600 }}>
                        EXTENDED +{e.extension_sec}s
                      </span>
                    ) : (
                      <span style={{ color: "#EF4444", fontWeight: 600 }}>
                        REJECTED{" "}
                        <span style={{ fontWeight: 400, color: "#94A3B8" }}>
                          {e.filter_result.replace("rejected_", "")}
                        </span>
                      </span>
                    )}
                    {e.risk_level && e.risk_level !== "unknown" && (
                      <RiskBadge level={e.risk_level} />
                    )}
                  </div>
                </div>
                <span
                  style={{
                    color: "#64748B",
                    fontSize: 11,
                    fontFamily: "monospace",
                    flexShrink: 0,
                    whiteSpace: "nowrap",
                  }}
                >
                  {timeAgo(e.event_time)}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {selectedEvent && (
        <VisionModal
          event={selectedEvent}
          onClose={() => setSelectedEvent(null)}
        />
      )}
    </>
  );
}
