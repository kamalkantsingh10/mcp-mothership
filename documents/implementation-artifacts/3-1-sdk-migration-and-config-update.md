# Story 3.1: SDK Migration & Config Update

Status: review

## Story

As a developer,
I want to swap the deprecated `google-cloud-aiplatform` SDK for `google-genai` and update the server config to target Nano Banana Pro,
so that the project is on a supported SDK before the Imagen API shuts down (June 2026).

## Acceptance Criteria

1. **Given** `pyproject.toml` dependencies **When** the migration is complete **Then** `google-cloud-aiplatform` is removed and `google-genai>=1.0.0` is added **And** `poetry install` succeeds cleanly
2. **Given** `servers/imagen/config.py` with `ImagenConfig` **When** the server starts **Then** the default model is `gemini-3-pro-image-preview` **And** all existing config fields still load from `.env` and `config.yaml`
3. **Given** `servers/imagen/server.py` **When** the server initializes **Then** a `genai.Client(vertexai=True, ...)` is created at module level using config values **And** no references to `vertexai.init` or `ImageGenerationModel` remain
4. **Given** `tests/imagen/` **When** I run `poetry run pytest tests/imagen/` **Then** all tests pass with the new SDK mocked at the `genai.Client` boundary

## Tasks / Subtasks

- [x] Task 1: Swap SDK dependency in pyproject.toml (AC: #1)
  - [x] Remove `google-cloud-aiplatform = ">=1.60.0"` from `[tool.poetry.dependencies]`
  - [x] Add `google-genai = ">=1.0.0"` to `[tool.poetry.dependencies]`
  - [x] Run `poetry lock` and `poetry install` to verify clean install
  - [x] Verify no import errors from `google.genai` in a quick smoke test
- [x] Task 2: Update `servers/imagen/config.py` — change default model (AC: #2)
  - [x] Change `imagen_model` default from `"imagen-3.0-generate-002"` to `"gemini-3-pro-image-preview"`
  - [x] Verify `ImagenConfig` still loads all fields from `.env` and `config.yaml`
  - [x] Update `tests/imagen/test_config.py` to assert new default model value
- [x] Task 3: Rewrite `servers/imagen/server.py` — replace Imagen SDK with google-genai (AC: #3)
  - [x] Remove imports: `vertexai`, `google.api_core.exceptions`, `ImageGenerationModel`
  - [x] Add imports: `from google import genai`, `from google.genai import types, errors`
  - [x] Replace module-level `vertexai.init(...)` with `genai.Client(vertexai=True, project=config.imagen_gcp_project, location=config.imagen_gcp_region)`
  - [x] Remove `SUPPORTED_ASPECT_RATIOS` constant and `_map_dimensions_to_aspect_ratio()` function (Gemini handles dimensions natively via `image_config`)
  - [x] Replace `generate_image` tool internals: use `client.models.generate_content()` with `response_modalities=["TEXT", "IMAGE"]` for single-shot generation (session support comes in Story 3.2)
  - [x] Update response handling: extract image from `response.parts` using `part.as_image()` pattern, save with PIL `image.save()`
  - [x] Update error handling: replace `google.api_core.exceptions.*` catches with `google.genai.errors.ClientError` and `google.genai.errors.ServerError` — map to same typed exceptions from `shared/errors.py`
  - [x] Keep existing: prompt validation, style prompt engineering, output path sandboxing, `_sanitize_filename`
  - [x] Keep `if __name__ == "__main__": mcp.run(transport="stdio")` entry point
- [x] Task 4: Rewrite `tests/imagen/test_server.py` — new mock boundary (AC: #4)
  - [x] Replace `mock_vertex_stack` fixture: mock `genai.Client` and its return values instead of `vertexai`/`ImageGenerationModel`
  - [x] Update `TestGenerateImageSuccess` tests to assert `client.models.generate_content()` calls
  - [x] Update `TestGenerateImageErrors` tests to use `google.genai.errors.ClientError` and `ServerError` instead of `google.api_core.exceptions`
  - [x] Keep all existing test classes: `TestDimensionMapping` (update to test Gemini dimension params), `TestStyleParameter`, `TestOutputPathHandling`, `TestPromptValidation`, `TestSanitizeFilename`, `TestCredentialSafety`, `TestNoTimeout`
  - [x] Remove aspect ratio mapping tests (no longer applicable)
  - [x] Add dimension pass-through tests (verify width/height passed via `image_config`)
- [x] Task 5: Run full test suite and verify no regressions (AC: #1-#4)
  - [x] Run `poetry run pytest tests/imagen/ -v`
  - [x] Run `poetry run pytest -v` (full suite) to verify zero regressions

## Dev Notes

### Architecture Compliance

- **SDK swap is clean replacement** — remove `google-cloud-aiplatform`, add `google-genai`. Do NOT keep both.
- **Error handling uses ONLY typed exceptions from `shared/errors.py`** — CredentialError, ApiUnavailableError, GenerationError. No new error classes.
- **Credential safety is a HARD requirement (NFR1-NFR3)** — no credential values in error messages, ever. Use static reason strings in `CredentialError`, never raw `str(e)`.
- **No timeout on API calls (NFR5)** — user waits for result; if API fails, surface clear error.
- **Logging to stderr only** — stdout reserved for MCP stdio.
- **Do NOT modify any `shared/` module files** — they are stable from Story 1.2.
- **This story is single-shot only** — session/chat support comes in Story 3.2. Use `client.models.generate_content()`, NOT `client.chats.create()`.

### google-genai SDK Reference

**Package:** `google-genai` (PyPI, latest stable ~1.70.0)

**Initialization:**
```python
from google import genai
from google.genai import types, errors

client = genai.Client(
    vertexai=True,
    project=config.imagen_gcp_project,
    location=config.imagen_gcp_region,
)
```

**Single-shot image generation (this story):**
```python
response = client.models.generate_content(
    model=config.imagen_model,
    contents=effective_prompt,
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
    ),
)
```

**Dimension/aspect ratio via image_config:**
```python
config=types.GenerateContentConfig(
    response_modalities=["TEXT", "IMAGE"],
    image_config=types.ImageConfig(
        aspect_ratio="16:9",  # or "1:1", "9:16", "4:3", "3:4"
    ),
)
```

**Response handling — extract image:**
```python
for part in response.parts:
    if part.text is not None:
        logger.info("Model response: %s", part.text)
    elif image := part.as_image():
        image.save(output_path_resolved)
```

**IMPORTANT:** `part.as_image()` returns a PIL Image object. The `Pillow` library is a transitive dependency of `google-genai` — do NOT add it to pyproject.toml.

### google-genai Exception Hierarchy

The SDK uses its **own** exceptions in `google.genai.errors` — NOT `google.api_core.exceptions`:

```
errors.APIError          — base for all API errors (has .code, .message, .status)
  errors.ClientError     — 4xx errors (400, 401, 403, 404, 429)
  errors.ServerError     — 5xx errors (500, 503)
```

**Error mapping for this project:**

| google.genai Exception | HTTP Code | Maps To |
|------------------------|-----------|---------|
| `ClientError` with code 403 | 403 | `CredentialError("IMAGEN_GCP_PROJECT", reason="permission denied — check IAM roles")` |
| `ClientError` with code 404 | 404 | `CredentialError("IMAGEN_GCP_PROJECT", reason="project not found or API not enabled")` |
| `ClientError` with code 400 | 400 | `GenerationError("Invalid request — check prompt and parameters")` |
| `ClientError` with code 429 | 429 | `GenerationError("Quota exceeded — try again later")` |
| `ServerError` (any) | 5xx | `ApiUnavailableError("Vertex AI API unavailable")` |
| `APIError` (fallback) | * | `GenerationError("Image generation failed")` |
| `ConnectionError`, `TimeoutError` | N/A | `ApiUnavailableError("Network error during image generation")` |

**CRITICAL:** Use `e.code` to distinguish ClientError subtypes. Do NOT use string matching on error messages. Example:
```python
except errors.ClientError as e:
    if e.code == 403:
        raise CredentialError("IMAGEN_GCP_PROJECT", reason="permission denied — check IAM roles") from e
    elif e.code == 404:
        raise CredentialError("IMAGEN_GCP_PROJECT", reason="project not found or API not enabled") from e
    elif e.code == 429:
        raise GenerationError("Quota exceeded — try again later") from e
    else:
        raise GenerationError(f"Invalid request — check prompt and parameters") from e
```

### Dimension Handling Change

**Old (Imagen):** Required manual aspect ratio mapping from width/height. Used `SUPPORTED_ASPECT_RATIOS` constant and `_map_dimensions_to_aspect_ratio()` helper.

**New (Gemini):** Pass dimensions via `types.ImageConfig(aspect_ratio="16:9")`. The `_map_dimensions_to_aspect_ratio()` function can be kept for mapping user width/height to Gemini's supported ratios, OR removed if you pass width/height directly. Gemini supports: `1:1`, `9:16`, `16:9`, `4:3`, `3:4`.

**Decision:** Keep `_map_dimensions_to_aspect_ratio()` — it's useful and well-tested. Pass the result into `image_config`.

### Style Handling — No Change

Nano Banana Pro does NOT have a native style parameter either. Keep the existing prompt engineering approach: `"{style} style: {prompt}"` for non-"natural" styles.

### Existing Codebase — What's Already Built

**shared/config.py** — `BaseServerConfig(BaseSettings)` with `from_yaml()`, custom `YamlSettingsSource`. Unchanged.

**shared/errors.py** — Error hierarchy: `EngagementManagerError` → `ConfigurationError`, `ApiUnavailableError`, `CredentialError`, `GenerationError`. Unchanged.

**shared/logging.py** — `setup_logging(log_level)` → stderr only. Unchanged.

**servers/imagen/config.py** — `ImagenConfig(BaseServerConfig)` with custom `_ImagenYamlSource`. Only change: default model value.

**servers/imagen/server.py** — Current state uses `vertexai` + `ImageGenerationModel`. This file gets a significant rewrite.

**tests/imagen/test_server.py** — 42 tests. Mock boundary shifts from `vertexai`/`ImageGenerationModel` to `genai.Client`.

**tests/imagen/test_config.py** — 10 tests. Minor update for new default model value.

### Previous Story Learnings

- **pydantic-settings init kwargs have HIGHEST priority** — `from_yaml()` handles this correctly via custom `YamlSettingsSource`. No changes needed to config loading.
- **ROS Jazzy pytest plugins conflict** — already handled via `addopts` in pyproject.toml.
- **Run tests with `PYTHONPATH="" poetry run pytest`** to avoid ROS system path pollution.
- **Config loaded at module level** — importing server.py requires `IMAGEN_GCP_PROJECT` env var. Tests use `autouse` fixture with `monkeypatch.setenv`.
- **Credential safety in error handlers** — always use static reason strings, never `f"...{e}"` in `CredentialError` reason. This was a code review finding that was fixed.
- **Output path sandboxing** — custom paths must be within `config.default_output_dir`. This logic is unchanged.

### Testing Strategy

- **New mock boundary:** Mock `genai.Client` and its methods. The client is created at module level, so mock `servers.imagen.server.genai.Client` or patch the module-level `client` object.
- **Response mock structure:** Create mock response with `.parts` list, each part having `.text` or `.as_image()` returning a mock PIL Image.
- **Error simulation:** Configure mocks to raise `google.genai.errors.ClientError(code, message)` and `ServerError(code, message)`.
- **Keep existing test patterns:** `tmp_path`, `monkeypatch` for isolated testing. `autouse` fixture for env var.

### Anti-Patterns to Avoid

- Do NOT keep `google-cloud-aiplatform` alongside `google-genai` — clean swap
- Do NOT import from `vertexai` or `google.api_core` — all replaced
- Do NOT implement chat/session support — that's Story 3.2
- Do NOT modify `shared/` modules — they are stable
- Do NOT add `Pillow` to dependencies — it's a transitive dep of `google-genai`
- Do NOT use string matching on error messages for error classification — use `e.code`
- Do NOT use bare `except Exception` — catch specific `errors.ClientError`, `errors.ServerError`
- Do NOT include raw exception messages in `CredentialError` reason — use static strings

### Environment Variables

| Variable | Source | Required | Description |
|----------|--------|----------|-------------|
| `IMAGEN_GCP_PROJECT` | `.env` | Yes | GCP project ID for Vertex AI |
| `IMAGEN_GCP_REGION` | `.env` or `config.yaml` | No (default: us-central1) | GCP region |
| `IMAGEN_MODEL` | `config.yaml` | No (default: gemini-3-pro-image-preview) | Model ID |

### Project Structure Notes

Files modified in this story:

```
pyproject.toml                # MODIFIED — swap google-cloud-aiplatform → google-genai
poetry.lock                   # MODIFIED — regenerated
servers/imagen/config.py      # MODIFIED — new default model value
servers/imagen/server.py      # MODIFIED — rewrite to use google-genai SDK
tests/imagen/test_config.py   # MODIFIED — update default model assertion
tests/imagen/test_server.py   # MODIFIED — new mock boundary, updated error types
```

No new files needed. No files deleted.

### References

- [Source: documents/planning-artifacts/architecture.md#Nano Banana Pro Migration — Architecture Addendum]
- [Source: documents/planning-artifacts/architecture.md#SDK Migration Decision]
- [Source: documents/planning-artifacts/architecture.md#Error Handling Changes]
- [Source: documents/planning-artifacts/architecture.md#Config Changes]
- [Source: documents/planning-artifacts/architecture.md#Testing Strategy Changes]
- [Source: documents/planning-artifacts/epics.md#Story 3.1: SDK Migration & Config Update]
- [Source: documents/planning-artifacts/prd.md#Non-Functional Requirements — NFR1-NFR3 Security]
- [Source: documents/planning-artifacts/prd.md#Non-Functional Requirements — NFR5 No Timeout]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- All 109 tests pass with zero regressions after full SDK migration

### Completion Notes List

- **Task 1:** Swapped `google-cloud-aiplatform` for `google-genai>=1.0.0` in pyproject.toml. Poetry lock/install clean. Smoke test confirmed `google.genai` imports work.
- **Task 2:** Changed `imagen_model` default from `imagen-3.0-generate-002` to `gemini-3-pro-image-preview`. Updated test assertion. 10/10 config tests pass.
- **Task 3:** Rewrote `server.py` — replaced `vertexai.init()` with `genai.Client(vertexai=True, ...)`, replaced `ImageGenerationModel.from_pretrained()/generate_images()` with `client.models.generate_content()` using `GenerateContentConfig` with `response_modalities=["TEXT","IMAGE"]` and `ImageConfig(aspect_ratio=...)`. Updated response handling to iterate `response.parts` and use `part.as_image()`. Replaced all `google.api_core.exceptions` error handling with `google.genai.errors.ClientError/ServerError/APIError` using `e.code` dispatch. Kept `_map_dimensions_to_aspect_ratio()`, `_sanitize_filename()`, prompt validation, style engineering, output path sandboxing unchanged.
- **Task 4:** Rewrote `test_server.py` — replaced `mock_vertex_stack` fixture with `mock_genai_stack` that patches `servers.imagen.server.client`. Updated all success tests to assert `client.models.generate_content()` calls and verify `GenerateContentConfig`/`ImageConfig` params. Replaced all `google.api_core.exceptions` error tests with `google.genai.errors` equivalents using `e.code` for ClientError subtypes. Added `TestDimensionPassThrough` class for image_config verification. Removed old aspect ratio mapping tests that tested `generate_images()` kwargs. 41/41 server tests pass.
- **Task 5:** Full suite: 109/109 pass, zero regressions.

### Change Log

- 2026-04-01: Story 3.1 implementation complete — SDK migrated from google-cloud-aiplatform to google-genai, default model updated to gemini-3-pro-image-preview, server.py rewritten for new SDK, all tests updated and passing.

### File List

- `pyproject.toml` — MODIFIED: swapped google-cloud-aiplatform for google-genai
- `poetry.lock` — MODIFIED: regenerated
- `servers/imagen/config.py` — MODIFIED: default model changed to gemini-3-pro-image-preview
- `servers/imagen/server.py` — MODIFIED: rewritten to use google-genai SDK
- `tests/imagen/test_config.py` — MODIFIED: updated default model assertion
- `tests/imagen/test_server.py` — MODIFIED: new mock boundary, updated error types, added dimension pass-through tests
