---
stepsCompleted: [1, 2, 3, 4]
status: 'complete'
completedAt: '2026-04-07'
inputDocuments: ['documents/planning-artifacts/prd.md', 'documents/planning-artifacts/architecture-mothership.md', 'documents/planning-artifacts/architecture.md']
---

# Engagement-Manager - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Engagement-Manager, decomposing the requirements from the PRD and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

**Original (Imagen MCP — Epics 1-3):**

FR1: User can submit a text prompt to generate an image via the Imagen MCP tool
FR2: User can specify image dimensions (width/height) when generating an image
FR3: User can specify an output style or artistic direction for the generated image
FR4: User can specify a custom output location for the generated image
FR5: System generates a single image per prompt request
FR6: System stores the generated image locally and returns the file path to the user
FR7: User can configure MCP server settings via a YAML configuration file
FR8: User can configure sensitive credentials (API keys, GCP project) via environment variables (.env)
FR9: System validates configuration on startup and reports missing or invalid settings
FR10: System reports clear error messages when the Vertex AI API is unavailable or returns an error
FR11: System reports clear error messages when credentials are missing or invalid
FR12: System reports clear error messages when image generation fails (bad prompt, quota exceeded, etc.)

**MCP Mothership (New — Epics 4+):**

MFR1: Operator can start an individual MCP server from the dashboard
MFR2: Operator can stop a running MCP server from the dashboard
MFR3: System detects when a managed MCP server process crashes and updates its status
MFR4: System stops all running MCP servers when the manager process exits
MFR5: Operator can start the entire Mothership system (manager + dashboard) with a single CLI command
MFR6: System discovers MCP server configurations by scanning for YAML config files in the designated directory
MFR7: Operator can register a new MCP server by dropping a YAML config file without modifying manager code
MFR8: Config file specifies server name, description, entry point, port, and required environment variable names
MFR9: System validates MCP config files on discovery and reports errors for malformed configs
MFR10: Agents can discover available tools on a running MCP server via the MCP protocol tools/list method
MFR11: Each managed MCP server is exposed via Streamable HTTP transport on its configured port
MFR12: Multiple agents from different projects can connect to the same MCP server simultaneously
MFR13: System assigns ports to MCP servers based on config or auto-assigns from a configurable range
MFR14: Dashboard displays a list of all registered MCP servers with their current status (running, stopped, crashed)
MFR15: Dashboard displays per-server metrics: uptime, request count, error count, last request time
MFR16: Dashboard shows which tools each MCP server exposes
MFR17: Dashboard updates server status in near real-time without manual page refresh
MFR18: Dashboard provides a log viewer for each MCP server showing its dedicated log output
MFR19: Operator can select which MCP server's logs to view
MFR20: Log viewer displays recent log entries with timestamps and log levels
MFR21: Each MCP server writes logs to a dedicated log file separate from other servers
MFR22: Manager writes its own logs to a separate dedicated log file
MFR23: Crash events are logged with full error context (exit code, stderr output, timestamp)
MFR24: Log files are size-limited or rotated to prevent unbounded disk usage
MFR25: System tracks request count per MCP server
MFR26: System tracks error count per MCP server
MFR27: System tracks last request timestamp per MCP server
MFR28: System calculates uptime per MCP server from process start time
MFR29: Existing Imagen MCP server operates over Streamable HTTP transport instead of stdio
MFR30: All existing Imagen functionality (image generation, session-based refinement) works identically after transport migration
MFR31: Imagen is registered as the first managed MCP server via a config file
MFR32: Project is renamed from Engagement Manager to MCP Mothership across repository, pyproject.toml, and code references
MFR33: Existing shared modules (config, errors, logging) are retained and available for MCP servers

### NonFunctional Requirements

**Original (Imagen MCP — Epics 1-3):**

NFR1: API keys and GCP credentials must be stored in .env files, never in YAML config or source code
NFR2: .env files must be included in .gitignore to prevent accidental commit
NFR3: System must not log or echo credential values in any output
NFR4: System must support Vertex AI Imagen API as the sole image generation backend
NFR5: System must handle API latency gracefully — no timeout on image generation (user waits for result)
NFR6: System must surface API error responses (quota, permissions, model errors) without exposing credentials in error messages

**MCP Mothership (New — Epics 4+):**

