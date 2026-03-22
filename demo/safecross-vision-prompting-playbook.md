# SafeCross SF — Vision Near-Miss Detection Prompting Playbook

**5 prompts. Copy-paste each one into Claude Code in sequence.**
**Estimated total: 2.5–3 hours. Run after the existing demo is working.**

Prerequisite: the existing demo stack (simulator + FastAPI + React dashboard + Gemini) must be running.

---

## Prompt 1 of 5: Download crosswalk images

```
I need crosswalk images for the SafeCross demo. Create two scripts in
simulator/:

SCRIPT 1: simulator/download_streetview.py
Download Google Street View images for 10 SF intersections using the
Street View Static API.

URL format:
https://maps.googleapis.com/maps/api/streetview?size=640x480&location={lat},{lng}&heading={heading}&pitch=-10&fov=90&key={GOOGLE_API_KEY}

Intersections and coordinates:
  INT-2025-0001: Market St & 5th St, 37.7837, -122.4073
  INT-2025-0002: Geary Blvd & Masonic Ave, 37.7842, -122.4462
  INT-2025-0003: Mission St & 16th St, 37.7650, -122.4194
  INT-2025-0004: Van Ness Ave & Eddy St, 37.7836, -122.4213
  INT-2025-0005: Stockton St & Clay St, 37.7934, -122.4082
  INT-2025-0006: 3rd St & Evans Ave, 37.7432, -122.3872
  INT-2025-0007: Taraval St & 19th Ave, 37.7434, -122.4756
  INT-2025-0008: Polk St & Turk St, 37.7824, -122.4186
  INT-2025-0009: Ocean Ave & Geneva Ave, 37.7235, -122.4419
  INT-2025-0010: Sutter St & Larkin St, 37.7876, -122.4182

For each intersection, download 4 images at headings 0, 90, 180, 270.
Save as simulator/images/{intersection_id}_{heading}.jpg
Total: 40 images.

Load GOOGLE_API_KEY from environment variable or .env file.

SCRIPT 2: simulator/generate_danger_images.py
Using PIL/Pillow, create 4 synthetic "danger scenario" images by
taking random existing downloaded images and overlaying:
  a. danger_vehicle_close.jpg — draw a colored rectangle (car shape,
     ~120x60px, silver/white fill with dark outline) positioned 15-25
     pixels from the crosswalk edge to simulate a car approaching
  b. danger_vehicle_in_crosswalk.jpg — same car rectangle but overlapping
     the crosswalk stripes
  c. danger_turning.jpg — car rectangle at an angle near a corner
  d. danger_double_parked.jpg — car rectangle parked very close to
     the crosswalk on the right side

If no downloaded images exist yet, generate simple synthetic crosswalk
backgrounds first:
  - 640x480, gray road surface (#555555)
  - White crosswalk stripes (6 stripes, each 10px tall, 80px wide, spaced 15px)
  - Lighter gray sidewalk (#999999) at top and bottom 80px
  - Add intersection name text at bottom-left
  - Add "SafeCross CAM" + timestamp text at top-right in small white font

Save danger images to simulator/images/danger_{1-4}.jpg

Create the images/ directory if it doesn't exist.

After creating both scripts, run the appropriate one:
- If GOOGLE_API_KEY is set: run download_streetview.py then generate_danger_images.py
- If not: run generate_danger_images.py with synthetic backgrounds
Verify at least 8 images exist in simulator/images/
```

**✅ Checkpoint:** `ls simulator/images/*.jpg | wc -l` shows 8+ images.

---

## Prompt 2 of 5: Backend vision analysis

