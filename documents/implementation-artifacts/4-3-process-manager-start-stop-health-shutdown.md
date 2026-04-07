# Story 4.3: Process Manager — Start, Stop, Health & Shutdown

Status: review

## Story

As an operator,
I want to start and stop MCP servers as isolated subprocesses, with automatic crash detection and clean shutdown,
so that I can trust that one server's crash won't affect others and no orphaned processes remain.

## Acceptance Criteria

1. **Given** a `mothership/manager.py` module with a `ServerManager` class **When** I call `start_server(server_name)` **Then** the server's Python module is launched via `asyncio.create_subprocess_exec` **And** the manager tracks: PID, status ("running"), start time **And** the server runs as an independent process
2. **Given** a running MCP server **When** I call `stop_server(server_name)` **Then** SIGTERM is sent to the process **And** the status updates to "stopped"
3. **Given** a running MCP server that crashes **When** the health monitoring loop polls (<=5 second interval) **Then** the crash is detected via `process.returncode` **And** status updates to "crashed" **And** stderr output and exit code are captured in the server's state
4. **Given** the manager process is shutting down (SIGTERM/SIGINT) **When** clean shutdown executes **Then** SIGTERM is sent to all running child processes **And** a grace period elapses before SIGKILL for unresponsive processes **And** no orphaned child processes remain
5. **Given** 10+ registered MCP servers **When** all are started simultaneously **Then** the manager handles them without degradation
6. **Given** `mothership/__main__.py` **When** I run `python -m mothership` **Then** the manager starts, discovers configs, and is ready to start/stop servers
7. **Given** `tests/mothership/test_manager.py` **When** I run `poetry run pytest tests/mothership/test_manager.py` **Then** all process management tests pass (start, stop, crash detection, clean shutdown)

## Tasks / Subtasks