MNFR1: A crash in any managed MCP server must not affect other running MCP servers or the manager process
MNFR2: Manager must detect child process termination within 5 seconds and update status accordingly
MNFR3: Manager shutdown must cleanly terminate all child MCP server processes (no orphaned processes)
MNFR4: Dashboard must remain operational and accessible even when all MCP servers are stopped or crashed
MNFR5: API keys and credentials must be stored in .env files only, never in MCP config YAML files or source code
MNFR6: .env files must be included in .gitignore to prevent accidental commit
MNFR7: Log output must never contain credential values, API keys, or secrets
MNFR8: Error messages surfaced to agents or the dashboard must not expose credential values
MNFR9: Dashboard must load and display current server states within 3 seconds
MNFR10: MCP server start/stop actions from the dashboard must initiate within 1 second
MNFR11: Dashboard status updates must reflect actual server state within 5 seconds of a change
MNFR12: The manager must support 10+ registered MCP servers without degradation in dashboard responsiveness
MNFR13: All managed MCP servers must be fully compliant with the MCP protocol specification (tools/list, tool invocation, error responses)
MNFR14: Streamable HTTP transport must work with standard MCP clients (Claude Code, Claude Desktop, and other MCP-compatible agents)
MNFR15: Existing Imagen MCP functionality must pass identical test coverage after transport migration from stdio to Streamable HTTP

### Additional Requirements

**Original (Epics 1-3):**

- Architecture specifies custom project structure (no starter template) — Poetry initialization is the first implementation step
- Shared Python modules required: `shared/errors.py` (typed exception hierarchy), `shared/config.py` (BaseServerConfig with pydantic-settings), `shared/logging.py` (stderr logging setup)
- Per-server config models using pydantic-settings for startup validation (FR9)
- Error class hierarchy: EngagementManagerError → ConfigurationError, ApiUnavailableError, CredentialError, GenerationError
- Logging to stderr only (stdout reserved for MCP stdio protocol), log level configurable via config.yaml
- Tests using pytest with unittest.mock, mirroring source structure in `tests/`
- MCP servers use FastMCP with `@mcp.tool()` decorators and stdio transport
- `.env.example` file to document required environment variables
- Monorepo structure: each MCP server in `servers/<name>/` with `server.py` and `config.py`

**MCP Mothership (New — Epics 4+):**

- Streamable HTTP transport for all MCP servers (SSE deprecated June 2025)
- FastAPI + vanilla HTML/JS dashboard served by manager process on single port
- `asyncio.create_subprocess_exec` for process management
- Health monitoring via polling `process.returncode` at ≤5s intervals
- Each MCP server exposes `/metrics` endpoint (JSON: request_count, error_count, last_request_time)
- Manager polls `/metrics` alongside health checks
- Config discovery scans `servers/*/mothership.yaml`
- Rescan via `POST /api/rescan` (no restart required for new configs)
- Port auto-assignment from configurable range (default 8100-8199)
- Error hierarchy renamed: `MothershipError` base class, new `ServerLifecycleError` added
- Per-server `RotatingFileHandler` logging (5MB default, 3 backups)
- REST API: GET /api/servers, POST /api/servers/{name}/start, POST /api/servers/{name}/stop, GET /api/servers/{name}/logs, POST /api/rescan
- Dashboard polls every 3-5 seconds for status updates
- Each child process reads `.env` directly (no credential proxying through manager)
- `mothership/` package: `__main__.py`, `manager.py`, `discovery.py`, `api.py`, `config.py`, `static/index.html`

### UX Design Requirements

N/A — Dashboard is a single vanilla HTML+JS file. No formal UX specification.

### FR Coverage Map

FR1:  Epic 2 - Submit text prompt to generate image
FR2:  Epic 2 - Specify image dimensions
FR3:  Epic 2 - Specify output style/artistic direction
FR4:  Epic 2 - Specify custom output location
FR5:  Epic 2 - Single image per request
FR6:  Epic 2 - Store locally, return file path
FR7:  Epic 1 - YAML configuration file
FR8:  Epic 1 - Environment variable credentials
FR9:  Epic 1 - Startup config validation
FR10: Epic 1 - API unavailable error reporting
FR11: Epic 1 - Credential error reporting
FR12: Epic 2 - Generation failure error reporting

