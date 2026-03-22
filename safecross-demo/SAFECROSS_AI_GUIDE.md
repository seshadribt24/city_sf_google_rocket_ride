# SafeCross SF — AI Session Guide

> **Paste this entire file into a Claude or Gemini session to give the AI full context on how to run the SafeCross demo and work with pedestrian crossing data.**

**Repo:** https://github.com/seshadribt24/city_sf_google_rocket_ride

---

## 1. Project Overview

SafeCross is a smart pedestrian signal system that **extends walk times for seniors and disabled pedestrians** at San Francisco's high-injury intersections. It uses NFC card readers (Clipper transit cards) to identify eligible pedestrians, then sends SNMP commands to traffic signal controllers to extend the walk phase.

### Architecture

```
┌──────────────────┐     RS-485      ┌──────────────────┐     SNMP/NTCIP     ┌──────────────────┐
│  NFC Firmware     │ ──────────────► │  Edge Controller  │ ──────────────────► │ Signal Controller │
│  (STM32 + PN5180) │                │  (Python/asyncio) │                     │ (Econolite/McCain)│
└──────────────────┘                 └────────┬─────────┘                     └──────────────────┘
                                              │ HTTP/WebSocket
                                              ▼
                                     ┌──────────────────┐
                                     │  Demo App         │
                                     │  FastAPI + React  │
                                     │  + Gemini AI      │
                                     └──────────────────┘
```

The **demo app** (`safecross-demo/`) is a full-stack simulation with:
- **Backend:** FastAPI (Python 3.12), SQLite, Google Gemini 2.5 Flash for vision analysis
- **Dashboard:** React 19 + TypeScript + Vite, Mapbox GL map, Recharts, real-time WebSocket feed
- **Simulator:** Generates realistic NFC tap events with optional crosswalk camera images

---

## 2. Running the Demo

### Prerequisites

- Python 3.12+
- Node.js 22+
- A Google Gemini API key (for AI vision analysis and insights)
- (Optional) A Mapbox token for the map layer

### Environment Variables

Create a `.env` file in `safecross-demo/`:

```bash
GEMINI_API_KEY=your-gemini-api-key-here
VITE_MAPBOX_TOKEN=your-mapbox-token-here  # optional, dashboard falls back gracefully
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | Yes | — | Google Gemini API key (vision analysis + AI insights) |
| `VITE_MAPBOX_TOKEN` | No | `""` | Mapbox GL token for map visualization |
| `SAFECROSS_DB` | No | `safecross.db` | SQLite database path |
| `API_URL` | No | `http://localhost:8000` | Backend URL (used by simulator in Docker) |
| `RATE` | No | `3` | Simulator events per minute |
| `BURST` | No | `false` | Enable burst mode (5 events every 30s) |

### Option A: One-Command Start (recommended)

```bash
cd safecross-demo
chmod +x start.sh && ./start.sh
```

This script:
1. Installs backend dependencies
2. Starts the FastAPI backend on port 8000
3. Seeds 30 days of historical data
4. Generates crosswalk + danger images
5. Starts the React dashboard on port 5173
6. Starts the tap simulator in burst mode

### Option B: Manual Step-by-Step

```bash
cd safecross-demo

# 1. Install backend
pip install -r backend/requirements.txt

# 2. Start backend
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &

# 3. Seed 30 days of historical data
python -m simulator.seed_historical

# 4. Generate crosswalk images (danger scenarios + synthetic backgrounds)
python simulator/generate_danger_images.py

# 5. (Optional) Download real Google Street View images
python simulator/download_streetview.py

# 6. Start dashboard
cd dashboard && npm install && npm run dev &

# 7. Start simulator
cd .. && python -m simulator.tap_simulator --rate 4 --burst
```

### Option C: Docker Compose

```bash
cd safecross-demo
echo "GEMINI_API_KEY=your-key" > .env
docker compose up --build
```

Services: backend (port 8000), dashboard (port 5173), simulator (auto-seeds + runs).

### Access Points

| Service | URL |
|---|---|
| Dashboard | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |
| WebSocket | ws://localhost:8000/ws/events |

---

## 3. Pilot Intersections (SF High Injury Network)

All 10 intersections are hardcoded in `backend/seed_data.py`:

