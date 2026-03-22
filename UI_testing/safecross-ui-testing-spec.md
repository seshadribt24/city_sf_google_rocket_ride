# SafeCross SF — UI Testing Spec (Claude in Chrome)

**Purpose:** Verify the 3 untested UI interactions on the SafeCross dashboard using the Claude in Chrome browser extension tools.

**Prerequisites:**
- Backend running at `http://localhost:8000`
- Dashboard running at `http://localhost:5173`
- Simulator running with `--burst` flag (so events flow during testing)
- Claude in Chrome extension connected

---

## Test 1 of 3: Map Marker Click → Intersection Detail Panel

### What we're testing
Clicking a map marker should replace the Live Event Feed with an Intersection Detail panel showing: intersection name, stats row, hourly bar chart, last 10 events, and an AI Recommendation button.

### Steps

```
Using the Claude in Chrome browser tools, test the map marker click
interaction on the SafeCross dashboard.

1. Get the tab context:
   Call tabs_context_mcp with createIfEmpty=true

2. Navigate to the dashboard:
   Call navigate with url="http://localhost:5173"
   Call computer action=wait duration=5

3. Take a baseline screenshot:
   Call computer action=screenshot
   Verify: map is visible with teal markers, Live Event Feed on right,
   AI Safety Analyst panel at bottom-right.
   NOTE: Record the coordinates of visible map markers from the screenshot.

4. Locate a map marker using find:
   Call find with query="map marker" or "intersection marker"
   If find returns results, use the ref to click.
   If find doesn't find markers (Mapbox renders to canvas, not DOM):
   use the screenshot coordinates instead.

5. Alternative: use JavaScript to trigger a marker click programmatically:
   Call javascript_tool with:
   ```
   // Get the Mapbox map instance and simulate clicking on Market & 5th
   // Market St & 5th St coordinates: 37.7837, -122.4073
   const map = document.querySelector('.mapboxgl-map')?.__mapbox_map ||
               window._map;
   if (map) {
     // Project the lat/lng to pixel coordinates
     const point = map.project([-122.4073, 37.7837]);
     map.fire('click', {
       point: point,
       lngLat: { lng: -122.4073, lat: 37.7837 },
       originalEvent: new MouseEvent('click')
     });
     'Map click fired at Market & 5th: ' + JSON.stringify(point);
   } else {
     // Try finding map via React fiber
     const mapContainer = document.querySelector('[class*="map"]');
     'Map container found: ' + !!mapContainer + ', classes: ' +
       (mapContainer?.className || 'none');
   }
   ```

   If the map instance is not directly accessible, fall back to
   coordinate-based clicking:
   - Take a zoomed screenshot of the map area:
     Call computer action=zoom region=[0, 90, 580, 800]
   - Identify the teal marker dots in the zoomed image
   - Calculate the click coordinates for the largest/most central marker
   - Call computer action=left_click coordinate=[x, y]

6. Wait for detail panel to render:
   Call computer action=wait duration=2

7. Take a screenshot to verify:
   Call computer action=screenshot
   PASS criteria:
   - [ ] The Live Event Feed is REPLACED by an Intersection Detail panel
   - [ ] Intersection name is visible (e.g., "Market St & 5th St")
   - [ ] A close/back button (X) is visible to return to the event feed
   - [ ] An hourly bar chart is rendered (using Recharts)
   - [ ] Recent events for this specific intersection are shown
   - [ ] An "AI Recommendation" button is visible

8. If the detail panel did NOT appear:
   - Check the browser console for errors:
     Call read_console_messages
   - Check if the click landed on the map canvas:
     Call javascript_tool with:
     'document.querySelector(".mapboxgl-canvas") !== null'
   - Try clicking at different coordinates (markers may have shifted
     based on zoom level)
   - Try using the find tool to look for any clickable element inside
     the map container

9. Verify the close button works:
   Call find with query="close button" or "back button" or "X button"
   Click the found element
   Call computer action=wait duration=1
   Call computer action=screenshot
   PASS criteria:
   - [ ] The Intersection Detail panel is replaced by the Live Event Feed
```

### Expected result
Screenshot shows intersection detail panel with name, chart, events, and AI Recommendation button.

---

## Test 2 of 3: AI Recommendation Button

### What we're testing
From the Intersection Detail panel, clicking the "AI Recommendation" button should call `GET /api/v1/ai/recommendation/{intersection_id}` and display a structured recommendation card with: recommendation text, peak hours, confidence level, reasoning, and estimated impact.

### Steps