NFR1-NFR3: Epic 1 - Security patterns (config, errors, gitignore)
NFR4-NFR6: Epic 2 - Vertex AI integration patterns

MFR1:  Epic 4 - Start MCP server from dashboard/CLI
MFR2:  Epic 4 - Stop running MCP server
MFR3:  Epic 4 - Crash detection and status update
MFR4:  Epic 4 - Clean shutdown of all servers on exit
MFR5:  Epic 4 - Single CLI command to start system
MFR6:  Epic 4 - Config file scanning/discovery
MFR7:  Epic 4 - Drop-in config registration
MFR8:  Epic 4 - Config format (name, entry_point, port, env_vars)
MFR9:  Epic 4 - Config validation on discovery
MFR10: Epic 5 - MCP tools/list discovery
MFR11: Epic 5 - Streamable HTTP transport per server
MFR12: Epic 5 - Multi-agent simultaneous connections
MFR13: Epic 4 - Port assignment (config or auto-assign)
MFR14: Epic 6 - Dashboard server list with status
MFR15: Epic 6 - Dashboard per-server metrics display
MFR16: Epic 6 - Dashboard tool display per server
MFR17: Epic 6 - Dashboard near real-time updates
MFR18: Epic 6 - Dashboard log viewer per server
MFR19: Epic 6 - Log server selection
MFR20: Epic 6 - Log entries with timestamps and levels
MFR21: Epic 4 - Per-server dedicated log files
MFR22: Epic 4 - Manager dedicated log file
MFR23: Epic 4 - Crash event logging with full context
MFR24: Epic 4 - Log rotation/size limits
MFR25: Epic 5 - Request count tracking per server
MFR26: Epic 5 - Error count tracking per server
MFR27: Epic 5 - Last request timestamp per server
MFR28: Epic 5 - Uptime calculation per server
MFR29: Epic 5 - Imagen transport migration to Streamable HTTP
MFR30: Epic 5 - Identical Imagen functionality after migration
MFR31: Epic 5 - Imagen registered via config file
MFR32: Epic 4 - Project rename to MCP Mothership
MFR33: Epic 4 - Shared modules retained

MNFR1-MNFR3: Epic 4 - Process isolation, crash detection, clean shutdown
MNFR4: Epic 6 - Dashboard resilience
MNFR5-MNFR8: Epic 4 - Credential security patterns
MNFR9-MNFR11: Epic 6 - Dashboard performance
MNFR12: Epic 4 - 10+ server scalability
MNFR13-MNFR15: Epic 5 - MCP compliance and transport compatibility

## Epic List

### Epic 1: Project Foundation & Configuration
User can install, configure, and validate the Engagement Manager tool is ready to use — Poetry project initialized, credentials set, config validated, clear errors if anything is wrong.
**FRs covered:** FR7, FR8, FR9, FR10, FR11
**NFRs covered:** NFR1, NFR2, NFR3

### Epic 2: Image Generation
User can generate AI images from text prompts with control over dimensions, style, and output location — the core creative capability of the MVP.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR12
**NFRs covered:** NFR4, NFR5, NFR6

### Epic 3: Nano Banana Pro Migration
Migrate from deprecated Imagen API to Nano Banana Pro (Gemini 3 Pro Image) with conversational multi-turn image refinement — enabling iterative creative workflows within Claude Code.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR12 (replaces Epic 2 implementation)
**NFRs covered:** NFR4, NFR5, NFR6
**Architecture ref:** Nano Banana Pro Migration addendum (2026-04-01)

### Epic 4: Project Migration & Process Manager
Operator can rename the project to MCP Mothership, register MCP servers by dropping a config file, start/stop them as isolated subprocesses, and trust that crashes are detected and shutdown is clean — all from a single CLI command.
**MFRs covered:** MFR1, MFR2, MFR3, MFR4, MFR5, MFR6, MFR7, MFR8, MFR9, MFR13, MFR21, MFR22, MFR23, MFR24, MFR32, MFR33
**MNFRs covered:** MNFR1, MNFR2, MNFR3, MNFR5, MNFR6, MNFR7, MNFR8, MNFR12

