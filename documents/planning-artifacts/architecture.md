---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
lastStep: 8
status: 'complete'
completedAt: '2026-03-29'
addendumDate: '2026-04-01'
addendum: 'Nano Banana Pro Migration'
inputDocuments: ['documents/planning-artifacts/product-brief-engagement-manager.md', 'documents/planning-artifacts/prd.md']
workflowType: 'architecture'
project_name: 'Engagement-Manager'
user_name: 'Kamal'
date: '2026-03-29'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
12 FRs across 3 categories. The image generation category (FR1-FR6) defines a clean request-response pattern: prompt in, image file path out, with user-configurable dimensions, style, and output location. Configuration (FR7-FR9) establishes a dual-layer config pattern — YAML for settings, `.env` for secrets — with startup validation. Error reporting (FR10-FR12) requires clear, actionable messages across API unavailability, credential issues, and generation failures.

**Non-Functional Requirements:**
6 NFRs, all security or integration focused. The security requirements (NFR1-NFR3) create a hard boundary: credentials must never appear in config files, source code, or logs. The integration requirements (NFR4-NFR6) lock the MVP to Vertex AI Imagen as the sole backend, with graceful latency handling and credential-safe error surfacing.

**Scale & Complexity:**

- Primary domain: CLI tooling / MCP server ecosystem
- Complexity level: Low
- Estimated architectural components: 1 MCP server (MVP), with patterns designed for 3-5 additional servers post-MVP

### Technical Constraints & Dependencies

- **Python 3.x** — pure Python, no compiled extensions
- **stdio transport only** — MCP servers communicate via stdin/stdout with Claude Code
- **Vertex AI Imagen API** — sole external dependency, requires GCP account with Vertex AI enabled
- **No distribution packaging** — runs directly from repository (no pip/npm/Docker)
- **Claude Code as sole host** — no multi-IDE support in v1
- **YAML + .env configuration pattern** — established by PRD, must be consistent across future components

### Cross-Cutting Concerns Identified

- **Credential management pattern** — must be reusable across all future MCP servers (WordPress will need its own creds)
- **Configuration loading** — YAML + .env pattern needs to be consistent and easy to replicate
- **Error reporting conventions** — clear, credential-safe error messages as a standard across all servers
- **MCP server structure** — project layout and boilerplate that makes adding the next server straightforward
- **Startup validation** — each server should validate its own config on launch using a shared approach

## Starter Template Evaluation

### Primary Technology Domain

Python CLI tooling / MCP server ecosystem — based on project requirements analysis.

### Starter Options Considered

**1. python-mcp-starter (ltwlf)** — Opinionated scaffold with Docker, GitHub Actions, VS Code debug config. Uses `uv`, not Poetry. Includes more infrastructure than needed (Docker, CI/CD) for a personal utility tool. Designed for single-server projects, not a growing monorepo.

**2. mcp-server-template (ntk148v)** — Cookiecutter-based, cleaner structure, but also uses `uv` and includes Docker. Same single-server limitation.

**3. Custom project structure** — Poetry + official MCP Python SDK with FastMCP. Define a clean monorepo structure that accommodates multiple MCP servers, skills, and agents.

### Selected Starter: Custom Project Structure

**Rationale for Selection:**
Existing MCP starter templates are designed for single standalone servers using `uv`. This project requires a monorepo that grows to hold multiple MCP servers, skills, and agents — and uses Poetry per developer preference. A custom structure gives us the right foundation without fighting against a template's assumptions.

**Project Layout:**

```
engagement-manager/
├── pyproject.toml              # Poetry root project
├── .env                        # Credentials (gitignored)
├── config.yaml                 # Shared settings
├── servers/
│   └── imagen/
│       ├── __init__.py
│       └── server.py           # FastMCP Imagen server
├── shared/                     # Shared modules (errors, config, logging)
├── tests/                      # Tests mirroring source structure
├── _bmad/em/                   # EM agents/workflows config (within _bmad/)
├── .claude/skills/             # Claude Code skill files (markdown)
└── documents/                  # Planning & project docs
```

