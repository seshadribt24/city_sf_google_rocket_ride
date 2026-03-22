# SafeCross SF — Demo Build Spec (Claude Code)

## Context for Claude Code

You are building a hackathon demo for SafeCross SF — an AI-powered adaptive pedestrian crossing system for seniors. The system extends pedestrian walk signals when a senior taps their Clipper transit card at an NFC reader on the signal pole.

**Layers 1 and 2 are already built.** Layer 1 is C firmware for an NFC reader. Layer 2 is a Python edge controller that receives card tap events and sends NTCIP/SNMP commands to extend walk signals. Both are tested and working.

**What you're building now is the demo stack** — everything a judge needs to see in a 60-second live demo:

1. **Tap simulator** — generates realistic card tap events (we don't have hardware at the hackathon)
2. **Cloud API** — receives events from edge controllers, stores them, serves analytics
3. **Ops dashboard** — React app with live map, event feed, intersection detail
4. **AI insights panel** — Gemini-powered natural language analysis of crossing patterns

**Hackathon constraints:**
- Must use Gemini (Google product requirement)
- Must use RocketRide IDE extension (build the project in RocketRide)
- The demo must look compelling in 60 seconds
- Prioritize visual impact over production robustness

---

## Architecture overview

```
┌──────────────────┐     POST /api/v1/events      ┌─────────────────────┐
│  Tap Simulator   │ ─────────────────────────────▶│   FastAPI Backend   │
│  (Python script) │     POST /api/v1/heartbeat    │   (Layer 3)         │
│                  │ ─────────────────────────────▶│                     │
└──────────────────┘                                │  ┌───────────────┐ │
                                                    │  │  SQLite DB    │ │
                                                    │  └───────────────┘ │
                                                    │  ┌───────────────┐ │
                                                    │  │  Gemini API   │ │
                                                    │  └───────────────┘ │
                                                    └────────┬────────────┘
                                                             │
                                            GET /api/v1/analytics/*
                                            GET /api/v1/ai/insights
                                            WebSocket /ws/events
                                                             │
                                                    ┌────────▼────────────┐
                                                    │  React Dashboard    │
                                                    │  (Layer 5)          │
                                                    │  - Live map         │
                                                    │  - Event feed       │
                                                    │  - AI insights      │
                                                    └─────────────────────┘
```

---

## Data contracts (from Layer 2 spec — do not change)

### POST `/api/v1/events` — edge controller reports tap events

```json
{
  "device_id": "EDGE-0042",
  "intersection_id": "INT-2025-0042",
  "events": [
    {
      "event_time": "2026-03-21T14:32:05.123Z",
      "crossing_id": "NS",
      "card_type": 1,
      "card_uid_hash": "a1b2c3d4",
      "read_method": 2,
      "filter_result": "accepted",
      "extension_sec": 8,
      "phase_state_at_tap": "PED_WALK",
      "snmp_result": "ok"
    }
  ]
}
```

**Card types:** 0 = unknown, 1 = senior RTC, 2 = disabled RTC, 3 = standard adult, 4 = youth

**Filter results:** "accepted", "rejected_cooldown", "rejected_clearance", "rejected_duplicate", "rejected_card_type"

**SNMP results:** "ok", "timeout", "error", "simulated"

### POST `/api/v1/heartbeat` — edge controller health check

```json
{
  "device_id": "EDGE-0042",
  "intersection_id": "INT-2025-0042",
  "timestamp": "2026-03-21T14:35:00Z",
  "edge_status": "ok",
  "reader_status": "ok",
  "signal_controller_status": "auto",
  "uptime_sec": 86420,
  "events_pending": 0,
  "last_extension_time": "2026-03-21T14:32:05Z",
  "software_version": "1.0.0"
}
```

---

## Intersection seed data

Use these 10 real SF intersections on the High Injury Network. These are the demo's "pilot deployment."

```python
PILOT_INTERSECTIONS = [
    {
        "intersection_id": "INT-2025-0001",
        "device_id": "EDGE-0001",
        "name": "Market St & 5th St",
        "lat": 37.7837, "lng": -122.4073,
        "crossings": [
            {"crossing_id": "NS", "width_ft": 72, "base_walk_sec": 7, "max_extension_sec": 13},
            {"crossing_id": "EW", "width_ft": 48, "base_walk_sec": 7, "max_extension_sec": 8},
        ]
    },
    {
        "intersection_id": "INT-2025-0002",
        "device_id": "EDGE-0002",
        "name": "Geary Blvd & Masonic Ave",
        "lat": 37.7842, "lng": -122.4462,
        "crossings": [
            {"crossing_id": "NS", "width_ft": 80, "max_extension_sec": 13},
            {"crossing_id": "EW", "width_ft": 60, "max_extension_sec": 10},
        ]
    },
    {
        "intersection_id": "INT-2025-0003",
        "device_id": "EDGE-0003",
        "name": "Mission St & 16th St",
        "lat": 37.7650, "lng": -122.4194,
        "crossings": [
            {"crossing_id": "NS", "width_ft": 65, "max_extension_sec": 11},
            {"crossing_id": "EW", "width_ft": 50, "max_extension_sec": 8},
        ]
    },
    {
        "intersection_id": "INT-2025-0004",
        "device_id": "EDGE-0004",
        "name": "Van Ness Ave & Eddy St",
        "lat": 37.7836, "lng": -122.4213,
        "crossings": [
            {"crossing_id": "NS", "width_ft": 95, "max_extension_sec": 13},
            {"crossing_id": "EW", "width_ft": 45, "max_extension_sec": 8},
        ]
    },
    {
        "intersection_id": "INT-2025-0005",
        "device_id": "EDGE-0005",
        "name": "Stockton St & Clay St",
        "lat": 37.7934, "lng": -122.4082,
        "crossings": [
            {"crossing_id": "NS", "width_ft": 50, "max_extension_sec": 8},
            {"crossing_id": "EW", "width_ft": 50, "max_extension_sec": 8},
        ]
    },
    {
        "intersection_id": "INT-2025-0006",
        "device_id": "EDGE-0006",
        "name": "3rd St & Evans Ave",
        "lat": 37.7432, "lng": -122.3872,
        "crossings": [
            {"crossing_id": "NS", "width_ft": 70, "max_extension_sec": 12},
            {"crossing_id": "EW", "width_ft": 55, "max_extension_sec": 9},
        ]
    },
    {
        "intersection_id": "INT-2025-0007",
        "device_id": "EDGE-0007",
        "name": "Taraval St & 19th Ave",
        "lat": 37.7434, "lng": -122.4756,
        "crossings": [
            {"crossing_id": "NS", "width_ft": 90, "max_extension_sec": 13},
            {"crossing_id": "EW", "width_ft": 45, "max_extension_sec": 7},
        ]
    },
    {
        "intersection_id": "INT-2025-0008",
        "device_id": "EDGE-0008",
        "name": "Polk St & Turk St",
        "lat": 37.7824, "lng": -122.4186,
        "crossings": [
            {"crossing_id": "NS", "width_ft": 55, "max_extension_sec": 9},
            {"crossing_id": "EW", "width_ft": 50, "max_extension_sec": 8},
        ]
    },
    {
        "intersection_id": "INT-2025-0009",
        "device_id": "EDGE-0009",
        "name": "Ocean Ave & Geneva Ave",
        "lat": 37.7235, "lng": -122.4419,
        "crossings": [
            {"crossing_id": "NS", "width_ft": 75, "max_extension_sec": 12},
            {"crossing_id": "EW", "width_ft": 60, "max_extension_sec": 10},
        ]
    },
    {
        "intersection_id": "INT-2025-0010",
        "device_id": "EDGE-0010",
        "name": "Sutter St & Larkin St",
        "lat": 37.7876, "lng": -122.4182,
        "crossings": [
            {"crossing_id": "NS", "width_ft": 55, "max_extension_sec": 9},
            {"crossing_id": "EW", "width_ft": 50, "max_extension_sec": 8},
        ]
    },
]
```

---

## Project structure

```
safecross-demo/
├── simulator/
│   ├── tap_simulator.py          # Generates realistic tap events
│   └── seed_historical.py        # Seeds 30 days of historical data
├── backend/
│   ├── main.py                   # FastAPI app entry point
│   ├── models.py                 # Pydantic models for all API contracts
│   ├── database.py               # SQLite setup + queries
│   ├── seed_data.py              # Intersection definitions (from above)
│   ├── routes_events.py          # POST /api/v1/events, /heartbeat
│   ├── routes_analytics.py       # GET analytics endpoints
│   ├── routes_ai.py              # GET /api/v1/ai/insights, /ai/ask
│   ├── gemini_client.py          # Gemini API integration
│   ├── websocket_manager.py      # WebSocket broadcast for live events
│   └── requirements.txt
├── dashboard/
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx               # Main layout
│   │   ├── components/
│   │   │   ├── MapView.tsx       # Mapbox GL map with intersection markers
│   │   │   ├── EventFeed.tsx     # Real-time scrolling event log
│   │   │   ├── StatsBar.tsx      # Summary counters at top
│   │   │   ├── IntersectionDetail.tsx  # Drill-down panel
│   │   │   ├── AIInsights.tsx    # Gemini-powered insights panel
│   │   │   └── Header.tsx        # Logo + system status
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts   # WebSocket hook for live events
│   │   │   └── useApi.ts         # REST API hook
│   │   ├── types.ts              # TypeScript interfaces
│   │   └── index.tsx
│   └── public/
│       └── index.html
├── docker-compose.yml            # Runs everything together
└── README.md
```

---

## Prompt sequence

### Prompt 1: Project skeleton + backend foundation

```
Create the SafeCross demo project. This is a hackathon demo for an adaptive
pedestrian crossing system.

Create the directory structure:
  safecross-demo/
    simulator/
    backend/
    dashboard/

Start with the backend. Create backend/main.py with a FastAPI app.

backend/models.py — Pydantic models:
- TapEvent: event_time (datetime), crossing_id (str), card_type (int 0-4),
  card_uid_hash (str), read_method (int), filter_result (str), extension_sec
  (optional int), phase_state_at_tap (str), snmp_result (str)
- EventBatch: device_id (str), intersection_id (str), events (list[TapEvent])
- Heartbeat: device_id, intersection_id, timestamp, edge_status, reader_status,
  signal_controller_status, uptime_sec, events_pending, last_extension_time,
  software_version
- IntersectionInfo: intersection_id, device_id, name, lat (float), lng (float),
  crossings (list of dicts with crossing_id, width_ft, max_extension_sec)

backend/seed_data.py — paste in the PILOT_INTERSECTIONS list from the spec
(10 real SF intersections with coordinates and crossing definitions).

backend/database.py — SQLite with aiosqlite:
- Tables: tap_events (matching the TapEvent fields + id, intersection_id,
  device_id), heartbeats, intersections (loaded from seed_data on startup)
- Functions: init_db(), insert_events(), insert_heartbeat(),
  get_events(since, intersection_id=None, limit=100),
  get_summary(), get_intersection_stats(intersection_id),
  get_hourly_distribution(intersection_id=None),
  get_heatmap_data()
- The init_db function should create tables and insert the 10 pilot
  intersections if the intersections table is empty.

backend/requirements.txt:
  fastapi
  uvicorn[standard]
  aiosqlite
  pydantic
  httpx
  google-generativeai
  python-dotenv

backend/main.py:
- Call init_db() on startup
- Mount routes from routes_events, routes_analytics, routes_ai
- Add CORS middleware allowing all origins
- Add a WebSocket endpoint at /ws/events
- Run on port 8000

Create a simple backend/websocket_manager.py:
- ConnectionManager class with connect(), disconnect(), broadcast()
- Singleton instance

Create backend/routes_events.py:
- POST /api/v1/events — validate EventBatch, insert each event into DB,
  broadcast each event via WebSocket as JSON (include intersection name and
  coords from seed data), return {"status": "ok", "events_received": N}
- POST /api/v1/heartbeat — insert heartbeat, return {"status": "ok"}

Create backend/routes_analytics.py:
- GET /api/v1/analytics/summary — returns total taps today, total extensions
  today, avg extension seconds, unique intersections active, acceptance rate
- GET /api/v1/analytics/intersections — returns list of all 10 intersections
  with their latest heartbeat status and today's tap count
- GET /api/v1/analytics/intersection/{intersection_id} — returns that
  intersection's details + hourly tap distribution for last 24h +
  last 20 events
- GET /api/v1/analytics/heatmap — returns list of {lat, lng, weight} where
  weight is tap count in last 24h, for the map heatmap layer

Test: run `uvicorn backend.main:app --reload` and verify all endpoints return
valid JSON. POST a test event manually with curl.
```

### Prompt 2: Tap simulator

```
Create simulator/tap_simulator.py — a script that generates realistic card
tap events and POSTs them to the backend API.

The simulator should:

1. Run in an infinite loop, generating tap events at a configurable rate.

2. Realistic timing patterns:
   - Peak hours: 7-9am and 4-6pm (3x event rate)
   - Moderate: 10am-3pm (1.5x rate)
   - Low: early morning and evening (0.5x rate)
   - Very low: midnight-5am (0.1x rate)
   Use the current hour to determine the rate multiplier.

3. Card type distribution (realistic for SF senior crossings):
   - 65% senior RTC (card_type=1)
   - 10% disabled RTC (card_type=2)
   - 20% standard adult (card_type=3) — these get rejected by filter
   - 5% youth (card_type=4) — also rejected

4. Filter results:
   - Senior and disabled cards: 90% accepted, 5% rejected_cooldown,
     3% rejected_clearance, 2% rejected_duplicate
   - Standard and youth cards: 100% rejected_card_type

5. For accepted taps, calculate extension_sec based on the intersection's
   crossing width: extension = max(min_ext, min(max_ext,
   round(width_ft / 3.5 * 1.2 - base_walk)))
   Clamp to min 4, max 13 seconds.

6. Randomly pick from the 10 pilot intersections, weighted:
   - Market & 5th: weight 3 (busiest)
   - Geary & Masonic, Mission & 16th, Stockton & Clay: weight 2
   - All others: weight 1

7. Generate unique card_uid_hash values (8-char hex) but reuse some UIDs
   to simulate repeat users. Keep a pool of ~50 "regular" UIDs that appear
   60% of the time.

8. POST events individually or in small batches (1-3) to
   http://localhost:8000/api/v1/events

9. Send heartbeats for all 10 intersections every 60 seconds to
   http://localhost:8000/api/v1/heartbeat

10. Command line args:
    --rate: base events per minute (default 2)
    --api-url: backend URL (default http://localhost:8000)
    --burst: if set, send 5 events in rapid succession every 30 seconds
      (useful for demo — shows events appearing in real time on dashboard)

11. Log each event to console with colored output:
    GREEN for accepted taps, RED for rejected, YELLOW for heartbeats.

Also create simulator/seed_historical.py that generates 30 days of
historical data and bulk-inserts it into the database (not via API, directly
into SQLite). This provides the AI analytics with enough data to find
meaningful patterns.

The historical data should follow the same timing and distribution patterns,
generating roughly 50-80 events per day across all intersections. Insert
about 2,000 total historical events.

Run seed_historical.py first, then test tap_simulator.py and verify events
appear at GET /api/v1/analytics/summary.
```

### Prompt 3: Gemini AI integration

```
Create the Gemini AI integration. This is the most important part for
hackathon scoring — AI must be visibly core to the solution.

backend/gemini_client.py:
- Use the google-generativeai Python SDK
- Load GEMINI_API_KEY from environment variable or .env file
- Use model "gemini-2.0-flash" (fast, cheap, good enough for demo)
- Create a SafeCrossAI class with these methods:

1. generate_insights(events_summary: dict) -> str
   Given a summary of recent tap data (from the analytics endpoints), generate
   a natural-language insights report. The prompt to Gemini should be:

   """
   You are an AI traffic safety analyst for SafeCross SF, an adaptive
   pedestrian crossing system that extends walk signals for seniors.

   Analyze this crossing data and provide 3-4 actionable insights for
   SFMTA traffic engineers. Focus on:
   - Which intersections have the highest senior crossing demand
   - Time-of-day patterns that suggest permanent timing changes
   - Any intersections where rejection rates suggest a problem
   - Specific recommendations with numbers (e.g., "increase baseline
     walk time by 8 seconds at Market & 5th during 8-9am")

   Data:
   {json_summary}

   Respond in 3-4 concise bullet points. Be specific with intersection
   names, times, and recommended seconds. No hedging language.
   """

2. generate_recommendation(intersection_data: dict) -> dict
   Given detailed data for one intersection, generate a specific timing
   recommendation. Return structured JSON:
   {
     "intersection": "Market St & 5th St",
     "recommendation": "Increase baseline walk time by 8 seconds",
     "peak_hours": "8:00-9:00 AM, 4:00-5:30 PM",
     "confidence": "high",
     "reasoning": "34 senior taps per day during morning peak...",
     "estimated_impact": "Would eliminate 89% of extension requests during peak"
   }

   Use Gemini's JSON mode for structured output. The prompt should instruct
   Gemini to return ONLY valid JSON matching that schema.

3. answer_question(question: str, context: dict) -> str
   A free-form Q&A endpoint where engineers can ask questions about the
   crossing data. The prompt should include the full system context and
   current data summary as context.

backend/routes_ai.py:
- GET /api/v1/ai/insights — calls generate_insights with the current
  analytics summary. Cache results for 5 minutes (don't call Gemini on
  every request).
- GET /api/v1/ai/recommendation/{intersection_id} — calls
  generate_recommendation for that intersection
- POST /api/v1/ai/ask — accepts {"question": "..."} body, calls
  answer_question with the question + current analytics context
- All AI endpoints should gracefully handle Gemini API errors — return
  a fallback message like "AI analysis temporarily unavailable" rather
  than crashing.

Create a .env.example file:
  GEMINI_API_KEY=your-api-key-here

Test: seed historical data, then call GET /api/v1/ai/insights and verify
Gemini returns meaningful, specific recommendations referencing actual
intersection names and numbers from the data.
```

### Prompt 4: React dashboard — layout + map

```
Create the React dashboard. Use Vite + React + TypeScript.

cd safecross-demo && npm create vite@latest dashboard -- --template react-ts
cd dashboard && npm install

Install dependencies:
  npm install mapbox-gl @types/mapbox-gl recharts lucide-react

Use Mapbox GL JS for the map. Use the Mapbox token from environment
variable VITE_MAPBOX_TOKEN. If no token is set, show a fallback message.
For the hackathon demo, we'll use a free Mapbox token.

dashboard/src/types.ts — TypeScript interfaces matching all API models:
- TapEvent, EventBatch, Heartbeat, IntersectionInfo, AnalyticsSummary,
  HeatmapPoint, AIInsights, AIRecommendation

dashboard/src/App.tsx — Main layout:
- Dark theme (bg: #0F172A, cards: #1E293B, accent: #0D9488 teal,
  highlight: #F59E0B amber)
- Header bar with SafeCross logo (walking icon + text), system status
  indicator (green dot + "10 intersections online"), current time
- Below header: 3-column layout
  - Left column (55%): MapView component
  - Right column (45%): split vertically
    - Top: StatsBar (4 metric cards)
    - Middle: EventFeed (scrolling live events)
    - Bottom: AIInsights panel

dashboard/src/components/Header.tsx:
- Dark bar across top
- SafeCross SF logo left-aligned
- "10 intersections online" with green dot, center
- Live clock, right-aligned

dashboard/src/components/StatsBar.tsx:
- 4 horizontal metric cards:
  1. "Extensions Today" — big number, teal
  2. "Avg Extension" — seconds with 1 decimal, amber
  3. "Acceptance Rate" — percentage, green
  4. "Active Intersections" — count, blue
- Fetch from GET /api/v1/analytics/summary every 10 seconds
- Numbers should animate when they change (count-up effect)

dashboard/src/components/MapView.tsx:
- Mapbox GL map centered on SF (37.76, -122.44), zoom 12
- Dark map style: mapbox://styles/mapbox/dark-v11
- Markers for each of the 10 intersections:
  - Default: teal circle with white dot
  - When a new tap event arrives via WebSocket: marker pulses (CSS
    animation, scales up and fades) in amber for 3 seconds, then
    returns to teal
  - Marker size proportional to today's tap count (min 12px, max 28px)
- Click a marker to select it — opens IntersectionDetail panel
  (replaces EventFeed temporarily)
- Optional: heatmap layer using GET /api/v1/analytics/heatmap

dashboard/src/hooks/useWebSocket.ts:
- Connect to ws://localhost:8000/ws/events
- Parse incoming JSON messages as TapEvent + intersection metadata
- Expose: events (array, most recent 50), isConnected (boolean)
- Auto-reconnect on disconnect with exponential backoff

dashboard/src/hooks/useApi.ts:
- Simple fetch wrapper: useApi<T>(url, refreshInterval?)
- Returns { data, loading, error, refetch }

Make sure the dashboard runs on port 5173 (Vite default) and proxies
API requests to localhost:8000. Add a vite.config.ts proxy:
  server: { proxy: { '/api': 'http://localhost:8000', '/ws': { target: 'http://localhost:8000', ws: true } } }

Test: start the backend, start the dashboard, verify the map renders
with 10 markers and the stats bar shows zeros.
```

### Prompt 5: Event feed + intersection detail

```
Build the real-time event feed and intersection detail panel.

dashboard/src/components/EventFeed.tsx:
- Scrolling list of the most recent 30 tap events from WebSocket
- Each event card shows:
  - Intersection name (e.g., "Market St & 5th St")
  - Crossing direction (NS/EW)
  - Card type icon: 👴 senior, ♿ disabled, 🚶 adult, 🧒 youth
  - Filter result: green "EXTENDED +8s" for accepted, red "REJECTED"
    with reason for rejected
  - Timestamp (relative: "12s ago", "2m ago")
- New events slide in from the top with a brief animation
- Accepted events have a subtle green-left-border, rejected have red
- Show a "Waiting for events..." placeholder when empty with a
  pulsing dot animation

dashboard/src/components/IntersectionDetail.tsx:
- Shown when a map marker is clicked (replaces EventFeed)
- Header: intersection name + back button (X) to return to EventFeed
- Stats row: today's taps, acceptance rate, avg extension for this
  intersection
- Hourly bar chart (using Recharts BarChart):
  - X axis: hour of day (6am-10pm)
  - Y axis: tap count
  - Bars colored teal for accepted, stacked red for rejected
  - Fetched from GET /api/v1/analytics/intersection/{id}
- Last 10 events list (compact version of EventFeed)
- "AI Recommendation" button that fetches
  GET /api/v1/ai/recommendation/{id} and displays the structured
  recommendation in a highlighted card:
  - Recommendation text in amber
  - Peak hours, confidence level, reasoning, estimated impact
  - Loading spinner while Gemini responds

Test: run the simulator with --burst flag, verify events appear in the
feed in real time with sliding animation. Click an intersection marker,
verify the detail panel shows the hourly chart. Click the AI
Recommendation button and verify Gemini returns a meaningful suggestion.
```

### Prompt 6: AI insights panel

```
Build the AI insights panel. This is the centerpiece of the demo for
the hackathon judges — it must be visually prominent and clearly show
AI generating real value.

dashboard/src/components/AIInsights.tsx:
- Fixed panel at the bottom-right of the dashboard
- Header: "🧠 AI Safety Analyst" with a subtle animated gradient
  border (teal to purple) to draw the eye
- Two modes:

  MODE 1 — Auto-generated insights (default):
  - On mount, fetch GET /api/v1/ai/insights
  - Display Gemini's bullet-point insights as styled cards
  - Each insight card has:
    - An icon (📍 for location-specific, ⏰ for timing, ⚠️ for warning,
      ✅ for recommendation)
    - The insight text, with intersection names and numbers highlighted
      in teal/amber
    - A subtle "Powered by Gemini" badge
  - "Refresh Insights" button to re-fetch
  - "Last updated: 2m ago" timestamp
  - While loading: show a typing animation ("Analyzing crossing
    patterns..." with animated dots)

  MODE 2 — Ask the AI (toggle):
  - Text input: "Ask about crossing patterns..."
  - Submit button
  - Displays Gemini's response in a chat-style bubble
  - Example questions shown as clickable chips:
    "Which intersection needs the longest extensions?"
    "When are seniors most active at Stockton & Clay?"
    "Should we permanently increase walk time at Van Ness?"
  - Chat history persists during the session (up to 10 exchanges)

Styling:
- The entire AI panel should feel distinct from the rest of the
  dashboard — use a subtle purple-tinted background (#1a1a2e) to
  differentiate it from the teal/dark theme
- The Gemini responses should stream in with a typewriter effect
  if possible (or at minimum a loading state followed by fade-in)
- Include the Gemini logo or a "Powered by Google Gemini" watermark
  at the bottom of the panel

Test the full demo flow:
1. Start backend: cd backend && uvicorn main:app --reload
2. Seed data: cd simulator && python seed_historical.py
3. Start dashboard: cd dashboard && npm run dev
4. Start simulator: cd simulator && python tap_simulator.py --rate 4 --burst
5. Open dashboard at localhost:5173
6. Verify: map shows markers, events scroll in, stats update, AI
   insights panel shows meaningful analysis
7. Click an intersection → verify detail panel with chart + AI
   recommendation
8. Ask the AI a question → verify coherent response
```

### Prompt 7: Docker compose + polish

```
Create docker-compose.yml to run everything with one command.

services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
    volumes:
      - ./data:/app/data  # persist SQLite

  dashboard:
    build: ./dashboard
    ports: ["5173:5173"]  # or 80 if using nginx
    depends_on: [backend]

  simulator:
    build: ./simulator
    depends_on: [backend]
    environment:
      - API_URL=http://backend:8000
      - RATE=3
      - BURST=true

Create Dockerfiles for each service. The dashboard Dockerfile should
build the Vite app and serve it (use a multi-stage build with nginx,
or just use `npm run preview`).

Also create a simple start.sh script for running without Docker:
  #!/bin/bash
  # Terminal 1: Backend
  cd backend && pip install -r requirements.txt && python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
  # Seed data
  cd simulator && python seed_historical.py
  # Terminal 2: Dashboard
  cd dashboard && npm install && npm run dev &
  # Terminal 3: Simulator
  sleep 5 && cd simulator && python tap_simulator.py --rate 4 --burst

Final polish:
- Add a README.md with:
  - One-line description
  - Architecture diagram (ASCII)
  - Quick start instructions (both Docker and manual)
  - Environment variables needed
  - Screenshots section (placeholder)
  - Tech stack list
  - Team members section

- Add error boundaries in the React app so a single component crash
  doesn't take down the whole dashboard

- Add a "Demo Mode" banner at the top of the dashboard:
  "🔴 DEMO MODE — Simulated data from 10 pilot intersections"
  This is honest and judges appreciate transparency.

Test the complete flow end-to-end. The demo should be launchable with
a single command and produce a visually compelling dashboard within
10 seconds of starting.
```

---

## Demo script (what to show in 60 seconds)

This is the sequence to follow during the live presentation:

1. **[0-10s]** Show the dashboard with the map. "Here's our live operations dashboard monitoring 10 pilot intersections across SF's High Injury Network."

2. **[10-20s]** Point to the event feed. "Watch — a senior just tapped their Clipper card at Market & 5th. The system granted an 8-second extension in under 500 milliseconds." (The simulator's burst mode ensures events are flowing.)

3. **[20-30s]** Click on a map marker. "Let me drill into Market & 5th — you can see the hourly crossing pattern. Peak demand is 8-9 AM when seniors are heading to appointments."

4. **[30-40s]** Click the AI Recommendation button. "Here's where Gemini comes in — it analyzes crossing patterns across all intersections and generates specific timing recommendations for SFMTA engineers."

5. **[40-50s]** Switch to the AI insights panel. "The AI Safety Analyst runs continuously. Right now it's recommending a permanent 8-second baseline increase at Market & 5th during morning peak — that would eliminate 89% of extension requests."

6. **[50-60s]** Ask the AI a question. Type: "Which intersection should we prioritize next?" "Engineers can ask questions in natural language. The AI draws on the full dataset to give specific, actionable answers."

---

## Troubleshooting prompts

If Gemini API returns errors:
```
The Gemini API is returning 429 rate limit errors. Add retry logic with
exponential backoff (1s, 2s, 4s) to gemini_client.py. Also add a
response cache — cache insights for 5 minutes and recommendations for
2 minutes to reduce API calls. If all retries fail, return a graceful
fallback message.
```

If WebSocket events aren't showing in the dashboard:
```
WebSocket events from the simulator aren't appearing in the React
dashboard. Debug the WebSocket chain:
1. Verify the FastAPI WebSocket endpoint at /ws/events accepts connections
2. Verify websocket_manager.broadcast() is called in routes_events.py
   after inserting events
3. Verify the React useWebSocket hook connects and parses messages
4. Check browser console for WebSocket errors
Add console.log at each step to trace where events are being lost.
```

If the map doesn't render:
```
The Mapbox map is blank. This is likely a token issue. Check:
1. Is VITE_MAPBOX_TOKEN set in dashboard/.env?
2. Is the token valid? Test at https://api.mapbox.com/tokens/v2?access_token=YOUR_TOKEN
3. Fallback: replace Mapbox with a simple SVG map of SF with circle
   markers positioned by pixel coordinates. Less pretty but works
   without a token.
```

---

## Estimated build time

| Component | Prompts | Estimated time |
|-----------|---------|----------------|
| Backend + DB | Prompt 1 | 30-45 min |
| Simulator | Prompt 2 | 20-30 min |
| Gemini integration | Prompt 3 | 20-30 min |
| Dashboard layout + map | Prompt 4 | 30-45 min |
| Event feed + detail | Prompt 5 | 30-40 min |
| AI insights panel | Prompt 6 | 30-40 min |
| Docker + polish | Prompt 7 | 20-30 min |
| **Total** | **7 prompts** | **~3-4 hours** |

---

## Key assumptions (not yet verified)

- **Gemini API key**: You need a valid Google AI Studio API key. Get one at https://aistudio.google.com/apikey — the free tier should be sufficient for the demo.
- **Mapbox token**: You need a Mapbox access token. The free tier allows 50K map loads/month which is plenty. Get one at https://account.mapbox.com/access-tokens/
- **RocketRide IDE**: The spec assumes you'll run these prompts inside RocketRide's IDE extension. If RocketRide has its own Claude Code integration, use that. The prompts are written to be copy-pasted directly.
- **Network access**: The demo needs outbound HTTPS to Gemini API and Mapbox tile servers. Verify the hackathon venue has internet access.
- **No real hardware**: The entire demo runs on simulated data. This is honest and expected at a hackathon — the simulator accurately models what real hardware would produce.