```
Using the Claude in Chrome browser tools, test the AI Recommendation
button on the SafeCross dashboard.

PREREQUISITE: Test 1 must have passed — the Intersection Detail panel
must be open for a specific intersection. If not, repeat Test 1 steps
1-7 first to get the detail panel open.

1. Verify the detail panel is open:
   Call computer action=screenshot
   Confirm an intersection detail panel is visible.
   If not, repeat the map marker click from Test 1.

2. Find the AI Recommendation button:
   Call find with query="AI Recommendation button"
   Record the ref ID.

   If find doesn't locate it, try:
   Call find with query="recommendation"
   Or: Call find with query="Get AI" or "Ask AI" or "Analyze"

   If still not found, use the screenshot to locate the button
   visually and click by coordinates.

3. Click the AI Recommendation button:
   Call computer action=left_click using the ref or coordinates
   
4. Wait for Gemini API response:
   Call computer action=wait duration=5
   (Gemini API typically takes 1-3 seconds, allow 5 for safety)

5. Take a screenshot to verify:
   Call computer action=screenshot
   PASS criteria:
   - [ ] A recommendation card is visible (likely highlighted in amber
         or with a distinct background)
   - [ ] Recommendation text is shown (e.g., "Increase baseline walk
         time by X seconds")
   - [ ] Peak hours are displayed (e.g., "8:00-9:00 AM, 4:00-5:30 PM")
   - [ ] Confidence level is shown (high/medium/low)
   - [ ] Reasoning text references actual data (tap counts, patterns)
   - [ ] Estimated impact is shown (e.g., "Would eliminate X% of
         extension requests")

6. Verify the API was actually called:
   Call read_network_requests with urlPattern="/api/v1/ai/recommendation"
   PASS criteria:
   - [ ] A GET request to /api/v1/ai/recommendation/{intersection_id}
         was made
   - [ ] Response status is 200
   - [ ] Response contains JSON with recommendation, peak_hours,
         confidence, reasoning, estimated_impact fields

7. If the recommendation card shows a loading state that never resolves:
   - Check console for errors: Call read_console_messages
   - Check if the API returned an error:
     Call javascript_tool with:
     'fetch("/api/v1/ai/recommendation/INT-2025-0001")
       .then(r => r.json()).then(d => JSON.stringify(d))'
   - If Gemini is rate-limited, wait 30 seconds and retry

8. If the recommendation card shows "AI analysis temporarily unavailable":
   - This means the Gemini API failed and the fallback message is shown
   - Check the backend logs for Gemini API errors
   - Mark as PARTIAL PASS — the UI works, but Gemini is unavailable
```

### Expected result
Screenshot shows a recommendation card with specific timing recommendation, peak hours, confidence, reasoning, and impact — all referencing the selected intersection's actual data.

---

## Test 3 of 3: Ask AI Tab + Free-form Question

### What we're testing
The AI Safety Analyst panel should have an "Ask AI" tab that switches to a free-form Q&A interface. Typing a question and submitting should call `POST /api/v1/ai/ask` and display Gemini's response in a chat bubble.

### Steps

