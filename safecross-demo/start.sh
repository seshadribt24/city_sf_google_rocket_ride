#!/bin/bash
set -e

echo "=== SafeCross Demo — Starting all services ==="
cd "$(dirname "$0")"

# Ensure data/images directory exists for vision analysis
mkdir -p data/images

# Backend
echo "[1/6] Installing backend dependencies..."
pip install -q -r backend/requirements.txt

echo "[2/6] Starting backend..."
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
sleep 3

# Verify backend is up
if ! curl -s http://localhost:8000/api/v1/analytics/summary > /dev/null 2>&1; then
    echo "ERROR: Backend failed to start"
    exit 1
fi
echo "  Backend running (PID $BACKEND_PID)"

# Seed historical data (includes risk_level values for near-miss demo)
echo "[3/6] Seeding historical data..."
python -m simulator.seed_historical

# Generate crosswalk images if not already present
IMAGE_COUNT=$(find simulator/images -name "*.jpg" 2>/dev/null | wc -l)
if [ "$IMAGE_COUNT" -lt 8 ]; then
    echo "[4/6] Generating crosswalk images..."
    if [ -n "$GOOGLE_API_KEY" ]; then
        python simulator/download_streetview.py
    fi
    python simulator/generate_danger_images.py
else
    echo "[4/6] Crosswalk images already present ($IMAGE_COUNT files)"
fi

# Dashboard
echo "[5/6] Starting dashboard..."
(cd dashboard && npm install --silent && npm run dev -- --port 5173 &)
DASHBOARD_PID=$!
sleep 3
echo "  Dashboard running (PID $DASHBOARD_PID)"

# Simulator (with vision-enabled burst mode)
echo "[6/6] Starting simulator with vision analysis..."
echo "  Images: $(find simulator/images -name '*.jpg' 2>/dev/null | wc -l) crosswalk images loaded"
echo "  Danger: $(find simulator/images -name 'danger_*.jpg' 2>/dev/null | wc -l) danger scenarios"
echo ""
echo "=== SafeCross Demo Ready ==="
echo "  Dashboard: http://localhost:5173"
echo "  Backend:   http://localhost:8000"
echo "  API docs:  http://localhost:8000/docs"
echo ""

# Trap to clean up background processes on exit
trap "kill $BACKEND_PID $DASHBOARD_PID 2>/dev/null; echo 'Services stopped.'" EXIT

python -m simulator.tap_simulator --rate 4 --burst
