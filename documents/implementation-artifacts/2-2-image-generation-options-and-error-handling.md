# Story 2.2: Image Generation Options & Error Handling

Status: done

## Story

As a content creator,
I want to control image dimensions, style, and output location, and get clear feedback when something goes wrong,
so that I can fine-tune my generated images and recover from errors quickly.

## Acceptance Criteria

1. **Given** a valid prompt and the `generate_image` tool **When** I specify `width` and `height` parameters **Then** the generated image matches the requested dimensions
2. **Given** a valid prompt and the `generate_image` tool **When** I specify a `style` parameter (e.g., "natural", "digital art") **Then** the generated image reflects the requested artistic direction
3. **Given** a valid prompt and the `generate_image` tool **When** I specify a custom `output_path` **Then** the image is saved to the specified location instead of the default
4. **Given** a prompt that triggers a Vertex AI error (bad prompt, quota exceeded) **When** the API returns an error response **Then** a `GenerationError` is raised with a clear, actionable message **And** no credential values are exposed in the error
5. **Given** the Vertex AI API is unreachable or timing out **When** the tool is invoked **Then** the system waits for the response without a hard timeout **And** if the API ultimately fails, an `ApiUnavailableError` is surfaced clearly

## Tasks / Subtasks

- [x] Task 1: Enhance `generate_image` tool with dimension parameters (AC: #1)
  - [x] Validate `width` and `height` are positive integers within Imagen API supported ranges
  - [x] Pass dimensions to Imagen API `generate_images()` call via `aspect_ratio` or direct width/height parameters (check API support)
  - [x] If Imagen API does not support arbitrary dimensions, map width/height to closest supported aspect ratio and document the mapping
  - [x] Test that dimensions are correctly passed through to the API
- [x] Task 2: Implement style/artistic direction parameter (AC: #2)
  - [x] Research Imagen API support for style parameters — check if `style_preset`, `negative_prompt`, or prompt engineering is the correct approach
  - [x] If API supports native style parameter: pass it directly
  - [x] If API does not support native style: prepend style to prompt (e.g., `"digital art style: {prompt}"`) and document the approach
  - [x] Test style parameter handling for both native and prompt-engineering approaches
- [x] Task 3: Implement custom output path handling (AC: #3)
  - [x] Validate custom `output_path` — ensure parent directory is writable
  - [x] Create parent directories if they don't exist (`os.makedirs` with `exist_ok=True`)
  - [x] Handle edge cases: path exists (overwrite), invalid path characters, relative vs absolute paths
  - [x] Test custom output path with various path formats
- [x] Task 4: Implement comprehensive error handling (AC: #4, #5)
  - [x] Catch `google.api_core.exceptions.PermissionDenied` -> `CredentialError("IMAGEN_GCP_PROJECT", reason="permission denied — check IAM roles")`
  - [x] Catch `google.api_core.exceptions.NotFound` -> `CredentialError("IMAGEN_GCP_PROJECT", reason="project not found or Vertex AI not enabled")`
  - [x] Catch `google.api_core.exceptions.ResourceExhausted` -> `GenerationError("Quota exceeded — ...details...")`
  - [x] Catch `google.api_core.exceptions.InvalidArgument` -> `GenerationError("Invalid request — ...details...")`
  - [x] Catch `google.api_core.exceptions.ServiceUnavailable` / `google.api_core.exceptions.DeadlineExceeded` -> `ApiUnavailableError("Vertex AI API unavailable — ...details...")`
  - [x] Catch generic `google.api_core.exceptions.GoogleAPICallError` as fallback -> map to appropriate error type
  - [x] Catch `ConnectionError`, `TimeoutError`, network errors -> `ApiUnavailableError`
  - [x] NFR5: Do NOT set a timeout on the API call — let it complete or fail naturally
  - [x] Verify NO credential values appear in any error message (hard security requirement)
- [x] Task 5: Write comprehensive tests (AC: #1-#5)
  - [x] `tests/imagen/test_server.py` — extend with:
    - Test dimension parameter validation and pass-through
    - Test style parameter handling (native and prompt-engineering)
    - Test custom output path creation and saving
    - Test each error type mapping: PermissionDenied, NotFound, ResourceExhausted, InvalidArgument, ServiceUnavailable, DeadlineExceeded
    - Test that error messages never contain credential values
    - Test that no timeout is imposed on API calls
    - Test file overwrite behavior with existing output path
  - [x] All mocked at the Vertex AI boundary — no real API calls
- [x] Task 6: Run full test suite and verify no regressions (AC: #1-#5)
  - [x] Run `poetry run pytest tests/imagen/ -v`
  - [x] Run `poetry run pytest -v` (full suite) to verify zero regressions

## Dev Notes

### Architecture Compliance

- **All changes in `servers/imagen/server.py`** — this story extends the tool created in Story 2.1
- **Error handling uses ONLY typed exceptions from `shared/errors.py`** — CredentialError, ApiUnavailableError, GenerationError
- **Credential safety is a HARD requirement (NFR1-NFR3, NFR6)** — no credential values in error messages, ever
- **No timeout on API calls (NFR5)** — user waits for result; if API fails, surface clear error
- **Logging to stderr only** — stdout reserved for MCP stdio

### Vertex AI Error Handling Reference

The `google-cloud-aiplatform` library raises exceptions from `google.api_core.exceptions`. Key exception classes:

| Exception | HTTP Code | Maps To |
|-----------|-----------|---------|
| `PermissionDenied` | 403 | `CredentialError` |
| `NotFound` | 404 | `CredentialError` (project/API not found) |
| `InvalidArgument` | 400 | `GenerationError` (bad prompt/params) |
| `ResourceExhausted` | 429 | `GenerationError` (quota exceeded) |
| `ServiceUnavailable` | 503 | `ApiUnavailableError` |
| `DeadlineExceeded` | 504 | `ApiUnavailableError` |
| `GoogleAPICallError` | * | Fallback — map by context |

### Imagen API Dimension Handling

Imagen 3 supports generating images at specific aspect ratios rather than arbitrary pixel dimensions. Supported aspect ratios include: `1:1`, `9:16`, `16:9`, `3:4`, `4:3`. The developer should:

1. Check if the API accepts `width`/`height` directly, or only `aspect_ratio`
2. If only aspect ratio: calculate the closest supported ratio from the requested width/height
3. Document the mapping clearly in the tool docstring so users know the constraint

### Imagen API Style Handling

Imagen 3 does not have a dedicated `style` parameter. Style direction is applied through prompt engineering:
- Prepend or append style instructions to the prompt text
- Example: `"digital art style: a cat sitting on a rainbow"` or `"a cat sitting on a rainbow, in the style of digital art"`
- Document this approach in the tool docstring

### Existing Codebase — What Story 2.1 Creates

**servers/imagen/config.py** — `ImagenConfig(BaseServerConfig)`:
- `imagen_gcp_project: str` (required)
- `imagen_gcp_region: str = "us-central1"`
- `imagen_model: str = "imagen-3.0-generate-002"`
- `default_output_dir: str = "./output"`
- `default_width: int = 1024`
- `default_height: int = 1024`
- Env prefix: `IMAGEN_`

**servers/imagen/server.py** — FastMCP server with:
- `generate_image(prompt, width, height, style, output_path)` tool
- Basic Vertex AI integration
- `mcp.run()` entry point

**This story EXTENDS the existing tool** — do NOT rewrite server.py from scratch. Enhance the existing `generate_image` function with better parameter handling and comprehensive error handling.

### Previous Story Learnings

- **Config pattern:** `from_yaml()` class method handles dual-layer loading correctly. Subclasses with `env_prefix` work with the inherited `settings_customise_sources`.
- **Test pattern:** Use `tmp_path`, `monkeypatch` for isolated testing. Mock at the external boundary.
- **pytest ROS issue:** Already handled — use `PYTHONPATH="" poetry run pytest` or the addopts in pyproject.toml.

### Testing Strategy

- **Mock boundary:** Mock `vertexai.init`, `ImageGenerationModel.from_pretrained`, `model.generate_images`, and `image.save`
- **Error simulation:** Configure mocks to raise `google.api_core.exceptions.*` to test error mapping
- **Credential safety tests:** For each error path, verify the error message does NOT contain any value from config that could be a credential
- **No timeout test:** Verify that the API call does not have a `timeout` parameter set

### Anti-Patterns to Avoid

- Do NOT add a timeout to API calls — NFR5 explicitly prohibits this
- Do NOT create new error classes — use existing ones from `shared/errors.py`
- Do NOT modify `shared/` modules — they are complete
- Do NOT log credential values — hard security requirement
- Do NOT use bare `try: ... except Exception:` — catch specific exception types
- Do NOT implement retry logic — keep it simple for MVP

### Project Structure Notes

Files modified in this story:

```
servers/imagen/
├── server.py            # MODIFIED — enhanced generate_image with dimension/style/error handling

tests/imagen/
├── test_server.py       # MODIFIED — extended with dimension, style, output path, error handling tests
```

No new files should be needed — this story enhances what Story 2.1 creates.

### References

- [Source: documents/planning-artifacts/architecture.md#MCP Tool Patterns — Tool Definition Shape]
- [Source: documents/planning-artifacts/architecture.md#Error Handling Patterns — Error Class Hierarchy and Error Flow]
- [Source: documents/planning-artifacts/epics.md#Story 2.2: Image Generation Options & Error Handling]
- [Source: documents/planning-artifacts/prd.md#Functional Requirements — FR2, FR3, FR4, FR12]
- [Source: documents/planning-artifacts/prd.md#Non-Functional Requirements — NFR5, NFR6]
- [Source: documents/planning-artifacts/prd.md#Non-Functional Requirements — NFR1-NFR3 Security]

### Review Findings

- [x] [Review][Decision] **Path traversal via user-controlled `output_path`** — FIXED: Output path sandboxed to `config.default_output_dir`. Paths outside the allowed directory are rejected with `GenerationError`. (blind+edge)
- [x] [Review][Decision] **`vertexai.init()` called on every tool invocation** — FIXED: Moved to module-level startup per Google's recommendation. Called once, not per-request. (blind+edge)
- [x] [Review][Patch] **CredentialError reason field leaks raw exception messages** — FIXED: All `CredentialError` reason fields now use static sanitized messages, never raw `str(e)`. Added test verifying raw exception content is absent from error messages. (blind+edge+auditor)
- [x] [Review][Patch] **`image.save()` OSError and `response.images` None unhandled** — FIXED: Added `TypeError` to the catch for None images, added `OSError` catch for save failures. Both map to `GenerationError`. Added tests for both cases. (edge)
- [x] [Review][Patch] **Empty or whitespace-only prompt not validated** — FIXED: Added `if not prompt.strip()` guard at top of `generate_image`. `_sanitize_filename` now returns "untitled" for empty results. Added `TestPromptValidation` tests. (blind+edge)
- [x] [Review][Patch] **Bare `except Exception` fallback handlers remain** — FIXED: Removed all bare `except Exception` from generation path. `vertexai.init` moved to startup with `GoogleAPICallError` catch. `from_pretrained` now catches `GoogleAPICallError` as fallback. (auditor)
- [x] [Review][Patch] **Missing `servers/__init__.py`** — FIXED: Created `servers/__init__.py`. (blind)
- [x] [Review][Patch] **Add unit tests for `_sanitize_filename` with adversarial input** — FIXED: Added `TestSanitizeFilename` class with 6 tests: normal text, special chars, all-special (untitled fallback), empty string, long text truncation, unicode. (blind+edge)
- [x] [Review][Patch] **Add `GoogleAPICallError` catch to `from_pretrained()` block** — FIXED: Added `GoogleAPICallError` catch to model loading. `vertexai.init` moved to startup with its own `GoogleAPICallError` catch. (auditor)
- [x] [Review][Defer] **Global `_yaml_config_path` is a concurrency hazard** [shared/config.py:127] — deferred, pre-existing from story 1.2 design
- [x] [Review][Defer] **Module-level config causes import-time side effects** [servers/imagen/server.py:33] — deferred, pre-existing from story 2.1. Spec explicitly allows "module level or startup function"
- [x] [Review][Defer] **`.env` and `config.yaml` resolved relative to CWD** [shared/config.py, servers/imagen/server.py:33] — deferred, pre-existing pattern across all stories
- [x] [Review][Defer] **Unpinned dependency versions (`pydantic-settings = "*"`, `pyyaml = "*"`)** [pyproject.toml] — deferred, mitigated by poetry.lock
- [x] [Review][Defer] **`config.yaml` missing `imagen_model` and `imagen_gcp_region` documentation** [config.yaml] — deferred, documentation gap

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6 (1M context)

### Debug Log References
- Imagen 3 API uses `aspect_ratio` parameter only (not raw width/height). Implemented `_map_dimensions_to_aspect_ratio()` to find closest match from supported set.
- Imagen 3 has no native style parameter. Style applied via prompt engineering: `"{style} style: {prompt}"`. "natural" and empty string pass prompt through unchanged.
- Replaced generic `except Exception` string-matching error handling with specific `google.api_core.exceptions` catches for type-safe error mapping.

### Completion Notes List
- Task 1: Added `SUPPORTED_ASPECT_RATIOS` constant and `_map_dimensions_to_aspect_ratio()` function. Maps width/height to closest of 1:1, 9:16, 16:9, 4:3, 3:4. Validates positive integers. 7 new tests.
- Task 2: Style applied via prompt engineering — non-"natural" styles prepended as `"{style} style: {prompt}"`. 3 new tests.
- Task 3: Enhanced output path handling — relative paths resolved to absolute via `os.path.abspath()`, parent directory writability check added, existing files overwritten. 4 new tests.
- Task 4: Replaced generic exception catching with specific `google.api_core.exceptions`: PermissionDenied/NotFound -> CredentialError, ResourceExhausted/InvalidArgument -> GenerationError, ServiceUnavailable/DeadlineExceeded -> ApiUnavailableError, GoogleAPICallError -> GenerationError fallback, ConnectionError/TimeoutError -> ApiUnavailableError. Updated 2 existing tests to use specific exceptions.
- Task 5: 23 new tests total (32 in test_server.py, up from 9). Added TestDimensionMapping (7), TestStyleParameter (3), TestOutputPathHandling (4), 7 new error type tests, TestCredentialSafety (2), TestNoTimeout (1).
- Task 6: Full regression suite — 100/100 tests pass (32 server + 10 config + 58 existing).

### Change Log
- 2026-04-01: Story 2.2 implementation complete — dimension mapping, style prompt engineering, output path validation, comprehensive google.api_core error handling
- 2026-04-01: Code review findings resolved — 9 patches applied (path traversal sandbox, vertexai.init startup, credential leak fix, OSError/TypeError handling, prompt validation, sanitize filename fallback, servers/__init__.py, adversarial tests, GoogleAPICallError catches). 5 items deferred.

### File List
- `servers/imagen/server.py` — MODIFIED (dimension mapping, style prompt engineering, output path sandboxing, comprehensive error handling, module-level vertexai.init, prompt validation)
- `servers/__init__.py` — NEW (package init)
- `tests/imagen/test_server.py` — MODIFIED (42 tests: dimensions, style, output paths, path traversal, prompt validation, sanitize filename, error types, credential safety, no-timeout)