### Epic 5: Network Transport & Agent Connectivity
Agents from any project can connect to MCP servers over Streamable HTTP, discover available tools, and use capabilities without per-project MCP setup. Imagen is migrated as the first managed server with metrics tracking.
**MFRs covered:** MFR10, MFR11, MFR12, MFR25, MFR26, MFR27, MFR28, MFR29, MFR30, MFR31
**MNFRs covered:** MNFR13, MNFR14, MNFR15

### Epic 6: Dashboard & Operational Visibility
Operator has a web dashboard to see all registered MCP servers at a glance, start/stop them from the browser, view per-server metrics (uptime, requests, errors), and read per-server logs — all updating in near real-time.
**MFRs covered:** MFR14, MFR15, MFR16, MFR17, MFR18, MFR19, MFR20
**MNFRs covered:** MNFR4, MNFR9, MNFR10, MNFR11

## Epic 1: Project Foundation & Configuration

User can install, configure, and validate the Engagement Manager tool is ready to use — Poetry project initialized, credentials set, config validated, clear errors if anything is wrong.

### Story 1.1: Initialize Project Structure

As a developer,
I want to clone the repo and have a working Poetry project with the correct directory structure,
So that I have a solid foundation to build MCP servers on.

**Acceptance Criteria:**

**Given** a fresh clone of the repository
**When** I run `poetry install`
**Then** a virtual environment is created with all dependencies installed (mcp, pydantic-settings, pyyaml, pytest)
**And** the directory structure exists: `servers/imagen/`, `shared/`, `tests/`, `.claude/skills/`
**And** `pyproject.toml` specifies Python >=3.10
**And** `.gitignore` includes `.env`, `__pycache__/`, `.venv/`
**And** `.env.example` lists required environment variables with placeholder values

### Story 1.2: Shared Configuration & Error Handling

As a developer,
I want a validated configuration system and consistent error handling,
So that any MCP server I build has reliable config loading and credential-safe error reporting.

**Acceptance Criteria:**

**Given** a `shared/config.py` module with `BaseServerConfig` using pydantic-settings
**When** a server starts up with valid `.env` and `config.yaml`
**Then** configuration is loaded and validated with typed fields
**And** missing or invalid settings produce clear error messages naming the missing field

**Given** a `shared/errors.py` module with the error hierarchy
**When** an API is unavailable
**Then** an `ApiUnavailableError` is raised with a clear message
**And** credential values are never included in error messages

**Given** missing or invalid credentials in `.env`
**When** the server starts or attempts an API call
**Then** a `CredentialError` is raised with a clear message identifying the missing credential name
**And** the actual credential value is never logged or echoed

**Given** a `shared/logging.py` module
**When** any module initializes logging
**Then** log output goes to stderr only (stdout reserved for MCP stdio)
**And** log level is configurable via `config.yaml`

**Given** `tests/shared/` with test files
**When** I run `poetry run pytest tests/shared/`
**Then** all config validation, error hierarchy, and logging tests pass

## Epic 2: Image Generation

User can generate AI images from text prompts with control over dimensions, style, and output location — the core creative capability of the MVP.

### Story 2.1: Imagen MCP Server with Basic Image Generation

As a content creator,
I want to submit a text prompt and receive a generated image,
So that I can create visual content for my posts without leaving Claude Code.

**Acceptance Criteria:**

**Given** a configured Imagen MCP server with valid GCP credentials
**When** I call the `generate_image` tool with a text prompt
**Then** the system calls Vertex AI Imagen API and generates a single image
**And** the image is stored locally in the default output directory
**And** the file path is returned to the user

**Given** the Imagen MCP server is registered in Claude Code's MCP config
**When** Claude Code starts
**Then** the server connects via stdio transport
**And** the `generate_image` tool is available

**Given** `servers/imagen/config.py` with `ImagenConfig` extending `BaseServerConfig`
**When** the server starts
**Then** GCP project, region, and model settings are validated via pydantic-settings

**Given** `tests/imagen/` with test files
**When** I run `poetry run pytest tests/imagen/`
**Then** all server tests pass with Vertex AI API calls mocked

### Story 2.2: Image Generation Options & Error Handling

As a content creator,
I want to control image dimensions, style, and output location, and get clear feedback when something goes wrong,
So that I can fine-tune my generated images and recover from errors quickly.

**Acceptance Criteria:**

**Given** a valid prompt and the `generate_image` tool
**When** I specify `width` and `height` parameters
**Then** the generated image matches the requested dimensions