| ID | Name | Lat | Lng | NS Width (ft) | EW Width (ft) | Max Extension |
|---|---|---|---|---|---|---|
| INT-2025-0001 | Market St & 5th St | 37.7837 | -122.4073 | 72 | 48 | 13s |
| INT-2025-0002 | Geary Blvd & Masonic Ave | 37.7842 | -122.4462 | 80 | 60 | 13s |
| INT-2025-0003 | Mission St & 16th St | 37.7650 | -122.4194 | 65 | 50 | 11s |
| INT-2025-0004 | Van Ness Ave & Eddy St | 37.7836 | -122.4213 | 95 | 45 | 13s |
| INT-2025-0005 | Stockton St & Clay St | 37.7934 | -122.4082 | 50 | 50 | 8s |
| INT-2025-0006 | 3rd St & Evans Ave | 37.7432 | -122.3872 | 70 | 55 | 12s |
| INT-2025-0007 | Taraval St & 19th Ave | 37.7434 | -122.4756 | 90 | 45 | 13s |
| INT-2025-0008 | Polk St & Turk St | 37.7824 | -122.4186 | 55 | 50 | 9s |
| INT-2025-0009 | Ocean Ave & Geneva Ave | 37.7235 | -122.4419 | 75 | 60 | 12s |
| INT-2025-0010 | Sutter St & Larkin St | 37.7876 | -122.4182 | 55 | 50 | 9s |

**High-risk intersections** (elevated danger rates in simulation): Market St & 5th St, Van Ness Ave & Eddy St.

**Extension formula:** `extension = round(width_ft / 3.5 * 1.2 - base_walk_sec)`, clamped to `[4, 13]` seconds.

---

## 4. Getting Pedestrian Crossing Data

### 4.1 Seed 30 Days of Historical Data

```bash
python -m simulator.seed_historical
```

**What it generates:**
- ~1,500-2,000 tap events over 30 days (~50-80/day)
- Populates SQLite tables: `tap_events`, `heartbeats`, `intersections`
- Realistic time-of-day distribution:

| Hour | Multiplier | Period |
|---|---|---|
| 7-8am, 4-5pm | 3.0x | Rush hour |
| 10am-2pm | 1.5x | Midday |
| 5-6am, 7-11pm | 0.5x | Off-peak |
| Midnight-4am | 0.1x | Overnight |
| Other | 1.0x | Baseline |

**Card type distribution:**
- 65% Senior RTC (card_type=1) — accepted
- 10% Disabled RTC (card_type=2) — accepted
- 20% Standard Adult (card_type=3) — rejected
- 5% Youth (card_type=4) — rejected

**Filter results for eligible cards:** 90% accepted, 5% rejected_cooldown, 3% rejected_clearance, 2% rejected_duplicate.

**Risk level distribution:**
- Normal intersections: 75% low, 15% medium, 8% high, 2% critical
- High-risk intersections (Market & 5th, Van Ness & Eddy): 55% low, 20% medium, 16% high, 9% critical

**UID tracking:** 50 "regular" UIDs reused 60% of the time to simulate repeat pedestrians.

### 4.2 Download Real Street View Images

```bash
python simulator/download_streetview.py
```

Requires `GEMINI_API_KEY` (also used as Google Maps API key). Downloads 40 images (10 intersections x 4 compass headings) at 640x480 resolution.

**API call format:**
```
https://maps.googleapis.com/maps/api/streetview
  ?size=640x480
  &location={lat},{lng}
  &heading={0|90|180|270}
  &pitch=-10
  &fov=90
  &key={GEMINI_API_KEY}
```

**Output:** `simulator/images/INT-2025-XXXX_{heading}.jpg`

### 4.3 Real-Time Tap Simulator

```bash
python -m simulator.tap_simulator --rate 4 --burst
```

| Flag | Default | Description |
|---|---|---|
| `--rate` | 2 | Base events per minute (scaled by time-of-day) |
| `--api-url` | `http://localhost:8000` | Backend URL |
| `--burst` | off | Demo mode: 5 events every 30s, forces accepted taps, alternates danger/safe images |

**Intersection weighting:** Market & 5th = 3x, Geary/Mission/Stockton = 2x, others = 1x.

**Image attachment:** 70% of events include a crosswalk camera image (100% in burst mode). High-risk intersections have 20% chance of danger images. Burst mode alternates safe/danger every other event.

### 4.4 Tap Event Schema