```
Using the Claude in Chrome browser tools, test the Ask AI tab on the
SafeCross dashboard.

1. First, close the intersection detail panel if open:
   Call find with query="close button" or "X button" or "back"
   If found, click it and wait 1 second.
   Call computer action=screenshot to verify the main dashboard view
   is showing with the AI Safety Analyst panel visible at bottom-right.

2. Locate the AI panel and the Ask AI tab:
   Call find with query="Ask AI tab" or "Ask AI button"
   Record the ref ID.

   If not found, try:
   Call find with query="Ask AI"
   Or look for it visually in the screenshot — it should be a tab
   toggle in the AI Safety Analyst panel header, next to "Insights".

3. Click the Ask AI tab:
   Call computer action=left_click using the ref or coordinates

4. Wait for mode switch:
   Call computer action=wait duration=1

5. Take a screenshot to verify mode switch:
   Call computer action=screenshot
   PASS criteria:
   - [ ] The AI panel has switched from insights view to a Q&A view
   - [ ] A text input field is visible ("Ask about crossing patterns..."
         or similar placeholder)
   - [ ] Example question chips are visible (clickable suggestions)
   - [ ] A submit button is visible

6. Type a test question:
   Call find with query="text input" or "ask question input"
   Call form_input with the ref and value:
     "Which intersection should we prioritize for permanent timing changes?"

   If form_input doesn't work, try:
   - Click on the input field first:
     Call computer action=left_click on the input coordinates
   - Then type:
     Call computer action=type text="Which intersection should we prioritize for permanent timing changes?"

7. Submit the question:
   Call find with query="submit button" or "send button" or "ask button"
   Call computer action=left_click using the ref or coordinates

   If no submit button found, try pressing Enter:
   Call computer action=key text="Return"

8. Wait for Gemini response:
   Call computer action=wait duration=8
   (Free-form Q&A may take longer as Gemini processes more context)

9. Take a screenshot to verify:
   Call computer action=screenshot
   PASS criteria:
   - [ ] The question is displayed in a user chat bubble
   - [ ] Gemini's response is displayed in an AI chat bubble
   - [ ] The response references specific intersection names from the
         actual data (e.g., "Market St & 5th St", "Stockton St & Clay St")
   - [ ] The response includes specific numbers (tap counts, recommended
         seconds)
   - [ ] The response is coherent and answers the question asked

10. Verify the API was called:
    Call read_network_requests with urlPattern="/api/v1/ai/ask"
    PASS criteria:
    - [ ] A POST request to /api/v1/ai/ask was made
    - [ ] Request body contains the question text
    - [ ] Response status is 200
    - [ ] Response contains a meaningful answer string

11. Test clicking an example question chip (if visible):
    Call find with query="example question" or "suggested question"
    If found, click the first chip
    Call computer action=wait duration=8
    Call computer action=screenshot
    PASS criteria:
    - [ ] The chip's question text appears in a user bubble
    - [ ] A new Gemini response appears for that question

12. Switch back to Insights mode:
    Call find with query="Insights tab" or "Insights button"
    Click it
    Call computer action=wait duration=1
    Call computer action=screenshot
    PASS criteria:
    - [ ] The panel switches back to showing the auto-generated
          bullet-point insights
    - [ ] The insights are still present (not cleared by the mode switch)

13. If the question submission hangs or returns an error:
    - Check console: Call read_console_messages
    - Direct API test:
      Call javascript_tool with:
      ```
      fetch("/api/v1/ai/ask", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({question: "Which intersection has the most taps?"})
      }).then(r => r.json()).then(d => JSON.stringify(d))
      ```
    - If Gemini is rate-limited, wait 60 seconds and retry
```

### Expected result
Screenshot shows Q&A interface with the user's question and Gemini's data-grounded response in chat bubbles.

---

## Test Summary Template

After running all 3 tests, fill in this summary:

```
SAFECROSS UI TEST RESULTS — {date}

Test 1: Map Marker Click → Detail Panel
  Status: PASS / FAIL / PARTIAL
  Notes: {what happened}
  Screenshot: {saved screenshot path}

Test 2: AI Recommendation Button
  Status: PASS / FAIL / PARTIAL
  Notes: {what happened}
  Screenshot: {saved screenshot path}

Test 3: Ask AI Tab + Free-form Question
  Status: PASS / FAIL / PARTIAL
  Notes: {what happened}
  Screenshot: {saved screenshot path}

Overall: {X}/3 tests passed
Blocking issues: {list any issues that would break the demo}
Non-blocking issues: {list minor issues}
```

---

## Troubleshooting: common failures

### Map markers not clickable
Mapbox renders to a `<canvas>` element — DOM-based click tools (find, read_page) cannot see individual markers. Solutions:
1. Use coordinate-based clicking from screenshot: `computer action=left_click coordinate=[x,y]`
2. Use JavaScript to fire a map click event at known lat/lng coordinates
3. Zoom into the map area first with `computer action=zoom` to identify marker positions precisely

### Gemini API timeout
If any AI endpoint takes >10 seconds, it's likely a rate limit or network issue. The backend should return fallback messages. If it hangs indefinitely:
1. Check `read_network_requests` for the pending request
2. Check `read_console_messages` for timeout errors
3. Reload the page and retry — cached insights should return instantly (5-min cache)

### Dashboard not loading
If `localhost:5173` shows a connection error:
1. Verify the Vite dev server is running: check terminal output
2. Verify the backend is running: navigate to `http://localhost:8000/docs`
3. Check if the proxy config in `vite.config.ts` is correct for API and WebSocket forwarding

### Intersection detail panel doesn't appear after click
1. The click may have missed the marker — Mapbox markers are small (12-28px)
2. Zoom into the map area and retry with more precise coordinates
3. Check if the dashboard has an alternative way to select intersections (e.g., a dropdown or list)
4. Check console for React errors that might prevent the panel from rendering