**Architectural Decisions Provided by Structure:**

**Language & Runtime:**
Python >=3.10 (MCP SDK requirement), pure Python, no compiled extensions.

**MCP SDK:**
Official `mcp` package v1.26.0 (includes FastMCP). Servers use `@mcp.tool()` decorators with stdio transport.

**Dependency Management:**
Poetry with `pyproject.toml` for reproducible builds and dependency resolution.

**Configuration:**
`pydantic-settings` for both `.env` credential loading and `config.yaml` settings validation. Single library handles both sources natively. Dual-layer pattern consistent across all servers.

**Code Organization:**
Monorepo with `servers/` directory — each MCP server gets its own subdirectory. Skills and agents live alongside in their own top-level directories.

**Note:** Project initialization using Poetry and this structure should be the first implementation story.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Configuration architecture (`.env` + `config.yaml` with pydantic-settings)
- Error handling pattern (shared error module)
- MCP server structure (FastMCP, stdio, monorepo)

**Important Decisions (Shape Architecture):**
- Testing strategy (pytest + unittest.mock)
- Logging approach (stdlib logging to stderr, level via config.yaml)

**Deferred Decisions (Post-MVP):**
- CI/CD pipeline
- Multi-server shared dependency management patterns

### Configuration Architecture

- **Decision:** Dual-layer configuration — `.env` for secrets, `config.yaml` for operational settings
- **Library:** `pydantic-settings` for loading and validation from both sources
- **Env var naming:** Flat with server-name prefix (e.g., `IMAGEN_GCP_PROJECT`)
- **Rationale:** Clean separation of concerns. Pydantic-settings provides the startup validation required by FR9 with type checking and clear error messages. Config.yaml handles tunable settings (log level, output paths, defaults); `.env` handles credentials exclusively.
- **Affects:** All MCP servers, shared config module

### Error Handling

- **Decision:** Shared error module (`shared/errors.py`) with base exception classes
- **Pattern:** All servers inherit from common base classes for consistent error formatting
- **Error categories:** API unavailable, invalid credentials, generation failure
- **Credential safety:** Base error classes enforce that no credential values appear in error messages (NFR3, NFR6)
- **Rationale:** Consistent error reporting across all current and future MCP servers without building a framework — just a few base classes.
- **Affects:** All MCP servers

### Logging & Observability

- **Decision:** Python stdlib `logging` to stderr, log level configurable via `config.yaml`
- **Rationale:** stdout is reserved for MCP stdio protocol. Built-in logging is sufficient for a personal utility tool. No structured logging or external tools needed.
- **Affects:** All MCP servers

### Testing Strategy

- **Decision:** `pytest` with `unittest.mock` for external API mocking
- **Scope:** Unit tests for config validation and error handling; integration tests mocked at the Vertex AI API boundary
- **Rationale:** Minimal dependencies, pytest is the Python standard, unittest.mock avoids adding third-party mocking libraries.
- **Affects:** All MCP servers

### Infrastructure & Deployment

- **Decision:** No deployment infrastructure — runs directly from cloned repo
- **Python version:** >=3.10 (SDK minimum), development target 3.12
- **CI/CD:** Deferred post-MVP
- **Rationale:** Personal utility tool with no distribution requirements. CI/CD adds value later when the repo has multiple servers and contributors.

### Decision Impact Analysis

**Implementation Sequence:**
1. Project initialization (Poetry, pyproject.toml, directory structure)
2. Shared modules (config loading with pydantic-settings, error base classes, logging setup)
3. Imagen MCP server (built on shared foundation)

**Cross-Component Dependencies:**
- All servers depend on shared config and error modules
- pydantic-settings choice means config models are defined per-server but follow a shared pattern
- Logging setup is initialized once per server process using shared configuration

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:**
5 areas where AI agents could make different choices — code naming, project structure, MCP tool shape, configuration models, and error handling flow.

