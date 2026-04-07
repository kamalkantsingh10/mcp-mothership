# Story 5.1: Imagen Transport Migration — Streamable HTTP

Status: review

## Story

As a developer,
I want the Imagen MCP server to operate over Streamable HTTP instead of stdio,
so that agents from any project can connect to it over the network.

## Acceptance Criteria

1. **Given** the existing Imagen MCP server (`servers/imagen/server.py`) **When** the transport migration is complete **Then** the server starts with `transport="streamable-http"` on its configured port **And** no stdio transport code remains
2. **Given** an MCP-compatible client (Claude Code, Claude Desktop) **When** it connects to the Imagen server's Streamable HTTP endpoint **Then** `tools/list` returns the `generate_image` tool with correct schema
3. **Given** the Imagen server running on Streamable HTTP **When** a client calls `generate_image` with a prompt **Then** the image is generated and the file path is returned — identical behavior to the stdio version
4. **Given** the Imagen server running on Streamable HTTP **When** a client uses session-based refinement (session_id) **Then** conversational image generation works identically to the stdio version
5. **Given** `servers/imagen/mothership.yaml` **When** the manager discovers it **Then** Imagen is registered as a managed MCP server with name, description, entry_point, and port
6. **Given** `tests/servers/imagen/` **When** I run `poetry run pytest tests/servers/imagen/` **Then** all existing tests pass with the new transport (mocked at the same boundaries) **And** test coverage is identical to pre-migration

## Tasks / Subtasks

