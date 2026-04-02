# Story 2.1: Imagen MCP Server with Basic Image Generation

Status: done

## Story

As a content creator,
I want to submit a text prompt and receive a generated image,
so that I can create visual content for my posts without leaving Claude Code.

## Acceptance Criteria

1. **Given** a configured Imagen MCP server with valid GCP credentials **When** I call the `generate_image` tool with a text prompt **Then** the system calls Vertex AI Imagen API and generates a single image **And** the image is stored locally in the default output directory **And** the file path is returned to the user
2. **Given** the Imagen MCP server is registered in Claude Code's MCP config **When** Claude Code starts **Then** the server connects via stdio transport **And** the `generate_image` tool is available
3. **Given** `servers/imagen/config.py` with `ImagenConfig` extending `BaseServerConfig` **When** the server starts **Then** GCP project, region, and model settings are validated via pydantic-settings
4. **Given** `tests/imagen/` with test files **When** I run `poetry run pytest tests/imagen/` **Then** all server tests pass with Vertex AI API calls mocked

## Tasks / Subtasks

- [x] Task 1: Add `google-cloud-aiplatform` dependency (AC: #1)
  - [x] Add `google-cloud-aiplatform` to pyproject.toml Poetry dependencies
  - [x] Run `poetry lock` and `poetry install` to verify clean install
- [x] Task 2: Implement `servers/imagen/config.py` — ImagenConfig (AC: #3)
  - [x] Create `ImagenConfig(BaseServerConfig)` with fields: `imagen_gcp_project: str`, `imagen_gcp_region: str = "us-central1"`, `imagen_model: str = "imagen-3.0-generate-002"`, `default_output_dir: str = "./output"`, `default_width: int = 1024`, `default_height: int = 1024`
  - [x] Set `model_config` with `env_prefix = "IMAGEN_"` so env vars map as `IMAGEN_GCP_PROJECT`, `IMAGEN_GCP_REGION`, etc.
  - [x] Ensure config loads from both `.env` (secrets) and `config.yaml` `imagen:` section (operational settings) via inherited `from_yaml()`
- [x] Task 3: Implement `servers/imagen/server.py` — FastMCP server with `generate_image` tool (AC: #1, #2)
  - [x] Import and instantiate `FastMCP("imagen")` server
  - [x] Load config via `ImagenConfig.from_yaml()` at module level or in a startup function
  - [x] Initialize `setup_logging(config.log_level)` for stderr logging
  - [x] Implement `@mcp.tool() async def generate_image(prompt: str, width: int = 1024, height: int = 1024, style: str = "natural", output_path: str | None = None) -> str`
  - [x] Inside `generate_image`: initialize Vertex AI with `vertexai.init(project=config.imagen_gcp_project, location=config.imagen_gcp_region)`
  - [x] Load model via `ImageGenerationModel.from_pretrained(config.imagen_model)`
  - [x] Call `model.generate_images(prompt=prompt, number_of_images=1)` to generate a single image
  - [x] Determine output path: use `output_path` if provided, else `config.default_output_dir/{timestamp}_{sanitized_prompt}.png`
  - [x] Ensure output directory exists (`os.makedirs` with `exist_ok=True`)
  - [x] Save image using `response.images[0].save(output_path_resolved)`
  - [x] Return the absolute file path as a string
  - [x] Add `if __name__ == "__main__": mcp.run(transport="stdio")` entry point for stdio transport
- [x] Task 4: Implement error handling in server.py (AC: #1)
  - [x] Wrap Vertex AI calls in try/except
  - [x] Catch authentication/permission errors -> raise `CredentialError("IMAGEN_GCP_PROJECT", reason="...")`
  - [x] Catch API unavailable/network errors -> raise `ApiUnavailableError("...")`
  - [x] Catch generation failures (bad prompt, quota, model errors) -> raise `GenerationError("...")`
  - [x] Catch `ConfigurationError` on startup if config validation fails
  - [x] Never include credential values in any error message
- [x] Task 5: Write tests in `tests/imagen/` (AC: #4)
  - [x] `tests/imagen/test_config.py` — test ImagenConfig validation, defaults, env var loading, missing required fields
  - [x] `tests/imagen/test_server.py` — test `generate_image` tool with mocked Vertex AI API: successful generation, file saving, error scenarios (API unavailable, bad prompt, credential errors)
  - [x] Mock `vertexai.init` and `ImageGenerationModel.from_pretrained` in all server tests
  - [x] Test that output directory is created if it doesn't exist
  - [x] Test that default and custom output paths work correctly
- [x] Task 6: Run full test suite and verify no regressions (AC: #4)
  - [x] Run `poetry run pytest tests/imagen/ -v`
  - [x] Run `poetry run pytest -v` (full suite) to verify no regressions against story 1.1/1.2 tests

## Dev Notes

### Architecture Compliance

- **Server location:** `servers/imagen/server.py` and `servers/imagen/config.py` — per monorepo pattern in architecture.md
- **Config inheritance:** `ImagenConfig` MUST extend `BaseServerConfig` from `shared/config.py` — this is the established pattern
- **Error handling:** Use ONLY typed exceptions from `shared/errors.py` — never `raise Exception(...)` or `raise ValueError(...)`
- **Logging:** Use `shared/logging.py` `setup_logging()` for stderr-only output. Use `logger = logging.getLogger(__name__)` per module.
- **stdout is RESERVED for MCP stdio protocol** — never use `print()`, never log to stdout

### Key Dependencies & Versions

| Package | Version | Purpose |
|---------|---------|---------|
| `google-cloud-aiplatform` | `>=1.60.0` | Vertex AI SDK with ImageGenerationModel |
| `mcp` | `>=1.26.0` | MCP SDK with FastMCP (already installed) |
| `pydantic-settings` | latest | Config validation (already installed) |

### Vertex AI Imagen API Pattern

```python
import vertexai
from vertexai.preview.vision_models import ImageGenerationModel
# NOTE: Import may be vertexai.vision_models (GA) or vertexai.preview.vision_models
# depending on library version. Try GA first, fall back to preview.

# Initialize Vertex AI
vertexai.init(project="your-project-id", location="us-central1")

# Load model
model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-002")

# Generate — uses aspect_ratio, NOT raw width/height
response = model.generate_images(
    prompt="a cat sitting on a rainbow",
    number_of_images=1,
    aspect_ratio="1:1",  # Supported: "1:1", "9:16", "16:9", "4:3", "3:4"
    safety_filter_level="block_some",
    person_generation="allow_adult",
)

# Save — GeneratedImage has .save() method
response.images[0].save("output.png")
```

**IMPORTANT — Dimension handling:** Imagen 3 uses `aspect_ratio` parameter, NOT arbitrary pixel dimensions. Supported ratios: `1:1`, `9:16`, `16:9`, `4:3`, `3:4`. Map user-requested width/height to the closest supported aspect ratio. This story should use a sensible default (e.g., `1:1`). Story 2.2 will implement the full dimension mapping.

**Authentication:** The `google-cloud-aiplatform` library uses Application Default Credentials (ADC). The user must have:
- `gcloud auth application-default login` executed, OR
- `GOOGLE_APPLICATION_CREDENTIALS` env var pointing to a service account JSON

**Required IAM role:** `roles/aiplatform.user` on the project.
**Required API:** `aiplatform.googleapis.com` must be enabled on the GCP project.

Note: `IMAGEN_GCP_PROJECT` in `.env` is for config validation and `vertexai.init()`. The actual GCP auth is handled by ADC, not by passing API keys directly.

### FastMCP Server Pattern

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("imagen")

@mcp.tool()
async def generate_image(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    style: str = "natural",
    output_path: str | None = None,
) -> str:
    """Generate an image from a text prompt using Vertex AI Imagen.

    Args:
        prompt: Text description of the image to generate.
        width: Image width in pixels.
        height: Image height in pixels.
        style: Artistic style direction.
        output_path: Custom file path for the generated image.
    """
    # Implementation here
    ...

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

**MCP Registration:** To register in Claude Code, add to `.mcp.json` (project-level) or `~/.mcp.json` (global):

```json
{
  "mcpServers": {
    "imagen": {
      "type": "stdio",
      "command": "poetry",
      "args": ["run", "python", "servers/imagen/server.py"],
      "env": {
        "IMAGEN_GCP_PROJECT": "${IMAGEN_GCP_PROJECT}"
      }
    }
  }
}
```

Or via CLI: `claude mcp add imagen -- poetry run python servers/imagen/server.py`

### ImagenConfig Pattern

```python
from shared.config import BaseServerConfig
from pydantic_settings import SettingsConfigDict

class ImagenConfig(BaseServerConfig):
    model_config = SettingsConfigDict(
        env_prefix="IMAGEN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    imagen_gcp_project: str           # Required — from IMAGEN_GCP_PROJECT env var
    imagen_gcp_region: str = "us-central1"
    imagen_model: str = "imagen-3.0-generate-002"
    default_output_dir: str = "./output"
    default_width: int = 1024
    default_height: int = 1024
```

**Config loading in server.py:**
```python
config = ImagenConfig.from_yaml(config_path="config.yaml")
```

This merges: env vars (IMAGEN_*) > .env file > config.yaml `imagen:` section > defaults.

### Existing Codebase — What's Already Built (Stories 1.1 & 1.2)

**shared/config.py** — `BaseServerConfig(BaseSettings)` with:
- `from_yaml(config_path, **overrides)` class method
- Custom `YamlSettingsSource` for YAML loading
- Priority: init > env > .env > yaml > defaults
- `settings_customise_sources()` override for proper source ordering
- `model_config` with `env_file=".env"`, `extra="ignore"`
- **IMPORTANT:** The `_yaml_config_path` module-level global is used to pass YAML path to the settings source. When subclassing, `from_yaml()` sets this before construction.

**shared/errors.py** — Error hierarchy:
- `EngagementManagerError(Exception)` — base
- `ConfigurationError(EngagementManagerError)` — missing/invalid config
- `ApiUnavailableError(EngagementManagerError)` — API unreachable
- `CredentialError(EngagementManagerError)` — auth failure, credential-safe (`credential_name`, `reason` params)
- `GenerationError(EngagementManagerError)` — generation failed

**shared/logging.py** — `setup_logging(log_level: str)` — stderr only, configurable level

**config.yaml** — Already has `imagen:` section with `default_output_dir`, `default_width`, `default_height`

**.env.example** — Already lists `IMAGEN_GCP_PROJECT` and `IMAGEN_API_KEY`

**pyproject.toml** — Poetry config with `package-mode = false`. pytest addopts disables ROS plugins.

### Previous Story Learnings (from Story 1.2 Dev Agent Record)

- pydantic-settings init kwargs have HIGHEST priority — if you pass YAML values as init kwargs, they override env vars. The custom `YamlSettingsSource` was created to fix this. Subclasses should use `from_yaml()` which handles this correctly.
- ROS Jazzy pytest plugins on this system conflict with virtualenv pytest. Already handled via `addopts` in pyproject.toml.
- Run tests with `PYTHONPATH="" poetry run pytest` to avoid ROS system path pollution.

### Testing Strategy

- **Mock boundary:** Mock at the `vertexai` and `ImageGenerationModel` level — never make real API calls in tests
- **Config tests:** Use `tmp_path` and `monkeypatch` for isolated config testing (pattern from `tests/shared/test_config.py`)
- **Server tests:** Mock the entire Vertex AI interaction chain: `vertexai.init`, `ImageGenerationModel.from_pretrained`, `model.generate_images`, `image.save`
- **Error tests:** Simulate API errors by having mocks raise appropriate exceptions, verify they're caught and re-raised as typed errors from `shared/errors.py`

### Anti-Patterns to Avoid

- Do NOT implement image dimension/style options beyond basic defaults — Story 2.2 handles advanced options
- Do NOT create a CLI interface — the server is MCP-only via stdio
- Do NOT hardcode GCP project or credentials — everything from config
- Do NOT use `print()` — use logging to stderr
- Do NOT create new error classes — use existing ones from `shared/errors.py`
- Do NOT modify any `shared/` module files — they are complete from Story 1.2
- Do NOT implement timeout handling — NFR5 says no timeout on image generation (Story 2.2 covers graceful error handling for API failures)

### Environment Variables

| Variable | Source | Required | Description |
|----------|--------|----------|-------------|
| `IMAGEN_GCP_PROJECT` | `.env` | Yes | GCP project ID for Vertex AI |
| `IMAGEN_GCP_REGION` | `.env` or `config.yaml` | No (default: us-central1) | GCP region |
| `IMAGEN_MODEL` | `config.yaml` | No (default: imagen-3.0-generate-002) | Imagen model ID |

### Project Structure Notes

Files created/modified in this story:

```
servers/imagen/
├── __init__.py          # Already exists from 1.1
├── config.py            # NEW — ImagenConfig extending BaseServerConfig
└── server.py            # NEW — FastMCP server with generate_image tool

tests/imagen/
├── __init__.py          # Already exists from 1.1
├── test_config.py       # NEW — ImagenConfig validation tests
└── test_server.py       # NEW — generate_image tool tests (mocked API)

pyproject.toml           # MODIFIED — add google-cloud-aiplatform dependency
```

### References

- [Source: documents/planning-artifacts/architecture.md#MCP Tool Patterns — Tool Definition Shape]
- [Source: documents/planning-artifacts/architecture.md#Configuration Patterns — Per-Server Config Model]
- [Source: documents/planning-artifacts/architecture.md#Error Handling Patterns — Error Flow]
- [Source: documents/planning-artifacts/architecture.md#Structure Patterns — Adding a New MCP Server]
- [Source: documents/planning-artifacts/architecture.md#Logging Patterns]
- [Source: documents/planning-artifacts/epics.md#Story 2.1: Imagen MCP Server with Basic Image Generation]
- [Source: documents/planning-artifacts/prd.md#Functional Requirements — FR1, FR5, FR6]
- [Source: documents/planning-artifacts/prd.md#Non-Functional Requirements — NFR4, NFR5]

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6 (1M context)

### Debug Log References
- Config YAML loading: `_yaml_config_path` is a module-level global in `shared.config`; subclass must access it via `_config_module._yaml_config_path` (module reference, not value copy) to get the correct path set by `from_yaml()`.
- pytest-asyncio required for async tool tests; added to dev dependencies.

### Completion Notes List
- Task 1: Added `google-cloud-aiplatform>=1.60.0` to pyproject.toml. Installed v1.143.0.
- Task 2: Implemented `ImagenConfig(BaseServerConfig)` with custom `_ImagenYamlSource` that flattens the `imagen:` YAML section into top-level keys for field resolution. No `env_prefix` needed — field names like `imagen_gcp_project` naturally map to `IMAGEN_GCP_PROJECT` env vars.
- Task 3: Implemented FastMCP server with `generate_image` tool. Uses `aspect_ratio="1:1"` (Imagen 3 pattern) rather than raw pixel dimensions. Sanitizes prompts for filenames. Imports vertexai at module level for testability.
- Task 4: Error handling implemented inline with Task 3. Credential, API unavailable, and generation errors mapped to typed exceptions from `shared/errors.py`. No credential values in error messages.
- Task 5: 10 config tests + 9 server tests = 19 new tests. Server tests mock `vertexai.init` and `ImageGenerationModel` at module level. Covers success paths (default/custom output, directory creation) and error paths (init failure, model load failure, bad prompt, auth errors, empty response).
- Task 6: Full suite regression check — 77/77 tests pass (19 new + 58 existing).

### Change Log
- 2026-03-30: Story 2.1 implementation complete — Imagen MCP server with basic image generation

### File List
- `pyproject.toml` — MODIFIED (added google-cloud-aiplatform, pytest-asyncio dependencies)
- `poetry.lock` — MODIFIED (regenerated)
- `servers/imagen/config.py` — NEW (ImagenConfig extending BaseServerConfig)
- `servers/imagen/server.py` — NEW (FastMCP server with generate_image tool)
- `tests/imagen/test_config.py` — NEW (10 config validation tests)
- `tests/imagen/test_server.py` — NEW (9 server tests with mocked Vertex AI)