```json
{
  "device_id": "EDGE-0001",
  "intersection_id": "INT-2025-0001",
  "events": [
    {
      "event_time": "2026-03-22T14:30:45.123456+00:00",
      "crossing_id": "NS",
      "card_type": 1,
      "card_uid_hash": "abc12345",
      "read_method": 1,
      "filter_result": "accepted",
      "extension_sec": 6,
      "phase_state_at_tap": "walk",
      "snmp_result": "success",
      "image_base64": "<optional base64 JPEG>",
      "risk_level": "high"
    }
  ]
}
```

### 4.5 Database Schema

```sql
CREATE TABLE tap_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    intersection_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    event_time TEXT NOT NULL,
    crossing_id TEXT NOT NULL,
    card_type INTEGER NOT NULL,       -- 1=senior, 2=disabled, 3=adult, 4=youth
    card_uid_hash TEXT NOT NULL,
    read_method INTEGER NOT NULL,     -- 1=tap, 2=hold
    filter_result TEXT NOT NULL,      -- accepted, rejected_cooldown, rejected_clearance, rejected_duplicate, rejected_card_type
    extension_sec INTEGER,            -- 4-13 seconds if accepted
    phase_state_at_tap TEXT NOT NULL,  -- walk, ped_clear, dont_walk
    snmp_result TEXT NOT NULL,        -- success, not_sent
    risk_level TEXT DEFAULT 'unknown', -- low, medium, high, critical
    vision_analysis TEXT,             -- JSON blob from Gemini
    image_path TEXT                   -- /images/{event_id}.jpg
);

CREATE TABLE heartbeats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    intersection_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    edge_status TEXT NOT NULL,
    reader_status TEXT NOT NULL,
    signal_controller_status TEXT NOT NULL,
    uptime_sec INTEGER NOT NULL,
    events_pending INTEGER NOT NULL,
    last_extension_time TEXT,
    software_version TEXT NOT NULL
);

CREATE TABLE intersections (
    intersection_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    name TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    crossings TEXT NOT NULL  -- JSON array
);
```

---

## 5. Generating Synthetic Danger Scenarios

### 5.1 Generate Danger Images

```bash
python simulator/generate_danger_images.py
```

Creates 4 danger scenario images in `simulator/images/`:

| Filename | Scenario | Gemini Prompt |
|---|---|---|
| `danger_vehicle_close.jpg` | Silver sedan approaching ~15ft | "Add realistic silver sedan approaching the crosswalk from the right side, about 15 feet away. The car should look like it's moving toward the crosswalk at moderate speed." |
| `danger_vehicle_in_crosswalk.jpg` | White SUV blocking crosswalk | "Add a realistic white SUV that is stopped directly inside the crosswalk, blocking pedestrian passage." |
| `danger_turning.jpg` | Pickup truck mid-right-turn | "Add a realistic dark pickup truck making a right turn at the intersection corner, cutting close to the crosswalk." |
| `danger_double_parked.jpg` | Delivery van blocking sightlines | "Add a realistic delivery van double-parked very close to the crosswalk on the right side of the road, partially blocking the view." |

**Generation pipeline:**
1. Loads base images from `simulator/images/` (Street View downloads or synthetic backgrounds)
2. Sends base image + prompt to `gemini-2.5-flash-image` model for image editing
3. Falls back to PIL-drawn colored rectangles if Gemini is unavailable

**PIL fallback** creates 640x480 synthetic crosswalk backgrounds: dark gray road, white stripes, light gray sidewalks, camera timestamp overlay, then draws colored rectangles representing vehicles at scenario-appropriate positions.

If no Street View images exist, it also generates `synthetic_01.jpg` through `synthetic_10.jpg` as generic intersection backgrounds.

### 5.2 Vision Analysis Pipeline

When a tap event includes an `image_base64` field, the backend sends it to **Gemini 2.5 Flash** for real-time risk assessment.

**Gemini vision prompt** (from `backend/gemini_client.py`):

```
You are a traffic safety AI analyzing a crosswalk camera image from
{intersection_name} ({crossing_id} crossing) in San Francisco.
A senior pedestrian has just activated an extended crossing signal.

Assess:
1. Is a vehicle within dangerous proximity of the crosswalk? (yes/no)
2. Risk level: low (no vehicles nearby), medium (vehicle present but
   yielding), high (vehicle close and moving toward crosswalk),
   critical (vehicle in or about to enter crosswalk)
3. Vehicle type and estimated distance from crosswalk if present
4. Any other safety concerns (blocked sightlines, double-parked cars,
   construction, poor lighting)

Respond with ONLY valid JSON, no markdown:
{"vehicle_present": true/false, "risk_level": "low|medium|high|critical",
 "vehicle_description": "description or null",
 "estimated_distance_ft": number or null,
 "safety_concerns": "description or empty string"}
```

