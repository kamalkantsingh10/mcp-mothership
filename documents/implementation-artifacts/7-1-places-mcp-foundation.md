# Story 7.1: Places MCP Server Foundation

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want a Places MCP server skeleton registered with the Mothership,
so that it appears on the dashboard and accepts network traffic over Streamable HTTP using Mothership conventions — ready for tool implementations in Stories 7.2 and 7.3.

## Acceptance Criteria

1. **Given** a new `servers/places/` package **When** the package is created **Then** the directory contains `__init__.py`, `server.py`, `config.py`, and `mothership.yaml` **And** `servers/places/mothership.yaml` declares name (`places`), description, entry_point (`servers.places.server`), port, and env_vars including `GOOGLE_PLACES_API_KEY`

2. **Given** `servers/places/config.py` with `PlacesConfig` extending `BaseServerConfig` **When** the server starts with a valid `.env` **Then** `GOOGLE_PLACES_API_KEY` is validated via pydantic-settings **And** a missing or empty key raises `CredentialError` with a clear message naming the missing variable **And** the actual key value is never logged or echoed

3. **Given** `servers/places/server.py` using FastMCP **When** `python -m servers.places.server` is invoked **Then** the server starts with `transport="streamable-http"` on its configured port **And** a `/metrics` endpoint is exposed returning `{"request_count": N, "error_count": N, "last_request_time": "ISO8601 or null"}` **And** a `tools/list` call returns an empty tool list (tool implementations land in Stories 7.2 and 7.3)

4. **Given** the Mothership manager is running **When** it scans `servers/*/mothership.yaml` **Then** `places` is discovered and listed with status `stopped` **And** the dashboard surfaces Places with start/stop controls — no manager or dashboard code changes required

5. **Given** a tool-boundary error translator in `servers/places/server.py` **When** a typed exception is raised inside a tool implementation **Then** the tool returns a structured response `{"error": "message", "code": "NOT_FOUND" | "QUOTA" | "AUTH" | "UNKNOWN"}` **And** `CredentialError` → `AUTH`, `ApiUnavailableError` with HTTP 429 or quota signal → `QUOTA`, Places 404 → `NOT_FOUND`, everything else → `UNKNOWN` **And** credential values never appear in the returned payload

6. **Given** `tests/servers/places/test_config.py` and `tests/servers/places/test_error_mapping.py` **When** I run `PYTHONPATH="" poetry run pytest tests/servers/places/ -v` **Then** all config validation and error-mapping tests pass **And** running the full suite produces zero regressions against existing tests

## Tasks / Subtasks

