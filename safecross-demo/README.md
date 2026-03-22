# SafeCross SF — Adaptive Pedestrian Crossing System

AI-powered system that extends walk signals for seniors and disabled pedestrians at San Francisco's most dangerous intersections.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     React Dashboard (:5173)                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │  Mapbox   │  │  Stats   │  │  Event   │  │  AI Safety │  │
│  │  GL Map   │  │  Bar     │  │  Feed    │  │  Analyst   │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────┬──────┘  │
│                                                   │         │
│                    WebSocket ◄─────────────────────┼─────┐   │
└────────────────────┬──────────────────────────────┘     │   │
                     │ REST API                           │   │
┌────────────────────▼────────────────────────────────────┤   │
│                FastAPI Backend (:8000)                   │   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐│   │
│  │  Events  │  │Analytics │  │    AI    │  │WebSocket ├┘   │
│  │  Routes  │  │  Routes  │  │  Routes  │  │ Manager  │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────┘    │
│       │              │              │                        │
│  ┌────▼──────────────▼──┐    ┌─────▼──────┐                 │
│  │  SQLite (aiosqlite)  │    │  Gemini AI │                 │
│  └──────────────────────┘    └────────────┘                 │
└─────────────────────────────────────────────────────────────┘
         ▲
         │ POST /api/v1/events
┌────────┴────────────────┐
│    Tap Simulator        │
│  (realistic NFC events) │
└─────────────────────────┘
```

## Quick Start

### Manual (recommended for development)

```bash
# 1. Set environment variables
export GEMINI_API_KEY=your-key-here
export VITE_MAPBOX_TOKEN=your-token-here  # optional, for map

# 2. Start backend
cd safecross-demo
pip install -r backend/requirements.txt
python -m simulator.seed_historical          # seed 30 days of data
uvicorn backend.main:app --port 8000 &

# 3. Start dashboard
cd dashboard && npm install && npm run dev &

# 4. Start simulator
cd .. && python -m simulator.tap_simulator --rate 4 --burst
```

Or use the all-in-one script:
```bash
chmod +x start.sh && ./start.sh
```

### Docker

```bash
echo "GEMINI_API_KEY=your-key" > .env
docker compose up --build
```

Open **http://localhost:5173**

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google Gemini API key for AI insights |
| `VITE_MAPBOX_TOKEN` | No | Mapbox GL token for the map (shows fallback without it) |

## Tech Stack

- **Backend:** FastAPI, SQLite (aiosqlite), Python 3.12
- **Frontend:** React 19, TypeScript, Vite, Mapbox GL JS, Recharts
- **AI:** Google Gemini 2.5 Flash — real-time crossing pattern analysis
- **Real-time:** WebSocket for live event streaming
- **Deployment:** Docker Compose, nginx

## Pilot Intersections (SF High Injury Network)

| # | Intersection | Widest Crossing |
|---|---|---|
| 1 | Market St & 5th St | 72 ft (NS) |
| 2 | Geary Blvd & Masonic Ave | 80 ft (NS) |
| 3 | Mission St & 16th St | 65 ft (NS) |
| 4 | Van Ness Ave & Eddy St | 95 ft (NS) |
| 5 | Stockton St & Clay St | 50 ft |
| 6 | 3rd St & Evans Ave | 70 ft (NS) |
| 7 | Taraval St & 19th Ave | 90 ft (NS) |
| 8 | Polk St & Turk St | 55 ft (NS) |
| 9 | Ocean Ave & Geneva Ave | 75 ft (NS) |
| 10 | Sutter St & Larkin St | 55 ft (NS) |

## Screenshots

_Screenshots of the live dashboard will be added here._

## Team

_Team members will be listed here._
