---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
lastStep: 8
status: 'complete'
completedAt: '2026-04-07'
inputDocuments: ['documents/planning-artifacts/prd.md', 'documents/planning-artifacts/mcp-capability-platform-brainstorm.md', 'documents/planning-artifacts/architecture.md', 'documents/planning-artifacts/product-brief-engagement-manager.md']
workflowType: 'architecture'
project_name: 'MCP Mothership'
user_name: 'Kamal'
date: '2026-04-07'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
33 FRs across 8 categories. The lifecycle management category (FR1-FR5) defines the subprocess manager core: start, stop, crash detection, clean shutdown, and single CLI entry. Registration & discovery (FR6-FR10) establishes a convention-based YAML config pattern where new MCPs are added by dropping a file. Network transport (FR11-FR13) moves all MCP servers to SSE/HTTP with per-server ports and multi-agent connectivity. Dashboard (FR14-FR20) introduces a web UI for server list, start/stop controls, real-time status, metrics display, and per-server log viewing. Logging (FR21-FR24) requires per-MCP isolated log files with rotation. Metrics (FR25-FR28) track request count, error count, last request, and uptime in-memory. Imagen migration (FR29-FR31) brings the existing server into the new transport model. Project migration (FR32-FR33) rebrands to MCP Mothership.

