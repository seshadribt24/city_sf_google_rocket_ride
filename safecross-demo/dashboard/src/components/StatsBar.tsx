import { useEffect, useRef, useState } from "react";
import { useApi } from "../hooks/useApi";
import type { AnalyticsSummary, RiskSummaryItem } from "../types";
import { Activity, Clock, CheckCircle, AlertTriangle } from "lucide-react";

function AnimatedNumber({ value, decimals = 0 }: { value: number; decimals?: number }) {
  const [display, setDisplay] = useState(value);
  const prev = useRef(value);
  const frameRef = useRef<number>(0);

  useEffect(() => {
    const start = prev.current;
    const end = value;
    const duration = 600;
    const startTime = performance.now();

    const animate = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(start + (end - start) * eased);
      if (progress < 1) frameRef.current = requestAnimationFrame(animate);
    };

    frameRef.current = requestAnimationFrame(animate);
    prev.current = value;
    return () => cancelAnimationFrame(frameRef.current);
  }, [value]);

  return <>{display.toFixed(decimals)}</>;
}

export function StatsBar() {
  const { data } = useApi<AnalyticsSummary>("/api/v1/analytics/summary", 10000);
  const { data: riskData } = useApi<RiskSummaryItem[]>("/api/v1/analytics/risk-summary", 10000);

  const nearMissCount = (riskData ?? []).reduce(
    (sum, r) => sum + (r.high_count ?? 0) + (r.critical_count ?? 0),
    0,
  );

  const cards = [
    {
      label: "Extensions Today",
      value: data?.total_extensions_today ?? 0,
      color: "#0D9488",
      icon: Activity,
      decimals: 0,
      suffix: "",
    },
    {
      label: "Avg Extension",
      value: data?.avg_extension_sec ?? 0,
      color: "#F59E0B",
      icon: Clock,
      decimals: 1,
      suffix: "s",
    },
    {
      label: "Acceptance Rate",
      value: data?.acceptance_rate ?? 0,
      color: "#22C55E",
      icon: CheckCircle,
      decimals: 1,
      suffix: "%",
    },
    {
      label: "Near Misses",
      value: nearMissCount,
      color: nearMissCount > 0 ? "#EA580C" : "#64748B",
      icon: AlertTriangle,
      decimals: 0,
      suffix: "",
    },
  ];

  return (
    <div style={{ display: "flex", gap: 12 }}>
      {cards.map(({ label, value, color, icon: Icon, decimals, suffix }) => (
        <div
          key={label}
          style={{
            flex: 1,
            background: "#1E293B",
            borderRadius: 12,
            padding: "16px 18px",
            border: `1px solid ${color}33`,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <Icon size={16} color={color} />
            <span style={{ color: "#94A3B8", fontSize: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
              {label}
            </span>
          </div>
          <div style={{ fontSize: 28, fontWeight: 700, color }}>
            <AnimatedNumber value={value} decimals={decimals} />
            {suffix}
          </div>
        </div>
      ))}
    </div>
  );
}
