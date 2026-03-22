# SafeCross SF — Vision Near-Miss Detection Add-on (Claude Code)

## Context for Claude Code

The SafeCross demo is already built and running:
- Tap simulator → FastAPI backend (SQLite + Gemini) → React dashboard
- All 10 pilot intersections with live event streaming
- AI Safety Analyst panel with Gemini text insights

**What you're adding:** A vision analysis layer that sends a crosswalk camera image with each tap event to Gemini Vision, which assesses whether a vehicle is dangerously close to the pedestrian crossing. This transforms AI from an analytics add-on into a real-time safety-critical component.

**Why this matters for hackathon scoring:**
- Before: remove Gemini and the system still works → AI is supplementary
- After: remove Gemini and you lose near-miss detection entirely → AI is core

---

## Step 1: Collect crosswalk images

Create `safecross-demo/simulator/images/` directory with crosswalk images from the 10 pilot intersections. These simulate what an intersection camera would capture when a senior taps their card.

### Script to download Street View images

Create `simulator/download_streetview.py`:

```
Create simulator/download_streetview.py that downloads Google Street View
images for each of the 10 pilot intersections.

Use the Google Maps Street View Static API:
  https://maps.googleapis.com/maps/api/streetview
  ?size=640x480
  &location={lat},{lng}
  &heading={heading}
  &pitch=-10
  &fov=90
  &key={GOOGLE_API_KEY}

For each intersection, download 2-3 images at different headings to
capture different crosswalk views. Use headings 0, 90, 180, 270
(north, east, south, west facing) and pick the 2-3 that show
crosswalks best.

Intersection coordinates (from seed_data.py):
  Market St & 5th St: 37.7837, -122.4073
  Geary Blvd & Masonic Ave: 37.7842, -122.4462
  Mission St & 16th St: 37.7650, -122.4194
  Van Ness Ave & Eddy St: 37.7836, -122.4213
  Stockton St & Clay St: 37.7934, -122.4082
  3rd St & Evans Ave: 37.7432, -122.3872
  Taraval St & 19th Ave: 37.7434, -122.4756
  Polk St & Turk St: 37.7824, -122.4186
  Ocean Ave & Geneva Ave: 37.7235, -122.4419
  Sutter St & Larkin St: 37.7876, -122.4182

Download 4 images per intersection (headings 0, 90, 180, 270).
Save as: simulator/images/{intersection_id}_{heading}.jpg
Total: 40 images.

Load GOOGLE_API_KEY from environment or .env file.
If no API key is available, print instructions for getting one and
provide a fallback: download 15 royalty-free crosswalk images from
Unsplash using the Unsplash API or save placeholder images.

Usage: python simulator/download_streetview.py
```

**Alternative if no Google API key:** The user can manually screenshot Google Street View from a browser at each intersection. Or use the image_search results we'll pull below.

---

## Step 2: Backend — add vision analysis endpoint

### Prompt: Add vision analysis to the backend