**Non-Functional Requirements:**
15 NFRs across 4 categories. Reliability (NFR1-NFR4) mandates process isolation (crash in one server doesn't affect others), 5-second crash detection, clean shutdown with no orphans, and dashboard resilience independent of server state. Security (NFR5-NFR8) carries forward the credential safety pattern: `.env` only, gitignored, never in logs or error messages. Performance (NFR9-NFR12) sets dashboard load time at 3s, action initiation at 1s, status update latency at 5s, and 10+ server scalability. Integration (NFR13-NFR15) requires full MCP protocol compliance, standard client compatibility, and identical test coverage after transport migration.

**Scale & Complexity:**

- Primary domain: Developer infrastructure — process manager with web dashboard
- Complexity level: Medium
- Estimated architectural components: 6 (manager process, subprocess handler, web dashboard, config discovery, logging system, metrics collector)

### Technical Constraints & Dependencies

- **Python >=3.10**, development target 3.12 — pure Python, no compiled extensions
- **Poetry** for dependency management — consistent with existing codebase
- **MCP SDK** (`mcp` package with FastMCP) — servers use `@mcp.tool()` decorators
- **SSE/HTTP transport** — each managed MCP server exposed on its own network port
- **Single CLI entry point** — `python -m mothership` or Poetry script starts everything
- **Single-user local operation** — no auth, no multi-user, no distribution in MVP
- **Brownfield** — existing `shared/` modules (config, errors, logging), Imagen server, and Nano Banana Pro migration code must be retained and evolved
- **pydantic-settings** for configuration validation — established pattern from existing architecture

### Cross-Cutting Concerns Identified

- **Credential flow** — `.env` values must propagate to child MCP server processes without appear in YAML configs, logs, or error messages
- **Per-server logging** — each MCP server and the manager itself write to isolated log files; dashboard reads these for display
- **Config validation** — manager config and per-MCP configs both validated at startup using pydantic-settings
- **Process health monitoring** — consistent state tracking (PID, status, start time, metrics) for every managed subprocess
- **Error reporting** — credential-safe error messages across manager, dashboard, and all MCP servers, using the existing shared error hierarchy
- **Port management** — config-specified or auto-assigned ports for each MCP server, avoiding conflicts

## Starter Template Evaluation

### Primary Technology Domain

Python process manager with web dashboard — infrastructure tooling for MCP server lifecycle management.

### Starter Options Considered

**1. FastMCP Composition (mount/proxy)** — FastMCP 2.x supports `mcp.mount()` to compose multiple servers into a single process behind one endpoint. Reduces operational complexity. However, this violates NFR1 (process isolation — one crash must not affect others) and removes the ability to independently start/stop individual MCP servers. Rejected for MVP; could be offered as an alternative mode post-MVP for simpler deployments.

**2. Orchestrator-MCP (community)** — Open-source MCP orchestrator focused on AI workflow automation. Solves a different problem (task orchestration, not process management with operational visibility). Not applicable.

**3. Custom project structure** — Evolve the existing brownfield codebase. Add manager process, subprocess handling, web dashboard, and config discovery on top of established patterns (Poetry, `shared/` modules, pydantic-settings, typed errors). No starter template addresses this combination of requirements.

### Selected Starter: Custom Project Structure (Evolved)

**Rationale for Selection:**
This is a brownfield project with established Python patterns. The new capabilities (process management, web dashboard, network transport) are standard library and lightweight framework territory — not something a starter template provides. Evolving the existing structure avoids fighting a template's assumptions while preserving working code.

**Transport Decision: Streamable HTTP (not SSE)**
SSE was deprecated in the June 2025 MCP spec revision. All managed MCP servers will use Streamable HTTP transport via FastMCP's built-in `transport="streamable-http"` support. This is the current standard for network-accessible MCP servers.

**Dashboard Decision: FastAPI + lightweight HTML/JS**
The manager process serves both the dashboard web UI and its own management API on a single port. FastAPI provides the REST endpoints for start/stop/status/logs; a simple HTML+JS frontend renders the dashboard. This avoids adding Streamlit as a heavy dependency and fits the "single CLI command starts everything" requirement naturally.

**Architectural Decisions Provided by Structure:**

**Language & Runtime:**
Python >=3.10 (MCP SDK requirement), development target 3.12. Pure Python, no compiled extensions.

**MCP SDK:**
FastMCP 2.x (bundled in `mcp` package). Servers use `@mcp.tool()` decorators with Streamable HTTP transport.

**Dependency Management:**
Poetry with `pyproject.toml` — consistent with existing codebase.

**Configuration:**
`pydantic-settings` for `.env` credential loading and `config.yaml` settings validation. Per-MCP registration via YAML config files (`mothership.yaml` per server).

**Web Framework:**
FastAPI for dashboard API + static file serving. Single port for manager + dashboard.

**Process Management:**
Python `asyncio.subprocess` for spawning and monitoring MCP server child processes.

**Testing:**
pytest + unittest.mock — consistent with existing patterns.

**Code Organization:**
Monorepo with `servers/` for MCP servers, `shared/` for common modules, `mothership/` for the manager+dashboard application.

**Note:** Project rename and directory restructuring should be the first implementation story.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Process management architecture (subprocess spawning, health monitoring, credential flow)
- Network transport (Streamable HTTP for all MCP servers)
- Dashboard architecture (FastAPI + vanilla JS, polling, REST API)
- Config discovery (YAML per server, scan + rescan)

**Important Decisions (Shape Architecture):**
- Port assignment strategy (explicit or auto-assign from range)
- Logging architecture (per-server RotatingFileHandler)
- Metrics exposure (per-server `/metrics` endpoint)

**Deferred Decisions (Post-MVP):**
- CI/CD pipeline
- Dashboard authentication
- Auto-restart on crash
- Remote access (Tailscale/VPN)

### Process Management Architecture

- **Decision:** Manager uses `asyncio.create_subprocess_exec` to spawn each MCP server as an independent child process running its Python module
- **Health Monitoring:** Periodic asyncio loop polls `process.returncode` at ≤5-second intervals to detect crashes (satisfies NFR2)
- **Clean Shutdown:** Manager sends SIGTERM to all child processes on exit, with a grace period before SIGKILL (satisfies NFR3)
- **Credential Flow:** Each child process reads `.env` directly via pydantic-settings — no credential proxying through the manager
- **State Tracking:** Manager maintains in-memory dict per server: PID, status (running/stopped/crashed), start time, last exit code, stderr capture on crash
- **Rationale:** Simplest approach that satisfies all reliability NFRs. Direct subprocess management avoids external dependencies. Each process is fully isolated — a crash in one has zero effect on others or the manager.
- **Affects:** All managed MCP servers, manager core

### Network Transport

- **Decision:** All managed MCP servers use Streamable HTTP transport via FastMCP's `transport="streamable-http"`
- **SSE Status:** Deprecated in June 2025 MCP spec revision — not used
- **Port Assignment:** Each server gets a port from its `mothership.yaml` config, or auto-assigned from a configurable range (default 8100-8199) if omitted
- **Multi-client:** Streamable HTTP natively supports multiple simultaneous agent connections per server (satisfies FR12)
- **Rationale:** Streamable HTTP is the current MCP standard for network-accessible servers. FastMCP handles the transport layer — servers just set the transport parameter.
- **Affects:** All MCP servers, agent connectivity

### Dashboard Architecture

- **Decision:** FastAPI serves both the REST API and a single static HTML+JS dashboard file on one port
- **Real-time Updates:** Frontend polls `GET /api/servers` on a 3-5 second interval for status/metrics refresh
- **Log Viewing:** `GET /api/servers/{name}/logs?lines=100` returns tail of the server's log file; frontend polls for updates
- **No Build Step:** Vanilla HTML+JS, served as a static file. No frontend framework, no bundler, no node_modules.
- **Rationale:** Single-user tool needs a functional dashboard, not a frontend engineering project. Polling at 3-5s satisfies NFR11 (5-second status update latency). One port for everything satisfies FR5 (single CLI command starts the system).
- **Affects:** Manager process, dashboard UI

### REST API Design

- **Decision:** Resource-based REST API served by FastAPI

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/servers` | GET | List all servers with status and metrics |
| `/api/servers/{name}/start` | POST | Start a server |
| `/api/servers/{name}/stop` | POST | Stop a server |
| `/api/servers/{name}/logs` | GET | Tail server log file (query: `lines`) |
| `/api/rescan` | POST | Rescan config directory for new/changed MCP configs |

- **Rationale:** Minimal API surface that covers all dashboard operations. RESTful and predictable.
- **Affects:** Dashboard frontend, manager process

### Config Discovery & Registration

- **Decision:** Manager scans `servers/*/mothership.yaml` at startup and on `POST /api/rescan`
- **Config Format:** YAML with fields: `name`, `description`, `entry_point`, `port` (optional), `env_vars` (list of required env var names)
- **Validation:** pydantic model validates each config on discovery; malformed configs reported as errors in manager log and dashboard (satisfies FR9)
- **New Server Flow:** Drop `mothership.yaml` in `servers/<name>/`, hit rescan in dashboard, server appears in list
- **Rationale:** Convention-based registration matches Journey 2 in PRD. Rescan avoids requiring a manager restart for new configs.
- **Affects:** Manager config discovery, dashboard server list

### Metrics Collection

- **Decision:** Each MCP server exposes a `/metrics` endpoint returning JSON (request count, error count, last request timestamp). Manager polls this endpoint alongside health checks.
- **Storage:** In-memory only — no persistent metrics store for MVP
- **Uptime:** Calculated by manager from process start time (not reported by server)
- **Rationale:** Keeps metrics ownership with the server that generates them. Manager only needs to poll one endpoint per server for both health and metrics.
- **Affects:** All MCP servers (must implement `/metrics`), manager polling loop

### Logging Architecture

- **Decision:** Python stdlib `logging` with `RotatingFileHandler` per server. Each MCP server logs to `logs/<server_name>.log`. Manager logs to `logs/mothership.log`.
- **Rotation:** Size-based rotation (configurable, default 5MB, 3 backups)
- **Log Level:** Configurable per-server in `config.yaml`, default INFO
- **Credential Safety:** Inherited from shared error hierarchy — never log credential values
- **Rationale:** Evolution of existing logging pattern. Per-file isolation enables the dashboard log viewer.
- **Affects:** All MCP servers, manager, dashboard log viewer

### Infrastructure & Deployment

- **Decision:** No deployment infrastructure — runs directly from cloned repo via `python -m mothership` or Poetry script
- **CI/CD:** Deferred post-MVP
- **Rationale:** Personal utility tool with no distribution requirements.

### Security

- **Decision:** Carried forward from existing architecture with no changes for MVP
- **Credentials:** `.env` only, gitignored, never in YAML configs, logs, or error messages
- **Dashboard Auth:** None for MVP (single-user, localhost). Phase 2 adds basic auth.
- **Rationale:** Single-user local tool. Auth adds complexity with no MVP value.

### Decision Impact Analysis

**Implementation Sequence:**
1. Project rename and directory restructuring
2. Manager core (subprocess spawning, health monitoring, clean shutdown)
3. Config discovery (YAML scanning, validation, rescan)
4. Imagen server transport migration (stdio → Streamable HTTP, add `/metrics` endpoint)
5. Dashboard API (FastAPI REST endpoints)
6. Dashboard UI (static HTML+JS)
7. Logging architecture (per-server files, rotation)
8. Integration testing (end-to-end: manager → start server → agent connects → dashboard shows status)

**Cross-Component Dependencies:**
- Dashboard depends on manager API, which depends on process management core
- MCP servers must implement `/metrics` endpoint for manager polling
- Config discovery feeds the server list to both manager and dashboard
- Logging must be set up before servers start so log files exist for dashboard viewing

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:**
6 areas where AI agents could make different choices — code naming, project structure, API response formats, MCP tool shape, configuration models, and error/logging flow.

### Naming Patterns

**Code Naming Conventions (PEP 8):**
- Functions and variables: `snake_case` — e.g., `start_server`, `server_name`
- Classes: `PascalCase` — e.g., `ServerManager`, `ImagenConfig`, `MothershipConfig`
- Constants: `UPPER_SNAKE_CASE` — e.g., `DEFAULT_PORT_RANGE_START`, `MAX_LOG_SIZE`
- Files and modules: `snake_case.py` — e.g., `server_manager.py`, `config.py`
- Private members: `_leading_underscore` — e.g., `_poll_health`, `_sessions`

**API Naming Conventions:**
- REST endpoints: lowercase, plural nouns — `/api/servers`, `/api/servers/{name}/logs`
- URL parameters: `snake_case` — e.g., `{server_name}`
- Query parameters: `snake_case` — e.g., `?lines=100`
- JSON response fields: `snake_case` — e.g., `request_count`, `last_request_time`

**Environment Variable Naming:**
- Flat with component prefix: `IMAGEN_GCP_PROJECT`, `MOTHERSHIP_PORT`, `MOTHERSHIP_LOG_DIR`
- Boolean env vars: `MOTHERSHIP_DEBUG=true` (lowercase string)

**Config File Naming:**
- Per-MCP registration: `mothership.yaml` inside each `servers/<name>/` directory
- Manager config: `config.yaml` at project root

### Structure Patterns

**Project Organization:**
- MCP servers: `servers/<server_name>/` with `__init__.py`, `server.py`, `config.py`, `mothership.yaml`
- Manager application: `mothership/` with `__init__.py`, `__main__.py`, `manager.py`, `api.py`, `config.py`
- Dashboard frontend: `mothership/static/index.html` (single file)
- Shared modules: `shared/` — `errors.py`, `logging_config.py`, `config.py` (base classes)
- Tests mirror source: `tests/mothership/`, `tests/servers/imagen/`, `tests/shared/`
- Logs directory: `logs/` (gitignored)

**Adding a New MCP Server:**
1. Create `servers/<name>/` with `__init__.py`, `server.py`, `config.py`
2. Define a pydantic settings model in `config.py` inheriting shared base
3. Register tools with `@mcp.tool()` decorators in `server.py`
4. Add `mothership.yaml` with name, description, entry_point, optional port, env_vars
5. Add server-specific env vars to `.env`
6. Implement `/metrics` endpoint in `server.py`
7. Add tests in `tests/servers/<name>/`

### MCP Tool Patterns

**Tool Definition Shape:**
```python
@mcp.tool()
async def generate_image(
    prompt: str,
    session_id: str | None = None,
    width: int = 1024,
    height: int = 1024,
    output_path: str | None = None,
) -> str:
    """Generate or refine an image from a text prompt.

    Args:
        prompt: Text description or refinement instruction.
        session_id: Existing session ID for iterative refinement.
        width: Image width in pixels.
        height: Image height in pixels.
        output_path: Custom file path for the generated image.
    """
```

**Tool Docstrings:** Imperative mood, one-line summary, Args section. These are what Claude reads — clarity matters.

**Tool Return Values:** Tool-specific — return whatever makes sense. No forced wrapper.

### API Response Patterns

**Dashboard REST API responses:**
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

**Date/Time:** ISO 8601 strings in all API responses.

### Metrics Endpoint Pattern

**Every MCP server must expose:**
```python
@app.get("/metrics")
async def metrics():
    return {
        "request_count": _request_count,
        "error_count": _error_count,
        "last_request_time": _last_request_time,  # ISO 8601 or null
    }
```

Tracked via a lightweight middleware or decorator that increments counters on each tool invocation.

### Error Handling Patterns

**Error Class Hierarchy (evolved):**
```python
class MothershipError(Exception):
    """Base error — all project errors inherit from this."""

class ConfigurationError(MothershipError):
    """Missing or invalid configuration."""

class ApiUnavailableError(MothershipError):
    """External API is unreachable or returning errors."""

class CredentialError(MothershipError):
    """Authentication/authorization failure (never includes credential values)."""

class GenerationError(MothershipError):
    """Content generation failed (bad input, quota, model error)."""

class ServerLifecycleError(MothershipError):
    """MCP server failed to start, stop, or encountered a lifecycle issue."""
```

**Note:** Base class renamed from `EngagementManagerError` to `MothershipError`. New `ServerLifecycleError` added for manager operations.

**Error Flow — MCP Servers:**
1. Tool code raises typed exception from `shared/errors.py`
2. Server catches and converts to MCP error response
3. Error message is always credential-safe

**Error Flow — Manager/Dashboard:**
1. Manager operations raise `ServerLifecycleError` or `ConfigurationError`
2. API endpoint catches and returns `{"ok": false, "error": "..."}` with appropriate HTTP status
3. Dashboard displays the error message

### Logging Patterns

- Each module: `logger = logging.getLogger(__name__)`
- MCP servers: log to `logs/<server_name>.log` via `RotatingFileHandler`
- Manager: log to `logs/mothership.log` via `RotatingFileHandler`
- Console output: stderr only for startup messages
- Never log credential values
- Log format: `%(asctime)s %(levelname)s %(name)s %(message)s`

### Configuration Patterns

**Manager Config (`mothership/config.py`):**
```python
class MothershipConfig(BaseSettings):
    port: int = 8080
    log_dir: str = "./logs"
    port_range_start: int = 8100
    port_range_end: int = 8199
    log_max_bytes: int = 5_242_880  # 5MB
    log_backup_count: int = 3
```

**Per-Server Config (inherits shared base):**
```python
class ImagenConfig(BaseServerConfig):
    imagen_gcp_project: str
    imagen_gcp_region: str = "us-central1"
    imagen_model: str = "gemini-3-pro-image-preview"
    default_output_dir: str = "./output"
```

**MCP Registration Config (`mothership.yaml`):**
```yaml
name: imagen
description: "Image generation via Vertex AI Nano Banana Pro"
entry_point: servers.imagen.server
port: 8101
env_vars:
  - IMAGEN_GCP_PROJECT
  - IMAGEN_GCP_REGION
```

### Enforcement Guidelines

**All AI Agents MUST:**
- Follow PEP 8 naming conventions without exception
- Place new MCP servers in `servers/<name>/` following the established structure
- Include a `mothership.yaml` in every new MCP server directory
- Implement a `/metrics` endpoint in every MCP server
- Use typed exceptions from `shared/errors.py` — never raise bare `Exception`
- Validate config at startup using pydantic-settings models
- Write tests in `tests/` mirroring the source structure
- Never log or surface credential values in errors or output
- Use `snake_case` for all JSON response fields
- Return ISO 8601 for all datetime values in APIs

**Anti-Patterns to Avoid:**
- Creating utility modules outside `shared/` — all shared code goes in one place
- Defining error classes inside individual servers — use `shared/errors.py`
- Using `print()` for output — use `logging` to file
- Hardcoding config values — everything comes from `.env`, `config.yaml`, or `mothership.yaml`
- Using SSE transport — use Streamable HTTP
- Adding frontend build tools — the dashboard is a single vanilla HTML+JS file
- Proxying credentials through the manager — each server reads `.env` directly

## Project Structure & Boundaries

### Complete Project Directory Structure

```
mcp-mothership/
├── pyproject.toml                          # Poetry project config, dependencies
├── poetry.lock                             # Locked dependency versions
├── .env                                    # Secrets only (gitignored)
├── .env.example                            # Template showing required env vars
├── config.yaml                             # Manager + shared operational settings
├── .gitignore
├── README.md
│
├── mothership/                             # Manager application
│   ├── __init__.py
│   ├── __main__.py                         # Entry point: python -m mothership
│   ├── config.py                           # MothershipConfig (pydantic-settings)
│   ├── manager.py                          # Process manager: spawn, monitor, stop
│   ├── discovery.py                        # Config scanner: find/validate mothership.yaml files
│   ├── api.py                              # FastAPI app: REST endpoints + static file serving
│   └── static/
│       └── index.html                      # Dashboard UI (single vanilla HTML+JS file)
│
├── servers/
│   └── imagen/
│       ├── __init__.py
│       ├── server.py                       # FastMCP server, tool definitions, /metrics endpoint
│       ├── config.py                       # ImagenConfig (pydantic-settings)
│       └── mothership.yaml                 # MCP registration config
│
├── shared/
│   ├── __init__.py
│   ├── errors.py                           # MothershipError hierarchy
│   ├── config.py                           # BaseServerConfig, config loading utilities
│   └── logging_config.py                   # RotatingFileHandler setup, log format
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                         # Shared pytest fixtures
│   ├── mothership/
│   │   ├── __init__.py
│   │   ├── test_manager.py                 # Process spawning, health monitoring, shutdown
│   │   ├── test_discovery.py               # Config scanning, validation, rescan
│   │   ├── test_api.py                     # REST endpoint tests
│   │   └── test_config.py                  # MothershipConfig validation
│   ├── servers/
│   │   └── imagen/
│   │       ├── __init__.py
│   │       ├── test_server.py              # Tool function tests, session management
│   │       └── test_config.py              # ImagenConfig validation
│   └── shared/
│       ├── __init__.py
│       ├── test_errors.py                  # Error hierarchy tests
│       └── test_config.py                  # BaseServerConfig tests
│
├── logs/                                   # Runtime log files (gitignored)
│   ├── mothership.log                      # Manager log
│   └── imagen.log                          # Per-server logs (created at runtime)
│
├── _bmad/                                  # BMad project config
│   ├── core/
│   └── bmm/
│
├── .claude/
│   └── skills/                             # Claude Code skills (markdown)
│
└── documents/
    ├── planning-artifacts/                 # Architecture, PRD, briefs
    └── implementation-artifacts/           # Sprint plans, stories
```

### Architectural Boundaries

**Manager Boundary:**
The `mothership/` package is the orchestration layer. It spawns and monitors MCP server processes but never imports from `servers/`. It communicates with running servers only via HTTP (polling `/metrics` endpoints). It serves the dashboard API and static UI.

**MCP Server Boundary:**
Each server in `servers/<name>/` is a standalone Streamable HTTP process. Servers never import from other servers or from `mothership/`. They only import from `shared/`. Each server is independently startable: `python -m servers.imagen.server`.

**Shared Module Boundary:**
`shared/` provides base classes and utilities only. It never imports from `servers/` or `mothership/`. No business logic lives here — just infrastructure patterns (config base, error hierarchy, logging setup).

**Dashboard Boundary:**
`mothership/static/index.html` is a pure client. It communicates exclusively via the REST API (`/api/*`). No server-side rendering, no template engine. The manager serves it as a static file.

### Requirements to Structure Mapping

| Requirement | Location |
|---|---|
| FR1-FR2 (Start/Stop servers) | `mothership/manager.py`, `mothership/api.py` |
| FR3 (Crash detection) | `mothership/manager.py` (health poll loop) |
| FR4 (Clean shutdown) | `mothership/manager.py` (SIGTERM handler) |
| FR5 (Single CLI command) | `mothership/__main__.py` |
| FR6-FR9 (Config discovery/validation) | `mothership/discovery.py` |
| FR10 (Tool discovery via MCP) | `servers/*/server.py` (native MCP `tools/list`) |
| FR11-FR13 (Network transport, ports) | `servers/*/server.py` + `mothership/manager.py` |
| FR14-FR17 (Dashboard server list/metrics) | `mothership/api.py` + `mothership/static/index.html` |
| FR18-FR20 (Dashboard log viewing) | `mothership/api.py` (log tail endpoint) + `mothership/static/index.html` |
| FR21-FR24 (Logging system) | `shared/logging_config.py` + per-server setup |
| FR25-FR28 (Metrics tracking) | `servers/*/server.py` (`/metrics` endpoint) + `mothership/manager.py` (polling) |
| FR29-FR31 (Imagen migration) | `servers/imagen/server.py` (transport change) |
| FR32-FR33 (Project rename) | `pyproject.toml`, all module references |
| NFR1-NFR4 (Reliability) | `mothership/manager.py` |
| NFR5-NFR8 (Security) | `.env` + `.gitignore` + `shared/errors.py` |
| NFR9-NFR12 (Performance) | `mothership/api.py` + `mothership/static/index.html` |
| NFR13-NFR15 (Integration) | `servers/*/server.py` |

### Data Flow

```
Agent (any project)
    │
    ├── connects to ─→ MCP Server (port 8101) ─→ External API (Vertex AI, etc.)
    │                        │
    │                        ├── /metrics ←── Manager polls
    │                        └── logs → logs/<name>.log
    │
Dashboard (browser)
    │
    └── polls ─→ Manager API (port 8080)
                     │
                     ├── GET /api/servers ──→ in-memory state + polled metrics
                     ├── POST /api/servers/{name}/start ──→ asyncio.subprocess
                     ├── POST /api/servers/{name}/stop ──→ SIGTERM
                     ├── GET /api/servers/{name}/logs ──→ read log file
                     └── POST /api/rescan ──→ scan servers/*/mothership.yaml
```

### External Integration Points

- **Vertex AI Gemini API** — called from `servers/imagen/server.py`, credentials from `.env`
- **Local filesystem** — image output, config files, log files
- **MCP clients** — any MCP-compatible agent connects via Streamable HTTP to individual server ports

## Architecture Validation Results

### Coherence Validation

**Decision Compatibility:** All technology choices (Python 3.12, FastMCP 2.x, Poetry, pydantic-settings, FastAPI, pytest) are fully compatible with no version conflicts. FastAPI and FastMCP both use Starlette/uvicorn internally.

**Pattern Consistency:** PEP 8 naming, pydantic-based config, typed error hierarchy, `snake_case` JSON fields, and RotatingFileHandler logging all follow standard Python conventions and align with FastAPI's native capabilities.

**Structure Alignment:** Project structure supports all decisions — `mothership/` for manager isolation, `servers/` for process isolation, `shared/` for code reuse, clear import boundaries enforced.

### Requirements Coverage Validation

**Functional Requirements:** All 33 FRs (FR1-FR33) have explicit architectural support mapped to specific files and patterns.

**Non-Functional Requirements:** All 15 NFRs (NFR1-NFR15) are addressed through process isolation, config patterns, error hierarchy, polling intervals, and MCP protocol compliance.

**Coverage: 100% — no gaps.**

### Implementation Readiness Validation

**Decision Completeness:** All critical decisions documented with library choices, code examples, and rationale.

**Structure Completeness:** Full directory tree defined with every file and its purpose. Requirements mapped to specific locations.

**Pattern Completeness:** All identified conflict points addressed with conventions, examples, and anti-patterns.

### Implementation Note

The `/metrics` endpoint on MCP servers must coexist with the Streamable HTTP MCP transport on the same port. FastMCP servers use Starlette internally, so custom routes can be added to the underlying ASGI app. The implementing agent should mount the `/metrics` route on the same Starlette app that FastMCP uses.

### Architecture Completeness Checklist

**Requirements Analysis**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed (Medium)
- [x] Technical constraints identified (Python, Streamable HTTP, Vertex AI)
- [x] Cross-cutting concerns mapped (credentials, logging, config, health, errors, ports)

**Architectural Decisions**
- [x] Critical decisions documented with versions
- [x] Technology stack fully specified
- [x] Integration patterns defined
- [x] Security considerations addressed

**Implementation Patterns**
- [x] Naming conventions established (PEP 8 + API conventions)
- [x] Structure patterns defined (server layout, shared module, manager)
- [x] MCP tool patterns specified (FastMCP decorators, docstrings)
- [x] Process patterns documented (error flow, config loading, logging, metrics)

**Project Structure**
- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** High

**Key Strengths:**
- Clear process isolation model matching reliability NFRs
- Simple polling-based dashboard avoids frontend complexity
- Convention-based config registration enables easy MCP server addition
- Brownfield evolution preserves working patterns while adding new capabilities
- Every requirement mapped to a specific file — no ambiguity for implementing agents

**Areas for Future Enhancement:**
- CI/CD pipeline (deferred post-MVP)
- Dashboard authentication (Phase 2)
- Auto-restart on crash (Phase 2)
- Remote access via Tailscale/VPN (Phase 3)
- Persistent metrics with historical trends (Phase 3)

### Implementation Handoff

**AI Agent Guidelines:**
- Follow all architectural decisions exactly as documented
- Use implementation patterns consistently across all components
- Respect project structure and boundaries (especially import rules)
- Refer to this document for all architectural questions

**First Implementation Priority:**
1. Rename project from Engagement Manager to MCP Mothership (`pyproject.toml`, module names)
2. Create `mothership/` directory structure
3. Evolve `shared/` modules (rename base error class, add logging config)
4. Build manager core (subprocess spawning, health monitoring, clean shutdown)
5. Build config discovery (`mothership.yaml` scanning and validation)
6. Migrate Imagen server to Streamable HTTP transport + add `/metrics`
7. Build dashboard API (FastAPI REST endpoints)
8. Build dashboard UI (static HTML+JS)
