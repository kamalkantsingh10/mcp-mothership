# Story 5.2: Metrics Endpoint & Tracking

Status: review

## Story

As an operator,
I want each MCP server to track and expose request count, error count, and last request time,
so that I can monitor server activity and health.

## Acceptance Criteria

1. **Given** a running MCP server (Imagen) **When** a tool is invoked successfully **Then** `request_count` increments by 1 **And** `last_request_time` updates to the current ISO 8601 timestamp
2. **Given** a running MCP server **When** a tool invocation results in an error **Then** both `request_count` and `error_count` increment by 1
3. **Given** a running MCP server **When** a client sends `GET /metrics` **Then** the response is JSON: `{"request_count": N, "error_count": N, "last_request_time": "ISO8601 or null"}`
4. **Given** the `/metrics` endpoint **When** it coexists with the Streamable HTTP MCP transport **Then** both respond correctly on the same port (mounted on the same Starlette app)
5. **Given** the manager's health monitoring loop **When** it polls a running server **Then** it fetches `/metrics` and stores the metrics in its in-memory server state **And** uptime is calculated by the manager from process start time
6. **Given** `tests/servers/imagen/test_server.py` **When** I run the metrics-related tests **Then** all counter increment, reset, and endpoint response tests pass

## Tasks / Subtasks