```
Add Gemini Vision near-miss detection to the SafeCross backend.

1. Update backend/models.py — add:

class VisionAnalysis(BaseModel):
    vehicle_present: bool
    risk_level: str  # "low", "medium", "high", "critical"
    vehicle_description: Optional[str] = None
    estimated_distance_ft: Optional[float] = None
    safety_concerns: str = ""
    analysis_time_ms: int = 0

Update TapEvent model to add optional fields:
    image_base64: Optional[str] = None
    vision_analysis: Optional[VisionAnalysis] = None
    risk_level: Optional[str] = None
    image_path: Optional[str] = None

2. Update backend/gemini_client.py — add method to SafeCrossAI:

async def analyze_crosswalk_image(self, image_base64: str,
    intersection_name: str, crossing_id: str) -> dict:

Use Gemini multimodal API:
    import google.generativeai as genai
    from PIL import Image
    import io, base64, time

    image_bytes = base64.b64decode(image_base64)
    image = Image.open(io.BytesIO(image_bytes))

    prompt = f"""You are a traffic safety AI analyzing a crosswalk camera
    image from {intersection_name} ({crossing_id} crossing) in San Francisco.
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
    {{"vehicle_present": true/false, "risk_level": "low|medium|high|critical",
      "vehicle_description": "description or null",
      "estimated_distance_ft": number or null,
      "safety_concerns": "description or empty string"}}"""

    start = time.time()
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content([prompt, image])
    elapsed_ms = int((time.time() - start) * 1000)

    Parse the JSON response. If parsing fails (strip markdown fences first),
    return {"vehicle_present": false, "risk_level": "low",
    "safety_concerns": "", "analysis_time_ms": elapsed_ms}

    Add 1 retry with 2-second delay on API errors.

3. Update backend/database.py:

Add columns to tap_events table:
    risk_level TEXT DEFAULT 'unknown',
    vision_analysis TEXT,  -- JSON string
    image_path TEXT

Add functions:
    get_near_misses(since=None, limit=20) — returns events with
        risk_level in ('high', 'critical')
    get_risk_summary() — returns per-intersection:
        {intersection_id, name, total_analyzed, high_count,
         critical_count, risk_rate}

4. Update backend/routes_events.py — modify POST /api/v1/events:

When an event includes image_base64:
    a. Call gemini.analyze_crosswalk_image() with the image
    b. Attach the VisionAnalysis result to the event
    c. Save the image to data/images/{event_id}.jpg
    d. Store risk_level + JSON vision_analysis in the database
    e. If risk_level is "high" or "critical", broadcast a WebSocket
       message with type "near_miss_alert" including the analysis
       and image_path (NOT the base64 — too large for WebSocket)

Create the data/images/ directory on startup if it doesn't exist.

5. Add new routes in backend/routes_analytics.py:

GET /api/v1/analytics/near-misses — returns last 20 high/critical events
    with intersection name, time, risk_level, vehicle_description,
    image_path, vision_analysis

GET /api/v1/analytics/risk-summary — returns per-intersection risk stats

6. Update generate_insights() in gemini_client.py — add near-miss data
to the prompt context so AI insights include vehicle conflict analysis.

7. Serve images as static files:
    from fastapi.staticfiles import StaticFiles
    app.mount("/images", StaticFiles(directory="data/images"), name="images")

8. Update seed_historical.py to include realistic risk_level values:
    75% "low", 15% "medium", 8% "high", 2% "critical"
    Weight high-risk toward Van Ness & Eddy and Market & 5th.

Test: POST a test event with a base64-encoded image from simulator/images/
using curl. Verify the response includes vision_analysis with a risk_level,
and the image is saved to data/images/.
```

**✅ Checkpoint:** `curl -X POST http://localhost:8000/api/v1/events -H "Content-Type: application/json" -d '{"device_id":"EDGE-0001","intersection_id":"INT-2025-0001","events":[{"event_time":"2026-03-21T20:00:00Z","crossing_id":"NS","card_type":1,"card_uid_hash":"test1234","read_method":2,"filter_result":"accepted","extension_sec":8,"phase_state_at_tap":"PED_WALK","snmp_result":"ok","image_base64":"'$(base64 -w0 simulator/images/INT-2025-0001_0.jpg)'"}]}'` returns a response with vision_analysis containing a risk_level.

---

## Prompt 3 of 5: Simulator — attach images to events

```
Update simulator/tap_simulator.py to attach crosswalk images to tap events.

1. On startup, scan simulator/images/ directory and build a mapping:
   intersection_id -> list of image file paths

   Also load the danger images (danger_*.jpg) separately.

2. When generating a tap event:
   - 70% of accepted events: attach a random image for that intersection
   - If intersection is Market & 5th or Van Ness & Eddy: 20% chance of
     using a danger image instead (produces more high-risk events at
     the busiest/most dangerous intersections)
   - 30% of events: no image (simulates camera offline)
   - Rejected events: never attach an image (no point analyzing if
     the extension was rejected)

3. Read the image file, base64-encode it, and include it in the event
   as the image_base64 field.

4. After POSTing the event, check the response for vision_analysis.
   Log the result with colored output:
   - GREEN: "✅ LOW RISK at Market St & 5th St (no vehicles)"
   - YELLOW: "⚠️ MEDIUM RISK at Van Ness & Eddy (vehicle yielding, ~20ft)"
   - ORANGE: "🔶 HIGH RISK at Polk & Turk (SUV 8ft from crosswalk)"
   - RED: "🚨 CRITICAL at Market & 5th (vehicle in crosswalk!)"

5. When --burst mode is active, ALWAYS include an image so the demo
   shows vision analysis happening in real time. Alternate between
   safe images and danger images to ensure the demo shows both green
   badges and red alerts.

6. Add a 1-second delay between events when images are attached to
   avoid Gemini rate limiting. Without images, use the normal rate.

7. Update heartbeat sending to include a camera_status field:
   "camera_status": "online" (if images directory has files for this
   intersection) or "offline" (if no images available).

Test: run simulator with --burst, verify colored risk logs appear,
verify events with images are processed within 1-3 seconds, verify
both safe and high-risk events appear in the backend at
GET /api/v1/analytics/near-misses.
```

