# Story 6.2: Dashboard UI — Server List & Controls

Status: review

## Story

As an operator,
I want a web dashboard showing all MCP servers with their status and start/stop buttons,
so that I can manage my MCP infrastructure from a browser at a glance.

## Acceptance Criteria

1. **Given** `mothership/static/index.html` (single vanilla HTML+JS file) **When** I open the dashboard in a browser at `http://localhost:8080` **Then** the page loads and displays a list of all registered MCP servers
2. **Given** the server list **When** rendered for each server **Then** I see: server name, description, status indicator (running/stopped/crashed), port number, and start/stop button
3. **Given** a server with status "running" **When** displayed **Then** the status indicator is visually distinct (e.g., green) and the button shows "Stop"
4. **Given** a server with status "stopped" or "crashed" **When** displayed **Then** the status indicator reflects the state (e.g., grey/red) and the button shows "Start"
5. **Given** I click "Start" on a stopped server **When** the action completes **Then** the server status updates to "running" without a manual page refresh
6. **Given** I click "Stop" on a running server **When** the action completes **Then** the server status updates to "stopped" without a manual page refresh
7. **Given** the dashboard is open **When** 3-5 seconds elapse **Then** the server list refreshes automatically via polling `GET /api/servers` (MNFR11)
8. **Given** all MCP servers are stopped or crashed **When** I load the dashboard **Then** it remains fully operational and accessible (MNFR4)
9. **Given** the dashboard **When** the page loads **Then** it displays current server states within 3 seconds (MNFR9)

## Tasks / Subtasks

- [x] Task 1: Create `mothership/static/index.html` with basic structure (AC: #1)
  - [x] Create `mothership/static/` directory
  - [x] Create `index.html` — single vanilla HTML file with embedded CSS and JS
  - [x] Include a page title "MCP Mothership" and a container for the server list
  - [x] No external dependencies, no build step, no framework
- [x] Task 2: Implement server list rendering (AC: #2, #3, #4)
  - [x] Fetch `GET /api/servers` on page load
  - [x] For each server, render a card/row showing: name, description, status indicator, port, start/stop button
  - [x] Status indicator colors: green for running, grey for stopped, red for crashed
  - [x] Button text: "Stop" for running servers, "Start" for stopped/crashed servers
- [x] Task 3: Implement start/stop button actions (AC: #5, #6)
  - [x] On "Start" click: `POST /api/servers/{name}/start`, then refresh the server list
  - [x] On "Stop" click: `POST /api/servers/{name}/stop`, then refresh the server list
  - [x] Disable button during the request to prevent double-clicks
  - [x] Show error feedback if the action fails (e.g., server already running)
- [x] Task 4: Implement auto-polling (AC: #7)
  - [x] Set up `setInterval` to call `GET /api/servers` every 5 seconds
  - [x] Update the server list in place without full page reload
  - [x] The polling interval satisfies MNFR11 (5-second status update latency)
- [x] Task 5: Verify dashboard resilience (AC: #8, #9)
  - [x] Test that the dashboard loads and renders correctly even when all servers are stopped
  - [x] Test that the dashboard displays within 3 seconds (MNFR9)
  - [x] Verify no JS errors in console when servers are in any state
- [x] Task 6: Verify static file serving from API (AC: #1)
  - [x] Confirm Story 6.1's static mount serves `index.html` at `http://localhost:8080/`
  - [x] If not yet integrated, add static file mount in `mothership/api.py`
- [x] Task 7: Run full regression (AC: all)
  - [x] Run `PYTHONPATH="" poetry run pytest -v` to verify zero regressions
  - [x] Manual verification: start the mothership, open browser, verify dashboard loads

## Dev Notes

### Architecture Compliance

- **Single file:** `mothership/static/index.html` — vanilla HTML+JS+CSS in one file. No build tools, no npm, no framework. Per architecture doc: "No Build Step."
- **Polling:** Frontend polls `GET /api/servers` every 5 seconds for status updates. Per architecture doc.
- **Single port:** Dashboard served on same port as API (8080). Per architecture doc.

### Dashboard Design Guidelines

Keep it functional and clean — this is a developer tool, not a consumer product. Key principles:
- Dark or neutral theme (developer-friendly)
- Monospace font for technical data
- Clear visual distinction between running/stopped/crashed states
- Responsive enough for a laptop screen — no mobile optimization needed

### HTML Structure

```html
<!DOCTYPE html>
<html>
<head>
    <title>MCP Mothership</title>
    <style>/* embedded CSS */</style>
</head>
<body>
    <h1>MCP Mothership</h1>
    <div id="server-list"></div>
    <script>/* embedded JS */</script>
</body>
</html>
```

### JavaScript Pattern

```javascript
async function fetchServers() {
    const response = await fetch('/api/servers');
    const data = await response.json();
    renderServers(data.servers);
}

function renderServers(servers) {
    const container = document.getElementById('server-list');
    container.innerHTML = servers.map(s => renderServerCard(s)).join('');
}

// Auto-poll every 5 seconds
setInterval(fetchServers, 5000);
fetchServers(); // Initial load
```

### No Automated Tests for UI

This story is a single HTML file with embedded JS. Automated testing of vanilla HTML/JS in pytest is not practical. Verification is:
1. Backend regression tests still pass
2. Manual verification that the dashboard loads and functions correctly

### Files to Create

```
mothership/static/index.html         # Dashboard UI
```

### Files NOT Modified

No backend code changes expected (API already exists from Story 6.1).

### Dependencies on Previous Stories

- Story 6.1: REST API endpoints exist (`GET /api/servers`, `POST /api/servers/{name}/start`, etc.)
- Story 6.1: Static file serving mounted at `/`

### Anti-Patterns to Avoid

- Do NOT add React, Vue, or any frontend framework
- Do NOT add npm, webpack, or any build tools
- Do NOT split into multiple files — keep everything in one `index.html`
- Do NOT add external CDN dependencies
- Do NOT add authentication UI — no auth in MVP
- Do NOT add WebSocket — use polling per architecture decision

### Previous Story Learnings

- Run tests with `PYTHONPATH=""` to avoid ROS plugin conflicts
- FastAPI static file serving uses `StaticFiles` from starlette

### References

- [Source: documents/planning-artifacts/architecture-mothership.md#Dashboard Architecture]
- [Source: documents/planning-artifacts/epics.md#Story 6.2]
- [Source: documents/planning-artifacts/prd.md#FR14-FR17, MNFR4, MNFR9, MNFR11]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- None

### Completion Notes List

- Created `mothership/static/index.html` — single vanilla HTML+CSS+JS file, dark theme, monospace font
- Server cards show: name, description, status dot (green/grey/red), port, uptime, request/error counts, last request time
- Start/Stop buttons with color coding (green/red), disabled during requests to prevent double-clicks
- Auto-polling every 5 seconds via `setInterval` (satisfies MNFR11)
- Error toast notification for failed actions (4-second auto-dismiss)
- XSS-safe rendering via `textContent` escaping
- Uptime formatted as human-readable (Xs, Xm Ys, Xh Ym)
- Dashboard handles empty server list and all-stopped states gracefully (MNFR4)
- No external dependencies, no build step, no framework — pure vanilla HTML/JS/CSS
- Static file serving already set up in Story 6.1's `api.py`

### Change Log

- 2026-04-07: Story 6.2 implementation complete — Dashboard UI with server list, status indicators, start/stop controls, auto-polling

### File List

- `mothership/static/index.html` — created (dashboard UI)