```
Add vision-based near-miss detection to the SafeCross backend.

This feature sends a crosswalk camera image with each tap event to
Gemini Vision, which analyzes whether a vehicle is dangerously close
to the pedestrian crossing.

1. Update backend/models.py — add new models:

   class VisionAnalysis(BaseModel):
       vehicle_present: bool
       risk_level: str  # "low", "medium", "high", "critical"
       vehicle_description: Optional[str] = None
       estimated_distance_ft: Optional[float] = None
       safety_concerns: str = ""
       analysis_time_ms: int = 0

   Update TapEvent to add optional fields:
       image_base64: Optional[str] = None  # base64 encoded JPEG
       vision_analysis: Optional[VisionAnalysis] = None

2. Update backend/gemini_client.py — add a new method to SafeCrossAI:

   async def analyze_crosswalk_image(self, image_base64: str,
       intersection_name: str, crossing_id: str) -> dict:
       """
       Send a crosswalk image to Gemini Vision for near-miss analysis.
       Returns structured risk assessment.
       """

   The Gemini prompt should be:

   """
   You are a traffic safety AI analyzing a crosswalk camera image from
   {intersection_name} ({crossing_id} crossing) in San Francisco.

   A senior pedestrian has just activated an extended crossing signal
   at this location. Analyze the image for pedestrian safety risks.

   Assess:
   1. Is a vehicle present within or approaching the crosswalk area?
   2. Risk level: low (no vehicles nearby), medium (vehicle present but
      yielding), high (vehicle close to crosswalk and moving),
      critical (vehicle in crosswalk or about to enter)
   3. Vehicle type and estimated distance from crosswalk if present
   4. Any other safety concerns (blocked sightlines, double-parked
      cars, construction, poor lighting)

   Respond with ONLY valid JSON:
   {
     "vehicle_present": true/false,
     "risk_level": "low|medium|high|critical",
     "vehicle_description": "description or null",
     "estimated_distance_ft": number or null,
     "safety_concerns": "description of concerns or empty string"
   }
   """

   Use the Gemini multimodal API to send both the image and text prompt:

   import google.generativeai as genai
   from PIL import Image
   import io, base64

   image_bytes = base64.b64decode(image_base64)
   image = Image.open(io.BytesIO(image_bytes))

   model = genai.GenerativeModel("gemini-2.0-flash")
   response = model.generate_content([prompt_text, image])

   Parse the JSON response. If parsing fails, return a default
   low-risk result. Track analysis time in milliseconds.

   Add retry logic: 1 retry with 2-second delay on API errors.
   Cache is NOT appropriate here — each image is unique.

3. Update backend/routes_events.py — modify POST /api/v1/events:

   When an event includes image_base64:
   a. Call analyze_crosswalk_image() with the image
   b. Attach the VisionAnalysis to the event before storing
   c. Store the risk_level in the tap_events database table
   d. If risk_level is "high" or "critical", broadcast a special
      alert via WebSocket with type "near_miss_alert"
   e. Store the image as a file in data/images/{event_id}.jpg
      (don't store base64 in SQLite — too large)

   Add a new column to tap_events table:
     risk_level TEXT DEFAULT 'unknown'
     vision_analysis TEXT  -- JSON string of full analysis
     image_path TEXT  -- path to saved image file

4. Add new analytics endpoint:

   GET /api/v1/analytics/near-misses
   Returns list of high/critical risk events with:
   - intersection name, time, risk level, vehicle description
   - image path (served as static file)
   - vision analysis details

   GET /api/v1/analytics/risk-summary
   Returns per-intersection risk statistics:
   - total events analyzed, high/critical count, risk rate percentage

5. Update the AI insights prompt in generate_insights() to include
   near-miss data:

   Add to the prompt:
   """
   Near-miss data (events where vehicles were dangerously close to
   seniors crossing):
   {near_miss_summary}

   Include analysis of near-miss patterns in your recommendations.
   Which intersections have the highest near-miss rates? What
   infrastructure changes would reduce vehicle encroachment?
   """

6. Serve saved images as static files:
   app.mount("/images", StaticFiles(directory="data/images"), name="images")

Test: POST a test event with a base64-encoded crosswalk image and verify
the vision analysis is returned in the response and stored in the database.
```

---

## Step 3: Simulator — attach images to tap events

### Prompt: Update simulator to include images

```
Update simulator/tap_simulator.py to attach crosswalk images to tap events.

1. On startup, scan simulator/images/ directory and build a mapping of
   intersection_id -> list of available image paths.

2. When generating a tap event:
   - 70% of events: attach a random image for that intersection
     (base64 encoded JPEG)
   - 30% of events: no image (simulates camera offline or night mode)

3. The images should produce a realistic distribution of risk levels
   when analyzed by Gemini. Since we're using real Street View images,
   the results will vary naturally. But to ensure we get some high-risk
   events for the demo, create 3-4 synthetic "danger" images:

   Create simulator/generate_danger_images.py:
   - Use PIL/Pillow to take existing crosswalk images and add simple
     overlays simulating dangerous scenarios:
     a. Draw a colored rectangle (car-shaped) close to the crosswalk
        area in 2-3 images
     b. Add a slight red tint to simulate brake lights
   - Save as simulator/images/danger_{n}.jpg
   - These will be randomly mixed in at ~15% frequency for events at
     high-traffic intersections (Market & 5th, Van Ness & Eddy)

4. For the --burst mode, always include an image (so the demo shows
   vision analysis happening in real time).

5. Slightly increase the delay between events when images are attached
   (add 0.5 seconds) to account for Gemini Vision API latency and
   avoid rate limiting.

6. Log the vision analysis result when the backend returns it:
   - GREEN: "✅ LOW RISK - Clear crossing at Market St & 5th St"
   - YELLOW: "⚠️ MEDIUM RISK - Vehicle yielding at Van Ness & Eddy"
   - RED: "🚨 HIGH RISK - Vehicle 8ft from crosswalk at Polk & Turk"

Also update simulator/seed_historical.py:
- Don't include images in historical data (too large for bulk insert)
- But DO include realistic risk_level values in the historical events:
  75% "low", 15% "medium", 8% "high", 2% "critical"
  Weight high-risk events toward Van Ness & Eddy and Market & 5th
  (wider crossings with more turning conflicts)
- This gives the AI insights historical near-miss patterns to analyze

Test: run the simulator with --burst and verify that events with images
get vision analysis results back from the backend. Check that some
events produce medium/high risk levels.
```

