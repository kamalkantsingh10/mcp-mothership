# Story 4.1: Project Rename & Shared Module Evolution

Status: review

## Story

As a developer,
I want the project renamed to MCP Mothership with evolved shared modules,
so that the codebase reflects the new scope and the error hierarchy supports manager operations.

## Acceptance Criteria

1. **Given** the existing Engagement Manager codebase **When** the migration is complete **Then** `pyproject.toml` reflects `mcp-mothership` as the project name **And** the `mothership/` package directory exists with `__init__.py` and `__main__.py` **And** `shared/errors.py` base class is renamed from `EngagementManagerError` to `MothershipError` **And** a new `ServerLifecycleError` class exists in `shared/errors.py` **And** `shared/logging_config.py` supports `RotatingFileHandler` setup for named log files **And** all existing tests pass with the renamed error classes **And** `python -m mothership` runs without error (can be a no-op stub at this stage)

## Tasks / Subtasks

- [x] Task 1: Rename project in pyproject.toml (AC: #1)
  - [x] Change `name = "engagement-manager"` to `name = "mcp-mothership"` in `pyproject.toml`
  - [x] Update `description` to reflect MCP server management scope
  - [x] Add `fastapi` and `uvicorn[standard]` to dependencies (needed by later stories)
  - [x] Run `poetry lock --no-update` to refresh the lock file
- [x] Task 2: Evolve shared/errors.py (AC: #1)
  - [x] Rename `EngagementManagerError` to `MothershipError` in `shared/errors.py`
  - [x] Update module docstring from "Engagement Manager" to "MCP Mothership"
  - [x] Add `ServerLifecycleError(MothershipError)` with docstring: "MCP server failed to start, stop, or encountered a lifecycle issue."
  - [x] All existing subclasses (`ConfigurationError`, `ApiUnavailableError`, `CredentialError`, `GenerationError`) inherit from `MothershipError`
- [x] Task 3: Update all references to EngagementManagerError (AC: #1)
  - [x] Update `tests/shared/test_errors.py` — all assertions referencing `EngagementManagerError` become `MothershipError`
  - [x] Add test for `ServerLifecycleError` in `tests/shared/test_errors.py`
  - [x] Grep entire codebase for any remaining `EngagementManagerError` references and update
- [x] Task 4: Rename shared/logging.py to shared/logging_config.py (AC: #1)
  - [x] Rename file from `shared/logging.py` to `shared/logging_config.py`
  - [x] Update `setup_logging()` to accept an optional `log_name` parameter for per-server log file naming (e.g., `logs/imagen.log`, `logs/mothership.log` instead of hardcoded `logs/server.log`)
  - [x] Keep the existing `LOG_DIR` default and `RotatingFileHandler` settings (5MB, 3 backups)
  - [x] Update the default log format to: `%(asctime)s %(levelname)s %(name)s %(message)s` (matching architecture spec)
  - [x] Update `servers/imagen/server.py` import from `shared.logging` to `shared.logging_config`
  - [x] Update `tests/shared/test_logging.py` to test new `log_name` parameter
- [x] Task 5: Create mothership/ package stub (AC: #1)
  - [x] Create `mothership/__init__.py` (empty)
  - [x] Create `mothership/__main__.py` with a minimal stub that prints "MCP Mothership starting..." and exits cleanly
  - [x] Verify `python -m mothership` runs without error
- [x] Task 6: Run full regression suite (AC: #1)
  - [x] Run `PYTHONPATH="" poetry run pytest -v` to verify all existing tests pass
  - [x] Verify `python -m mothership` runs and exits cleanly

## Dev Notes

### Architecture Compliance

- **Base error rename:** `EngagementManagerError` -> `MothershipError`. This is a codebase-wide rename — every import and reference must be updated.
- **New error class:** `ServerLifecycleError` is used by the process manager (Story 4.3) for start/stop/crash failures. Add it now so it's available.
- **Logging rename:** The file rename from `logging.py` to `logging_config.py` avoids shadowing Python's stdlib `logging` module — a latent bug in the current codebase. The architecture doc specifies `shared/logging_config.py`.
- **Log file naming:** Current `shared/logging.py` hardcodes `logs/server.log`. The architecture requires per-server log files (`logs/imagen.log`, `logs/mothership.log`). Update `setup_logging()` to accept a `log_name` parameter that determines the log filename.
- **Log format change:** Current format uses ` - ` separators. Architecture spec uses space separators: `%(asctime)s %(levelname)s %(name)s %(message)s`. Update to match.
- **Dependencies:** Add `fastapi` and `uvicorn[standard]` now since they're required by Story 6.1 (Dashboard REST API) and the `mothership/` package. Adding early prevents dependency conflicts later.

### Current File State (What Exists Today)

```
shared/
  __init__.py
  errors.py          # EngagementManagerError base class
  config.py          # BaseServerConfig with pydantic-settings
  logging.py         # setup_logging() with RotatingFileHandler to logs/server.log

servers/imagen/
  __init__.py
  server.py          # Imports: from shared.logging import setup_logging
  config.py          # ImagenConfig extends BaseServerConfig

tests/shared/
  __init__.py
  test_errors.py     # Tests EngagementManagerError hierarchy
  test_config.py     # Tests BaseServerConfig
  test_logging.py    # Tests setup_logging()
```

### Files to Create

```
mothership/
  __init__.py        # Empty
  __main__.py        # Stub entry point
```

### Files to Modify

```
pyproject.toml                      # Rename project, add fastapi/uvicorn deps
shared/errors.py                    # Rename base class, add ServerLifecycleError
shared/logging.py -> shared/logging_config.py  # Rename + add log_name param + update format
servers/imagen/server.py            # Update import: shared.logging -> shared.logging_config
tests/shared/test_errors.py         # Update base class refs, add ServerLifecycleError test
tests/shared/test_logging.py        # Update import, test log_name parameter
```

### Anti-Patterns to Avoid

- Do NOT remove any existing error classes — only rename the base and add `ServerLifecycleError`
- Do NOT change `shared/config.py` — the base config system stays as-is
- Do NOT modify `servers/imagen/server.py` beyond updating the logging import
- Do NOT add business logic to `mothership/__main__.py` — it's a stub for now
- Do NOT use `print()` in the stub — use `logging` or a simple startup message via `sys.stderr`
- Do NOT create `mothership/config.py`, `mothership/manager.py`, etc. yet — those are later stories

### Previous Story Learnings

- Run tests with `PYTHONPATH=""` to avoid ROS plugin conflicts (from Story 3.3)
- Config loaded at module level in `servers/imagen/server.py` — `autouse` fixture with `monkeypatch.setenv` required for tests
- The `shared/logging.py` name shadows Python stdlib `logging` — this rename fixes that

### References

- [Source: documents/planning-artifacts/architecture-mothership.md#Error Handling Patterns]
- [Source: documents/planning-artifacts/architecture-mothership.md#Logging Patterns]
- [Source: documents/planning-artifacts/architecture-mothership.md#Project Structure & Boundaries]
- [Source: documents/planning-artifacts/epics.md#Story 4.1: Project Rename & Shared Module Evolution]
- [Source: documents/planning-artifacts/prd.md#Project Migration — FR32, FR33]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- 2 pre-existing test failures in `tests/imagen/test_config.py` (environment API key leaking into test isolation) — not caused by this story's changes

### Completion Notes List

- Renamed project from `engagement-manager` to `mcp-mothership` in pyproject.toml with updated description
- Added `fastapi` and `uvicorn[standard]` dependencies for future stories
- Renamed `EngagementManagerError` to `MothershipError` across all source and test files
- Added `ServerLifecycleError(MothershipError)` for process manager use in Story 4.3
- Renamed `shared/logging.py` to `shared/logging_config.py` to avoid stdlib shadowing
- Added `log_name` parameter to `setup_logging()` for per-server log files (default: "server")
- Updated log format from ` - ` separators to space separators per architecture spec
- Created `mothership/` package stub with `__init__.py` and `__main__.py`
- `python -m mothership` runs and exits cleanly
- 120/122 tests pass (2 pre-existing failures unrelated to this story)

### Change Log

- 2026-04-07: Story 4.1 implementation complete — project renamed, error hierarchy evolved, logging module renamed with per-server support, mothership package stub created

### File List

- `pyproject.toml` — modified (name, description, dependencies)
- `poetry.lock` — modified (refreshed after dependency changes)
- `shared/errors.py` — modified (EngagementManagerError → MothershipError, added ServerLifecycleError)
- `shared/logging.py` — deleted (renamed to logging_config.py)
- `shared/logging_config.py` — new (renamed from logging.py, added log_name param, updated format)
- `servers/imagen/server.py` — modified (import updated: shared.logging → shared.logging_config)
- `tests/shared/test_errors.py` — modified (EngagementManagerError → MothershipError, added ServerLifecycleError test)
- `tests/shared/test_logging.py` — modified (updated import, added log_name and format tests)
- `mothership/__init__.py` — new (empty)
- `mothership/__main__.py` — new (stub entry point)