**Given** a valid prompt and the `generate_image` tool
**When** I specify a `style` parameter (e.g., "natural", "digital art")
**Then** the generated image reflects the requested artistic direction

**Given** a valid prompt and the `generate_image` tool
**When** I specify a custom `output_path`
**Then** the image is saved to the specified location instead of the default

**Given** a prompt that triggers a Vertex AI error (bad prompt, quota exceeded)
**When** the API returns an error response
**Then** a `GenerationError` is raised with a clear, actionable message
**And** no credential values are exposed in the error

**Given** the Vertex AI API is unreachable or timing out
**When** the tool is invoked
**Then** the system waits for the response without a hard timeout
**And** if the API ultimately fails, an `ApiUnavailableError` is surfaced clearly

## Epic 3: Nano Banana Pro Migration

Migrate from deprecated Imagen API to Nano Banana Pro (Gemini 3 Pro Image) with conversational multi-turn image refinement — enabling iterative creative workflows within Claude Code.

### Story 3.1: SDK Migration & Config Update

As a developer,
I want to swap the deprecated `google-cloud-aiplatform` SDK for `google-genai` and update the server config to target Nano Banana Pro,
So that the project is on a supported SDK before the Imagen API shuts down (June 2026).

**Acceptance Criteria:**

**Given** `pyproject.toml` dependencies
**When** the migration is complete
**Then** `google-cloud-aiplatform` is removed and `google-genai` is added
**And** `poetry install` succeeds cleanly

**Given** `servers/imagen/config.py` with `ImagenConfig`
**When** the server starts
**Then** the default model is `gemini-3-pro-image-preview`
**And** all existing config fields still load from `.env` and `config.yaml`

**Given** `servers/imagen/server.py`
**When** the server initializes
**Then** a `genai.Client(vertexai=True, ...)` is created at module level using config values
**And** no references to `vertexai.init` or `ImageGenerationModel` remain

**Given** `tests/imagen/`
**When** I run `poetry run pytest tests/imagen/`
**Then** all tests pass with the new SDK mocked at the `genai.Client` boundary

### Story 3.2: Conversational Image Generation

As a content creator,
I want to generate an image and then iteratively refine it through follow-up instructions,
So that I can achieve my creative vision through a back-and-forth conversation without starting over each time.

**Acceptance Criteria:**

**Given** a configured Imagen MCP server with valid GCP credentials
**When** I call `generate_image` with a prompt and no `session_id`
**Then** a new chat session is created via `client.chats.create()`
**And** the image is generated and saved locally
**And** the tool returns JSON with `session_id` and `image_path`

**Given** a valid `session_id` from a previous generation
**When** I call `generate_image` with a refinement prompt and the `session_id`
**Then** the message is sent to the existing chat session
**And** the model refines the image while maintaining visual consistency
**And** the refined image is saved and the same `session_id` is returned

**Given** an invalid or expired `session_id`
**When** I call `generate_image` with that `session_id`
**Then** a `GenerationError` is raised with a clear message

**Given** `tests/imagen/`
**When** I run `poetry run pytest tests/imagen/`
**Then** all session management tests pass (create, continue, invalid ID, multi-turn response parsing)

### Story 3.3: Updated Tests & Regression

As a developer,
I want comprehensive tests covering the new Gemini-based image generation and session management,
So that I have confidence the migration is correct and future changes won't break functionality.

**Acceptance Criteria:**

**Given** `tests/imagen/test_server.py` with updated tests
**When** I run `poetry run pytest tests/imagen/ -v`
**Then** all tests pass with `genai.Client` and `chat.send_message` mocked
**And** tests cover: new session creation, session continuation, invalid session, text+image response parsing, image data extraction and file saving, all error type mappings to typed exceptions, credential safety, no timeout on API calls

**Given** `tests/imagen/test_config.py` with config tests
**When** I run `poetry run pytest tests/imagen/test_config.py -v`
**Then** all tests pass including the updated default model value

**Given** the full test suite
**When** I run `poetry run pytest -v`
**Then** all tests pass with zero regressions against shared module tests

## Epic 4: Project Migration & Process Manager

Operator can rename the project to MCP Mothership, register MCP servers by dropping a config file, start/stop them as isolated subprocesses, and trust that crashes are detected and shutdown is clean — all from a single CLI command.

