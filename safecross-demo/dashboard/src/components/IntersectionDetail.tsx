import { useState, useCallback, useEffect } from "react";
import { useApi } from "../hooks/useApi";
import type { AIRecommendation, NearMissEvent } from "../types";
import { X, Sparkles, Loader2 } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie,
} from "recharts";

interface IntersectionStats {
  intersection_id: string;
  name: string;
  taps_today: number;
  crossings: { crossing_id: string; width_ft: number; max_extension_sec: number }[];
  hourly_distribution: { hour: number; count: number }[];
  recent_events: {
    event_time: string;
    crossing_id: string;
    card_type: number;
    filter_result: string;
    extension_sec: number | null;
    risk_level?: string;
  }[];
  latest_heartbeat: { edge_status: string } | null;
}

interface Props {
  intersectionId: string;
  onClose: () => void;
}

const CARD_ICONS: Record<number, string> = {
  1: "\u{1F474}",
  2: "\u267F",
  3: "\u{1F6B6}",
  4: "\u{1F9D2}",
};

const API_BASE = "";

const RISK_COLORS: Record<string, string> = {
  low: "#22C55E",
  medium: "#F59E0B",
  high: "#EA580C",
  critical: "#DC2626",
};

export function IntersectionDetail({ intersectionId, onClose }: Props) {
  const { data, loading } = useApi<IntersectionStats>(
    `/api/v1/analytics/intersection/${intersectionId}`,
    15000,
  );

  const [rec, setRec] = useState<AIRecommendation | null>(null);
  const [recLoading, setRecLoading] = useState(false);
  const [nearMisses, setNearMisses] = useState<NearMissEvent[]>([]);

  // Fetch near-misses for this intersection
  useEffect(() => {
    fetch(`${API_BASE}/api/v1/analytics/near-misses`)
      .then((r) => r.json())
      .then((all: NearMissEvent[]) => {
        setNearMisses(
          all.filter((e) => e.intersection_id === intersectionId).slice(0, 5),
        );
      })
      .catch(() => {});
  }, [intersectionId]);

  const fetchRecommendation = useCallback(async () => {
    setRecLoading(true);
    try {
      const resp = await fetch(`${API_BASE}/api/v1/ai/recommendation/${intersectionId}`);
      const json = await resp.json();
      setRec(json);
    } catch {
      setRec({
        intersection: "Unknown",
        recommendation: "AI unavailable",
        peak_hours: "N/A",
        confidence: "low",
        reasoning: "Could not reach AI service",
        estimated_impact: "N/A",
      });
    } finally {
      setRecLoading(false);
    }
  }, [intersectionId]);

  if (loading || !data) {
    return (
      <div style={{ background: "#1E293B", borderRadius: 12, padding: 24, flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Loader2 size={24} color="#0D9488" className="spin" />
      </div>
    );
  }

  const accepted = data.recent_events.filter((e) => e.filter_result === "accepted").length;
  const total = data.recent_events.length;
  const accRate = total > 0 ? Math.round((accepted / total) * 100) : 0;
  const avgExt = (() => {
    const exts = data.recent_events.filter((e) => e.extension_sec).map((e) => e.extension_sec!);
    return exts.length > 0 ? (exts.reduce((a, b) => a + b, 0) / exts.length).toFixed(1) : "0";
  })();

  // Chart data
  const chartData = data.hourly_distribution
    .filter((h) => h.hour >= 6 && h.hour <= 22)
    .map((h) => ({
      hour: `${h.hour % 12 || 12}${h.hour < 12 ? "a" : "p"}`,
      count: h.count,
    }));

  // Risk distribution for donut chart
  const riskCounts: Record<string, number> = { low: 0, medium: 0, high: 0, critical: 0 };
  for (const e of data.recent_events) {
    const rl = e.risk_level || "low";
    if (rl in riskCounts) riskCounts[rl]++;
  }
  const riskPieData = Object.entries(riskCounts)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value }));

  const totalAnalyzed = Object.values(riskCounts).reduce((a, b) => a + b, 0);
  const nearMissRate =
    totalAnalyzed > 0
      ? (((riskCounts.high + riskCounts.critical) / totalAnalyzed) * 100).toFixed(1)
      : "0";

  const last10 = data.recent_events.slice(0, 10);

  return (
    <div
      style={{
        background: "#1E293B",
        borderRadius: 12,
        padding: 16,
        flex: 1,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h3 style={{ color: "#F1F5F9", fontSize: 15, fontWeight: 600, margin: 0 }}>
          {data.name}
        </h3>
        <button
          onClick={onClose}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            color: "#94A3B8",
            padding: 4,
            display: "flex",
          }}
        >
          <X size={18} />
        </button>
      </div>

      {/* Stats row */}
      <div style={{ display: "flex", gap: 8 }}>
        {[
          { label: "Taps Today", value: data.taps_today, color: "#0D9488" },
          { label: "Accept Rate", value: `${accRate}%`, color: "#22C55E" },
          { label: "Avg Extension", value: `${avgExt}s`, color: "#F59E0B" },
        ].map((s) => (
          <div
            key={s.label}
            style={{
              flex: 1,
              background: "#0F172A",
              borderRadius: 8,
              padding: "8px 10px",
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: 10, color: "#64748B", textTransform: "uppercase", marginBottom: 4 }}>
              {s.label}
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, color: s.color }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Hourly chart */}
      <div style={{ height: 120, flexShrink: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
            <XAxis
              dataKey="hour"
              tick={{ fill: "#64748B", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "#64748B", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              allowDecimals={false}
            />
            <Tooltip
              contentStyle={{ background: "#0F172A", border: "1px solid #334155", borderRadius: 6, fontSize: 12 }}
              labelStyle={{ color: "#F1F5F9" }}
              itemStyle={{ color: "#0D9488" }}
            />
            <Bar dataKey="count" radius={[3, 3, 0, 0]}>
              {chartData.map((_, idx) => (
                <Cell key={idx} fill="#0D9488" />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Safety Analysis Section */}
      {(riskPieData.length > 0 || nearMisses.length > 0) && (
        <div style={{ flexShrink: 0 }}>
          <div style={{ fontSize: 11, color: "#64748B", textTransform: "uppercase", marginBottom: 8 }}>
            Safety Analysis
          </div>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            {riskPieData.length > 0 && (
              <div style={{ width: 80, height: 80, flexShrink: 0 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={riskPieData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={22}
                      outerRadius={36}
                      paddingAngle={2}
                      strokeWidth={0}
                    >
                      {riskPieData.map((entry) => (
                        <Cell
                          key={entry.name}
                          fill={RISK_COLORS[entry.name] || "#64748B"}
                        />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, color: "#F1F5F9", fontWeight: 600 }}>
                Near-miss rate: {nearMissRate}%
              </div>
              <div style={{ fontSize: 11, color: "#64748B", marginTop: 2 }}>
                {riskCounts.high} high, {riskCounts.critical} critical of {totalAnalyzed} analyzed
              </div>
            </div>
          </div>

          {/* Near-miss event list */}
          {nearMisses.length > 0 && (
            <div style={{ marginTop: 8 }}>
              {nearMisses.map((nm) => (
                <div
                  key={nm.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "4px 8px",
                    marginBottom: 3,
                    borderRadius: 6,
                    borderLeft: `2px solid ${RISK_COLORS[nm.risk_level] || "#EA580C"}`,
                    background: "#0F172A",
                    fontSize: 11,
                  }}
                >
                  {nm.image_path && (
                    <img
                      src={`${API_BASE}/images/${nm.image_path.split("/").pop()}`}
                      alt=""
                      style={{
                        width: 32,
                        height: 24,
                        borderRadius: 3,
                        objectFit: "cover",
                        flexShrink: 0,
                      }}
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = "none";
                      }}
                    />
                  )}
                  <span
                    style={{
                      fontSize: 9,
                      fontWeight: 700,
                      padding: "1px 4px",
                      borderRadius: 3,
                      background: `${RISK_COLORS[nm.risk_level] || "#EA580C"}22`,
                      color: RISK_COLORS[nm.risk_level] || "#EA580C",
                      textTransform: "uppercase",
                      flexShrink: 0,
                    }}
                  >
                    {nm.risk_level}
                  </span>
                  <span style={{ color: "#94A3B8", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {nm.vehicle_description || "Vehicle detected"}
                  </span>
                  <span style={{ color: "#475569", fontSize: 10, fontFamily: "monospace", flexShrink: 0 }}>
                    {new Date(nm.event_time).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Recent events compact list */}
      <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
        <div style={{ fontSize: 11, color: "#64748B", textTransform: "uppercase", marginBottom: 6 }}>
          Recent Events
        </div>
        {last10.map((e, i) => {
          const acc = e.filter_result === "accepted";
          return (
            <div
              key={`${e.event_time}-${i}`}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "5px 8px",
                marginBottom: 3,
                borderRadius: 6,
                borderLeft: `2px solid ${acc ? "#0D9488" : "#EF4444"}`,
                background: "#0F172A",
                fontSize: 12,
              }}
            >
              <span style={{ fontSize: 14 }}>{CARD_ICONS[e.card_type] ?? "\u{1F6B6}"}</span>
              <span style={{ color: "#94A3B8", flex: 1 }}>{e.crossing_id}</span>
              {acc ? (
                <span style={{ color: "#0D9488", fontWeight: 600 }}>+{e.extension_sec}s</span>
              ) : (
                <span style={{ color: "#EF4444", fontSize: 11 }}>
                  {e.filter_result.replace("rejected_", "")}
                </span>
              )}
              <span style={{ color: "#475569", fontSize: 10, fontFamily: "monospace" }}>
                {new Date(e.event_time).toLocaleTimeString()}
              </span>
            </div>
          );
        })}
      </div>

      {/* AI Recommendation */}
      {!rec ? (
        <button
          onClick={fetchRecommendation}
          disabled={recLoading}
          style={{
            background: recLoading ? "#334155" : "linear-gradient(135deg, #F59E0B22, #F59E0B11)",
            border: "1px solid #F59E0B44",
            borderRadius: 8,
            padding: "10px 16px",
            color: "#F59E0B",
            fontWeight: 600,
            fontSize: 13,
            cursor: recLoading ? "wait" : "pointer",
            display: "flex",
            alignItems: "center",
            gap: 8,
            justifyContent: "center",
          }}
        >
          {recLoading ? (
            <>
              <Loader2 size={14} className="spin" />
              Analyzing with Gemini...
            </>
          ) : (
            <>
              <Sparkles size={14} />
              AI Recommendation
            </>
          )}
        </button>
      ) : (
        <div
          style={{
            background: "#F59E0B0D",
            border: "1px solid #F59E0B33",
            borderRadius: 8,
            padding: 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
            <Sparkles size={14} color="#F59E0B" />
            <span style={{ color: "#F59E0B", fontWeight: 600, fontSize: 13 }}>
              AI Recommendation
            </span>
            <span
              style={{
                marginLeft: "auto",
                fontSize: 10,
                padding: "2px 6px",
                borderRadius: 4,
                background:
                  rec.confidence === "high" ? "#22C55E22" :
                  rec.confidence === "medium" ? "#F59E0B22" : "#EF444422",
                color:
                  rec.confidence === "high" ? "#22C55E" :
                  rec.confidence === "medium" ? "#F59E0B" : "#EF4444",
              }}
            >
              {rec.confidence} confidence
            </span>
          </div>
          <p style={{ color: "#F59E0B", fontSize: 13, fontWeight: 500, marginBottom: 8, lineHeight: 1.4 }}>
            {rec.recommendation}
          </p>
          <div style={{ fontSize: 11, color: "#94A3B8", lineHeight: 1.5 }}>
            <div><strong style={{ color: "#CBD5E1" }}>Peak hours:</strong> {rec.peak_hours}</div>
            <div style={{ marginTop: 4 }}><strong style={{ color: "#CBD5E1" }}>Reasoning:</strong> {rec.reasoning}</div>
            <div style={{ marginTop: 4 }}><strong style={{ color: "#CBD5E1" }}>Impact:</strong> {rec.estimated_impact}</div>
          </div>
        </div>
      )}
    </div>
  );
}
