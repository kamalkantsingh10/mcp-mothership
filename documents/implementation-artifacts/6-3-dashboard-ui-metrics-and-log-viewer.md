# Story 6.3: Dashboard UI — Metrics & Log Viewer

Status: review

## Story

As an operator,
I want to see per-server metrics and view server logs from the dashboard,
so that I can monitor activity and diagnose issues without leaving the browser.

## Acceptance Criteria

1. **Given** a running MCP server with activity **When** the dashboard displays its entry **Then** I see: uptime, request count, error count, and last request time
2. **Given** metrics displayed on the dashboard **When** the polling interval elapses (3-5 seconds) **Then** metrics update to reflect the latest values from the API
3. **Given** the server list **When** I select a server for log viewing **Then** a log viewer panel displays recent log entries for that server
4. **Given** the log viewer for a specific server **When** log entries are displayed **Then** each entry shows timestamp, log level, and message
5. **Given** the log viewer is open **When** new log entries are written by the server **Then** the viewer updates on the next poll cycle to show the latest entries
6. **Given** a server showing which tools it exposes **When** the dashboard fetches server data **Then** the tools list is displayed for operator reference (MFR16)

## Tasks / Subtasks

- [x] Task 1: Add metrics display to server cards (AC: #1, #2)
  - [x] Extend the server card/row from Story 6.2 to show: uptime (formatted as HH:MM:SS or "—"), request_count, error_count, last_request_time
  - [x] Uptime is already calculated by the API (`GET /api/servers` response)
  - [x] Metrics auto-update on each polling cycle (already polling every 5 seconds from Story 6.2)
  - [x] Format uptime as human-readable (e.g., "2h 15m" or "0:02:15")
  - [x] Show "—" for metrics when server is stopped/crashed
- [x] Task 2: Add tools list display (AC: #6)
  - [x] Show the tools list from the API response for each server
  - [x] Display as a comma-separated list or badges (e.g., "generate_image")
  - [x] Show "No tools" or empty state for servers that haven't reported tools yet
- [x] Task 3: Implement log viewer panel (AC: #3, #4)
  - [x] Add a "Logs" button or expandable section to each server card
  - [x] On click: fetch `GET /api/servers/{name}/logs?lines=50`
  - [x] Display log entries in a scrollable, monospace-font panel
  - [x] Each log line should be visually parseable (timestamp, level, message are space-separated per log format)
  - [x] Color-code log levels: ERROR in red, WARNING in yellow, INFO in default
- [x] Task 4: Implement log auto-refresh (AC: #5)
  - [x] When the log viewer is open for a server, poll `GET /api/servers/{name}/logs?lines=50` on each cycle
  - [x] Update the log panel content without closing/reopening
  - [x] Auto-scroll to bottom when new entries appear
  - [x] Stop polling logs when the log viewer is closed
- [x] Task 5: Verify metrics update on polling cycle (AC: #2)
  - [x] Confirm that the existing 5-second polling from Story 6.2 also refreshes metrics
  - [x] Metrics should visually update without full re-render (or re-render is fast enough to be imperceptible)
- [x] Task 6: Run full regression (AC: all)
  - [x] Run `PYTHONPATH="" poetry run pytest -v` to verify zero regressions
  - [x] Manual verification: start mothership with Imagen, generate an image, verify metrics/logs update in dashboard

## Dev Notes

### Architecture Compliance

- **Metrics display:** Uptime, request count, error count, last request time — all from `GET /api/servers` response (calculated by manager). Per architecture doc.
- **Log viewing:** `GET /api/servers/{name}/logs?lines=N` returns tail of log file. Per architecture doc.
- **Tools list:** FR16 requires showing which tools a server exposes. The API returns this in the server list.
- **Polling:** Same 5-second interval from Story 6.2. Log viewer adds a secondary poll for the specific server's logs.

### Uptime Formatting

The API returns uptime in seconds (integer or null). Format for display:
- `null` → "—"
- `< 60` → "Xs" (e.g., "45s")
- `< 3600` → "Xm Ys" (e.g., "12m 30s")
- `>= 3600` → "Xh Ym" (e.g., "2h 15m")

### Log Format

Log entries follow the format: `%(asctime)s %(levelname)s %(name)s %(message)s`
Example: `2026-04-07 14:30:00,123 INFO servers.imagen.server Image saved to: /path/to/file.png`

The log viewer should display raw lines — no parsing needed beyond optional color-coding by level.

### Log Viewer UX

- Expandable panel below each server card, or a modal/sidebar
- Default: closed. Click "Logs" to open.
- When open: show last 50 lines, auto-refresh every 5 seconds
- Monospace font, dark background for readability
- Optional: scroll lock (auto-scroll to bottom vs. stay in place)

### No Automated Tests for UI

Same as Story 6.2 — this is vanilla HTML/JS modification. Verification is manual + backend regression tests.

### Files to Modify

```
mothership/static/index.html         # Add metrics display, tools list, log viewer
```

### Files NOT Modified

No backend code changes expected (API endpoints already exist from Story 6.1).

### Dependencies on Previous Stories

- Story 6.1: REST API with `GET /api/servers` (includes metrics) and `GET /api/servers/{name}/logs`
- Story 6.2: Dashboard UI with server list and polling infrastructure

### Anti-Patterns to Avoid

- Do NOT add a separate metrics page — metrics are inline with server cards
- Do NOT add persistent log storage or search — MVP is tail of log file
- Do NOT add charts or graphing libraries — plain numbers for MVP
- Do NOT add log filtering beyond what the API provides
- Do NOT break out into multiple HTML files — keep everything in one `index.html`

### Previous Story Learnings

- Run tests with `PYTHONPATH=""` to avoid ROS plugin conflicts
- Log files are at `logs/{server_name}.log` (from `shared/logging_config.py` LOG_DIR)

### References

- [Source: documents/planning-artifacts/architecture-mothership.md#Dashboard Architecture]
- [Source: documents/planning-artifacts/architecture-mothership.md#Logging Architecture]
- [Source: documents/planning-artifacts/epics.md#Story 6.3]
- [Source: documents/planning-artifacts/prd.md#FR16-FR20, MNFR11]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- None

### Completion Notes List

- Metrics display was already built into Story 6.2 (uptime, request_count, error_count, last_request_time in server cards)
- Added tools list display as styled badges in each server card
- Added expandable log viewer panel with "Logs" toggle button per server card
- Log viewer fetches `GET /api/servers/{name}/logs?lines=50` on open
- Log auto-refresh: polls every 5 seconds while panel is open, stops polling on close
- Auto-scrolls to bottom when new log entries appear
- Log level color-coding: ERROR (red), WARNING (yellow), DEBUG (grey), INFO (default)
- Dark background for log panel for readability
- All metrics update on the existing 5-second polling cycle
- No backend changes — all improvements in the single `index.html` file

### Change Log

- 2026-04-07: Story 6.3 implementation complete — metrics display, tools list badges, expandable log viewer with auto-refresh and color-coding

### File List

- `mothership/static/index.html` — modified (added tools badges, log viewer panel, log polling, log color-coding)
