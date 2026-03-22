import { useState, useEffect, useCallback, useRef } from "react";
import { useApi } from "../hooks/useApi";
import type { AIInsights } from "../types";
import { RefreshCw, Send, MessageSquare, BarChart3 } from "lucide-react";

// ── Helpers ──────────────────────────────────────────────────────────────────

function timeAgo(ts: number): string {
  const diff = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

const INSIGHT_ICONS = ["\u{1F4CD}", "\u23F0", "\u26A0\uFE0F", "\u2705"];

function pickIcon(text: string): string {
  const lower = text.toLowerCase();
  if (lower.includes("intersection") || lower.includes("location") || lower.includes("market") || lower.includes("mission"))
    return INSIGHT_ICONS[0]; // 📍
  if (lower.includes("time") || lower.includes("hour") || lower.includes("peak") || lower.includes("am") || lower.includes("pm"))
    return INSIGHT_ICONS[1]; // ⏰
  if (lower.includes("reject") || lower.includes("problem") || lower.includes("concern") || lower.includes("issue"))
    return INSIGHT_ICONS[2]; // ⚠️
  return INSIGHT_ICONS[3]; // ✅
}

function highlightText(text: string): React.ReactElement[] {
  // Highlight intersection names and numbers
  const parts = text.split(
    /(\b(?:Market|Geary|Mission|Van Ness|Stockton|3rd|Taraval|Polk|Ocean|Sutter)\b[^,.)]*(?:St|Ave|Blvd)[^,.)]* ?& ?[^,.)]*(?:St|Ave|Blvd)?|\d+(?:\.\d+)?(?:\s*(?:seconds?|sec|s|%|taps?))\b)/gi
  );
  return parts.map((part, i) => {
    if (
      /(?:Market|Geary|Mission|Van Ness|Stockton|3rd|Taraval|Polk|Ocean|Sutter)/i.test(part)
    ) {
      return (
        <span key={i} style={{ color: "#0D9488", fontWeight: 600 }}>
          {part}
        </span>
      );
    }
    if (/\d+(?:\.\d+)?(?:\s*(?:seconds?|sec|s|%|taps?))/i.test(part)) {
      return (
        <span key={i} style={{ color: "#F59E0B", fontWeight: 600 }}>
          {part}
        </span>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

// ── Typewriter effect ────────────────────────────────────────────────────────

function Typewriter({ text, speed = 8 }: { text: string; speed?: number }) {
  const [displayed, setDisplayed] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    setDisplayed("");
    setDone(false);
    let idx = 0;
    const id = setInterval(() => {
      idx++;
      setDisplayed(text.slice(0, idx));
      if (idx >= text.length) {
        setDone(true);
        clearInterval(id);
      }
    }, speed);
    return () => clearInterval(id);
  }, [text, speed]);

  return (
    <span>
      {done ? highlightText(displayed) : displayed}
      {!done && <span className="typing-cursor">|</span>}
    </span>
  );
}

// ── Chat message type ────────────────────────────────────────────────────────

interface ChatMessage {
  role: "user" | "ai";
  text: string;
}

// ── Example question chips ───────────────────────────────────────────────────

const EXAMPLE_QUESTIONS = [
  "Which intersection needs the longest extensions?",
  "When are seniors most active at Stockton & Clay?",
  "Should we permanently increase walk time at Van Ness?",
  "Which intersections have the most vehicle conflicts?",
];

// ── Main Component ───────────────────────────────────────────────────────────

export function AIInsightsPanel() {
  const [mode, setMode] = useState<"insights" | "ask">("insights");
  const { data, loading, error, refetch } = useApi<AIInsights>("/api/v1/ai/insights");
  const [fetchedAt, setFetchedAt] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [, setTick] = useState(0);

  // Chat state
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [askLoading, setAskLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Track when insights were fetched
  useEffect(() => {
    if (data && !loading) setFetchedAt(Date.now());
  }, [data, loading]);

  // Update "time ago" display
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 10000);
    return () => clearInterval(id);
  }, []);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  }, [refetch]);

  const handleAsk = useCallback(
    async (q: string) => {
      if (!q.trim() || askLoading) return;
      const userQ = q.trim();
      setQuestion("");
      setChatHistory((prev) => [...prev.slice(-9), { role: "user", text: userQ }]);
      setAskLoading(true);
      try {
        const resp = await fetch("/api/v1/ai/ask", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: userQ }),
        });
        const json = await resp.json();
        setChatHistory((prev) => [
          ...prev,
          { role: "ai", text: json.answer || "No response" },
        ]);
      } catch {
        setChatHistory((prev) => [
          ...prev,
          { role: "ai", text: "AI analysis temporarily unavailable." },
        ]);
      } finally {
        setAskLoading(false);
      }
    },
    [askLoading],
  );

  // Scroll to bottom on new chat messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory, askLoading]);

  // Parse insights into bullet cards
  const insightCards = (data?.insights ?? "")
    .split(/\n/)
    .map((l) => l.replace(/^[\s*•\-]+/, "").trim())
    .filter((l) => l.length > 20);

  return (
    <div className="ai-panel">
      {/* Gradient border wrapper */}
      <div className="ai-panel-inner">
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 18 }}>{"\u{1F9E0}"}</span>
            <h3
              style={{
                color: "#F1F5F9",
                fontSize: 15,
                margin: 0,
                fontWeight: 700,
              }}
            >
              AI Safety Analyst
            </h3>
          </div>
          {/* Mode toggle */}
          <div
            style={{
              display: "flex",
              background: "#0F172A",
              borderRadius: 6,
              padding: 2,
              gap: 2,
            }}
          >
            <button
              onClick={() => setMode("insights")}
              className={`ai-tab ${mode === "insights" ? "ai-tab-active" : ""}`}
            >
              <BarChart3 size={12} />
              Insights
            </button>
            <button
              onClick={() => setMode("ask")}
              className={`ai-tab ${mode === "ask" ? "ai-tab-active" : ""}`}
            >
              <MessageSquare size={12} />
              Ask AI
            </button>
          </div>
        </div>

        {/* MODE 1 — Insights */}
        {mode === "insights" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, flex: 1, overflow: "hidden" }}>
            {(loading || refreshing) && (
              <div className="ai-loading">
                <span className="typing-dots">
                  Analyzing crossing patterns
                  <span className="dot1">.</span>
                  <span className="dot2">.</span>
                  <span className="dot3">.</span>
                </span>
              </div>
            )}

            {error && !loading && (
              <p style={{ color: "#EF4444", fontSize: 13, padding: 8 }}>
                AI analysis unavailable. Retrying...
              </p>
            )}

            {!loading && !refreshing && insightCards.length > 0 && (
              <div
                style={{
                  flex: 1,
                  overflowY: "auto",
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                }}
              >
                {insightCards.map((text, i) => (
                  <div
                    key={i}
                    className="insight-card"
                    style={{ animationDelay: `${i * 0.1}s` }}
                  >
                    <span style={{ fontSize: 16, flexShrink: 0 }}>
                      {pickIcon(text)}
                    </span>
                    <p
                      style={{
                        color: "#CBD5E1",
                        fontSize: 12,
                        lineHeight: 1.55,
                        margin: 0,
                      }}
                    >
                      {highlightText(text)}
                    </p>
                  </div>
                ))}
              </div>
            )}

            {/* Footer */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                paddingTop: 8,
                borderTop: "1px solid #ffffff0a",
              }}
            >
              <span style={{ fontSize: 10, color: "#475569" }}>
                {fetchedAt > 0 && `Updated ${timeAgo(fetchedAt)}`}
                {data?.cached && " (cached)"}
              </span>
              <button
                onClick={handleRefresh}
                disabled={refreshing}
                style={{
                  background: "none",
                  border: "1px solid #334155",
                  borderRadius: 6,
                  color: "#94A3B8",
                  fontSize: 11,
                  padding: "4px 10px",
                  cursor: refreshing ? "wait" : "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                <RefreshCw size={11} className={refreshing ? "spin" : ""} />
                Refresh
              </button>
            </div>

            {/* Powered by badge */}
            <div style={{ textAlign: "center", paddingTop: 4 }}>
              <span className="gemini-badge">
                {"\u2728"} Powered by Google Gemini
              </span>
            </div>
          </div>
        )}

        {/* MODE 2 — Ask AI */}
        {mode === "ask" && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              flex: 1,
              overflow: "hidden",
              gap: 8,
            }}
          >
            {/* Chat history */}
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                display: "flex",
                flexDirection: "column",
                gap: 8,
                minHeight: 60,
              }}
            >
              {chatHistory.length === 0 && !askLoading && (
                <div style={{ padding: "8px 0" }}>
                  <p
                    style={{
                      color: "#64748B",
                      fontSize: 12,
                      marginBottom: 10,
                    }}
                  >
                    Ask about crossing patterns, timing, or safety data:
                  </p>
                  <div
                    style={{
                      display: "flex",
                      flexWrap: "wrap",
                      gap: 6,
                    }}
                  >
                    {EXAMPLE_QUESTIONS.map((q) => (
                      <button
                        key={q}
                        onClick={() => handleAsk(q)}
                        className="example-chip"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {chatHistory.map((msg, i) => (
                <div
                  key={i}
                  className={`chat-bubble ${msg.role === "user" ? "chat-user" : "chat-ai"}`}
                >
                  {msg.role === "ai" ? (
                    <Typewriter text={msg.text} speed={6} />
                  ) : (
                    msg.text
                  )}
                </div>
              ))}

              {askLoading && (
                <div className="chat-bubble chat-ai">
                  <span className="typing-dots">
                    Thinking
                    <span className="dot1">.</span>
                    <span className="dot2">.</span>
                    <span className="dot3">.</span>
                  </span>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Input */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleAsk(question);
              }}
              style={{ display: "flex", gap: 6 }}
            >
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask about crossing patterns..."
                disabled={askLoading}
                className="ai-input"
              />
              <button
                type="submit"
                disabled={askLoading || !question.trim()}
                className="ai-send-btn"
              >
                <Send size={14} />
              </button>
            </form>

            {/* Powered by badge */}
            <div style={{ textAlign: "center", paddingTop: 2 }}>
              <span className="gemini-badge">
                {"\u2728"} Powered by Google Gemini
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