### Naming Patterns

**Code Naming Conventions (PEP 8):**
- Functions and variables: `snake_case` — e.g., `generate_image`, `output_path`
- Classes: `PascalCase` — e.g., `ImagenConfig`, `ApiUnavailableError`
- Constants: `UPPER_SNAKE_CASE` — e.g., `DEFAULT_IMAGE_WIDTH`, `MAX_PROMPT_LENGTH`
- Files and modules: `snake_case.py` — e.g., `server.py`, `config.py`
- Private members: `_leading_underscore` — e.g., `_validate_credentials`

**Environment Variable Naming:**
- Flat with server prefix: `IMAGEN_GCP_PROJECT`, `IMAGEN_API_KEY`
- Boolean env vars: `IMAGEN_DEBUG=true` (lowercase string)

### Structure Patterns

**Project Organization:**
- Each MCP server lives in `servers/<server_name>/` with `__init__.py`, `server.py`, `config.py`
- Shared Python code lives in `shared/` — `errors.py`, `logging.py`, `config.py` (base classes)
- Tests mirror source: `tests/<server_name>/test_server.py`, `tests/shared/test_errors.py`
- Skills are Claude Code skill files (markdown) in `.claude/skills/` — following the BMad pattern (SKILL.md + bmad-skill-manifest.yaml per skill)
- Agents are Claude Code skills with persona definitions and capabilities tables that invoke other skills — same BMad agent pattern (e.g., `bmad-agent-analyst`)
- Agent/workflow configuration lives in `_bmad/em/` (within the existing `_bmad/` structure)

**Adding a New MCP Server:**
1. Create `servers/<name>/` with `__init__.py`, `server.py`, `config.py`
2. Define a Pydantic settings model in `config.py` inheriting shared base
3. Register tools with `@mcp.tool()` decorators in `server.py`
4. Add server-specific env vars to `.env`
5. Add operational settings to `config.yaml` under a server-name key
6. Add tests in `tests/<name>/`

**Adding a New Agent/Skill:**
1. Create `.claude/skills/<skill-name>/` with `SKILL.md` and `bmad-skill-manifest.yaml`
2. For agents: define persona, communication style, principles, and capabilities table in `SKILL.md`
3. For workflow skills: define step-by-step workflow with micro-file architecture if complex
4. Add any agent/workflow config to `_bmad/em/`

### MCP Tool Patterns

**Tool Definition Shape:**
```python
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
```

**Tool Input Validation:** Pydantic models for complex inputs; simple type hints for tools with few parameters.

**Tool Return Values:** Tool-specific — return whatever makes sense for the tool (file path string, dict of results, etc.). No forced wrapper structure.

**Tool Docstrings:** Imperative mood, one-line summary, Args section with parameter descriptions. These are what Claude reads, so clarity matters.

### Error Handling Patterns

**Error Flow:**
1. Tool code raises typed exception from `shared/errors.py`
2. Server catches and converts to MCP error response
3. Error message is always credential-safe

**Error Class Hierarchy:**
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

### Configuration Patterns

**Per-Server Config Model:**
```python
# servers/imagen/config.py
from shared.config import BaseServerConfig

class ImagenConfig(BaseServerConfig):
    gcp_project: str
    gcp_region: str = "us-central1"
    imagen_model: str = "imagen-3.0-generate-002"
    default_width: int = 1024
    default_height: int = 1024
```

**Config sources:** Secrets from `.env`, operational settings from `config.yaml`, validated at startup via pydantic-settings.

### Logging Patterns

- Each module: `logger = logging.getLogger(__name__)`
- Output to stderr only (stdout reserved for MCP stdio)
- Log level from `config.yaml`
- Never log credential values

### Enforcement Guidelines