### Story 4.1: Project Rename & Shared Module Evolution

As a developer,
I want the project renamed to MCP Mothership with evolved shared modules,
So that the codebase reflects the new scope and the error hierarchy supports manager operations.

**Acceptance Criteria:**

**Given** the existing Engagement Manager codebase
**When** the migration is complete
**Then** `pyproject.toml` reflects `mcp-mothership` as the project name
**And** the `mothership/` package directory exists with `__init__.py` and `__main__.py`
**And** `shared/errors.py` base class is renamed from `EngagementManagerError` to `MothershipError`
**And** a new `ServerLifecycleError` class exists in `shared/errors.py`
**And** `shared/logging_config.py` supports `RotatingFileHandler` setup for named log files
**And** all existing tests pass with the renamed error classes
**And** `python -m mothership` runs without error (can be a no-op stub at this stage)

### Story 4.2: Config Discovery & Registration

As an operator,
I want to register a new MCP server by dropping a `mothership.yaml` config file into its directory,
So that I can add capabilities without modifying manager code.

**Acceptance Criteria:**

**Given** a `mothership/discovery.py` module
**When** the manager scans `servers/*/mothership.yaml`
**Then** all valid config files are discovered and parsed into a list of server registrations

**Given** a `mothership.yaml` with fields: name, description, entry_point, port, env_vars
**When** the config is loaded
**Then** each field is validated via a pydantic model
**And** missing required fields produce a `ConfigurationError` with a clear message

**Given** a config file with no `port` specified
**When** the config is loaded
**Then** a port is auto-assigned from the configurable range (default 8100-8199)
**And** no two servers receive the same auto-assigned port

**Given** a malformed or invalid config file
**When** discovery runs
**Then** the error is logged to the manager log
**And** other valid configs are still loaded successfully

**Given** `tests/mothership/test_discovery.py`
**When** I run `poetry run pytest tests/mothership/test_discovery.py`
**Then** all config scanning, validation, and port assignment tests pass

### Story 4.3: Process Manager — Start, Stop, Health & Shutdown

As an operator,
I want to start and stop MCP servers as isolated subprocesses, with automatic crash detection and clean shutdown,
So that I can trust that one server's crash won't affect others and no orphaned processes remain.

**Acceptance Criteria:**

**Given** a `mothership/manager.py` module with a `ServerManager` class
**When** I call `start_server(server_name)`
**Then** the server's Python module is launched via `asyncio.create_subprocess_exec`
**And** the manager tracks: PID, status ("running"), start time
**And** the server runs as an independent process

**Given** a running MCP server
**When** I call `stop_server(server_name)`
**Then** SIGTERM is sent to the process
**And** the status updates to "stopped"

**Given** a running MCP server that crashes
**When** the health monitoring loop polls (≤5 second interval)
**Then** the crash is detected via `process.returncode`
**And** status updates to "crashed"
**And** stderr output and exit code are captured in the server's state

**Given** the manager process is shutting down (SIGTERM/SIGINT)
**When** clean shutdown executes
**Then** SIGTERM is sent to all running child processes
**And** a grace period elapses before SIGKILL for unresponsive processes
**And** no orphaned child processes remain

**Given** 10+ registered MCP servers
**When** all are started simultaneously
**Then** the manager handles them without degradation

**Given** `mothership/__main__.py`
**When** I run `python -m mothership`
**Then** the manager starts, discovers configs, and is ready to start/stop servers

**Given** `tests/mothership/test_manager.py`
**When** I run `poetry run pytest tests/mothership/test_manager.py`
**Then** all process management tests pass (start, stop, crash detection, clean shutdown)

### Story 4.4: Per-Server Logging System

As an operator,
I want each MCP server and the manager to write logs to dedicated files with rotation,
So that I can diagnose issues per-server without digging through combined output.

**Acceptance Criteria:**

**Given** a running MCP server named "imagen"
**When** it writes log output
**Then** logs are written to `logs/imagen.log` via `RotatingFileHandler`

**Given** the manager process
**When** it writes log output
**Then** logs are written to `logs/mothership.log` via `RotatingFileHandler`

**Given** a log file reaching the size limit (default 5MB)
**When** the next log entry is written
**Then** the file rotates with up to 3 backup files

