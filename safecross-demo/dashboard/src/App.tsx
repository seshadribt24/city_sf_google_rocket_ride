import { useState } from "react";
import { DemoBanner } from "./components/DemoBanner";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Header } from "./components/Header";
import { StatsBar } from "./components/StatsBar";
import { MapView } from "./components/MapView";
import { EventFeed } from "./components/EventFeed";
import { IntersectionDetail } from "./components/IntersectionDetail";
import { AIInsightsPanel } from "./components/AIInsightsPanel";
import { NearMissAlert } from "./components/NearMissAlert";
import { useWebSocket } from "./hooks/useWebSocket";

const WS_URL =
  (window.location.protocol === "https:" ? "wss:" : "ws:") +
  "//" +
  window.location.host +
  "/ws/events";

function App() {
  const { events, isConnected, nearMissAlerts, dismissAlert } = useWebSocket(WS_URL);
  const [selectedIntersection, setSelectedIntersection] = useState<string | null>(null);

  return (
    <div
      style={{
        background: "#0F172A",
        color: "#F1F5F9",
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        fontFamily: "'Inter', -apple-system, sans-serif",
      }}
    >
      <DemoBanner />
      <Header />

      <div
        style={{
          flex: 1,
          display: "flex",
          gap: 16,
          padding: 16,
          overflow: "hidden",
        }}
      >
        {/* Left — Map (55%) */}
        <div style={{ flex: "0 0 55%", minHeight: 0 }}>
          <ErrorBoundary>
            <MapView
              wsEvents={events}
              nearMissAlerts={nearMissAlerts}
              onSelectIntersection={(id) => setSelectedIntersection(id)}
            />
          </ErrorBoundary>
        </div>

        {/* Right — Panels (45%) */}
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            gap: 12,
            minHeight: 0,
            overflow: "hidden",
          }}
        >
          <ErrorBoundary>
            <StatsBar />
          </ErrorBoundary>

          <div style={{ position: "relative", marginBottom: 4 }}>
            <span
              style={{
                display: "inline-block",
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: isConnected ? "#22C55E" : "#EF4444",
                marginRight: 6,
              }}
            />
            <span style={{ color: "#64748B", fontSize: 11 }}>
              {isConnected ? "WebSocket connected" : "WebSocket disconnected"}
            </span>
          </div>

          <ErrorBoundary>
            {selectedIntersection ? (
              <IntersectionDetail
                intersectionId={selectedIntersection}
                onClose={() => setSelectedIntersection(null)}
              />
            ) : (
              <EventFeed events={events} />
            )}
          </ErrorBoundary>

          <ErrorBoundary>
            <AIInsightsPanel />
          </ErrorBoundary>
        </div>
      </div>

      {/* Near-miss alert toasts */}
      <NearMissAlert
        alerts={nearMissAlerts}
        onDismiss={dismissAlert}
      />
    </div>
  );
}

export default App;