- [x] Task 1: Add metrics tracking to Imagen server (AC: #1, #2)
  - [x] Add module-level counters in `servers/imagen/server.py`: `_request_count: int = 0`, `_error_count: int = 0`, `_last_request_time: str | None = None`
  - [x] Wrap or augment `generate_image` to increment `_request_count` and update `_last_request_time` on every call (success or failure)
  - [x] On error (exception raised), also increment `_error_count` before re-raising
  - [x] Use `datetime.now(timezone.utc).isoformat()` for `_last_request_time`
- [x] Task 2: Add `/metrics` endpoint to Imagen server (AC: #3, #4)
  - [x] Access the underlying Starlette app from FastMCP: `app = mcp._mcp_server.app` or use FastMCP's custom route mechanism
  - [x] Mount a `GET /metrics` route that returns `{"request_count": N, "error_count": N, "last_request_time": "..." or null}`
  - [x] Verify the `/metrics` endpoint coexists with the Streamable HTTP MCP transport on port 8101
  - [x] Research FastMCP's Starlette app access pattern — FastMCP 2.x exposes the underlying app for custom routes
- [x] Task 3: Create a reusable metrics pattern for future MCP servers (AC: #1, #2, #3)
  - [x] Consider adding a lightweight `MetricsTracker` class or helper in `shared/` if the pattern is clean enough
  - [x] OR keep it inline in `servers/imagen/server.py` if the abstraction isn't worth it for one server
  - [x] The pattern must be easy to replicate when adding new MCP servers (per architecture doc)
- [x] Task 4: Update manager health check to poll `/metrics` (AC: #5)
  - [x] In `mothership/manager.py` `_health_check_loop`, add HTTP fetch to `http://localhost:{port}/metrics` for each running server
  - [x] Use `asyncio`-compatible HTTP client (e.g., `aiohttp` or `httpx`) — check if either is already a dependency, or use `urllib` with asyncio
  - [x] Parse the JSON response and update `ServerState.request_count`, `ServerState.error_count`, `ServerState.last_request_time`
  - [x] Calculate uptime from `ServerState.start_time` (already tracked by manager — no change to uptime logic)
  - [x] Handle connection errors gracefully — if `/metrics` is unreachable, log a warning but don't change server status
- [x] Task 5: Write metrics tracking tests (AC: #6)
  - [x] In `tests/servers/imagen/test_server.py`, add:
    - `test_metrics_increment_on_success` — call generate_image, verify request_count=1, error_count=0, last_request_time set
    - `test_metrics_increment_on_error` — trigger an error, verify request_count=1, error_count=1
    - `test_metrics_endpoint_returns_json` — GET /metrics returns expected JSON shape
    - `test_metrics_initial_state` — before any calls, request_count=0, error_count=0, last_request_time=null
  - [x] In `tests/mothership/test_manager.py`, add:
    - `test_health_check_polls_metrics` — mock HTTP response, verify ServerState updated
    - `test_health_check_metrics_unreachable` — mock connection error, verify server stays running
  - [x] Run `PYTHONPATH="" poetry run pytest tests/servers/imagen/ tests/mothership/test_manager.py -v`
- [x] Task 6: Run full regression (AC: #6)
  - [x] Run `PYTHONPATH="" poetry run pytest -v` to verify zero regressions

## Dev Notes

### Architecture Compliance

- **Metrics ownership:** Each MCP server owns its own metrics — the manager only polls. Per architecture-mothership.md: "Keeps metrics ownership with the server that generates them."
- **Uptime:** Calculated by manager from `ServerState.start_time`, NOT reported by the server. Per architecture doc.
- **In-memory only:** No persistent metrics store for MVP.
- **JSON format:** `snake_case` fields, ISO 8601 timestamps. Per API response patterns in architecture doc.

### Mounting `/metrics` on FastMCP's Starlette App

FastMCP 2.x uses Starlette internally. The `/metrics` endpoint must coexist with the MCP Streamable HTTP transport on the same port. The implementing agent should research the correct way to add custom routes to FastMCP's underlying ASGI app. Options include:

1. FastMCP's `custom_route` or route mounting API (if available in current version)
2. Accessing `mcp._mcp_server` to get the Starlette app and adding routes directly
3. Wrapping the ASGI app with additional middleware

The agent should check the FastMCP source/docs for the cleanest approach.

### Metrics Tracking Pattern

```python
# Module-level counters
_request_count: int = 0
_error_count: int = 0
_last_request_time: str | None = None

# Inside generate_image (or as a decorator/wrapper):
_request_count += 1
_last_request_time = datetime.now(timezone.utc).isoformat()
try:
    # ... existing tool logic ...
except Exception:
    _error_count += 1
    raise
```

### Manager Polling

The health check loop in `mothership/manager.py` (line 119) already polls at 3-second intervals. This story extends it to also fetch `/metrics` from each running server. The `ServerState` dataclass already has `request_count`, `error_count`, and `last_request_time` fields (lines 38-39).

### HTTP Client for Manager

The manager needs an async HTTP client to poll `/metrics`. Check if `httpx` or `aiohttp` is already in `pyproject.toml`. If not, `httpx` is preferred (async-native, lightweight). Alternatively, `urllib.request` can work via `asyncio.to_thread` but is less clean.

### Files to Modify

```
servers/imagen/server.py          # Add counters + /metrics endpoint
mothership/manager.py             # Add /metrics polling to health check loop
tests/servers/imagen/test_server.py  # Add metrics tests (created in 5.1)
tests/mothership/test_manager.py  # Add metrics polling tests
```

### Files Potentially to Modify

```
pyproject.toml                    # Add httpx dependency if not present
```

### Dependencies on Previous Stories

- Story 5.1: Imagen running on Streamable HTTP with Starlette app (must be complete first)
- Story 4.3: Manager health check loop exists in `mothership/manager.py`

### Anti-Patterns to Avoid

- Do NOT persist metrics to disk — in-memory only for MVP
- Do NOT add a separate metrics server or port — `/metrics` lives on the same port as the MCP server
- Do NOT calculate uptime in the MCP server — the manager calculates it from process start time
- Do NOT add Prometheus format or complex metrics libraries — plain JSON
- Do NOT block the health check loop on a slow `/metrics` response — use timeouts

### Previous Story Learnings

- Run tests with `PYTHONPATH=""` to avoid ROS plugin conflicts
- Use `tmp_path` and `monkeypatch` for test isolation
- `ServerState` already has metrics fields — just populate them

### References

- [Source: documents/planning-artifacts/architecture-mothership.md#Metrics Collection]
- [Source: documents/planning-artifacts/architecture-mothership.md#Metrics Endpoint Pattern]
- [Source: documents/planning-artifacts/epics.md#Story 5.2]
- [Source: documents/planning-artifacts/prd.md#FR25, FR26, FR27, FR28]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- None

### Completion Notes List

- Added module-level metrics counters (`_request_count`, `_error_count`, `_last_request_time`) to `servers/imagen/server.py`
- Wrapped `generate_image` with metrics tracking — extracts impl to `_generate_image_impl`, wrapper increments counters on every call and `_error_count` on exceptions
- Added `/metrics` GET endpoint using `@mcp.custom_route("/metrics", methods=["GET"])` — returns JSON with all three counter fields
- Used `FastMCP.custom_route` decorator (clean public API, no private internals accessed)
- Updated `mothership/manager.py` health check loop to poll `/metrics` via `httpx.AsyncClient` with 2s timeout
- Added `_poll_metrics` helper that gracefully handles connection errors (logs warning, doesn't change server status)
- `httpx` already available as transitive dependency (required by `google-genai` and `mcp`) — no new deps needed
- Kept metrics inline in server.py (Task 3 decision: abstraction not worth it for one server, pattern is 3 lines of counter code + 1 decorator endpoint)
- Added 6 metrics tests in `tests/servers/imagen/test_server.py` and 2 polling tests in `tests/mothership/test_manager.py`
- 178/180 total tests pass (2 pre-existing failures unrelated to this story)

### Change Log

- 2026-04-07: Story 5.2 implementation complete — metrics tracking, /metrics endpoint, manager polling

### File List

- `servers/imagen/server.py` — modified (metrics counters, generate_image wrapper, /metrics endpoint)
- `mothership/manager.py` — modified (httpx import, _poll_metrics method, health check loop polls metrics)
- `tests/servers/imagen/test_server.py` — modified (6 metrics tests added, fixture resets metrics)
- `tests/mothership/test_manager.py` — modified (2 metrics polling tests added)