**VisionAnalysis response schema:**

```json
{
  "vehicle_present": true,
  "risk_level": "high",
  "vehicle_description": "Silver sedan approaching from right",
  "estimated_distance_ft": 15.0,
  "safety_concerns": "Vehicle moving toward crosswalk at moderate speed",
  "analysis_time_ms": 1234
}
```

**Concurrency controls:** max 3 concurrent requests, max 10 queued, 15-second timeout per image, images resized to max 640px width.

**Risk level definitions:**
| Level | Meaning |
|---|---|
| `low` | No vehicles nearby |
| `medium` | Vehicle present but yielding |
| `high` | Vehicle close and moving toward crosswalk |
| `critical` | Vehicle in or about to enter crosswalk |

### 5.3 AI Insights Generation

The backend also uses Gemini for traffic engineering insights:

- **`GET /api/v1/ai/insights`** — Analyzes crossing patterns (5-min cache), returns 3-4 actionable bullet points for SFMTA engineers
- **`GET /api/v1/ai/recommendation/{intersection_id}`** — Specific timing recommendation with confidence level
- **`POST /api/v1/ai/ask`** — Free-form Q&A with full system context

**System context** provided to all AI calls:
```
You are an AI traffic safety analyst for SafeCross SF, an adaptive pedestrian
crossing system deployed at 10 pilot intersections on San Francisco's High
Injury Network. The system uses NFC card readers to detect seniors and disabled
pedestrians, then extends walk signal times via SNMP commands to the signal
controller. Card types: 1=senior RTC, 2=disabled RTC, 3=standard adult
(rejected), 4=youth (rejected). Filter results: accepted (extension granted),
rejected_cooldown, rejected_clearance, rejected_duplicate, rejected_card_type.
```

---

## 6. API Reference

### Events & Heartbeats
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/events` | Receive tap event batch (with optional images for vision analysis) |
| POST | `/api/v1/heartbeat` | Receive device heartbeat |

### Analytics
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/analytics/summary` | Daily stats (taps, extensions, acceptance rate) |
| GET | `/api/v1/analytics/intersections` | All intersections with today's tap count |
| GET | `/api/v1/analytics/intersection/{id}` | Detailed stats, hourly distribution, recent events |
| GET | `/api/v1/analytics/heatmap` | Location data with weights for map layer |
| GET | `/api/v1/analytics/near-misses` | High/critical risk events with vision analysis |
| GET | `/api/v1/analytics/risk-summary` | Risk stats by intersection |

### AI / Insights
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/ai/insights` | Cached AI-generated insights (5-min TTL) |
| GET | `/api/v1/ai/recommendation/{id}` | Timing recommendation for intersection |
| POST | `/api/v1/ai/ask` | Custom question about system data |

### Real-Time
| Protocol | Endpoint | Description |
|---|---|---|
| WebSocket | `/ws/events` | Live event stream + near-miss alerts |

---

## 7. Key Files Reference

| File | Purpose |
|---|---|
| `start.sh` | One-command startup script |
| `docker-compose.yml` | Multi-container Docker deployment |
| `.env` / `.env.example` | Environment variable configuration |
| `backend/main.py` | FastAPI app setup, WebSocket, lifespan |
| `backend/models.py` | Pydantic models (TapEvent, VisionAnalysis, Heartbeat) |
| `backend/database.py` | Async SQLite operations, schema migrations |
| `backend/gemini_client.py` | Gemini API client (vision + text + insights) |
| `backend/seed_data.py` | 10 pilot intersection definitions |
| `backend/routes_events.py` | POST /api/v1/events + vision analysis pipeline |
| `backend/routes_analytics.py` | Analytics endpoints including risk summary |
| `backend/routes_ai.py` | AI endpoints (insights, recommendations, Q&A) |
| `backend/websocket_manager.py` | Real-time event broadcasting |
| `simulator/tap_simulator.py` | Real-time NFC tap event generator |
| `simulator/seed_historical.py` | 30-day historical data seeder |
| `simulator/generate_danger_images.py` | Danger scenario image generator (Gemini + PIL fallback) |
| `simulator/download_streetview.py` | Google Street View image downloader |
| `dashboard/src/` | React 19 + TypeScript frontend |
| `dashboard/package.json` | Frontend dependencies (Mapbox GL, Recharts, Lucide) |