**All AI Agents MUST:**
- Follow PEP 8 naming conventions without exception
- Place new MCP servers in `servers/<name>/` following the established structure
- Place new skills/agents in `.claude/skills/<name>/` following the BMad pattern
- Use typed exceptions from `shared/errors.py` — never raise bare `Exception`
- Validate config at startup using pydantic-settings models
- Write tests in `tests/` mirroring the source structure
- Never log or surface credential values in errors or output

**Anti-Patterns to Avoid:**
- Creating utility modules outside `shared/` — all shared code goes in one place
- Defining error classes inside individual servers — use `shared/errors.py`
- Using `print()` for output — use `logging` to stderr
- Hardcoding config values — everything comes from `.env` or `config.yaml`
- Creating agents as Python code — agents are markdown-based Claude Code skills

## Project Structure & Boundaries

### Complete Project Directory Structure

```
engagement-manager/
├── pyproject.toml                      # Poetry project config, dependencies
├── poetry.lock                         # Locked dependency versions
├── .env                                # Secrets only (gitignored)
├── .env.example                        # Template showing required env vars
├── config.yaml                         # Operational settings (log level, defaults)
├── .gitignore
├── README.md
│
├── servers/
│   └── imagen/
│       ├── __init__.py
│       ├── server.py                   # FastMCP server, tool definitions
│       └── config.py                   # ImagenConfig pydantic model
│
├── shared/
│   ├── __init__.py
│   ├── errors.py                       # Base exception hierarchy
│   ├── config.py                       # BaseServerConfig, config loading
│   └── logging.py                      # Stderr logging setup
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                     # Shared pytest fixtures
│   ├── imagen/
│   │   ├── __init__.py
│   │   ├── test_server.py              # Tool function tests
│   │   └── test_config.py              # Config validation tests
│   └── shared/
│       ├── __init__.py
│       ├── test_errors.py
│       └── test_config.py
│
├── _bmad/
│   ├── core/                           # BMad core config
│   ├── bmm/                            # BMad module config
│   └── em/                             # EM agents/workflows config
│
├── .claude/
│   └── skills/                         # Claude Code skills (markdown)
│       ├── em-agent-analyst/           # Research agent (post-MVP)
│       ├── em-skill-post-generator/    # Post generation skill (post-MVP)
│       └── em-skill-linkedin-formats/  # LinkedIn format types (post-MVP)
│
└── documents/
    ├── planning-artifacts/             # Architecture, PRD, briefs
    └── implementation-artifacts/       # Sprint plans, stories
```

### Architectural Boundaries

**MCP Server Boundary:**
Each server is a standalone stdio process. Servers never import from other servers. They only import from `shared/`.

**Shared Module Boundary:**
`shared/` provides base classes and utilities only. It never imports from `servers/`. No business logic lives here — just infrastructure patterns.

**Skill/Agent Boundary:**
Skills and agents are markdown files that orchestrate MCP tools. They don't contain Python code. They invoke MCP tools through Claude Code's tool-use interface. Configuration lives in `_bmad/em/`.

### Requirements to Structure Mapping

| Requirement | Location |
|---|---|
| FR1-FR6 (Image Generation) | `servers/imagen/server.py` |
| FR7 (YAML config) | `config.yaml` + `shared/config.py` |
| FR8 (Env credentials) | `.env` + `servers/imagen/config.py` |
| FR9 (Startup validation) | `shared/config.py` (base) + `servers/imagen/config.py` |
| FR10-FR12 (Error reporting) | `shared/errors.py` + `servers/imagen/server.py` |
| NFR1-NFR3 (Security) | `.env` + `.gitignore` + `shared/errors.py` |
| NFR4-NFR6 (Integration) | `servers/imagen/server.py` |

### Data Flow

```
User (Claude Code) → stdio → FastMCP Server → Vertex AI Imagen API
                                    ↓
                              Local filesystem (saved image)
                                    ↓
                        stdio → file path returned to user
```

### External Integration Points

