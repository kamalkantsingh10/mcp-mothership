# Story 1.1: Initialize Project Structure

Status: done

## Story

As a developer,
I want to clone the repo and have a working Poetry project with the correct directory structure,
so that I have a solid foundation to build MCP servers on.

## Acceptance Criteria

1. **Given** a fresh clone of the repository **When** I run `poetry install` **Then** a virtual environment is created with all dependencies installed (mcp, pydantic-settings, pyyaml, pytest)
2. **And** the directory structure exists: `servers/imagen/`, `shared/`, `tests/`, `.claude/skills/`
3. **And** `pyproject.toml` specifies Python >=3.10
4. **And** `.gitignore` includes `.env`, `__pycache__/`, `.venv/`
5. **And** `.env.example` lists required environment variables with placeholder values

## Tasks / Subtasks

- [x] Task 1: Initialize Poetry project (AC: #1, #3)
  - [x] Run `poetry init` or create `pyproject.toml` manually
  - [x] Set Python requirement to `>=3.10` with development target 3.12
  - [x] Add dependencies: `mcp>=1.26.0`, `pydantic-settings`, `pyyaml`
  - [x] Add dev dependencies: `pytest`
- [x] Task 2: Create complete directory structure (AC: #2)
  - [x] Create `servers/imagen/` with `__init__.py`
  - [x] Create `shared/` with `__init__.py`
  - [x] Create `tests/` with `__init__.py` and `conftest.py`
  - [x] Create `tests/imagen/` with `__init__.py`
  - [x] Create `tests/shared/` with `__init__.py`
  - [x] Ensure `.claude/skills/` exists (already present from BMad)
- [x] Task 3: Create `.gitignore` (AC: #4)
  - [x] Include `.env`, `__pycache__/`, `.venv/`, `*.pyc`, `dist/`, `*.egg-info`
- [x] Task 4: Create `.env.example` (AC: #5)
  - [x] List `IMAGEN_GCP_PROJECT=your-gcp-project-id`
  - [x] List `IMAGEN_API_KEY=your-api-key` (if applicable)
  - [x] Add comments explaining each variable
- [x] Task 5: Create skeleton `config.yaml` (AC: #1)
  - [x] Add `log_level: INFO` as default
  - [x] Add `imagen:` section with `default_output_dir`, `default_width`, `default_height` placeholders
- [x] Task 6: Verify `poetry install` runs clean (AC: #1)

## Dev Notes

### Architecture Compliance

- **Project layout must match exactly** what's defined in architecture.md "Complete Project Directory Structure" section. Do not deviate.
- Poetry is the dependency manager — not pip, not uv, not conda.
- `pyproject.toml` is the single source of truth for dependencies and project metadata.
- Python version: `>=3.10` in pyproject.toml. Development target is 3.12.

### Key Dependencies & Versions

| Package | Version | Purpose |
|---------|---------|---------|
| `mcp` | `>=1.26.0` | MCP SDK with FastMCP |
| `pydantic-settings` | latest | Config validation from .env + YAML |
| `pyyaml` | latest | YAML config file parsing |
| `pytest` | latest (dev) | Testing framework |

### Configuration Pattern

The architecture specifies a dual-layer config pattern:
- `.env` — secrets only (GCP project, API keys). Loaded by pydantic-settings.
- `config.yaml` — operational settings (log level, output paths, defaults). Parsed with PyYAML.

### Environment Variable Naming Convention

Flat with server prefix: `IMAGEN_GCP_PROJECT`, `IMAGEN_API_KEY`. Boolean env vars use lowercase string: `IMAGEN_DEBUG=true`.

### Anti-Patterns to Avoid

- Do NOT use `uv` — this project uses Poetry exclusively
- Do NOT create a `requirements.txt` — `pyproject.toml` is the single source
- Do NOT put credentials in `config.yaml` — secrets go in `.env` only
- Do NOT add Docker, CI/CD, or GitHub Actions — deferred post-MVP
- Do NOT create `setup.py` or `setup.cfg` — Poetry handles this

### Project Structure Notes

The full directory tree from architecture.md:

```
engagement-manager/
├── pyproject.toml
├── poetry.lock
├── .env                    # Secrets only (gitignored)
├── .env.example            # Template for required env vars
├── config.yaml             # Operational settings
├── .gitignore
├── servers/
│   └── imagen/
│       ├── __init__.py
│       ├── server.py       # (created in Story 2.1)
│       └── config.py       # (created in Story 1.2)
├── shared/
│   ├── __init__.py
│   ├── errors.py           # (created in Story 1.2)
│   ├── config.py           # (created in Story 1.2)
│   └── logging.py          # (created in Story 1.2)
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── imagen/
│   │   └── __init__.py
│   └── shared/
│       └── __init__.py
└── documents/              # Already exists
```

Only create the structure and placeholder `__init__.py` files in this story. Do NOT implement `shared/errors.py`, `shared/config.py`, `shared/logging.py`, or `servers/imagen/server.py` — those come in later stories.

### References

- [Source: documents/planning-artifacts/architecture.md#Starter Template Evaluation — "Selected Starter: Custom Project Structure"]
- [Source: documents/planning-artifacts/architecture.md#Complete Project Directory Structure]
- [Source: documents/planning-artifacts/architecture.md#Core Architectural Decisions — Configuration Architecture]
- [Source: documents/planning-artifacts/epics.md#Story 1.1: Initialize Project Structure]
- [Source: documents/planning-artifacts/prd.md#Language & Runtime Requirements]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- ROS Jazzy pytest plugins on system Python conflicted with virtualenv pytest. Resolved by adding `addopts` in pyproject.toml to disable ROS plugins (`-p no:ament_*`, `-p no:launch_testing*`).

### Completion Notes List

- Created `pyproject.toml` with Poetry config, Python >=3.10,<4.0, all required deps (mcp>=1.26.0, pydantic-settings, pyyaml, pytest dev)
- Set `package-mode = false` since this is not a distributable package
- Created full directory structure: `servers/imagen/`, `shared/`, `tests/`, `tests/imagen/`, `tests/shared/` with `__init__.py` placeholders
- Created `tests/conftest.py` (empty, ready for shared fixtures)
- Created `.gitignore` with `.env`, `__pycache__/`, `.venv/`, `*.pyc`, `dist/`, `*.egg-info`
- Created `.env.example` with `IMAGEN_GCP_PROJECT` and `IMAGEN_API_KEY` placeholders and comments
- Created `config.yaml` skeleton with `log_level: INFO` and `imagen:` section (default_output_dir, default_width, default_height)
- Verified `poetry install` creates virtualenv and installs all 35 packages successfully
- All 22 tests pass covering: pyproject.toml structure, directory existence, .gitignore entries, .env.example variables, config.yaml content

### Change Log

- 2026-03-30: Initial project structure implementation — all 6 tasks completed, 22 tests passing

### File List

- pyproject.toml (new)
- poetry.lock (new, auto-generated)
- .gitignore (new)
- .env.example (new)
- config.yaml (new)
- servers/__init__.py (new)
- servers/imagen/__init__.py (new)
- shared/__init__.py (new)
- tests/__init__.py (new)
- tests/conftest.py (new)
- tests/test_project_structure.py (new)
- tests/imagen/__init__.py (new)
- tests/shared/__init__.py (new)