**Given** a managed MCP server that crashes
**When** the crash is detected
**Then** the crash event is logged with exit code, stderr output, and timestamp

**Given** any log output across the system
**When** credential values are present in the context
**Then** they are never included in log messages

**Given** `tests/mothership/` and `tests/shared/`
**When** I run the relevant logging tests
**Then** all log setup, rotation, and crash logging tests pass

## Epic 5: Network Transport & Agent Connectivity

Agents from any project can connect to MCP servers over Streamable HTTP, discover available tools, and use capabilities without per-project MCP setup. Imagen is migrated as the first managed server with metrics tracking.

### Story 5.1: Imagen Transport Migration — Streamable HTTP

As a developer,
I want the Imagen MCP server to operate over Streamable HTTP instead of stdio,
So that agents from any project can connect to it over the network.

**Acceptance Criteria:**

**Given** the existing Imagen MCP server (`servers/imagen/server.py`)
**When** the transport migration is complete
**Then** the server starts with `transport="streamable-http"` on its configured port
**And** no stdio transport code remains

**Given** an MCP-compatible client (Claude Code, Claude Desktop)
**When** it connects to the Imagen server's Streamable HTTP endpoint
**Then** `tools/list` returns the `generate_image` tool with correct schema

**Given** the Imagen server running on Streamable HTTP
**When** a client calls `generate_image` with a prompt
**Then** the image is generated and the file path is returned — identical behavior to the stdio version

**Given** the Imagen server running on Streamable HTTP
**When** a client uses session-based refinement (session_id)
**Then** conversational image generation works identically to the stdio version

**Given** `servers/imagen/mothership.yaml`
**When** the manager discovers it
**Then** Imagen is registered as a managed MCP server with name, description, entry_point, and port

**Given** `tests/servers/imagen/`
**When** I run `poetry run pytest tests/servers/imagen/`
**Then** all existing tests pass with the new transport (mocked at the same boundaries)
**And** test coverage is identical to pre-migration

### Story 5.2: Metrics Endpoint & Tracking

As an operator,
I want each MCP server to track and expose request count, error count, and last request time,
So that I can monitor server activity and health.

**Acceptance Criteria:**

**Given** a running MCP server (Imagen)
**When** a tool is invoked successfully
**Then** `request_count` increments by 1
**And** `last_request_time` updates to the current ISO 8601 timestamp

**Given** a running MCP server
**When** a tool invocation results in an error
**Then** both `request_count` and `error_count` increment by 1

**Given** a running MCP server
**When** a client sends `GET /metrics`
**Then** the response is JSON: `{"request_count": N, "error_count": N, "last_request_time": "ISO8601 or null"}`

**Given** the `/metrics` endpoint
**When** it coexists with the Streamable HTTP MCP transport
**Then** both respond correctly on the same port (mounted on the same Starlette app)

**Given** the manager's health monitoring loop
**When** it polls a running server
**Then** it fetches `/metrics` and stores the metrics in its in-memory server state
**And** uptime is calculated by the manager from process start time

**Given** `tests/servers/imagen/test_server.py`
**When** I run the metrics-related tests
**Then** all counter increment, reset, and endpoint response tests pass

### Story 5.3: Multi-Agent Connectivity

As an agent builder,
I want multiple agents from different projects to connect to the same running MCP server simultaneously,
So that I can reuse capabilities across all my agentic projects without duplication.

**Acceptance Criteria:**

**Given** a running Imagen MCP server on Streamable HTTP
**When** two separate MCP clients connect concurrently
**Then** both can call `tools/list` and receive the correct tool schema
**And** both can invoke `generate_image` independently

**Given** two concurrent clients making requests
**When** both call `generate_image` simultaneously
**Then** each receives its own response without interference
**And** the metrics endpoint reflects the combined request count

**Given** one client disconnects
**When** the other client continues making requests
**Then** the server remains operational and responsive

**Given** `tests/servers/imagen/`
**When** I run concurrent connection tests
**Then** multi-client scenarios pass without race conditions or errors

## Epic 6: Dashboard & Operational Visibility

Operator has a web dashboard to see all registered MCP servers at a glance, start/stop them from the browser, view per-server metrics (uptime, requests, errors), and read per-server logs — all updating in near real-time.

