# Story 3.2: Conversational Image Generation

Status: review

## Story

As a content creator,
I want to generate an image and then iteratively refine it through follow-up instructions,
so that I can achieve my creative vision through a back-and-forth conversation without starting over each time.

## Acceptance Criteria

1. **Given** a configured Imagen MCP server with valid GCP credentials **When** I call `generate_image` with a prompt and no `session_id` **Then** a new chat session is created via `client.chats.create()` **And** the image is generated and saved locally **And** the tool returns JSON with `session_id` and `image_path`
2. **Given** a valid `session_id` from a previous generation **When** I call `generate_image` with a refinement prompt and the `session_id` **Then** the message is sent to the existing chat session **And** the model refines the image while maintaining visual consistency **And** the refined image is saved and the same `session_id` is returned
3. **Given** an invalid or expired `session_id` **When** I call `generate_image` with that `session_id` **Then** a `GenerationError` is raised with a clear message
4. **Given** `tests/imagen/` **When** I run `poetry run pytest tests/imagen/` **Then** all session management tests pass (create, continue, invalid ID, multi-turn response parsing)

## Tasks / Subtasks

- [x] Task 1: Add session_id parameter and update tool signature (AC: #1, #2, #3)
  - [x] Add `session_id: str | None = None` parameter to `generate_image`
  - [x] Update docstring to document session_id usage and JSON return value
  - [x] Add `import json` and `import uuid` to server.py imports
- [x] Task 2: Implement session state management (AC: #1, #2, #3)
  - [x] Add module-level `_sessions: dict[str, Any] = {}` to store active chat sessions
  - [x] Implement session lookup: if `session_id` provided, look up in `_sessions`
  - [x] If `session_id` not found in `_sessions`, raise `GenerationError("Invalid session ID — session not found or expired")`
  - [x] If no `session_id`, create new session: `chat = client.chats.create(model=config.imagen_model, config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]))`, generate new ID via `str(uuid.uuid4())`, store in `_sessions[new_id] = chat`
- [x] Task 3: Replace single-shot with chat-based generation (AC: #1, #2)
  - [x] Replace `client.models.generate_content()` with `chat.send_message(effective_prompt)`
  - [x] For new sessions: use the newly created chat
  - [x] For existing sessions: use the looked-up chat, send refinement prompt
  - [x] Pass dimension/config via per-message config override if needed: `chat.send_message(prompt, config=types.GenerateContentConfig(image_config=types.ImageConfig(aspect_ratio=aspect_ratio)))`
  - [x] Update response handling to iterate `response.candidates[0].content.parts` — extract image via `part.as_image()`
  - [x] If no image part in response, raise `GenerationError("No image was returned by the API")`
- [x] Task 4: Update return value to JSON (AC: #1, #2)
  - [x] Change return from plain file path string to `json.dumps({"session_id": session_id, "image_path": output_path_resolved})`
  - [x] Ensure session_id is the same for continuation calls
- [x] Task 5: Write tests for session management (AC: #4)
  - [x] Test new session creation (no session_id → chat created, session_id in return JSON)
  - [x] Test session continuation (valid session_id → existing chat used, same session_id returned)
  - [x] Test invalid session_id → GenerationError
  - [x] Test multi-turn: call twice with same session_id, verify chat.send_message called twice on same chat
  - [x] Test response parsing: text+image parts, image-only, no-image error
  - [x] Update existing tests to handle JSON return value (parse with json.loads)
- [x] Task 6: Run full test suite and verify no regressions (AC: #1-#4)
  - [x] Run `poetry run pytest tests/imagen/ -v`
  - [x] Run `poetry run pytest -v` (full suite) to verify zero regressions

## Dev Notes

### Architecture Compliance

- **Session state is in-memory only** — `_sessions: dict[str, Any] = {}` at module level. No persistence, no cleanup. Server process lifecycle handles this.
- **Single tool surface** — do NOT create separate tools for "new" vs "refine". One `generate_image` handles both.
- **Return value is JSON** — `{"session_id": "...", "image_path": "..."}`. This is the contract Claude Code uses to pass session_id back.
- **Error handling uses ONLY typed exceptions from `shared/errors.py`**
- **Credential safety is a HARD requirement (NFR1-NFR3)**
- **No timeout on API calls (NFR5)**
- **Do NOT modify `shared/` modules**

### Chat Session Pattern

**New session (no session_id):**
```python
chat = client.chats.create(
    model=config.imagen_model,
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
    ),
)
session_id = str(uuid.uuid4())
_sessions[session_id] = chat

response = chat.send_message(effective_prompt)
```

**Continue session (with session_id):**
```python
if session_id not in _sessions:
    raise GenerationError("Invalid session ID — session not found or expired")

chat = _sessions[session_id]
response = chat.send_message(effective_prompt)
```

### Response Handling Pattern

```python
image_saved = False
for part in response.candidates[0].content.parts:
    if part.text is not None:
        logger.info("Model response: %s", part.text[:200])
    elif image := part.as_image():
        image.save(output_path_resolved)
        image_saved = True

if not image_saved:
    raise GenerationError("No image was returned by the API")
```

### Per-Message Config for Dimensions

When continuing a session with new dimensions, pass config per-message:
```python
response = chat.send_message(
    effective_prompt,
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        image_config=types.ImageConfig(
            aspect_ratio=aspect_ratio,
        ),
    ),
)
```

### Error Handling — Same as Story 3.1

| google.genai Exception | Maps To |
|------------------------|---------|
| `ClientError` code 403 | `CredentialError("IMAGEN_GCP_PROJECT", reason="permission denied — check IAM roles")` |
| `ClientError` code 404 | `CredentialError("IMAGEN_GCP_PROJECT", reason="project not found or API not enabled")` |
| `ClientError` code 400 | `GenerationError("Invalid request — check prompt and parameters")` |
| `ClientError` code 429 | `GenerationError("Quota exceeded — try again later")` |
| `ServerError` (any) | `ApiUnavailableError("Vertex AI API unavailable")` |
| `ConnectionError`/`TimeoutError` | `ApiUnavailableError("Network error during image generation")` |
| Invalid session_id | `GenerationError("Invalid session ID — session not found or expired")` |

### Existing Code After Story 3.1

After 3.1, `server.py` uses:
- `from google import genai` and `from google.genai import types, errors`
- Module-level `client = genai.Client(vertexai=True, ...)`
- `client.models.generate_content()` for single-shot (this story replaces with chat)
- `part.as_image()` for image extraction
- `_sanitize_filename()`, prompt validation, style engineering, output path sandboxing — all unchanged

### What Changes in This Story

| Component | Before (3.1) | After (3.2) |
|-----------|-------------|-------------|
| Generation | `client.models.generate_content()` | `chat.send_message()` |
| State | Stateless | `_sessions` dict with chat objects |
| Parameters | No `session_id` | `session_id: str \| None = None` |
| Return | Plain file path string | JSON `{"session_id": "...", "image_path": "..."}` |
| Imports | — | Add `json`, `uuid` |

### Previous Story Learnings

- Config loaded at module level — `autouse` fixture with `monkeypatch.setenv`
- Run tests with `PYTHONPATH=""` to avoid ROS conflicts
- Credential safety: static reason strings, never `f"...{e}"` in CredentialError
- Output path sandboxing: paths must be within `config.default_output_dir`
- Use `e.code` on ClientError for error classification, not string matching

### Testing Strategy

- **Mock boundary:** Patch `servers.imagen.server.client` (the module-level genai.Client)
- **Session tests:** Verify `client.chats.create()` called for new sessions, not called for continuations
- **Multi-turn test:** Call generate_image twice with same session_id, verify same chat object used
- **Return value tests:** Parse JSON with `json.loads()`, assert keys present
- **Update existing tests:** All tests that checked plain string return must now parse JSON

### Anti-Patterns to Avoid

- Do NOT persist sessions to disk — in-memory only
- Do NOT implement session timeout/cleanup — server process lifecycle handles it
- Do NOT create separate "new_image" and "refine_image" tools — one tool
- Do NOT expose raw Gemini response objects through MCP
- Do NOT modify `shared/` modules
- Do NOT use bare `except Exception`
- Do NOT include raw exception messages in CredentialError reason

### Project Structure Notes

Files modified:
```
servers/imagen/server.py      # MODIFIED — add session management, chat-based generation, JSON return
tests/imagen/test_server.py   # MODIFIED — add session tests, update return value assertions
```

No new files needed.

### References

- [Source: documents/planning-artifacts/architecture.md#Nano Banana Pro Migration — Conversational Image Generation Pattern]
- [Source: documents/planning-artifacts/architecture.md#Session State Management]
- [Source: documents/planning-artifacts/architecture.md#MCP Tool Surface Changes]
- [Source: documents/planning-artifacts/epics.md#Story 3.2: Conversational Image Generation]
- [Source: documents/planning-artifacts/prd.md#Non-Functional Requirements — NFR1-NFR3, NFR5]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- All 115 tests pass with zero regressions after session management implementation

### Completion Notes List

- **Task 1:** Added `session_id: str | None = None` parameter to `generate_image`, added `import json`, `import uuid`, `from typing import Any`. Updated docstring to document session_id and JSON return.
- **Task 2:** Added module-level `_sessions: dict[str, Any] = {}`. Implemented session lookup (raises `GenerationError` for invalid IDs) and creation via `client.chats.create()` with UUID generation.
- **Task 3:** Replaced `client.models.generate_content()` with `chat.send_message()`. Per-message config passed with `GenerateContentConfig` including `image_config` for aspect ratio. Response handling updated to iterate `response.candidates[0].content.parts`.
- **Task 4:** Return value changed from plain path to `json.dumps({"session_id": ..., "image_path": ...})`.
- **Task 5:** Added `TestSessionManagement` (4 tests: new session, continuation, invalid ID, multi-turn), `TestResponseParsing` (3 tests: text+image, image-only, no-image error), `_clear_sessions` autouse fixture. Updated all existing tests to parse JSON return values. 47 server tests total.
- **Task 6:** Full suite: 115/115 pass, zero regressions.

### Change Log

- 2026-04-01: Story 3.2 implementation complete — added conversational multi-turn image generation with in-memory session management, chat-based generation via `client.chats.create()`/`chat.send_message()`, and JSON return format.

### File List

- `servers/imagen/server.py` — MODIFIED: added session management, chat-based generation, JSON return format
- `tests/imagen/test_server.py` — MODIFIED: added session/response tests, updated all tests for JSON return, added _clear_sessions fixture