- **Vertex AI Imagen API** — called from `servers/imagen/server.py`, credentials from `.env`
- **Local filesystem** — image output, config files
- **Claude Code** — MCP host, stdio transport

## Architecture Validation Results

### Coherence Validation

**Decision Compatibility:** All technology choices (Python 3.12, MCP SDK v1.26.0, Poetry, pydantic-settings, pytest) are fully compatible with no version conflicts.

**Pattern Consistency:** PEP 8 naming, Pydantic-based config, typed error hierarchy, and stderr logging all follow standard Python conventions and work naturally together.

**Structure Alignment:** Project structure supports all decisions — server isolation enables stdio process model, shared module prevents code duplication, BMad-pattern skills/agents integrate with existing infrastructure.

### Requirements Coverage Validation

**Functional Requirements:** All 12 FRs (FR1-FR12) have explicit architectural support mapped to specific files and patterns.

**Non-Functional Requirements:** All 6 NFRs (NFR1-NFR6) are addressed through configuration patterns, error hierarchy design, and enforcement guidelines.

**Coverage: 100% — no gaps.**

### Implementation Readiness Validation

**Decision Completeness:** All critical decisions documented with library versions, code examples, and rationale.

**Structure Completeness:** Full directory tree defined with every file and its purpose. Requirements mapped to specific locations.

**Pattern Completeness:** All identified conflict points addressed with conventions, examples, and anti-patterns.

### Architecture Completeness Checklist

**Requirements Analysis**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed (Low)
- [x] Technical constraints identified (Python, stdio, Vertex AI)
- [x] Cross-cutting concerns mapped (config, errors, logging)

**Architectural Decisions**
- [x] Critical decisions documented with versions
- [x] Technology stack fully specified
- [x] Integration patterns defined
- [x] Security considerations addressed

**Implementation Patterns**
- [x] Naming conventions established (PEP 8)
- [x] Structure patterns defined (server layout, shared module)
- [x] MCP tool patterns specified (FastMCP decorators, docstrings)
- [x] Process patterns documented (error flow, config loading, logging)

**Project Structure**
- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** High

**Key Strengths:**
- Simple, focused architecture matching project complexity
- Clear boundaries prevent future server-to-server coupling
- Shared patterns make adding new MCP servers straightforward
- BMad-pattern agents/skills leverage existing proven infrastructure

**Areas for Future Enhancement:**
- CI/CD pipeline (deferred post-MVP)
- Multi-server dependency management patterns (when second server is added)
- Post-MVP skill/agent architecture details (Analyst, post generator)

### Implementation Handoff

**AI Agent Guidelines:**
- Follow all architectural decisions exactly as documented
- Use implementation patterns consistently across all components
- Respect project structure and boundaries
- Refer to this document for all architectural questions

**First Implementation Priority:**
1. Initialize Poetry project with `pyproject.toml`
2. Create directory structure
3. Implement `shared/` modules (config, errors, logging)
4. Build Imagen MCP server on shared foundation

---

## Nano Banana Pro Migration — Architecture Addendum

_Added: 2026-04-01. Extends the original architecture to replace the deprecated Imagen API with Nano Banana Pro (Gemini 3 Pro Image) for conversational image generation._

### Migration Context

**Why migrate:**
- `imagen-3.0-generate-002` is deprecated and shuts down **June 24, 2026**
- The `vertexai.preview.vision_models` SDK module is deprecated alongside it
- The replacement — Nano Banana Pro — natively supports the multi-turn conversational refinement the project requires

**What changes:**
- SDK: `google-cloud-aiplatform` → `google-genai`
- Model: `imagen-3.0-generate-002` → `gemini-3-pro-image-preview`
- Pattern: stateless one-shot → stateful multi-turn chat sessions
- Capabilities: gains iterative refinement, 4K resolution, text rendering, character consistency

**What does NOT change:**
- Project structure (`servers/imagen/`, `shared/`, `tests/`)
- Config pattern (pydantic-settings, `.env` + `config.yaml`)
- Error handling hierarchy (`shared/errors.py`)
- Logging pattern (stderr only)
- MCP transport (stdio)