**✅ Checkpoint:** Simulator logs show mixed green/yellow/red risk assessments. `curl http://localhost:8000/api/v1/analytics/near-misses` returns high/critical events.

---

## Prompt 4 of 5: Dashboard — near-miss display (paused here)

```
Add vision near-miss detection display to the React dashboard.

1. Update src/types.ts — add:

interface VisionAnalysis {
    vehicle_present: boolean;
    risk_level: 'low' | 'medium' | 'high' | 'critical' | 'unknown';
    vehicle_description: string | null;
    estimated_distance_ft: number | null;
    safety_concerns: string;
    analysis_time_ms: number;
}

Update TapEvent to include:
    risk_level?: string;
    vision_analysis?: VisionAnalysis;
    image_path?: string;

2. Update src/components/EventFeed.tsx:

For events with vision_analysis, show a risk badge after the
EXTENDED/REJECTED text:
  - low: small green shield "✓"
  - medium: yellow shield "⚠"
  - high: orange shield "⚠ Vehicle nearby"
  - critical: red pulsing shield "🚨 Near miss"

High/critical events get a red-orange left border (instead of green)
and a subtle red background tint.

On click of any event with an image_path, show a modal/expanded view:
  - Crosswalk image (load from http://localhost:8000/images/{filename})
  - Large risk level badge
  - Vehicle description text
  - Estimated distance
  - Safety concerns
  - "Analyzed in {analysis_time_ms}ms by Gemini Vision" footer

3. Update src/components/StatsBar.tsx:

Change the 3-card layout to 4 cards:
  "Extensions Today" — teal
  "Avg Extension" — amber
  "Acceptance Rate" — green
  "Near Misses" — red/orange when > 0, gray when 0
    (count of high + critical events today)
    Fetch from GET /api/v1/analytics/risk-summary, sum all high+critical

4. Update src/components/MapView.tsx:

When a WebSocket message arrives with type "near_miss_alert":
  - Flash the intersection marker RED for 5 seconds (not amber)
  - Add a red pulse ring animation (CSS keyframes scale + fade)
  - This visually distinguishes normal crossings (amber) from
    dangerous ones (red)

5. Create src/components/NearMissAlert.tsx:

A toast notification that slides in from the top-right when a
near_miss_alert WebSocket message arrives:
  - Red background (#DC2626) with white text
  - "🚨 NEAR MISS — {intersection_name}"
  - Vehicle description + distance on second line
  - Small thumbnail of the crosswalk image on the left
  - Auto-dismisses after 8 seconds with fade-out
  - Click to expand to the full image + analysis modal
  - Stack up to 3 alerts if multiple arrive quickly

This is the most visually impactful element. When judges see a red
banner with "Vehicle detected 6 feet from crosswalk at Van Ness & Eddy"
with an actual image, they immediately understand why AI vision matters.

6. Update src/components/IntersectionDetail.tsx:

Add a "Safety Analysis" section below the hourly chart:
  - Small donut chart: risk level distribution (low/medium/high/critical)
    using Recharts PieChart with colors green/yellow/orange/red
  - "Near-miss rate: X%" text below the donut
  - List of last 5 near-miss events for this intersection with
    thumbnails and risk badges

7. Update src/components/AIInsights.tsx:

Add a new example question chip in Ask AI mode:
  "Which intersections have the most vehicle conflicts?"

The auto-generated insights will naturally include near-miss analysis
since we updated the backend prompt — no frontend change needed for that.

Test the full flow:
1. Reseed historical data: python simulator/seed_historical.py
2. Start backend + dashboard
3. Run simulator: python simulator/tap_simulator.py --rate 3 --burst
4. Watch for: risk badges on events, red near-miss alert banners,
   red marker flashes on map, near-miss count in stats bar
5. Click a near-miss event — verify image + analysis modal
6. Click an intersection marker — verify safety analysis section
7. Check AI insights — verify they mention near-miss patterns
```

