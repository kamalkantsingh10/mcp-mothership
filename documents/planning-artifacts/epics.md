---
stepsCompleted: [1, 2, 3, 4]
status: 'complete'
completedAt: '2026-03-29'
inputDocuments: ['documents/planning-artifacts/prd.md', 'documents/planning-artifacts/architecture.md']
---

# Engagement-Manager - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Engagement-Manager, decomposing the requirements from the PRD and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

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

### NonFunctional Requirements

NFR1: API keys and GCP credentials must be stored in .env files, never in YAML config or source code
NFR2: .env files must be included in .gitignore to prevent accidental commit
NFR3: System must not log or echo credential values in any output
NFR4: System must support Vertex AI Imagen API as the sole image generation backend
NFR5: System must handle API latency gracefully — no timeout on image generation (user waits for result)
NFR6: System must surface API error responses (quota, permissions, model errors) without exposing credentials in error messages

### Additional Requirements

- Architecture specifies custom project structure (no starter template) — Poetry initialization is the first implementation step
- Shared Python modules required: `shared/errors.py` (typed exception hierarchy), `shared/config.py` (BaseServerConfig with pydantic-settings), `shared/logging.py` (stderr logging setup)
- Per-server config models using pydantic-settings for startup validation (FR9)
- Error class hierarchy: EngagementManagerError → ConfigurationError, ApiUnavailableError, CredentialError, GenerationError
- Logging to stderr only (stdout reserved for MCP stdio protocol), log level configurable via config.yaml
- Tests using pytest with unittest.mock, mirroring source structure in `tests/`
- MCP servers use FastMCP with `@mcp.tool()` decorators and stdio transport
- `.env.example` file to document required environment variables
- Monorepo structure: each MCP server in `servers/<name>/` with `server.py` and `config.py`

### UX Design Requirements

N/A — CLI/MCP tool with no graphical user interface.

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