---

## Step 4: Dashboard — display vision analysis

### Prompt: Add vision analysis to dashboard

```
Add vision-based near-miss detection display to the React dashboard.

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

   For events with vision analysis, add a risk badge next to the
   EXTENDED/REJECTED status:
   - Low risk: small green shield icon "✓ Safe"
   - Medium risk: yellow warning icon "⚠ Caution"
   - High risk: orange alert icon "⚠ Vehicle nearby"
   - Critical risk: red flashing icon "🚨 Near miss!"

   High and critical risk events should have a red-orange background
   tint and appear at the top of the feed (pinned for 10 seconds).

   When you hover or click a vision-analyzed event, show a tooltip/modal
   with:
   - The crosswalk image thumbnail (loaded from /images/{event_id}.jpg)
   - Risk level badge (large)
   - Vehicle description and estimated distance
   - Safety concerns text
   - Analysis time in milliseconds

3. Update src/components/StatsBar.tsx:

   Add a 4th metric card (or replace one):
   "Near Misses" — count of high+critical risk events today
   Color: red/orange when > 0, gray when 0
   Show a small sparkline of near-misses over last 24 hours if possible

4. Update src/components/MapView.tsx:

   When a near-miss event (high/critical) arrives via WebSocket:
   - The intersection marker flashes RED (not amber) for 5 seconds
   - Show a brief red pulse ring animation around the marker
   - This visually distinguishes "senior crossed safely" (amber pulse)
     from "senior crossed but vehicle was dangerously close" (red pulse)

5. Update src/components/IntersectionDetail.tsx:

   Add a "Safety Analysis" section below the hourly chart:
   - Risk distribution donut chart: low/medium/high/critical percentages
   - List of recent near-miss events with thumbnails
   - Per-intersection near-miss rate vs system average

6. Update src/components/AIInsights.tsx:

   The AI insights from Gemini will now include near-miss analysis
   (because we updated the backend prompt). No frontend changes needed
   for the auto-generated insights — they'll naturally include near-miss
   patterns.

   But add a new example question chip in Ask AI mode:
   "Which intersections have the most near-miss events with vehicles?"

7. Add a new component: src/components/NearMissAlert.tsx

   A toast/banner that appears at the top of the dashboard when a
   critical near-miss event is detected:
   - Red background with white text
   - "🚨 NEAR MISS DETECTED at {intersection_name}"
   - Shows for 8 seconds, then fades
   - Includes a thumbnail of the image and the vehicle description
   - Click to expand to full image + analysis

   This is the single most visually impactful element during the demo.
   When judges see a red alert with an actual image and "Vehicle
   detected 6 feet from crosswalk", they understand immediately why
   AI vision is essential.

Test the full flow:
1. Seed historical data with risk levels
2. Start backend + dashboard
3. Run simulator with --burst
4. Verify: events show risk badges, near-miss alerts appear as red
   banners, map markers flash red for high-risk events, AI insights
   reference near-miss patterns
5. Click an intersection — verify safety analysis section with risk
   donut chart
```

---

## Step 5: Download crosswalk images (alternative to Street View API)

If you don't have a Google Maps API key for Street View, use this approach instead:

### Prompt: Generate synthetic crosswalk images