### SDK Migration Decision

**From:** `google-cloud-aiplatform` (`vertexai`, `ImageGenerationModel`)
**To:** `google-genai` (`google.genai`, `genai.Client`)

**Rationale:** The `google-genai` SDK is Google's unified SDK for all generative AI models. It supports Vertex AI as a backend via `genai.Client(vertexai=True, ...)` and is the only path to Gemini image generation models.

**Dependency change in `pyproject.toml`:**
```toml
# Remove:
google-cloud-aiplatform = ">=1.60.0"
# Add:
google-genai = ">=1.0.0"
```

**Authentication:** Unchanged — Application Default Credentials (ADC) via `gcloud auth application-default login`. The `google-genai` SDK with `vertexai=True` uses the same ADC mechanism.

### Model Selection Decision

**Model:** `gemini-3-pro-image-preview` (Nano Banana Pro)

| Attribute | Value |
|-----------|-------|
| Model ID | `gemini-3-pro-image-preview` |
| Status | Preview |
| Max resolution | 4096x4096 |
| Text rendering accuracy | ~94% |
| Subject consistency | Up to 5 characters, 14 objects across turns |
| Generation speed | ~8-12 seconds per image |
| Pricing | ~$0.134/image (2K), ~$0.24/image (4K) |

**Why Pro over Flash:** The iterative refinement use case demands strong cross-turn consistency. Pro maintains character/object fidelity across edits — Flash does not. The speed trade-off (8-12s vs 3s) is acceptable for a quality-focused workflow.

**Config field:** `imagen_model` → stores model ID. Default changes from `"imagen-3.0-generate-002"` to `"gemini-3-pro-image-preview"`.

### Conversational Image Generation Pattern

**Core architectural change:** The server now maintains **chat session state** across MCP tool invocations. Each image generation conversation is a multi-turn chat session where the model remembers prior images and instructions.

**Client initialization (module-level, once):**
```python
from google import genai
from google.genai import types

client = genai.Client(vertexai=True, project=config.imagen_gcp_project, location=config.imagen_gcp_region)
```

**Chat session lifecycle:**
```python
# Start a new session
chat = client.chats.create(
    model=config.imagen_model,
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
    ),
)

# Turn 1: Initial generation
response = chat.send_message("Create a professional logo for a tech startup")

# Turn 2+: Refinement (chat maintains visual context)
response = chat.send_message("Make it more minimalist and change colors to blue")
```

**Response handling:**
```python
for part in response.candidates[0].content.parts:
    if part.text:
        # Model commentary/explanation
        pass
    elif hasattr(part, 'inline_data') and part.inline_data:
        # Image data — save to file
        image_bytes = part.inline_data.data
        with open(output_path, "wb") as f:
            f.write(image_bytes)
```

### Session State Management

**Decision:** In-memory session store, keyed by session ID.

**Rationale:** MCP servers are single-process, single-user (stdio transport). No need for persistent storage or cross-process state. A simple dictionary of active chat sessions is sufficient.

**Session lifecycle:**
- `generate_image` with no `session_id` → creates a new chat session, returns `session_id` alongside the image path
- `generate_image` with `session_id` → sends message to existing chat session for refinement
- Sessions are kept in memory for the server's lifetime
- No explicit session cleanup needed — the server process is tied to the Claude Code session

**State structure:**
```python
_sessions: dict[str, Chat] = {}
```

### MCP Tool Surface Changes

**Decision:** Extend the existing `generate_image` tool rather than creating separate tools.

**Rationale:** From the user's perspective (Claude Code), there's one action: "generate/refine an image." Whether it's turn 1 or turn 5 is an implementation detail. A single tool with an optional `session_id` keeps the interface clean.

