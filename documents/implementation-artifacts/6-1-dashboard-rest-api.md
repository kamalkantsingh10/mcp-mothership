# Story 6.1: Dashboard REST API

Status: review

## Story

As an operator,
I want a REST API that exposes server state, controls, and logs,
so that the dashboard frontend has a reliable data source for all operational actions.

## Acceptance Criteria

1. **Given** a `mothership/api.py` module with a FastAPI app **When** the manager starts via `python -m mothership` **Then** the API is served on the configured port (default 8080)
2. **Given** registered MCP servers (running, stopped, or crashed) **When** a client sends `GET /api/servers` **Then** the response includes all servers with: name, description, status, port, uptime, request_count, error_count, last_request_time, and tools list
3. **Given** a stopped MCP server **When** a client sends `POST /api/servers/{name}/start` **Then** the server starts and the response is `{"ok": true, "message": "Server 'name' started"}`
4. **Given** a running MCP server **When** a client sends `POST /api/servers/{name}/stop` **Then** the server stops and the response is `{"ok": true, "message": "Server 'name' stopped"}`
5. **Given** a request for a non-existent server name **When** any server-specific endpoint is called **Then** the response is `{"ok": false, "error": "Server 'name' not found"}` with HTTP 404
6. **Given** an MCP server with log entries **When** a client sends `GET /api/servers/{name}/logs?lines=100` **Then** the response contains the last 100 lines from the server's log file
7. **Given** new `mothership.yaml` files added to `servers/` **When** a client sends `POST /api/rescan` **Then** the manager rescans configs and new servers appear in subsequent `GET /api/servers` responses
8. **Given** `tests/mothership/test_api.py` **When** I run `poetry run pytest tests/mothership/test_api.py` **Then** all endpoint tests pass (list, start, stop, logs, rescan, error cases)

## Tasks / Subtasks