- [x] **Task 1: Create `servers/places/` package skeleton** (AC: #1)
  - [x] Create directory `servers/places/`
  - [x] Create empty `servers/places/__init__.py`
  - [x] Create `servers/places/mothership.yaml` with exact fields:
    ```yaml
    name: places
    description: "Travel research via Google Places API (New) — attractions, restaurants, hotels"
    entry_point: servers.places.server
    port: 8102
    env_vars:
      - GOOGLE_PLACES_API_KEY
    ```
  - [x] Port 8102 chosen to avoid clash with Imagen's 8101 and leave room in the 8100-8199 range
  - [x] Do NOT add `imagen:` style config.yaml section yet — no server-specific operational settings required for 7.1

- [x] **Task 2: Implement `PlacesConfig` in `servers/places/config.py`** (AC: #2)
  - [x] Mirror the structural pattern of `servers/imagen/config.py` — inherit from `BaseServerConfig`, use `SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")`
  - [x] Fields:
    - `port: int = 8102`
    - `google_places_api_key: str | None = None` (pydantic uppercases → reads `GOOGLE_PLACES_API_KEY` env var)
    - `places_api_base_url: str = "https://places.googleapis.com/v1"`
    - `places_http_timeout_seconds: float = 10.0`
  - [x] Add a `_PlacesYamlSource` subclass of `YamlSettingsSource` that merges the `places:` section from `config.yaml` (exactly like `_ImagenYamlSource` in `servers/imagen/config.py`) — forward-looking hook for Stories 7.2/7.3 operational tuning
  - [x] Override `settings_customise_sources` with the same priority order used by `ImagenConfig`: init > env > .env > yaml > defaults
  - [x] Do NOT add a field validator that raises on empty API key inside `PlacesConfig` — startup validation happens in `server.py` so the error log message lands in Mothership's log file after `setup_logging` runs (see Task 3)

- [x] **Task 3: Implement `servers/places/server.py` skeleton** (AC: #2, #3, #5)
  - [x] Follow the top-of-file structure of `servers/imagen/server.py` (compare side-by-side while writing)
  - [x] Imports: `logging`, `datetime.datetime`, `datetime.timezone`, `typing.Any`, `mcp.server.fastmcp.FastMCP`, `servers.places.config.PlacesConfig`, `shared.errors.{MothershipError, CredentialError, ApiUnavailableError, ConfigurationError}`, `shared.logging_config.setup_logging`
  - [x] Module-level setup sequence (order matters):
    1. `logger = logging.getLogger(__name__)`
    2. `config = PlacesConfig.from_yaml(config_path="config.yaml")`
    3. `setup_logging(config.log_level, log_name="places")` — this routes logs to `logs/places.log`
    4. Startup log line: `logger.info("Places MCP server starting up")`
    5. Validate `GOOGLE_PLACES_API_KEY`:
       ```python
       if not config.google_places_api_key:
           raise CredentialError(
               "GOOGLE_PLACES_API_KEY",
               reason="is missing — set GOOGLE_PLACES_API_KEY in .env",
           )
       logger.info("Places API credential loaded")
       ```
    6. `mcp = FastMCP("places", host="0.0.0.0", port=config.port)` — host/port on constructor, NOT on `run()`
    7. `logger.info("MCP server created, ready to accept connections")`
  - [x] Module-level metrics counters (exact names, matching Imagen pattern for manager polling compatibility):
    ```python
    _request_count: int = 0
    _error_count: int = 0
    _last_request_time: str | None = None
    ```
  - [x] `/metrics` endpoint using `@mcp.custom_route("/metrics", methods=["GET"])` — exact pattern from `servers/imagen/server.py` lines 277-285. Returns `JSONResponse` from `starlette.responses`.
  - [x] `__main__` guard:
    ```python
    if __name__ == "__main__":
        logger.info("Starting MCP Streamable HTTP transport on port %d", config.port)
        mcp.run(transport="streamable-http")
    ```

- [x] **Task 4: Implement the tool-boundary error translator** (AC: #5)
  - [x] Add a helper in `servers/places/server.py` that future tools (Stories 7.2, 7.3) will use to convert typed exceptions into the structured error response
  - [x] Use this exact implementation — it is the contract the next two stories will depend on:
    ```python
    from shared.errors import (
        ApiUnavailableError,
        ConfigurationError,
        CredentialError,
        MothershipError,
    )


    class PlaceNotFoundError(MothershipError):
        """Raised when a Google Places lookup returns 404 for a place_id or query."""


    def _to_error_response(exc: Exception) -> dict[str, str]:
        """Translate a typed exception into the MCP tool error response shape.

        Shape: {"error": "<message>", "code": "NOT_FOUND"|"QUOTA"|"AUTH"|"UNKNOWN"}
        Credential values never appear — CredentialError carries only the credential NAME.
        """
        if isinstance(exc, CredentialError):
            return {"error": str(exc), "code": "AUTH"}
        if isinstance(exc, PlaceNotFoundError):
            return {"error": str(exc), "code": "NOT_FOUND"}
        if isinstance(exc, ApiUnavailableError):
            msg = str(exc).lower()
            if "quota" in msg or "rate" in msg or "429" in msg:
                return {"error": str(exc), "code": "QUOTA"}
            return {"error": str(exc), "code": "UNKNOWN"}
        if isinstance(exc, ConfigurationError):
            return {"error": str(exc), "code": "UNKNOWN"}
        # Never leak raw exception class name or stack — log it server-side instead
        logger.exception("Unexpected error in Places tool")
        return {"error": "Unexpected error", "code": "UNKNOWN"}
    ```
  - [x] `PlaceNotFoundError` lives in `server.py` for this story. **DO NOT** add it to `shared/errors.py` — shared contains cross-server primitives only. If a second server needs the same class later, promote it then (follow YAGNI).
  - [x] Export `_to_error_response` and `PlaceNotFoundError` via module-level names — Stories 7.2 and 7.3 will import them from `servers.places.server`

- [x] **Task 5: Verify manager discovery and dashboard integration** (AC: #4)
  - [x] No code changes expected. Run `poetry run python -m mothership` and hit `GET http://localhost:8080/api/servers` — confirm `places` appears in the response with `status: "stopped"` and `port: 8102`
  - [x] If it does NOT appear, STOP and flag to the user — this would mean the Mothership's `discover_servers()` contract has drifted (would be a regression in Epic 4-6 code under review, not a 7.1 bug)
  - [x] Expected `GET /api/servers` response includes an entry like:
    ```json
    {"name": "places", "description": "Travel research via Google Places API (New) — attractions, restaurants, hotels",
     "status": "stopped", "port": 8102, "uptime": null, "request_count": 0, "error_count": 0, "last_request_time": null}
    ```
  - [x] Also exercise `POST /api/servers/places/start` — server must start, `/metrics` must return the zero-state JSON, dashboard must flip to `running`. Then `POST /api/servers/places/stop` to return to `stopped`. This end-to-end check confirms AC #4.

- [x] **Task 6: Update `.env.example`** (AC: #2)
  - [x] Append to existing `.env.example`:
    ```
    # === Google Places MCP ===
    # Get key from https://console.cloud.google.com/ — enable "Places API (New)"
    GOOGLE_PLACES_API_KEY=your-places-api-key
    ```
  - [x] Do NOT modify the existing `IMAGEN_*` section — append only

- [x] **Task 7: Write tests** (AC: #2, #3, #5, #6)
  - [x] Create `tests/servers/places/__init__.py` (empty)
  - [x] Create `tests/servers/places/test_config.py` with tests:
    - `test_config_loads_api_key_from_env` — set `GOOGLE_PLACES_API_KEY=test-key` via `monkeypatch.setenv`, instantiate `PlacesConfig()`, assert `google_places_api_key == "test-key"`
    - `test_config_default_port_is_8102`
    - `test_config_default_base_url` — asserts `places.googleapis.com/v1`
    - `test_config_default_timeout` — asserts 10.0 seconds
    - `test_config_yaml_places_section_merges` — write a temp `config.yaml` with `places: { places_http_timeout_seconds: 20 }`, load via `PlacesConfig.from_yaml(config_path=tmp_path/"config.yaml")`, assert field picks up the YAML value
    - Use the autouse `_mock_config` fixture pattern from `tests/servers/imagen/test_server.py:16-19` — set a valid dummy env var before any test imports the server module
  - [x] Create `tests/servers/places/test_error_mapping.py` with tests:
    - `test_credential_error_maps_to_auth` — `_to_error_response(CredentialError("GOOGLE_PLACES_API_KEY"))` → `{"code": "AUTH", ...}`, assert no credential VALUE appears (the name is fine — Imagen does the same)
    - `test_place_not_found_maps_to_not_found`
    - `test_quota_in_message_maps_to_quota` — pass `ApiUnavailableError("Google Places quota exceeded")` → `"QUOTA"`
    - `test_rate_limit_in_message_maps_to_quota` — pass `ApiUnavailableError("HTTP 429 rate limit")` → `"QUOTA"`
    - `test_generic_api_unavailable_maps_to_unknown` — pass `ApiUnavailableError("network unreachable")` → `"UNKNOWN"`
    - `test_configuration_error_maps_to_unknown`
    - `test_bare_exception_logs_and_maps_to_unknown` — pass `RuntimeError("boom")` → `{"code": "UNKNOWN", "error": "Unexpected error"}` (note: message is sanitized, the raw exception text must NOT leak)
  - [x] Create `tests/servers/places/test_server.py` with a minimal transport-config suite (mirroring `TestTransportConfiguration` in `tests/servers/imagen/test_server.py:69-96`):
    - `test_mcp_server_host_is_all_interfaces` — `mcp.settings.host == "0.0.0.0"`
    - `test_mcp_server_port_matches_config` — `mcp.settings.port == config.port`
    - `test_mcp_server_default_port_is_8102`
    - `test_streamable_http_app_is_starlette`
    - `test_no_stdio_references_in_server_module`
    - `test_metrics_endpoint_initial_state` — call `/metrics` via the Starlette test client, assert `{"request_count": 0, "error_count": 0, "last_request_time": null}`
  - [x] Use autouse fixtures to set `GOOGLE_PLACES_API_KEY=test-key` via `monkeypatch.setenv` and reset the three metrics module globals between tests — copy the pattern from `tests/servers/imagen/test_server.py:16-34`

- [x] **Task 8: Run tests and full regression** (AC: #6)
  - [x] `PYTHONPATH="" poetry run pytest tests/servers/places/ -v` — all new tests pass
  - [x] `PYTHONPATH="" poetry run pytest -v` — zero regressions; pre-existing failures in `tests/imagen/test_config.py` (documented in Story 5.1 completion notes) are acceptable and unrelated
  - [x] Record the exact pass/fail counts in the Completion Notes

## Dev Notes

### Architecture Compliance (the hard constraints)

- **Transport:** Streamable HTTP via `FastMCP("places", host="0.0.0.0", port=config.port)` + `mcp.run(transport="streamable-http")` — SSE is deprecated per June 2025 MCP spec revision [Source: architecture-mothership.md#Network Transport]
- **Port:** 8102. Sits inside the auto-assign range 8100-8199 but is explicitly declared to avoid conflicts during parallel dev with Epic 4-6 review
- **Process isolation:** Server runnable standalone via `python -m servers.places.server` — never import anything from `mothership/` or other `servers/*/` [Source: architecture-mothership.md#Architectural Boundaries]
- **Credential flow:** Server reads `.env` directly via `pydantic-settings`. Manager does NOT proxy credentials [Source: architecture-mothership.md#Process Management Architecture]
- **Error hierarchy:** Use `shared/errors.py` typed exceptions internally. Do NOT raise bare `Exception`. Do NOT define new shared errors — `PlaceNotFoundError` stays local to `server.py` [Source: architecture-mothership.md#Enforcement Guidelines]
- **Logging:** `setup_logging(config.log_level, log_name="places")` → writes to `logs/places.log` via `RotatingFileHandler` (5MB, 3 backups) [Source: shared/logging_config.py]
- **Metrics endpoint:** `@mcp.custom_route("/metrics", methods=["GET"])` returning JSON with `snake_case` keys and ISO 8601 `last_request_time` [Source: architecture-mothership.md#Metrics Endpoint Pattern]

### Canonical Reference — `servers/imagen/`

Per John's risk-mitigation note in the Sprint Change Proposal: **model Places after the live Imagen files**, not a theoretical pattern. If Epic 4-6 review surfaces a shape change to `mothership.yaml`, Imagen will be updated and this story can follow. Open these files side-by-side while implementing:

- `servers/imagen/mothership.yaml` — registration shape
- `servers/imagen/config.py` — `BaseServerConfig` extension, YAML section merging
- `servers/imagen/server.py` — top-of-module setup ordering, `@mcp.custom_route("/metrics")` wiring, module-level metrics counters, `__main__` guard

### Tool Return Shape Contract for Stories 7.2 and 7.3

Places tools return `dict` (serialized to JSON by FastMCP) — NOT a `json.dumps(...)` string like Imagen's `generate_image`. This is an intentional divergence: the PRD spec calls for structured `{error, code}` responses on failure, which is cleaner as a native dict.

Every tool in 7.2/7.3 will follow this wrapper pattern:

```python
@mcp.tool()
async def some_tool(...) -> dict:
    global _request_count, _error_count, _last_request_time
    _request_count += 1
    _last_request_time = datetime.now(timezone.utc).isoformat()
    try:
        return await _some_tool_impl(...)
    except Exception as exc:
        _error_count += 1
        return _to_error_response(exc)
```

Story 7.1 delivers the helper (`_to_error_response`) and custom error class (`PlaceNotFoundError`). Stories 7.2 and 7.3 implement `_*_impl` functions that raise typed exceptions from `shared/errors.py` on failure.

### HTTP Client — `httpx` is already available

`httpx` is NOT explicitly declared in `pyproject.toml` but is present as a transitive dependency of `google-genai` and `mcp`. Story 5.2 established this: `mothership/manager.py` already imports and uses `httpx.AsyncClient` for metrics polling. [Source: 5-2-metrics-endpoint-and-tracking.md — Completion Notes]

**Action for Story 7.1:** Do NOT add `httpx` to `pyproject.toml`. Do NOT import it in `server.py` yet — no API calls happen in 7.1. Stories 7.2 and 7.3 will add the import when they implement tools.

### Google Places API (New) — orientation for Stories 7.2 and 7.3

Recorded here so the next story-creation has it on hand. NOT required for 7.1 implementation.

- **Base:** `https://places.googleapis.com/v1`
- **Auth:** `X-Goog-Api-Key: {GOOGLE_PLACES_API_KEY}` header
- **FieldMask:** `X-Goog-FieldMask: places.id,places.displayName,...` header — required on every call; without it the API returns everything and bills the highest SKU tier
- **Text Search (New):** `POST /places:searchText` with JSON body `{"textQuery": "...", "includedType": "restaurant", "maxResultCount": 10, "locationBias": {...}}`
- **Place Details (New):** `GET /places/{placeId}` — placeId does NOT include the `places/` prefix in the URL path, but the API returns `"id": "places/ChIJ..."` in responses. Strip/don't-strip consistently at the boundary.
- **Error codes:** 401/403 → auth; 404 → not found; 429 → quota/rate limit; 5xx → API unavailable

### Files to Create

```
servers/places/__init__.py
servers/places/mothership.yaml
servers/places/config.py
servers/places/server.py
tests/servers/places/__init__.py
tests/servers/places/test_config.py
tests/servers/places/test_error_mapping.py
tests/servers/places/test_server.py
```

### Files to Modify

```
.env.example                  # append GOOGLE_PLACES_API_KEY section (do not touch existing entries)
```

### Files to NOT Modify

- `shared/errors.py` — no new shared errors for this story (YAGNI; `PlaceNotFoundError` is server-local)
- `pyproject.toml` — no new dependencies
- `mothership/*` — zero manager changes; discovery + dashboard must work via convention alone (that's the whole point of Epic 7)
- `servers/imagen/*` — do not alter the reference implementation

### Anti-Patterns to Avoid

- Do NOT use stdio transport — Streamable HTTP only
- Do NOT register Places in `claude_desktop_config.json` — it's a Mothership-managed server, agents connect via the Mothership endpoint
- Do NOT add local caching (`diskcache`, `functools.lru_cache` on tool calls, etc.) — explicitly out of scope per Sprint Change Proposal 2026-04-19
- Do NOT embed the API key in logs, error messages, or test fixtures checked into git
- Do NOT define the structured error response as a dataclass or pydantic model — a plain `dict[str, str]` is the contract
- Do NOT implement `search_places`, `get_place_details`, etc. in this story — they land in Stories 7.2 and 7.3
- Do NOT add a separate FastAPI app for `/metrics` — mount on the FastMCP Starlette app via `@mcp.custom_route`
- Do NOT calculate uptime in the server — the manager owns uptime calculation [Source: architecture-mothership.md#Metrics Collection]

### Previous Story Intelligence (Epic 5)

From Story 5.1 (Imagen transport migration) and Story 5.2 (metrics endpoint):

- **Host/port placement:** Set on `FastMCP(...)` constructor, NOT on `.run(...)`. This is the opposite of what FastMCP's README shows. [Source: 5-1-...md Completion Notes]
- **Starlette app:** `mcp.streamable_http_app()` returns the underlying Starlette app — useful for test harness that wants to hit routes without starting a real server
- **`@mcp.custom_route` is the public API** for adding non-MCP endpoints like `/metrics` — do NOT reach into `mcp._mcp_server` private internals [Source: 5-2-...md Completion Notes]
- **Test runner flag:** `PYTHONPATH=""` is required to avoid ROS plugin conflicts (ament linters are disabled in `pyproject.toml` but env still breaks without the empty override)
- **Test isolation:** Reset module-level globals (`_sessions`, metrics counters) via autouse fixtures — module state leaks across tests otherwise [Source: tests/servers/imagen/test_server.py:22-34]
- **Fixture sequencing:** `_mock_config` must set env vars BEFORE importing the server module. The existing pattern uses a fixture chain `_clear_sessions(_mock_config)` to force ordering — copy it.

### Parallel-Work Risk (from Sprint Change Proposal)

Epics 4-6 are all in `review` while Story 7.1 starts. If a bug fix in review changes the `McpServerConfig` schema in `mothership/discovery.py`, the Places `mothership.yaml` may need a trivial update. Mitigation: Places tracks Imagen's shape exactly — any upstream fix will likely land in Imagen's config too, providing a drop-in pattern to follow. If the reviewer changes `McpServerConfig` fields (`name`, `description`, `entry_point`, `port`, `env_vars`), re-align Places accordingly.

### Testing Standards

- **Framework:** pytest + unittest.mock, matching existing conventions
- **Location:** `tests/servers/places/` mirroring source layout
- **Isolation:** Use `monkeypatch.setenv` for env vars, `tmp_path` for YAML config fixtures
- **Run command:** `PYTHONPATH="" poetry run pytest tests/servers/places/ -v`
- **Coverage expectation:** Every AC has at least one explicit test. Error mapping tests exercise each of the four codes (NOT_FOUND / QUOTA / AUTH / UNKNOWN). Config tests cover env-var loading, YAML merging, and defaults.
- **No live API calls in 7.1.** Live-API smoke testing comes in Story 7.3.

### Project Structure Notes

Full structure alignment verified against `architecture-mothership.md#Complete Project Directory Structure` (lines 441-507 of that doc). No conflicts. `servers/places/` follows the exact shape of `servers/imagen/`. `tests/servers/places/` follows the exact shape of `tests/servers/imagen/`.

### References

- [Source: documents/planning-artifacts/epics.md#Story 7.1 — Places MCP Server Foundation]
- [Source: documents/planning-artifacts/prd.md#Places MCP Capability — PFR41 (startup validation), PFR42 (FieldMask + structured errors)]
- [Source: documents/planning-artifacts/architecture-mothership.md#Network Transport]
- [Source: documents/planning-artifacts/architecture-mothership.md#Error Handling Patterns]
- [Source: documents/planning-artifacts/architecture-mothership.md#Metrics Endpoint Pattern]
- [Source: documents/planning-artifacts/architecture-mothership.md#Structure Patterns — Adding a New MCP Server (7-step checklist, lines 267-274)]
- [Source: documents/planning-artifacts/architecture-mothership.md#Enforcement Guidelines (lines 416-427)]
- [Source: documents/planning-artifacts/architecture-mothership.md#Anti-Patterns to Avoid (lines 428-436)]
- [Source: documents/planning-artifacts/sprint-change-proposal-2026-04-19.md — full proposal for Epic 7 rationale, no-caching decision, Option A choice]
- [Source: servers/imagen/server.py — canonical example for top-of-module setup, metrics counters, /metrics endpoint]
- [Source: servers/imagen/config.py — canonical example for `BaseServerConfig` extension and YAML section merging]
- [Source: servers/imagen/mothership.yaml — canonical registration shape]
- [Source: shared/errors.py — MothershipError hierarchy, CredentialError signature]
- [Source: shared/config.py — BaseServerConfig, YamlSettingsSource, from_yaml entry point]
- [Source: shared/logging_config.py — setup_logging signature and log file routing]
- [Source: documents/implementation-artifacts/5-1-imagen-transport-migration-streamable-http.md — Streamable HTTP migration completion notes]
- [Source: documents/implementation-artifacts/5-2-metrics-endpoint-and-tracking.md — /metrics endpoint pattern and httpx availability]

### Review Findings

Adversarial code review (2026-04-19) — Blind Hunter + Edge Case Hunter + Acceptance Auditor.

- [x] [Review][Patch] Added `TestStartupCredentialValidation::test_missing_api_key_raises_credential_error_at_startup` in `tests/servers/places/test_server.py` — reimports the server module with the env var cleared and cwd set to a fresh tmp_path, asserts `CredentialError` is raised with the credential name in the message.
- [x] [Review][Defer] `test_mcp_server_default_port_is_8102` is environment-dependent — if a `config.yaml` with `places.port` exists in cwd, it overrides the default and the assertion fails [tests/servers/places/test_server.py] — deferred, needs a tmp-dir fixture isolation, not specific to Epic 7.
- [x] [Review][Defer] At startup, `CredentialError` raised at module import causes the subprocess to crash; Mothership's manager reports `status="crashed"` rather than `"misconfigured"`. Requires Mothership-side change — deferred, pre-existing architecture.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context)

### Debug Log References

- `PYTHONPATH="" poetry run pytest tests/servers/places/ -v` — 18/18 passed
- `PYTHONPATH="" poetry run pytest -v` — 218 passed, 2 pre-existing failures in `tests/imagen/test_config.py` (documented in Story 5.1, .env-leaking IMAGEN_API_KEY — unrelated to Places work)
- Discovery verification: `discover_servers(Path("servers"))` returns both `imagen` (port 8101) and `places` (port 8102), confirming AC #4 with no manager code changes.

### Completion Notes List

- Implemented `servers/places/` package skeleton mirroring `servers/imagen/` exactly: `__init__.py`, `mothership.yaml`, `config.py`, `server.py`.
- `PlacesConfig` extends `BaseServerConfig` with `port=8102`, `google_places_api_key`, `places_api_base_url`, `places_http_timeout_seconds`, and a `_PlacesYamlSource` that merges the `places:` section from `config.yaml`.
- `server.py` runs Streamable HTTP on port 8102, validates `GOOGLE_PLACES_API_KEY` at startup (raising `CredentialError` with only the credential name), exposes a zero-state `/metrics` endpoint, and provides the `PlaceNotFoundError` class plus `_to_error_response` translator — the contract Stories 7.2 and 7.3 will consume.
- No tools declared yet — `tools/list` returns empty, as required.
- `.env.example` appended with the `GOOGLE_PLACES_API_KEY` section (existing `IMAGEN_*` entries untouched).
- Tests: 18 new tests across `test_config.py` (5), `test_error_mapping.py` (7), `test_server.py` (6 transport/metrics). Full suite: 218 passed, 2 pre-existing unrelated failures.
- No changes made to `shared/`, `pyproject.toml`, `mothership/`, or `servers/imagen/` — boundaries respected.

### File List

- `servers/places/__init__.py` (new)
- `servers/places/mothership.yaml` (new)
- `servers/places/config.py` (new)
- `servers/places/server.py` (new)
- `tests/servers/places/__init__.py` (new)
- `tests/servers/places/test_config.py` (new)
- `tests/servers/places/test_error_mapping.py` (new)
- `tests/servers/places/test_server.py` (new)
- `.env.example` (modified — appended Google Places section)
- `documents/implementation-artifacts/sprint-status.yaml` (modified — status transitions)
