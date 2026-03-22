# SafeCross SF

**Adaptive pedestrian crossing system for San Francisco's High Injury Network.**

SafeCross extends walk signal times for seniors and disabled pedestrians at dangerous intersections. When a Clipper transit card is tapped on a pole-mounted NFC reader, the system identifies the cardholder type and — for eligible riders — commands the traffic signal controller to hold the walk phase longer.

## Architecture

```
NFC Reader (STM32 + PN5180)
        │ RS-485
        ▼
Edge Controller (Python/asyncio)
        │ SNMP/NTCIP
        ▼
Traffic Signal Controller
        │ HTTP/WebSocket
        ▼
Demo Dashboard (FastAPI + React + Gemini AI)
```

## Components

| Directory | Description | Tech |
|---|---|---|
| `safecross-nfc-firmware/` | Bare-metal firmware for pole-mounted NFC reader | C11, STM32F407, PN5180 SPI, RS-485 |
| `safecross-edge/` | Edge controller in traffic signal cabinet | Python 3.11+, asyncio, SNMP, RS-485 |
| `safecross-demo/` | Full-stack demo with live dashboard | FastAPI, React 19, Gemini 2.5 Flash, Mapbox |
| `CMSIS/`, `STM32F4xx_HAL_Driver/`, `cmsis_device_f4/` | ARM vendor libraries for firmware build | C, ARM Cortex-M4 |

## Quick Start (Demo)

```bash
cd safecross-demo

# Set your API keys
export GEMINI_API_KEY=your-gemini-key
export VITE_MAPBOX_TOKEN=your-mapbox-token  # optional

# Option 1: One command
chmod +x start.sh && ./start.sh

# Option 2: Docker
docker compose up --build
```

**Access:**
- Dashboard: http://localhost:5173
- API + Swagger docs: http://localhost:8000/docs
- WebSocket: ws://localhost:8000/ws/events

## Pilot Intersections

10 locations on SF's High Injury Network:

| Intersection | Widest Crossing | Max Extension |
|---|---|---|
| Market St & 5th St | 72 ft | 13s |
| Geary Blvd & Masonic Ave | 80 ft | 13s |
| Mission St & 16th St | 65 ft | 11s |
| Van Ness Ave & Eddy St | 95 ft | 13s |
| Stockton St & Clay St | 50 ft | 8s |
| 3rd St & Evans Ave | 70 ft | 12s |
| Taraval St & 19th Ave | 90 ft | 13s |
| Polk St & Turk St | 55 ft | 9s |
| Ocean Ave & Geneva Ave | 75 ft | 12s |
| Sutter St & Larkin St | 55 ft | 9s |

## Data & Simulation

```bash
cd safecross-demo

# Seed 30 days of historical tap events
python -m simulator.seed_historical

# Download Google Street View images (requires Maps API)
python simulator/download_streetview.py

# Generate danger scenario images (Gemini image gen + PIL fallback)
python simulator/generate_danger_images.py

# Run real-time simulator with burst mode
python -m simulator.tap_simulator --rate 4 --burst
```

## AI Features (Gemini 2.5 Flash)

- **Vision analysis** — Real-time crosswalk camera image assessment (vehicle proximity, risk level)
- **Safety insights** — Actionable recommendations for SFMTA traffic engineers
- **Timing recommendations** — Per-intersection timing change suggestions with confidence levels
- **Q&A** — Free-form questions answered with live system data

## Built & Tested with RocketRide

The entire SafeCross demo was built and tested inside the **RocketRide IDE**. RocketRide served as both our development environment and our testing workflow engine throughout the hackathon.

### Development Workflow

All 7 build prompts from the [demo prompting playbook](demo/safecross-demo-prompting-playbook.md) and the 5 vision feature prompts from the [vision playbook](demo/safecross-vision-prompting-playbook.md) were executed inside RocketRide's Claude Code integration. The IDE managed the full build cycle: project scaffolding, backend API, React dashboard, simulator, and Gemini AI integration.

### Webhook Testing Pipeline

RocketRide's visual pipeline builder was used to test the event ingestion workflow end-to-end. The pipeline (`web-hook-pipeline.pipe`) defines a three-stage flow:

```
Webhook Source  →  Parse (extract tags)  →  Response Text
```

This let us fire simulated NFC tap events into the FastAPI backend (`POST /api/v1/events`) and verify the full chain — event storage, Gemini vision analysis, WebSocket broadcast, and dashboard updates — without needing real hardware. The webhook source accepts the same `EventBatch` JSON payload the edge controller produces, making it a drop-in substitute for the RS-485 reader during development.

### RocketRide Configuration

```env
ROCKETRIDE_URI=http://localhost:5565
ROCKETRIDE_APIKEY=<your-key>
```

The RocketRide instance runs locally on port 5565. Set these in your root `.env` to connect the IDE to the testing pipeline.

## Key Docs

- [`safecross-nfc-firmware-spec.md`](safecross-nfc-firmware-spec.md) — Firmware specification
- [`safecross-edge/SPEC.md.md`](safecross-edge/SPEC.md.md) — Edge controller specification
- [`safecross-demo/SAFECROSS_AI_GUIDE.md`](safecross-demo/SAFECROSS_AI_GUIDE.md) — Full AI session guide (paste into Claude/Gemini for context)
- [`safecross-edge-prompting-playbook.md`](safecross-edge-prompting-playbook.md) — Claude Code prompting playbook

## License

This project was built for the City of San Francisco hackathon.