- [x] Task 1: Define ServerState data model (AC: #1)
  - [x] In `mothership/manager.py`, define `ServerState` dataclass:
    ```python
    @dataclass
    class ServerState:
        config: McpServerConfig        # From discovery
        process: asyncio.subprocess.Process | None = None
        status: str = "stopped"         # stopped, running, crashed
        pid: int | None = None
        start_time: datetime | None = None
        last_exit_code: int | None = None
        last_stderr: str | None = None  # Captured stderr on crash
        request_count: int = 0
        error_count: int = 0
        last_request_time: str | None = None  # ISO 8601
    ```
- [x] Task 2: Implement ServerManager class with start_server (AC: #1)
  - [x] Create `ServerManager` class with `__init__(self, configs: list[McpServerConfig], mothership_config: MothershipConfig)`
  - [x] Store servers as `dict[str, ServerState]` keyed by server name
  - [x] Implement `async def start_server(self, name: str) -> None`:
    - Validate server exists and is not already running
    - Launch via `asyncio.create_subprocess_exec("python", "-m", config.entry_point, ...)`
    - Pass `stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE`
    - Set status="running", record PID and start_time
    - Raise `ServerLifecycleError` if server name not found
- [x] Task 3: Implement stop_server (AC: #2)
  - [x] Implement `async def stop_server(self, name: str) -> None`:
    - Validate server exists and is running
    - Send SIGTERM to process
    - Wait for process to exit (with timeout)
    - If process doesn't exit within grace period (5 seconds), send SIGKILL
    - Set status="stopped", clear PID
    - Raise `ServerLifecycleError` if server name not found or not running
- [x] Task 4: Implement health monitoring loop (AC: #3)
  - [x] Implement `async def _health_check_loop(self) -> None`:
    - Run in background as asyncio task
    - Poll every 3 seconds (within the <=5s NFR)
    - For each server with status="running": check `process.returncode`
    - If returncode is not None: crash detected
      - Read stderr from captured pipe
      - Set status="crashed", store exit_code and stderr
      - Log crash event: `"Server '{name}' crashed with exit code {code}: {stderr}"`
- [x] Task 5: Implement clean shutdown (AC: #4)
  - [x] Implement `async def shutdown(self) -> None`:
    - Send SIGTERM to all running processes
    - Wait up to 5 seconds for all to exit
    - SIGKILL any still alive after grace period
    - Log each server's shutdown result
  - [x] Register signal handlers in `__main__.py` for SIGTERM and SIGINT:
    - On signal: call `manager.shutdown()`, then exit
- [x] Task 6: Wire up __main__.py (AC: #6)
  - [x] Update `mothership/__main__.py`:
    - Load `MothershipConfig` from config.yaml
    - Call `discover_servers()` to find MCP configs
    - Create `ServerManager` with discovered configs
    - Start the health monitoring loop
    - Log "MCP Mothership ready — {N} servers registered"
    - Keep the event loop running (for later API integration in Story 6.1)
    - On shutdown signal: clean shutdown all servers
- [x] Task 7: Write tests (AC: #7)
  - [x] Create `tests/mothership/test_manager.py` with tests:
    - `test_start_server_launches_subprocess` — mock `asyncio.create_subprocess_exec`, verify called with correct args
    - `test_start_server_tracks_state` — after start, status="running", PID set, start_time set
    - `test_start_already_running_raises_error` — starting a running server raises `ServerLifecycleError`
    - `test_start_unknown_server_raises_error` — unknown name raises `ServerLifecycleError`
    - `test_stop_server_sends_sigterm` — verify SIGTERM sent to process
    - `test_stop_server_updates_status` — after stop, status="stopped"
    - `test_stop_unresponsive_sends_sigkill` — process that ignores SIGTERM gets SIGKILL after grace period
    - `test_crash_detection` — mock process with returncode != None, verify status="crashed" and stderr captured
    - `test_shutdown_stops_all_running` — multiple running servers all get SIGTERM
    - `test_shutdown_sigkill_after_grace` — unresponsive server gets SIGKILL during shutdown
    - `test_get_server_states` — verify state dict returned correctly
  - [x] Run `PYTHONPATH="" poetry run pytest tests/mothership/test_manager.py -v`
- [x] Task 8: Run full regression (AC: #7)
  - [x] Run `PYTHONPATH="" poetry run pytest -v` to verify zero regressions

## Dev Notes

### Architecture Compliance

- **Process spawning:** Use `asyncio.create_subprocess_exec` — NOT `subprocess.Popen`. The manager is async.
- **Process isolation:** Each MCP server is a completely independent subprocess. The manager NEVER imports server code. It launches them as `python -m {entry_point}`.
- **Health monitoring:** Poll `process.returncode` at <=5 second intervals (MNFR2). Use 3-second interval to stay well within the NFR.
- **Clean shutdown:** SIGTERM first, grace period (5s), then SIGKILL. This satisfies MNFR3 (no orphaned processes).
- **Credential flow:** Each child process reads `.env` directly. The manager does NOT proxy credentials — it just launches the subprocess and the server's pydantic-settings config handles env var loading.
- **State tracking:** In-memory dict per server. Metrics fields (request_count, error_count, last_request_time) are placeholders here — they'll be populated by polling `/metrics` in Story 5.2.

### Process Launch Command

```python
process = await asyncio.create_subprocess_exec(
    sys.executable, "-m", config.entry_point,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    cwd=project_root,  # Run from project root so imports work
)
```

Key details:
- Use `sys.executable` to ensure the same Python interpreter
- `cwd` must be the project root so that `from shared.errors import ...` resolves
- Capture stderr for crash diagnostics

### Signal Handling Pattern

```python
import signal

loop = asyncio.get_event_loop()
for sig in (signal.SIGTERM, signal.SIGINT):
    loop.add_signal_handler(sig, lambda: asyncio.ensure_future(shutdown()))
```

### Project Structure After This Story

```
mothership/
  __init__.py          # From Story 4.1
  __main__.py          # MODIFIED — full startup sequence
  config.py            # From Story 4.2
  discovery.py         # From Story 4.2
  manager.py           # NEW — ServerManager class

tests/mothership/
  __init__.py          # From Story 4.2
  test_discovery.py    # From Story 4.2
  test_config.py       # From Story 4.2
  test_manager.py      # NEW
```

### Files to Create

```
mothership/manager.py                   # ServerManager class
tests/mothership/test_manager.py        # Process management tests
```

### Files to Modify

```
mothership/__main__.py                  # Wire up manager, discovery, signal handlers
```

### Dependencies on Previous Stories

- Story 4.1: `shared/errors.py` has `ServerLifecycleError`, `mothership/` package exists
- Story 4.2: `mothership/discovery.py` has `discover_servers()` and `McpServerConfig`, `mothership/config.py` has `MothershipConfig`

### Anti-Patterns to Avoid

- Do NOT import from `servers/` — the manager only launches subprocesses
- Do NOT use `subprocess.Popen` — use `asyncio.create_subprocess_exec` for async compatibility
- Do NOT proxy credentials through the manager — each server reads `.env` directly
- Do NOT implement the REST API in this story — that's Story 6.1
- Do NOT implement metrics polling in this story — that's Story 5.2
- Do NOT start any servers automatically on manager startup — the API (Story 6.1) or CLI commands will trigger starts
- Do NOT use `os.kill()` directly — use `process.terminate()` (SIGTERM) and `process.kill()` (SIGKILL) on the asyncio subprocess

### Testing Strategy

Tests should mock `asyncio.create_subprocess_exec` to avoid actually spawning processes. Use `unittest.mock.AsyncMock` for async subprocess methods. Create mock processes with configurable `returncode`, `pid`, `communicate()`, and `terminate()`/`kill()` methods.

```python
# Example mock process
mock_process = AsyncMock()
mock_process.pid = 12345
mock_process.returncode = None  # Still running
mock_process.terminate = MagicMock()
mock_process.kill = MagicMock()
mock_process.communicate = AsyncMock(return_value=(b"", b"error output"))
mock_process.wait = AsyncMock()
```

### Previous Story Learnings

- Run tests with `PYTHONPATH=""` to avoid ROS plugin conflicts
- Use `pytest-asyncio` for async test functions (already in dev dependencies)
- `monkeypatch` and `tmp_path` fixtures for test isolation

### References

- [Source: documents/planning-artifacts/architecture-mothership.md#Process Management Architecture]
- [Source: documents/planning-artifacts/architecture-mothership.md#Project Structure & Boundaries]
- [Source: documents/planning-artifacts/epics.md#Story 4.3: Process Manager — Start, Stop, Health & Shutdown]
- [Source: documents/planning-artifacts/prd.md#MCP Server Lifecycle Management — MFR1-MFR5]
- [Source: documents/planning-artifacts/prd.md#Reliability — MNFR1-MNFR3]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- Initial SIGKILL tests hung due to mock `wait()` not respecting kill — fixed by making mock `kill()` reset the `wait()` side effect

### Completion Notes List

- Implemented `ServerState` dataclass with all fields per architecture spec (config, process, status, pid, start_time, exit_code, stderr, metrics placeholders)
- Implemented `ServerManager` with `start_server()` using `asyncio.create_subprocess_exec` with `sys.executable`
- Implemented `stop_server()` with SIGTERM → grace period → SIGKILL escalation
- Implemented `_health_check_loop()` polling every 3s (within <=5s NFR), crash detection with stderr capture
- Implemented `shutdown()` for clean multi-server shutdown with grace period
- Wired up `mothership/__main__.py` with full startup: config load, discovery, manager creation, signal handling, health monitoring
- 12 new tests covering start/stop/crash/shutdown/state scenarios

### Change Log

- 2026-04-07: Story 4.3 implementation complete — ServerManager with full process lifecycle management

### File List

- `mothership/manager.py` — new (ServerState, ServerManager with start/stop/health/shutdown)
- `mothership/__main__.py` — modified (full startup sequence with config, discovery, manager, signals)
- `tests/mothership/test_manager.py` — new (12 process management tests)