```
Create simulator/generate_crosswalk_images.py that generates synthetic
crosswalk images for the demo using PIL/Pillow.

We need 40 images total (4 per intersection). Each image should be a
simple top-down or angled view of a crosswalk scene, 640x480 pixels.

For each image:
1. Draw a gray road surface background
2. Draw white crosswalk stripes
3. Add a sidewalk area (lighter gray) at top and bottom
4. Randomly add one of these scenarios:
   a. CLEAR (60%): just the crosswalk, no vehicles
      - Maybe add a small pedestrian figure (circle + line body)
   b. VEHICLE_FAR (20%): a colored rectangle (car) 30-50 pixels
      from the crosswalk, clearly yielding
   c. VEHICLE_CLOSE (15%): a colored rectangle 5-15 pixels from
      the crosswalk, dangerously close
   d. VEHICLE_IN_CROSSWALK (5%): a colored rectangle overlapping
      the crosswalk stripes
5. Add the intersection name as text overlay at the bottom
6. Add a timestamp overlay at the top-right
7. Vary the car colors (white, black, red, silver, blue)
8. Add slight random noise/grain to make images look less synthetic

Save to simulator/images/:
  {intersection_id}_view{1-4}.jpg

This ensures the demo works even without Google API keys, and the
synthetic images will produce predictable risk assessments from
Gemini Vision (clear crosswalk → low risk, vehicle in crosswalk →
critical).

After generating, verify by opening a few images to check they look
reasonable. They don't need to be photorealistic — Gemini Vision can
analyze simple scenes.
```

---

## Demo script update (revised 60-second flow)

The near-miss detection changes the demo narrative significantly:

| Time | What to do | What to say |
|------|-----------|-------------|
| 0–10s | Show dashboard with map | "Live ops dashboard monitoring 10 pilot intersections. Every crossing is analyzed by AI in real time." |
| 10–20s | Point to event feed as events flow | "A senior just tapped at Market & 5th — 8-second extension granted. Gemini Vision analyzed the crosswalk camera and confirmed: safe crossing, no vehicles." |
| 20–30s | Wait for a red near-miss alert banner | "Now watch — a high-risk event. Gemini detected a vehicle 6 feet from the crosswalk at Van Ness & Eddy. This near-miss is flagged and logged automatically." |
| 30–40s | Click the near-miss alert to show image + analysis | "Here's the actual image. The AI identified a turning vehicle approaching the crosswalk. This data doesn't exist anywhere in SF today." |
| 40–50s | Show AI insights panel | "The AI Safety Analyst integrates near-miss patterns with crossing demand. It's recommending a leading pedestrian interval at Van Ness to separate turning vehicles from crossing seniors." |
| 50–60s | Ask AI a question | "Engineers can ask: 'Which intersections have the most vehicle conflicts?' — and get specific, data-driven answers." |

**Key difference:** The demo now has a dramatic moment (the red near-miss alert at 20–30s) that makes judges *feel* why AI vision matters. Before, the demo was informational. Now it has tension.

---

## Estimated additional build time

| Component | Estimated time |
|-----------|---------------|
| Download/generate crosswalk images | 20–30 min |
| Backend vision analysis endpoint | 30–40 min |
| Simulator image attachment | 20–30 min |
| Dashboard risk badges + near-miss alert | 40–50 min |
| Testing + tuning | 20–30 min |
| **Total** | **~2.5–3 hours** |

---

## Updated scoring projection (strict)

| Category | Before vision | After vision | Why |
|---|---|---|---|
| Use of AI | 6/10 | 8-9/10 | AI is multimodal, real-time, in the safety-critical path. Remove Gemini = no near-miss detection. |
| Innovation | 6/10 | 8/10 | No deployed system combines card-tap + vision near-miss detection. This is genuinely new. |
| Impact | 8/10 | 9/10 | Near-miss data is something SFMTA and Walk SF have explicitly asked for but don't have. |
| Execution | 7/10 | 7-8/10 | More complex demo, but also more things that could break. Net positive if it works. |
| Presentation | 8/10 | 9/10 | The red near-miss alert is a dramatic demo moment that makes judges remember you. |
| **Total** | **35/50** | **41-44/50** | |

---

## Assumptions not verified

- **Gemini 2.0 Flash vision latency:** Expect 1-3 seconds per image. For the demo this is fine (risk badge appears a moment after the event). If latency exceeds 5 seconds, it will feel slow.
- **Gemini Vision accuracy on Street View images:** These are static images, not live camera feeds. Gemini should handle them fine, but the analysis will be about what's visible in the static image, not a real-time scene.
- **Image size and API limits:** Base64-encoded 640x480 JPEG is ~50-100KB. Gemini accepts up to 20MB per request. No issue. But sending images increases event payload size — the WebSocket broadcast should send the risk analysis result without the image (send image_path instead, let the dashboard fetch it separately).
- **Google Maps Street View API:** Requires a Google Cloud project with Street View Static API enabled and a valid API key. The free tier includes $200/month of credit. Each image costs $0.007, so 40 images costs $0.28. If no API key is available, the synthetic image generator is the fallback.
