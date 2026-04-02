# Story 1.2: Shared Configuration & Error Handling

Status: done

## Story

As a developer,
I want a validated configuration system and consistent error handling,
so that any MCP server I build has reliable config loading and credential-safe error reporting.

## Acceptance Criteria

1. **Given** a `shared/config.py` module with `BaseServerConfig` using pydantic-settings **When** a server starts up with valid `.env` and `config.yaml` **Then** configuration is loaded and validated with typed fields **And** missing or invalid settings produce clear error messages naming the missing field
2. **Given** a `shared/errors.py` module with the error hierarchy **When** an API is unavailable **Then** an `ApiUnavailableError` is raised with a clear message **And** credential values are never included in error messages
3. **Given** missing or invalid credentials in `.env` **When** the server starts or attempts an API call **Then** a `CredentialError` is raised with a clear message identifying the missing credential name **And** the actual credential value is never logged or echoed
4. **Given** a `shared/logging.py` module **When** any module initializes logging **Then** log output goes to stderr only (stdout reserved for MCP stdio) **And** log level is configurable via `config.yaml`
5. **Given** `tests/shared/` with test files **When** I run `poetry run pytest tests/shared/` **Then** all config validation, error hierarchy, and logging tests pass

## Tasks / Subtasks

- [x] Task 1: Implement `shared/errors.py` — error class hierarchy (AC: #2, #3)
  - [x] Create `EngagementManagerError(Exception)` base class
  - [x] Create `ConfigurationError(EngagementManagerError)`
  - [x] Create `ApiUnavailableError(EngagementManagerError)`
  - [x] Create `CredentialError(EngagementManagerError)` — must enforce no credential values in message
  - [x] Create `GenerationError(EngagementManagerError)`
- [x] Task 2: Implement `shared/config.py` — base config with pydantic-settings (AC: #1)
  - [x] Create `BaseServerConfig` using pydantic-settings `BaseSettings`
  - [x] Load secrets from `.env` via pydantic-settings env var support
  - [x] Load operational settings from `config.yaml` via PyYAML
  - [x] Merge both sources into a single validated config object
  - [x] Produce clear validation errors naming the specific missing/invalid field
- [x] Task 3: Implement `shared/logging.py` — stderr logging setup (AC: #4)
  - [x] Create `setup_logging(log_level: str)` function
  - [x] Configure Python stdlib `logging` to output to stderr only
  - [x] Accept log level from config.yaml value
  - [x] Use `logging.getLogger(__name__)` pattern per module
- [x] Task 4: Write tests in `tests/shared/` (AC: #5)
  - [x] `tests/shared/test_errors.py` — verify hierarchy, credential safety
  - [x] `tests/shared/test_config.py` — verify validation, missing field errors, dual-source loading
  - [x] `tests/shared/test_logging.py` — verify stderr output, log level config
- [x] Task 5: Run `poetry run pytest tests/shared/` and verify all tests pass (AC: #5)

## Dev Notes

### Architecture Compliance

This story implements the three shared modules that ALL future MCP servers depend on. Get these patterns right — every server inherits from them.

### Error Handling Pattern — EXACT Specification

From architecture.md, the error class hierarchy:

```python
class EngagementManagerError(Exception):
    """Base error — all project errors inherit from this."""

class ConfigurationError(EngagementManagerError):
    """Missing or invalid configuration."""

class ApiUnavailableError(EngagementManagerError):
    """External API is unreachable or returning errors."""

class CredentialError(EngagementManagerError):
    """Authentication/authorization failure (never includes credential values)."""

class GenerationError(EngagementManagerError):
    """Content generation failed (bad input, quota, model error)."""
```

**Credential safety is a hard requirement (NFR1-NFR3).** The `CredentialError` class must enforce that credential values cannot appear in error messages. Consider a pattern where the error accepts a credential *name* (e.g., "IMAGEN_API_KEY") but never the *value*.

**Error flow:**
1. Tool code raises typed exception from `shared/errors.py`
2. Server catches and converts to MCP error response
3. Error message is always credential-safe

### Configuration Pattern — EXACT Specification

From architecture.md, the per-server config model pattern:

```python
# shared/config.py — Base
from pydantic_settings import BaseSettings

class BaseServerConfig(BaseSettings):
    log_level: str = "INFO"
    # Common fields all servers need

# servers/imagen/config.py — Server-specific (Story 2.1, NOT this story)
from shared.config import BaseServerConfig

class ImagenConfig(BaseServerConfig):
    gcp_project: str
    gcp_region: str = "us-central1"
    imagen_model: str = "imagen-3.0-generate-002"
    default_width: int = 1024
    default_height: int = 1024
```

**Dual-layer config loading:**
- `.env` → pydantic-settings loads env vars automatically (secrets)
- `config.yaml` → parse with PyYAML, pass values to pydantic model (operational settings)
- pydantic-settings handles validation and type coercion for both sources

**Env var naming:** Flat with server-name prefix: `IMAGEN_GCP_PROJECT`, `IMAGEN_API_KEY`.

### Logging Pattern — EXACT Specification

- Python stdlib `logging` module — no third-party logging libraries
- Output to **stderr only** — stdout is reserved for MCP stdio protocol
- Log level configurable via `config.yaml` `log_level` field
- Each module uses: `logger = logging.getLogger(__name__)`
- **Never log credential values** — this is a hard security requirement

### Naming Conventions (PEP 8)

- Functions/variables: `snake_case` (e.g., `setup_logging`, `log_level`)
- Classes: `PascalCase` (e.g., `BaseServerConfig`, `CredentialError`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_LOG_LEVEL`)
- Files: `snake_case.py`

### Testing Standards

- Framework: `pytest` with `unittest.mock`
- Tests mirror source: `tests/shared/test_errors.py`, `tests/shared/test_config.py`, `tests/shared/test_logging.py`
- Mock external dependencies (file system for config loading)
- Test cases must cover:
  - Valid config loading from both `.env` and `config.yaml`
  - Missing required field produces clear error with field name
  - Invalid field type produces clear validation error
  - Error hierarchy: each error class is instance of its parent
  - CredentialError never exposes credential values
  - Logging goes to stderr, not stdout
  - Log level is configurable

### Anti-Patterns to Avoid

- Do NOT create `servers/imagen/config.py` — that's Story 2.1
- Do NOT create `servers/imagen/server.py` — that's Story 2.1
- Do NOT use `print()` — use `logging` to stderr
- Do NOT raise bare `Exception` — always use typed exceptions from `shared/errors.py`
- Do NOT hardcode config values — everything from `.env` or `config.yaml`
- Do NOT create utility modules outside `shared/` — all shared code in one place
- Do NOT add structured logging libraries (structlog, etc.) — stdlib logging is sufficient

### Dependency on Story 1.1

This story assumes the Poetry project and directory structure from Story 1.1 are in place. `shared/` and `tests/shared/` directories with `__init__.py` files must exist.

### Project Structure Notes

Files created/modified in this story:

```
shared/
├── __init__.py          # Already exists from 1.1
├── errors.py            # NEW — error class hierarchy
├── config.py            # NEW — BaseServerConfig with pydantic-settings
└── logging.py           # NEW — stderr logging setup

tests/shared/
├── __init__.py          # Already exists from 1.1
├── test_errors.py       # NEW — error hierarchy tests
├── test_config.py       # NEW — config validation tests
└── test_logging.py      # NEW — logging setup tests
```

### References

- [Source: documents/planning-artifacts/architecture.md#Error Handling Patterns — Error Class Hierarchy]
- [Source: documents/planning-artifacts/architecture.md#Configuration Patterns — Per-Server Config Model]
- [Source: documents/planning-artifacts/architecture.md#Logging Patterns]
- [Source: documents/planning-artifacts/architecture.md#Core Architectural Decisions]
- [Source: documents/planning-artifacts/epics.md#Story 1.2: Shared Configuration & Error Handling]
- [Source: documents/planning-artifacts/prd.md#Non-Functional Requirements — NFR1-NFR3 Security]
- [Source: documents/planning-artifacts/prd.md#Functional Requirements — FR9 Startup Validation, FR10-FR11 Error Reporting]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- Initial `from_yaml` passed YAML values as init kwargs, which gave them highest priority over env vars in pydantic-settings. Fixed by implementing a custom `YamlSettingsSource` so priority is: init > env > .env > yaml > defaults.

### Completion Notes List

- Implemented `shared/errors.py` with full error hierarchy: EngagementManagerError (base), ConfigurationError, ApiUnavailableError, CredentialError (credential-safe by design — accepts name only, never value), GenerationError
- Implemented `shared/config.py` with `BaseServerConfig(BaseSettings)` using pydantic-settings, custom `YamlSettingsSource` for dual-layer loading, and `from_yaml()` class method
- Config priority chain: init kwargs > env vars > .env file > config.yaml > defaults
- Implemented `shared/logging.py` with `setup_logging()` — stderr-only output, configurable log level, duplicate handler prevention
- 36 tests covering: error hierarchy (5), credential safety (4), error messages (4), YAML loading (5), config validation (8), logging behavior (10)
- Full regression suite: 58 tests passing (36 new + 22 from story 1.1)

### Change Log

- 2026-03-30: Implemented shared configuration, error handling, and logging modules — all 5 tasks completed, 36 tests passing

### File List

- shared/errors.py (new)
- shared/config.py (new)
- shared/logging.py (new)
- tests/shared/test_errors.py (new)
- tests/shared/test_config.py (new)
- tests/shared/test_logging.py (new)