- [x] Task 1: Change Imagen server transport from stdio to Streamable HTTP (AC: #1)
  - [x] In `servers/imagen/server.py`, change `mcp.run(transport="stdio")` to `mcp.run(transport="streamable-http", host="0.0.0.0", port=config.port)`
  - [x] Add a `port` field to `ImagenConfig` (default 8101, matching `mothership.yaml`)
  - [x] Remove the docstring reference to "stdio transport" at the top of `server.py`
  - [x] Update the `if __name__ == "__main__"` block logger message from "Starting MCP stdio transport" to "Starting MCP Streamable HTTP transport on port {port}"
  - [x] Remove any remaining stdio-specific code or comments
- [x] Task 2: Add port config to ImagenConfig (AC: #1)
  - [x] Add `port: int = 8101` field to `ImagenConfig` in `servers/imagen/config.py`
  - [x] Ensure port is loadable from env var `IMAGEN_PORT`, `.env`, or `config.yaml`
  - [x] Verify `mothership.yaml` already specifies `port: 8101` (it does)
- [x] Task 3: Verify MCP tool listing over Streamable HTTP (AC: #2)
  - [x] Write test that starts the server and verifies `tools/list` returns `generate_image` with full schema
  - [x] Verify all tool parameters (prompt, width, height, style, output_path, session_id) appear in schema
- [x] Task 4: Verify image generation over Streamable HTTP (AC: #3)
  - [x] Write/update test that calls `generate_image` via the MCP protocol and gets a valid response
  - [x] Mock at the same boundary as existing tests (google-genai client)
  - [x] Verify the returned JSON contains `session_id` and `image_path`
- [x] Task 5: Verify session-based refinement over Streamable HTTP (AC: #4)
  - [x] Write/update test that creates a session, then sends a follow-up prompt using the returned session_id
  - [x] Verify the second call uses the existing chat session (not a new one)
  - [x] Mock at the same boundary as existing tests
- [x] Task 6: Verify manager discovery of Imagen (AC: #5)
  - [x] Confirm `servers/imagen/mothership.yaml` has: name, description, entry_point, port
  - [x] Verify `discover_servers()` in `mothership/discovery.py` correctly parses the Imagen config
  - [x] This should already work from Epic 4 — verify with existing test or write a quick check
- [x] Task 7: Create test directory and write transport tests (AC: #6)
  - [x] Create `tests/servers/__init__.py` and `tests/servers/imagen/__init__.py`
  - [x] Create `tests/servers/imagen/test_server.py` with tests covering:
    - `test_generate_image_returns_session_and_path` — basic generation
    - `test_generate_image_session_refinement` — multi-turn conversation
    - `test_generate_image_empty_prompt_raises` — error handling
    - `test_generate_image_invalid_dimensions_raises` — validation
    - `test_sanitize_filename` — utility function
    - `test_map_dimensions_to_aspect_ratio` — mapping logic
  - [x] Run `PYTHONPATH="" poetry run pytest tests/servers/imagen/ -v`
- [x] Task 8: Run full regression (AC: #6)
  - [x] Run `PYTHONPATH="" poetry run pytest -v` to verify zero regressions across all tests

## Dev Notes

### Architecture Compliance

- **Transport:** Streamable HTTP via FastMCP's `transport="streamable-http"` — SSE is deprecated per June 2025 MCP spec revision (see architecture-mothership.md)
- **Port:** 8101 as configured in `mothership.yaml`, also configurable via `ImagenConfig.port`
- **Process isolation:** Server remains independently runnable via `python -m servers.imagen.server`
- **Credential flow:** Server reads `.env` directly — no change from current behavior

### Current State of `servers/imagen/server.py`

The server currently:
- Uses `mcp.run(transport="stdio")` at line 255
- Has `FastMCP("imagen")` at line 76
- Has full `generate_image` tool with session support
- Logging already configured with `setup_logging(config.log_level, log_name="imagen")`
- Config loaded via `ImagenConfig.from_yaml(config_path="config.yaml")`

### Key Change

The primary code change is minimal — swap `mcp.run(transport="stdio")` to `mcp.run(transport="streamable-http", host="0.0.0.0", port=config.port)` and add `port` to `ImagenConfig`. The bulk of this story is verifying identical behavior and creating the test directory.

### FastMCP Streamable HTTP

FastMCP handles Streamable HTTP natively. The server call is:
```python
mcp.run(transport="streamable-http", host="0.0.0.0", port=8101)
```
This starts a Starlette/uvicorn server. The MCP endpoint is at the root path. Custom routes (like `/metrics` in Story 5.2) can be mounted on the same ASGI app.

### Test Directory

No `tests/servers/` directory exists yet. This story creates it with proper `__init__.py` files. Tests should mock the `google.genai` client at the same boundary as any existing test patterns.

### Files to Create

```
tests/servers/__init__.py
tests/servers/imagen/__init__.py
tests/servers/imagen/test_server.py
```

### Files to Modify

```
servers/imagen/server.py          # Transport change: stdio → streamable-http
servers/imagen/config.py          # Add port field
```

### Dependencies on Previous Stories

- Story 4.1: Project rename and shared module evolution (completed)
- Story 4.2: Config discovery and registration (completed)
- Story 4.4: Per-server logging (completed — `setup_logging` with `log_name` already wired)

### Anti-Patterns to Avoid

- Do NOT use SSE transport — it is deprecated; use Streamable HTTP
- Do NOT add a reverse proxy or gateway — each server runs on its own port
- Do NOT change the `generate_image` tool signature or behavior — transport migration only
- Do NOT remove session support — it must work identically over the new transport
- Do NOT hardcode the port — read from `ImagenConfig.port`

### Previous Story Learnings

- Run tests with `PYTHONPATH=""` to avoid ROS plugin conflicts
- Use `tmp_path` and `monkeypatch` for test isolation
- Mock at the `google.genai` client boundary, not at the HTTP transport layer

### References

- [Source: documents/planning-artifacts/architecture-mothership.md#Network Transport]
- [Source: documents/planning-artifacts/architecture-mothership.md#MCP Tool Patterns]
- [Source: documents/planning-artifacts/epics.md#Story 5.1]
- [Source: documents/planning-artifacts/prd.md#FR11, FR29, FR30, FR31, NFR13, NFR14, NFR15]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- None

### Completion Notes List

- Changed `FastMCP("imagen")` to `FastMCP("imagen", host="0.0.0.0", port=config.port)` — host/port set via constructor, not `run()`
- Changed `mcp.run(transport="stdio")` to `mcp.run(transport="streamable-http")` — transport param on `run()`, host/port on constructor
- Added `port: int = 8101` to `ImagenConfig` — loadable from env var `IMAGEN_PORT`, `.env`, or `config.yaml`
- Updated module docstring to reference Streamable HTTP transport
- Updated startup log message to include port number
- Verified zero remaining stdio references in server.py
- Created `tests/servers/imagen/test_server.py` with 16 tests covering transport config, tool schema, generation, session refinement, utility functions
- All 16 new tests pass, all 47 existing tests pass, 170/172 total pass (2 pre-existing failures in `tests/imagen/test_config.py` due to `.env` API key leak — unrelated to transport migration)
- Manager discovery of Imagen verified via existing `tests/mothership/test_discovery.py`

### Change Log

- 2026-04-07: Story 5.1 implementation complete — Imagen transport migrated from stdio to Streamable HTTP

### File List

- `servers/imagen/server.py` — modified (transport: stdio → streamable-http, host/port on FastMCP constructor)
- `servers/imagen/config.py` — modified (added `port: int = 8101`)
- `tests/servers/__init__.py` — created (empty init)
- `tests/servers/imagen/__init__.py` — created (empty init)
- `tests/servers/imagen/test_server.py` — created (16 tests: transport config, tool schema, generation, sessions, utilities)