**✅ Checkpoint:** Red "NEAR MISS" alert banners appear in the dashboard. Clicking shows the crosswalk image with Gemini's analysis. Map markers flash red for high-risk events.

---

## Prompt 5 of 5: Polish + end-to-end test

```
Final polish for the vision near-miss detection feature.

1. Verify the WebSocket broadcast for near_miss_alert events:
   - The broadcast should send a JSON object with:
     {
       "type": "near_miss_alert",
       "intersection_id": "...",
       "intersection_name": "...",
       "lat": ..., "lng": ...,
       "risk_level": "high" or "critical",
       "vehicle_description": "...",
       "estimated_distance_ft": ...,
       "safety_concerns": "...",
       "image_path": "/images/{event_id}.jpg",
       "event_time": "..."
     }
   - The React useWebSocket hook should handle both regular "event"
     messages and "near_miss_alert" messages

2. Handle edge cases:
   - Gemini Vision API timeout (>10 seconds): return risk_level "unknown",
     don't block the event processing. The extension still gets granted.
   - Image too large: resize to max 640px wide before sending to Gemini
   - No images available for an intersection: skip vision analysis silently
   - Gemini returns invalid JSON: fall back to risk_level "low"

3. Rate limiting protection:
   - Add a semaphore to limit concurrent Gemini Vision calls to 3
   - Queue additional requests and process them in order
   - If queue exceeds 10, drop the oldest requests (log a warning)

4. Update the AI insights prompt to emphasize near-miss patterns:
   Include in the data section:
   - Total near-miss events (high + critical) in last 24 hours
   - Per-intersection near-miss counts
   - Most common vehicle descriptions
   - Peak near-miss hours

5. Run the complete end-to-end test:
   a. Delete the SQLite database to start fresh
   b. Run seed_historical.py (now includes risk_level values)
   c. Start backend: uvicorn backend.main:app --reload
   d. Start dashboard: cd dashboard && npm run dev
   e. Run simulator: python simulator/tap_simulator.py --rate 3 --burst
   f. Open dashboard at localhost:5173

   Verify ALL of the following:
   [ ] Map shows 10 markers, teal by default
   [ ] Events stream into the feed with risk badges
   [ ] At least one red "NEAR MISS" banner appears within 60 seconds
   [ ] Clicking the banner shows the crosswalk image + analysis
   [ ] Stats bar shows "Near Misses" count > 0
   [ ] Map marker flashes red when a near-miss occurs
   [ ] AI insights panel mentions near-miss patterns
   [ ] Ask AI: "Which intersection has the most vehicle conflicts?"
       returns a coherent answer
   [ ] Clicking a map marker shows intersection detail with safety
       analysis section

6. If the near-miss alert is not appearing:
   - Check that generate_danger_images.py created danger images
   - Check that the simulator is using danger images for some events
   - Check that Gemini is actually returning "high" or "critical" for
     danger images (curl test a danger image directly)
   - Check the WebSocket broadcast is sending type "near_miss_alert"

Print "VISION NEAR-MISS DETECTION: ALL TESTS PASSED" when everything
works.
```

**✅ Checkpoint:** All verification items pass. Red near-miss banners appear with crosswalk images and Gemini analysis.

---

## Quick reference: what changed

| Component | What was added |
|-----------|---------------|
| simulator/images/ | 40+ crosswalk images (Street View or synthetic) |
| simulator/download_streetview.py | NEW — downloads Street View images |
| simulator/generate_danger_images.py | NEW — creates synthetic danger scenarios |
| simulator/tap_simulator.py | MODIFIED — attaches images to 70% of events |
| simulator/seed_historical.py | MODIFIED — includes risk_level values |
| backend/models.py | MODIFIED — VisionAnalysis model, image fields on TapEvent |
| backend/gemini_client.py | MODIFIED — analyze_crosswalk_image() method |
| backend/routes_events.py | MODIFIED — calls vision analysis, saves images, broadcasts alerts |
| backend/routes_analytics.py | MODIFIED — near-misses and risk-summary endpoints |
| backend/database.py | MODIFIED — risk columns, near-miss queries |
| dashboard EventFeed | MODIFIED — risk badges, click-to-expand image modal |
| dashboard StatsBar | MODIFIED — 4th card "Near Misses" |
| dashboard MapView | MODIFIED — red flash for near-miss markers |
| dashboard NearMissAlert | NEW — red toast banner with image thumbnail |
| dashboard IntersectionDetail | MODIFIED — safety analysis section with donut chart |
| dashboard AIInsights | MODIFIED — new example question chip |