- [x] Task 1: Create `mothership/api.py` with FastAPI app (AC: #1)
  - [x] Create `mothership/api.py` with a FastAPI app instance
  - [x] The app must accept a `ServerManager` instance (dependency injection, not a global)
  - [x] Mount static file serving for `mothership/static/` at `/` (for dashboard UI in Story 6.2)
  - [x] The app should be importable and testable independently of `__main__.py`
- [x] Task 2: Implement `GET /api/servers` endpoint (AC: #2)
  - [x] Return JSON: `{"servers": [...]}`
  - [x] Each server entry includes: `name`, `description`, `status`, `port`, `uptime` (seconds, calculated from `start_time`), `request_count`, `error_count`, `last_request_time`, `tools` (list of tool names — empty list for now, populated when server is running)
  - [x] Uptime is `null` for stopped/crashed servers, calculated as `(now - start_time).total_seconds()` for running servers
  - [x] All datetime values in ISO 8601, all field names `snake_case`
- [x] Task 3: Implement `POST /api/servers/{name}/start` endpoint (AC: #3, #5)
  - [x] Call `manager.start_server(name)` 
  - [x] On success: return `{"ok": true, "message": "Server '{name}' started"}`
  - [x] On `ServerLifecycleError`: return `{"ok": false, "error": str(e)}` with HTTP 400 (already running) or 404 (not found)
  - [x] Distinguish 404 (not found) from 400 (already running) by checking error message
- [x] Task 4: Implement `POST /api/servers/{name}/stop` endpoint (AC: #4, #5)
  - [x] Call `manager.stop_server(name)`
  - [x] On success: return `{"ok": true, "message": "Server '{name}' stopped"}`
  - [x] On `ServerLifecycleError`: return `{"ok": false, "error": str(e)}` with HTTP 400 (not running) or 404 (not found)
- [x] Task 5: Implement `GET /api/servers/{name}/logs` endpoint (AC: #6, #5)
  - [x] Accept query param `lines` (default 100)
  - [x] Read the last `lines` from `logs/{name}.log`
  - [x] Return `{"server": name, "lines": ["line1", "line2", ...]}`
  - [x] If server not found: return 404
  - [x] If log file doesn't exist: return `{"server": name, "lines": []}`
- [x] Task 6: Implement `POST /api/rescan` endpoint (AC: #7)
  - [x] Re-run `discover_servers()` on the `servers/` directory
  - [x] Merge new configs into the manager's server dict (keep existing running state, add new servers as stopped)
  - [x] Return `{"ok": true, "message": "Rescan complete — N servers registered"}`
  - [x] Add a `rescan()` method to `ServerManager` that handles the merge logic
- [x] Task 7: Integrate API into `mothership/__main__.py` (AC: #1)
  - [x] Import the FastAPI app and mount it with uvicorn
  - [x] Run uvicorn as an asyncio task alongside the existing event loop (health monitoring, signal handling)
  - [x] The API server runs on `MothershipConfig.port` (default 8080)
  - [x] Ensure clean shutdown stops the uvicorn server too
- [x] Task 8: Write API tests (AC: #8)
  - [x] Create `tests/mothership/test_api.py` with tests using FastAPI's `TestClient`:
    - `test_list_servers_returns_all` — GET /api/servers returns registered servers
    - `test_list_servers_includes_metrics` — response includes uptime, request_count, etc.
    - `test_start_server_success` — POST start on stopped server returns ok
    - `test_start_server_already_running` — POST start on running server returns error
    - `test_stop_server_success` — POST stop on running server returns ok
    - `test_stop_server_not_running` — POST stop on stopped server returns error
    - `test_server_not_found_returns_404` — any endpoint with bad name returns 404
    - `test_get_logs_returns_lines` — GET logs returns file content
    - `test_get_logs_missing_file` — GET logs with no file returns empty list
    - `test_rescan_discovers_new_servers` — POST rescan finds new configs
  - [x] Run `PYTHONPATH="" poetry run pytest tests/mothership/test_api.py -v`
- [x] Task 9: Run full regression (AC: #8)
  - [x] Run `PYTHONPATH="" poetry run pytest -v` to verify zero regressions

## Dev Notes

### Architecture Compliance

- **Single port:** FastAPI serves both REST API and static files on one port (default 8080). Per architecture doc.
- **API response format:** `snake_case` fields, ISO 8601 timestamps, `{"ok": bool}` for actions. Per architecture doc API response patterns.
- **Static serving:** `mothership/static/index.html` served at `/` — the dashboard UI (Story 6.2 creates the file, this story sets up the mount point).
- **Action latency:** Start/stop actions must initiate within 1 second (MNFR10).

### REST API Endpoints (from Architecture Doc)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/servers` | GET | List all servers with status and metrics |
| `/api/servers/{name}/start` | POST | Start a server |
| `/api/servers/{name}/stop` | POST | Stop a server |
| `/api/servers/{name}/logs` | GET | Tail server log file (query: `lines`) |
| `/api/rescan` | POST | Rescan config directory for new/changed MCP configs |

### API Response Patterns (from Architecture Doc)

```python
# Server list
{"servers": [{"name": "imagen", "status": "running", "uptime": 3600, "request_count": 23, "error_count": 0, "last_request_time": "2026-04-07T14:30:00Z", "port": 8101, "description": "Image generation via Nano Banana Pro"}]}

# Action responses
{"ok": true, "message": "Server 'imagen' started"}

# Error responses
{"ok": false, "error": "Server 'imagen' not found"}

# Log responses
{"server": "imagen", "lines": ["2026-04-07 14:30:00 INFO ...", ...]}
```

### Current Codebase State

- `mothership/__main__.py` — exists, runs `_run()` which creates `ServerManager`, starts health monitoring, waits for shutdown signal. Needs to be extended to also start the FastAPI/uvicorn server.
- `mothership/manager.py` — exists with `ServerManager` class (start, stop, shutdown, health check, metrics polling). Needs a `rescan()` method.
- `mothership/config.py` — exists with `MothershipConfig` including `port: int = 8080`.
- `mothership/discovery.py` — exists with `discover_servers()`.
- `shared/logging_config.py` — `LOG_DIR` constant points to `logs/` directory. Log files are at `logs/{server_name}.log`.
- `mothership/api.py` — does NOT exist yet (created in this story).
- `mothership/static/` — does NOT exist yet (directory created here, `index.html` in Story 6.2).
- FastAPI and uvicorn already in `pyproject.toml` dependencies.

### Uvicorn Integration Pattern

The manager runs an asyncio event loop with health monitoring and signal handlers. FastAPI/uvicorn must coexist in the same loop. Pattern:

```python
import uvicorn

config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="info")
server = uvicorn.Server(config)
# Run as asyncio task alongside other tasks
await server.serve()
```

### Log File Reading

Log files are at `logs/{server_name}.log`. To tail the last N lines efficiently, read the file and return the last N lines. For MVP, `readlines()[-N:]` is fine — log files are capped at 5MB with rotation.

### ServerManager.rescan() Method

Needs to:
1. Re-run `discover_servers()` 
2. For each discovered config: if name already exists, update config but keep runtime state; if new, add as stopped
3. Optionally: remove servers whose config files were deleted (or leave them — simpler)

### Files to Create

```
mothership/api.py                    # FastAPI REST API
mothership/static/                   # Static files directory (empty for now)
tests/mothership/test_api.py         # API endpoint tests
```

### Files to Modify

```
mothership/__main__.py               # Start uvicorn alongside health monitoring
mothership/manager.py                # Add rescan() method
```

### Dependencies on Previous Stories

- Story 4.2: Config discovery (`discover_servers()`) exists
- Story 4.3: Process manager (`ServerManager`) exists with start/stop/health
- Story 4.4: Per-server logging exists (log files at `logs/{name}.log`)
- Story 5.2: Metrics polling populates `ServerState.request_count`, etc.

### Anti-Patterns to Avoid

- Do NOT use global state for the manager — pass it to the FastAPI app via dependency injection or closure
- Do NOT add authentication — single-user local tool, auth is Phase 2
- Do NOT add WebSocket or SSE — polling is the architecture decision
- Do NOT add CORS middleware unless needed for local dev
- Do NOT read log files synchronously in the event loop — use `asyncio.to_thread` or keep it simple since files are small
- Do NOT create a separate process for the API server — it runs in the same process as the manager

### Previous Story Learnings

- Run tests with `PYTHONPATH=""` to avoid ROS plugin conflicts
- Use `tmp_path` and `monkeypatch` for test isolation
- FastAPI `TestClient` is synchronous and works well with pytest
- `httpx` is already available as a dependency

### References

- [Source: documents/planning-artifacts/architecture-mothership.md#Dashboard Architecture]
- [Source: documents/planning-artifacts/architecture-mothership.md#REST API Design]
- [Source: documents/planning-artifacts/architecture-mothership.md#API Response Patterns]
- [Source: documents/planning-artifacts/epics.md#Story 6.1]
- [Source: documents/planning-artifacts/prd.md#FR14-FR20, MNFR4, MNFR9, MNFR10]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- None

### Completion Notes List

- Created `mothership/api.py` with `create_app()` factory pattern — accepts `ServerManager` via closure, no global state
- Implemented all 5 REST endpoints: `GET /api/servers`, `POST /api/servers/{name}/start`, `POST /api/servers/{name}/stop`, `GET /api/servers/{name}/logs`, `POST /api/rescan`
- Added `rescan()` method to `ServerManager` — merges new configs while preserving runtime state
- Integrated uvicorn into `mothership/__main__.py` — runs as asyncio task alongside health monitoring
- Clean shutdown sets `api_server.should_exit = True` and awaits the task
- Static file serving mounted at `/` for future dashboard UI (Story 6.2)
- Created `mothership/static/` directory
- 16 API tests covering all endpoints, error cases, log reading, and rescan
- 200/202 total tests pass (2 pre-existing failures unrelated)

### Change Log

- 2026-04-07: Story 6.1 implementation complete — Dashboard REST API with all endpoints, uvicorn integration, 16 tests

### File List

- `mothership/api.py` — created (FastAPI REST API with all endpoints)
- `mothership/static/` — created (empty directory for future dashboard UI)
- `mothership/__main__.py` — modified (uvicorn integration, API startup/shutdown)
- `mothership/manager.py` — modified (added `rescan()` method)
- `tests/mothership/test_api.py` — created (16 endpoint tests)
