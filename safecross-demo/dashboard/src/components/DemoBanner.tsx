export function DemoBanner() {
  return (
    <div
      style={{
        background: "linear-gradient(90deg, #7C3AED22, #EF444422, #7C3AED22)",
        borderBottom: "1px solid #EF444433",
        padding: "6px 16px",
        textAlign: "center",
        fontSize: 12,
        color: "#F59E0B",
        fontWeight: 500,
        letterSpacing: 0.3,
      }}
    >
      {"\uD83D\uDD34"} DEMO MODE — Simulated data from 10 pilot intersections on SF's High Injury Network
    </div>
  );
}
