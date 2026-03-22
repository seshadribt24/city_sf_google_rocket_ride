import { useEffect, useState } from "react";
import { PersonStanding } from "lucide-react";

export function Header() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header
      style={{
        background: "#1E293B",
        borderBottom: "1px solid #334155",
        padding: "0 24px",
        height: 56,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      {/* Logo */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <PersonStanding size={28} color="#0D9488" />
        <span style={{ fontSize: 20, fontWeight: 700, color: "#F1F5F9" }}>
          SafeCross
        </span>
        <span
          style={{ fontSize: 14, color: "#94A3B8", fontWeight: 400, marginLeft: 4 }}
        >
          SF
        </span>
      </div>

      {/* Status */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: "#22C55E",
            display: "inline-block",
          }}
        />
        <span style={{ color: "#94A3B8", fontSize: 14 }}>
          10 intersections online
        </span>
      </div>

      {/* Clock */}
      <span style={{ color: "#94A3B8", fontSize: 14, fontFamily: "monospace" }}>
        {time.toLocaleTimeString()}
      </span>
    </header>
  );
}