### Story 6.1: Dashboard REST API

As an operator,
I want a REST API that exposes server state, controls, and logs,
So that the dashboard frontend has a reliable data source for all operational actions.

**Acceptance Criteria:**

**Given** a `mothership/api.py` module with a FastAPI app
**When** the manager starts via `python -m mothership`
**Then** the API is served on the configured port (default 8080)

**Given** registered MCP servers (running, stopped, or crashed)
**When** a client sends `GET /api/servers`
**Then** the response includes all servers with: name, description, status, port, uptime, request_count, error_count, last_request_time, and tools list

**Given** a stopped MCP server
**When** a client sends `POST /api/servers/{name}/start`
**Then** the server starts and the response is `{"ok": true, "message": "Server 'name' started"}`

**Given** a running MCP server
**When** a client sends `POST /api/servers/{name}/stop`
**Then** the server stops and the response is `{"ok": true, "message": "Server 'name' stopped"}`

**Given** a request for a non-existent server name
**When** any server-specific endpoint is called
**Then** the response is `{"ok": false, "error": "Server 'name' not found"}` with HTTP 404

**Given** an MCP server with log entries
**When** a client sends `GET /api/servers/{name}/logs?lines=100`
**Then** the response contains the last 100 lines from the server's log file

**Given** new `mothership.yaml` files added to `servers/`
**When** a client sends `POST /api/rescan`
**Then** the manager rescans configs and new servers appear in subsequent `GET /api/servers` responses

**Given** the API start/stop actions
**When** triggered by a client
**Then** the action initiates within 1 second (MNFR10)

**Given** `tests/mothership/test_api.py`
**When** I run `poetry run pytest tests/mothership/test_api.py`
**Then** all endpoint tests pass (list, start, stop, logs, rescan, error cases)

### Story 6.2: Dashboard UI — Server List & Controls

As an operator,
I want a web dashboard showing all MCP servers with their status and start/stop buttons,
So that I can manage my MCP infrastructure from a browser at a glance.

**Acceptance Criteria:**

**Given** `mothership/static/index.html` (single vanilla HTML+JS file)
**When** I open the dashboard in a browser at `http://localhost:8080`
**Then** the page loads and displays a list of all registered MCP servers

**Given** the server list
**When** rendered for each server
**Then** I see: server name, description, status indicator (running/stopped/crashed), port number, and start/stop button

**Given** a server with status "running"
**When** displayed
**Then** the status indicator is visually distinct (e.g., green) and the button shows "Stop"

**Given** a server with status "stopped" or "crashed"
**When** displayed
**Then** the status indicator reflects the state (e.g., grey/red) and the button shows "Start"

**Given** I click "Start" on a stopped server
**When** the action completes
**Then** the server status updates to "running" without a manual page refresh

**Given** I click "Stop" on a running server
**When** the action completes
**Then** the server status updates to "stopped" without a manual page refresh

**Given** the dashboard is open
**When** 3-5 seconds elapse
**Then** the server list refreshes automatically via polling `GET /api/servers` (MNFR11)

**Given** all MCP servers are stopped or crashed
**When** I load the dashboard
**Then** it remains fully operational and accessible (MNFR4)

**Given** the dashboard
**When** the page loads
**Then** it displays current server states within 3 seconds (MNFR9)

### Story 6.3: Dashboard UI — Metrics & Log Viewer

As an operator,
I want to see per-server metrics and view server logs from the dashboard,
So that I can monitor activity and diagnose issues without leaving the browser.

**Acceptance Criteria:**

**Given** a running MCP server with activity
**When** the dashboard displays its entry
**Then** I see: uptime, request count, error count, and last request time

**Given** metrics displayed on the dashboard
**When** the polling interval elapses (3-5 seconds)
**Then** metrics update to reflect the latest values from the API

**Given** the server list
**When** I select a server for log viewing
**Then** a log viewer panel displays recent log entries for that server

**Given** the log viewer for a specific server
**When** log entries are displayed
**Then** each entry shows timestamp, log level, and message

**Given** the log viewer is open
**When** new log entries are written by the server
**Then** the viewer updates on the next poll cycle to show the latest entries

**Given** a server showing which tools it exposes
**When** the dashboard fetches server data
**Then** the tools list is displayed for operator reference (MFR16)