**Updated tool signature:**
```python
@mcp.tool()
async def generate_image(
    prompt: str,
    session_id: str | None = None,
    width: int = 1024,
    height: int = 1024,
    style: str = "natural",
    output_path: str | None = None,
) -> str:
    """Generate or refine an image from a text prompt using Nano Banana Pro.

    Args:
        prompt: Text description or refinement instruction.
        session_id: ID of an existing session for iterative refinement.
            Omit to start a new generation. Provide to refine a previous result.
        width: Image width in pixels.
        height: Image height in pixels.
        style: Artistic style direction.
        output_path: Custom file path within the output directory.

    Returns:
        JSON string with session_id and image file path.
    """
```

**Return value change:** Returns JSON `{"session_id": "...", "image_path": "..."}` instead of a plain file path. This gives Claude the session ID to pass back for refinement turns.

### Error Handling Changes

**No new error classes.** The existing hierarchy from `shared/errors.py` covers all cases:

| Google GenAI Exception | Maps To |
|------------------------|---------|
| Authentication/permission errors | `CredentialError` |
| Model not found / API not enabled | `CredentialError` |
| Invalid prompt / safety filter | `GenerationError` |
| Quota exceeded | `GenerationError` |
| Service unavailable / network | `ApiUnavailableError` |
| Invalid `session_id` (not found) | `GenerationError` |

**Credential safety:** Same hard requirement. The `google-genai` SDK exceptions follow similar patterns to `google.api_core.exceptions`. All error handlers must use static reason strings, never raw `str(e)`.

### Config Changes

**`servers/imagen/config.py` — Updated fields:**

```python
class ImagenConfig(BaseServerConfig):
    imagen_gcp_project: str
    imagen_gcp_region: str = "us-central1"
    imagen_model: str = "gemini-3-pro-image-preview"  # Changed default
    default_output_dir: str = "./output"
    default_width: int = 1024
    default_height: int = 1024
```

**`config.yaml` — Updated defaults:**
```yaml
imagen:
  default_output_dir: ./output
  default_width: 1024
  default_height: 1024
  # imagen_model defaults to gemini-3-pro-image-preview
  # Override via IMAGEN_MODEL env var or here
```

**Environment variables:** Unchanged. `IMAGEN_GCP_PROJECT`, `IMAGEN_GCP_REGION`, `IMAGEN_MODEL` all work the same way.

### Testing Strategy Changes

**Mock boundary shifts:** Mock at the `genai.Client` and `chat.send_message` level instead of `vertexai.init` and `ImageGenerationModel`.

**New test scenarios:**
- Session creation (no `session_id` → new chat → returns `session_id`)
- Session continuation (valid `session_id` → sends to existing chat)
- Invalid session ID → `GenerationError`
- Multi-turn response parsing (text + image parts)
- Image data extraction and file saving from `inline_data`

**Removed test scenarios:**
- `vertexai.init()` mocking (no longer used)
- `ImageGenerationModel.from_pretrained()` mocking (no longer used)
- Aspect ratio mapping (Gemini handles dimensions natively)

### Implementation Sequence

1. **Swap SDK dependency** — Replace `google-cloud-aiplatform` with `google-genai` in `pyproject.toml`
2. **Update config** — Change default model to `gemini-3-pro-image-preview`
3. **Rewrite `server.py`** — Replace Imagen pattern with Gemini chat pattern, add session state management
4. **Update tests** — New mocking strategy at the `genai.Client` boundary
5. **Verify** — Full regression suite, manual testing with real API

### Anti-Patterns for Migration

- Do NOT keep both SDKs (`google-cloud-aiplatform` and `google-genai`) — clean swap
- Do NOT create a separate "refinement" tool — one tool handles both new and refine
- Do NOT persist sessions to disk — in-memory is correct for stdio MCP
- Do NOT implement session timeout/cleanup — the server process lifecycle handles this
- Do NOT expose raw Gemini response objects through MCP — extract image data and save to file
- Do NOT change the `shared/` modules — they remain stable
