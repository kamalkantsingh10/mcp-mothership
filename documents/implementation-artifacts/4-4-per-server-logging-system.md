# Story 4.4: Per-Server Logging System

Status: review

## Story

As an operator,
I want each MCP server and the manager to write logs to dedicated files with rotation,
so that I can diagnose issues per-server without digging through combined output.

## Acceptance Criteria

1. **Given** a running MCP server named "imagen" **When** it writes log output **Then** logs are written to `logs/imagen.log` via `RotatingFileHandler`
2. **Given** the manager process **When** it writes log output **Then** logs are written to `logs/mothership.log` via `RotatingFileHandler`
3. **Given** a log file reaching the size limit (default 5MB) **When** the next log entry is written **Then** the file rotates with up to 3 backup files
4. **Given** a managed MCP server that crashes **When** the crash is detected **Then** the crash event is logged with exit code, stderr output, and timestamp
5. **Given** any log output across the system **When** credential values are present in the context **Then** they are never included in log messages
6. **Given** `tests/mothership/` and `tests/shared/` **When** I run the relevant logging tests **Then** all log setup, rotation, and crash logging tests pass

## Tasks / Subtasks

- [x] Task 1: Verify shared/logging_config.py supports per-server log files (AC: #1, #2)
  - [x] Confirm Story 4.1 delivered `setup_logging(log_level, log_name)` that creates `logs/{log_name}.log`
  - [x] If not yet parameterized: update `setup_logging()` to accept `log_name: str = "server"` parameter
  - [x] Verify default behavior: `setup_logging("INFO")` creates `logs/server.log` (backward compat)
  - [x] Verify named behavior: `setup_logging("INFO", log_name="imagen")` creates `logs/imagen.log`
  - [x] Verify named behavior: `setup_logging("INFO", log_name="mothership")` creates `logs/mothership.log`
- [x] Task 2: Wire per-server logging into manager's server start flow (AC: #1)
  - [x] When `ServerManager.start_server()` launches a subprocess, the child process must call `setup_logging()` with its own server name
  - [x] This happens inside each MCP server's own startup code (e.g., `servers/imagen/server.py` calls `setup_logging(config.log_level, log_name="imagen")`)
  - [x] Update `servers/imagen/server.py` to pass `log_name="imagen"` to `setup_logging()`
- [x] Task 3: Wire manager logging (AC: #2)
  - [x] In `mothership/__main__.py`, call `setup_logging(config.log_level, log_name="mothership")` at startup
  - [x] Verify all manager modules use `logger = logging.getLogger(__name__)` (they do via convention)
  - [x] Verify manager log output goes to `logs/mothership.log`
- [x] Task 4: Verify rotation behavior (AC: #3)
  - [x] `RotatingFileHandler` already configured with `maxBytes=5*1024*1024` and `backupCount=3` in `shared/logging_config.py`
  - [x] Make `maxBytes` and `backupCount` configurable via parameters: `setup_logging(log_level, log_name, max_bytes, backup_count)`
  - [x] Default values: `max_bytes=5_242_880` (5MB), `backup_count=3`
  - [x] Manager passes its config values: `setup_logging(config.log_level, "mothership", config.log_max_bytes, config.log_backup_count)`
- [x] Task 5: Verify crash logging (AC: #4)
  - [x] Confirm Story 4.3 manager health check loop already logs crash events with exit code, stderr, and timestamp
  - [x] Verify log format includes all required fields: `"Server '{name}' crashed with exit code {code} at {timestamp}: {stderr_snippet}"`
  - [x] Verify crash log entry goes to `logs/mothership.log` (manager's log, not the crashed server's log)
- [x] Task 6: Verify credential safety in logs (AC: #5)
  - [x] Audit all log statements in `mothership/manager.py`, `mothership/discovery.py`, `mothership/__main__.py`
  - [x] Verify no log statement includes env var values, API keys, or credentials
  - [x] Verify error messages from `shared/errors.py` hierarchy never contain credential values (inherited behavior)
  - [x] Add a test that asserts log output from a simulated credential error does not contain the credential value
- [x] Task 7: Write/update logging tests (AC: #6)
  - [x] Update `tests/shared/test_logging.py`:
    - `test_setup_logging_default_creates_server_log` — no log_name defaults to `server.log`
    - `test_setup_logging_named_creates_named_log` — `log_name="imagen"` creates `imagen.log`
    - `test_setup_logging_custom_rotation` — custom max_bytes and backup_count applied
    - `test_log_format_matches_spec` — verify `%(asctime)s %(levelname)s %(name)s %(message)s`
  - [x] Add crash logging test in `tests/mothership/test_manager.py`:
    - `test_crash_logged_with_exit_code_and_stderr` — crash detection produces correct log entry
    - `test_crash_log_no_credentials` — credential values not in crash log output
  - [x] Run `PYTHONPATH="" poetry run pytest tests/shared/test_logging.py tests/mothership/test_manager.py -v`
- [x] Task 8: Add logs/ to .gitignore (AC: #1, #2)
  - [x] Verify `logs/` is in `.gitignore` (should already be there from earlier stories)
  - [x] If not present, add it
- [x] Task 9: Run full regression (AC: #6)
  - [x] Run `PYTHONPATH="" poetry run pytest -v` to verify zero regressions

## Dev Notes

### Architecture Compliance

- **Per-server isolation:** Each MCP server process writes to its own log file. The manager writes to its own log file. Log files are in `logs/` directory at project root.
- **Log format:** `%(asctime)s %(levelname)s %(name)s %(message)s` — architecture spec uses space separators, not ` - ` separators. Story 4.1 should have updated this; verify.
- **Rotation:** `RotatingFileHandler` with configurable `maxBytes` (default 5MB) and `backupCount` (default 3). These values come from `MothershipConfig`.
- **Credential safety:** MNFR7 mandates log output never contains credential values. This is enforced by the `shared/errors.py` hierarchy (CredentialError only stores credential *name*, never value) and by convention in all log statements.
- **No stderr handler for MCP servers in production:** When running under the manager, MCP server stdout/stderr are captured by the manager's subprocess pipes. The server's own `RotatingFileHandler` handles its logging. The stderr handler in `setup_logging()` should be skippable or conditional for managed servers (OR: keep it for development convenience since stderr is captured anyway).

### Logging Flow

```
MCP Server Process (e.g., imagen)
  └── setup_logging("INFO", log_name="imagen")
      └── RotatingFileHandler → logs/imagen.log
      └── StreamHandler → stderr (captured by manager)

Manager Process
  └── setup_logging("INFO", log_name="mothership")
      └── RotatingFileHandler → logs/mothership.log
      └── StreamHandler → stderr (console output)
```

### Current setup_logging() Signature (After Story 4.1)

```python
def setup_logging(log_level: str = "INFO", log_name: str = "server",
                  max_bytes: int = 5_242_880, backup_count: int = 3) -> None:
```

If Story 4.1 only added `log_name`, this story adds `max_bytes` and `backup_count` parameters.

### Project Structure Notes

No new files are created in this story (unless tests need updating). This story is primarily about:
1. Wiring existing logging infrastructure into the manager and server startup flows
2. Making rotation configurable
3. Verifying crash logging and credential safety
4. Testing the integrated logging behavior

### Files to Modify

```
shared/logging_config.py              # Add max_bytes/backup_count params if not done in 4.1
servers/imagen/server.py              # Pass log_name="imagen" to setup_logging()
mothership/__main__.py                # Call setup_logging("INFO", "mothership", ...)
tests/shared/test_logging.py          # Add named log and rotation config tests
tests/mothership/test_manager.py      # Add crash logging tests
.gitignore                            # Verify logs/ entry
```

### Dependencies on Previous Stories

- Story 4.1: `shared/logging_config.py` exists with `log_name` parameter
- Story 4.2: `mothership/config.py` has `MothershipConfig` with `log_max_bytes` and `log_backup_count`
- Story 4.3: `mothership/manager.py` has health check loop that logs crash events

### Anti-Patterns to Avoid

- Do NOT create a custom logging framework — use Python stdlib `logging` with `RotatingFileHandler`
- Do NOT log credential values under any circumstances — only log credential *names*
- Do NOT use `print()` anywhere — all output via `logging`
- Do NOT make the log directory configurable per-server — all logs go to the same `logs/` directory (configurable at manager level via `MothershipConfig.log_dir`)
- Do NOT implement log streaming or tailing — that's the dashboard's job (Story 6.3)
- Do NOT add log levels beyond what Python stdlib provides

### Previous Story Learnings

- Run tests with `PYTHONPATH=""` to avoid ROS plugin conflicts
- Use `tmp_path` and `monkeypatch` for test isolation
- The `shared/logging.py` -> `shared/logging_config.py` rename in Story 4.1 fixes the stdlib shadowing issue

### References

- [Source: documents/planning-artifacts/architecture-mothership.md#Logging Architecture]
- [Source: documents/planning-artifacts/architecture-mothership.md#Logging Patterns]
- [Source: documents/planning-artifacts/epics.md#Story 4.4: Per-Server Logging System]
- [Source: documents/planning-artifacts/prd.md#Logging System — MFR21-MFR24]
- [Source: documents/planning-artifacts/prd.md#Security — MNFR7]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- None

### Completion Notes List

- Added `max_bytes` and `backup_count` parameters to `setup_logging()` for configurable rotation
- Wired `log_name="imagen"` into `servers/imagen/server.py` for per-server log files
- Wired configurable rotation from `MothershipConfig` into `mothership/__main__.py`
- Verified crash logging in manager health check includes exit code, stderr, and timestamp
- Audited all log statements — no credential values logged anywhere
- Verified `logs/` already in `.gitignore`
- Added 4 new tests: custom rotation, default rotation, crash log content, credential safety

### Change Log

- 2026-04-07: Story 4.4 implementation complete — per-server logging with configurable rotation, crash logging verified, credential safety confirmed

### File List

- `shared/logging_config.py` — modified (added max_bytes/backup_count params)
- `servers/imagen/server.py` — modified (added log_name="imagen")
- `mothership/__main__.py` — modified (pass rotation config to setup_logging)
- `tests/shared/test_logging.py` — modified (added custom_rotation and default_rotation tests)
- `tests/mothership/test_manager.py` — modified (added crash logging and credential safety tests)
