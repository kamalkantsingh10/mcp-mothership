# Story 4.2: Config Discovery & Registration

Status: review

## Story

As an operator,
I want to register a new MCP server by dropping a `mothership.yaml` config file into its directory,
so that I can add capabilities without modifying manager code.

## Acceptance Criteria

1. **Given** a `mothership/discovery.py` module **When** the manager scans `servers/*/mothership.yaml` **Then** all valid config files are discovered and parsed into a list of server registrations
2. **Given** a `mothership.yaml` with fields: name, description, entry_point, port, env_vars **When** the config is loaded **Then** each field is validated via a pydantic model **And** missing required fields produce a `ConfigurationError` with a clear message
3. **Given** a config file with no `port` specified **When** the config is loaded **Then** a port is auto-assigned from the configurable range (default 8100-8199) **And** no two servers receive the same auto-assigned port
4. **Given** a malformed or invalid config file **When** discovery runs **Then** the error is logged to the manager log **And** other valid configs are still loaded successfully
5. **Given** `tests/mothership/test_discovery.py` **When** I run `poetry run pytest tests/mothership/test_discovery.py` **Then** all config scanning, validation, and port assignment tests pass

## Tasks / Subtasks

- [x] Task 1: Create MCP registration pydantic model (AC: #2)
  - [x] Create `mothership/discovery.py`
  - [x] Define `McpServerConfig` pydantic model with fields:
    - `name: str` (required) — display name for dashboard
    - `description: str` (required) — what this MCP does
    - `entry_point: str` (required) — Python module path (e.g., `servers.imagen.server`)
    - `port: int | None = None` — network port (optional, auto-assigned if omitted)
    - `env_vars: list[str] = []` — required environment variable names
  - [x] Validation: `ConfigurationError` raised on missing required fields with clear message naming the field
- [x] Task 2: Implement config directory scanning (AC: #1, #4)
  - [x] Implement `discover_servers(servers_dir: Path) -> list[McpServerConfig]` function
  - [x] Scan pattern: `servers/*/mothership.yaml` using `pathlib.Path.glob()`
  - [x] For each YAML file found: load with `yaml.safe_load()`, validate with `McpServerConfig`
  - [x] On validation error: log the error (with file path) to logger, skip that config, continue scanning
  - [x] Return list of all successfully validated configs
- [x] Task 3: Implement port auto-assignment (AC: #3)
  - [x] Add port range configuration to `mothership/config.py`:
    ```python
    class MothershipConfig(BaseServerConfig):
        port: int = 8080
        log_dir: str = "./logs"
        port_range_start: int = 8100
        port_range_end: int = 8199
        log_max_bytes: int = 5_242_880  # 5MB
        log_backup_count: int = 3
    ```
  - [x] Create `mothership/config.py` with `MothershipConfig` extending `BaseServerConfig`
  - [x] In `discover_servers()`, after loading all configs: assign ports to configs with `port=None` from the range, skipping ports already claimed by explicit configs
  - [x] Raise `ConfigurationError` if port range is exhausted
  - [x] Ensure no two servers get the same port (explicit or auto-assigned)
- [x] Task 4: Create Imagen mothership.yaml (AC: #1)
  - [x] Create `servers/imagen/mothership.yaml`:
    ```yaml
    name: imagen
    description: "Image generation via Vertex AI Nano Banana Pro"
    entry_point: servers.imagen.server
    port: 8101
    env_vars:
      - IMAGEN_GCP_PROJECT
      - IMAGEN_GCP_REGION
    ```
- [x] Task 5: Write tests (AC: #5)
  - [x] Create `tests/mothership/__init__.py`
  - [x] Create `tests/mothership/test_discovery.py` with tests:
    - `test_discover_valid_config` — single valid YAML returns one McpServerConfig
    - `test_discover_multiple_configs` — multiple server dirs each with valid YAML
    - `test_missing_required_field_raises_error` — YAML missing `name` logs error, skipped
    - `test_malformed_yaml_logs_error` — invalid YAML syntax logs error, skipped
    - `test_no_configs_returns_empty_list` — empty servers dir returns []
    - `test_port_auto_assignment` — config with no port gets auto-assigned from range
    - `test_port_no_collision` — explicit port not re-assigned to another server
    - `test_port_range_exhaustion` — more configs than range raises ConfigurationError
    - `test_valid_and_invalid_mixed` — valid configs loaded, invalid ones skipped with log
  - [x] Create `tests/mothership/test_config.py` with tests for `MothershipConfig` validation
  - [x] Run `PYTHONPATH="" poetry run pytest tests/mothership/ -v`
- [x] Task 6: Run full regression (AC: #5)
  - [x] Run `PYTHONPATH="" poetry run pytest -v` to verify zero regressions

## Dev Notes

### Architecture Compliance

- **Config format:** YAML with fields defined in architecture doc. Use pydantic for validation — NOT manual dict parsing.
- **Scan pattern:** `servers/*/mothership.yaml` — glob from the project root `servers/` directory. Do NOT recursively scan nested directories.
- **Port range:** Default 8100-8199 (100 ports). Architecture spec says configurable range.
- **Error handling:** Use `ConfigurationError` from `shared/errors.py` for validation failures. Log with `logging.getLogger(__name__)`.
- **Rescan support:** The `discover_servers()` function must be callable multiple times (for `POST /api/rescan` in Story 6.1). No caching or stale state.
- **Import boundary:** `mothership/discovery.py` imports from `shared/` only. It never imports from `servers/`.

### MothershipConfig (Manager Config)

The architecture specifies a `MothershipConfig` in `mothership/config.py`. This is the manager's own config (dashboard port, log dir, port range) — separate from per-MCP server configs (`mothership.yaml`). Create it now as it's needed for port range configuration.

```python
# mothership/config.py
from shared.config import BaseServerConfig

class MothershipConfig(BaseServerConfig):
    port: int = 8080                    # Dashboard/API port
    log_dir: str = "./logs"             # Log file directory
    port_range_start: int = 8100        # Auto-assign range start
    port_range_end: int = 8199          # Auto-assign range end
    log_max_bytes: int = 5_242_880      # 5MB per log file
    log_backup_count: int = 3           # Rotated backup count
```

Loads from `.env` (env vars prefixed with nothing — pydantic uppercases field names) and `config.yaml` top-level keys. Uses the same dual-layer loading as `BaseServerConfig`.

### Project Structure After This Story

```
mothership/
  __init__.py          # From Story 4.1
  __main__.py          # From Story 4.1
  config.py            # NEW — MothershipConfig
  discovery.py         # NEW — discover_servers(), McpServerConfig

servers/imagen/
  mothership.yaml      # NEW — Imagen registration config

tests/mothership/
  __init__.py          # NEW
  test_discovery.py    # NEW
  test_config.py       # NEW
```

### Files to Create

```
mothership/config.py                    # MothershipConfig pydantic model
mothership/discovery.py                 # McpServerConfig model + discover_servers()
servers/imagen/mothership.yaml          # Imagen registration config
tests/mothership/__init__.py            # Test package init
tests/mothership/test_discovery.py      # Discovery tests
tests/mothership/test_config.py         # MothershipConfig tests
```

### Dependencies on Story 4.1

- `shared/errors.py` must have `MothershipError` base class and `ConfigurationError`
- `shared/config.py` must have `BaseServerConfig` (unchanged)
- `mothership/__init__.py` and `mothership/__main__.py` must exist

### Anti-Patterns to Avoid

- Do NOT hardcode the servers directory path — accept it as a parameter to `discover_servers()`
- Do NOT import from `servers/` — discovery reads YAML files, never imports server code
- Do NOT cache discovery results — the function must be stateless for rescan support
- Do NOT validate that `entry_point` is importable — that's the manager's job at start time
- Do NOT check env vars exist — that's the server's job when it starts (each server reads `.env` directly)
- Do NOT create a custom YAML loader — use `yaml.safe_load()`

### Previous Story Learnings

- Run tests with `PYTHONPATH=""` to avoid ROS plugin conflicts
- Use `tmp_path` fixture for test isolation when creating temp config files
- pydantic validation errors are detailed — leverage them for clear error messages

### References

- [Source: documents/planning-artifacts/architecture-mothership.md#Config Discovery & Registration]
- [Source: documents/planning-artifacts/architecture-mothership.md#Configuration Patterns]
- [Source: documents/planning-artifacts/architecture-mothership.md#Structure Patterns]
- [Source: documents/planning-artifacts/epics.md#Story 4.2: Config Discovery & Registration]
- [Source: documents/planning-artifacts/prd.md#MCP Registration & Discovery — FR6-FR9]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- 2 pre-existing test failures in `tests/imagen/test_config.py` (environment API key leaking into test isolation) — not caused by this story

### Completion Notes List

- Created `McpServerConfig` pydantic model with name, description, entry_point, port, env_vars fields
- Implemented `discover_servers()` scanning `servers/*/mothership.yaml` with error handling (malformed/invalid configs logged and skipped)
- Implemented port auto-assignment from configurable range (default 8100-8199), skipping claimed ports, raising ConfigurationError on exhaustion
- Created `MothershipConfig` extending `BaseServerConfig` with dashboard port, log dir, port range, log rotation settings
- Created `servers/imagen/mothership.yaml` with explicit port 8101
- 18 new tests: 5 model validation, 9 discovery/scanning/port, 4 MothershipConfig

### Change Log

- 2026-04-07: Story 4.2 implementation complete — config discovery, validation, port auto-assignment, MothershipConfig

### File List

- `mothership/discovery.py` — new (McpServerConfig model + discover_servers function)
- `mothership/config.py` — new (MothershipConfig extending BaseServerConfig)
- `servers/imagen/mothership.yaml` — new (Imagen server registration config)
- `tests/mothership/__init__.py` — new (test package init)
- `tests/mothership/test_discovery.py` — new (14 discovery tests)
- `tests/mothership/test_config.py` — new (4 MothershipConfig tests)
