# Story 3.3: Updated Tests & Regression

Status: review

## Story

As a developer,
I want comprehensive tests covering the new Gemini-based image generation and session management,
so that I have confidence the migration is correct and future changes won't break functionality.

## Acceptance Criteria

1. **Given** `tests/imagen/test_server.py` with updated tests **When** I run `poetry run pytest tests/imagen/ -v` **Then** all tests pass with `genai.Client` and `chat.send_message` mocked **And** tests cover: new session creation, session continuation, invalid session, text+image response parsing, image data extraction and file saving, all error type mappings to typed exceptions, credential safety, no timeout on API calls
2. **Given** `tests/imagen/test_config.py` with config tests **When** I run `poetry run pytest tests/imagen/test_config.py -v` **Then** all tests pass including the updated default model value (`gemini-3-pro-image-preview`)
3. **Given** the full test suite **When** I run `poetry run pytest -v` **Then** all tests pass with zero regressions against shared module tests

## Tasks / Subtasks

- [x] Task 1: Verify and update test_config.py for new default model (AC: #2)
  - [x] Update `test_defaults_with_required_field` to assert `config.imagen_model == "gemini-3-pro-image-preview"`
  - [x] Verify all other config tests still pass
  - [x] Run `PYTHONPATH="" poetry run pytest tests/imagen/test_config.py -v`
- [x] Task 2: Rewrite test fixtures for google-genai mock boundary (AC: #1)
  - [x] Remove `mock_vertex_stack` fixture (patches `vertexai`/`ImageGenerationModel`)
  - [x] Remove `from google.api_core import exceptions as google_exceptions` import
  - [x] Add `mock_genai_client` fixture that patches `servers.imagen.server.client`
  - [x] Configure mock chain: `client.chats.create()` → mock chat → `chat.send_message()` → mock response with `.candidates[0].content.parts`
  - [x] Mock image parts: `part.as_image()` returns mock PIL Image with `.save()`
  - [x] Keep `_mock_config` autouse fixture unchanged
- [x] Task 3: Write session management tests (AC: #1)
  - [x] `test_new_session_creates_chat` — no session_id → `client.chats.create()` called
  - [x] `test_new_session_returns_session_id` — return JSON contains `session_id`
  - [x] `test_new_session_returns_image_path` — return JSON contains `image_path`
  - [x] `test_continue_session_uses_existing_chat` — valid session_id → existing chat reused
  - [x] `test_continue_session_returns_same_session_id` — same session_id returned
  - [x] `test_invalid_session_id_raises_generation_error` — unknown session_id → GenerationError
- [x] Task 4: Write multi-turn response parsing tests (AC: #1)
  - [x] `test_response_with_text_and_image_parts` — both parts handled correctly
  - [x] `test_image_extracted_via_as_image` — `part.as_image()` called, `.save()` called
  - [x] `test_response_with_no_image_raises_generation_error` — text-only → GenerationError
  - [x] `test_image_save_oserror_maps_to_generation_error` — `image.save()` OSError → GenerationError
  - [x] `test_empty_response_parts_raises_generation_error` — empty parts → GenerationError
- [x] Task 5: Write error mapping tests — ClientError codes, ServerError, credential safety (AC: #1)
  - [x] `test_client_error_400_maps_to_generation_error`
  - [x] `test_client_error_403_maps_to_credential_error`
  - [x] `test_client_error_404_maps_to_credential_error`
  - [x] `test_client_error_429_maps_to_generation_error`
  - [x] `test_server_error_maps_to_api_unavailable`
  - [x] `test_connection_error_maps_to_api_unavailable`
  - [x] `test_credential_error_does_not_expose_project_id`
  - [x] `test_credential_error_does_not_expose_raw_exception`
  - [x] `test_no_timeout_on_send_message`
- [x] Task 6: Run full regression suite (AC: #3)
  - [x] Run `PYTHONPATH="" poetry run pytest tests/imagen/ -v`
  - [x] Run `PYTHONPATH="" poetry run pytest -v` (full suite) to verify zero regressions

## Dev Notes

### Architecture Compliance

- **Mock boundary is `servers.imagen.server.client`** — the module-level `genai.Client` instance
- **Error handling uses ONLY typed exceptions from `shared/errors.py`**
- **Credential safety is a HARD requirement (NFR1-NFR3)**
- **No timeout on API calls (NFR5)** — verify no `timeout` kwarg passed
- **Do NOT modify `shared/` modules or their tests**
- **Do NOT modify production code** (`server.py`, `config.py`) — this is a test-only story

### google-genai Mock Structure

```python
# Fixture pattern
mock_client = MagicMock()
mock_chat = MagicMock()
mock_client.chats.create.return_value = mock_chat

mock_response = MagicMock()
mock_chat.send_message.return_value = mock_response

# Image part
mock_image_part = MagicMock()
mock_image_part.text = None
mock_pil_image = MagicMock()
mock_image_part.as_image.return_value = mock_pil_image

# Text part
mock_text_part = MagicMock()
mock_text_part.text = "Here is your image"
mock_text_part.as_image.return_value = None

mock_response.candidates[0].content.parts = [mock_text_part, mock_image_part]
```

### google-genai Exception Mocking

```python
from google.genai import errors

# ClientError with specific code
mock_chat.send_message.side_effect = errors.ClientError(403, "Permission denied")

# ServerError
mock_chat.send_message.side_effect = errors.ServerError(503, "Service unavailable")
```

Use `e.code` to distinguish ClientError subtypes, NOT string matching.

### Return Value Structure

After Stories 3.1/3.2, `generate_image` returns JSON:
```json
{"session_id": "uuid-string", "image_path": "/absolute/path/to/image.png"}
```
Parse with `json.loads()` in tests.

### Previous Story Learnings

- Config loaded at module level — `autouse` fixture with `monkeypatch.setenv` required
- Run with `PYTHONPATH=""` to avoid ROS conflicts
- Use `tmp_path` and `monkeypatch` for isolation
- Credential safety: static reason strings only, never `f"...{e}"` in CredentialError
- Output path sandboxing tests need `config.default_output_dir` swap in try/finally

### Anti-Patterns to Avoid

- Do NOT make real API calls — all mocked
- Do NOT modify `shared/` modules or their tests
- Do NOT modify production code — test-only story
- Do NOT import `google.api_core.exceptions` or `vertexai` — removed
- Do NOT use string matching on error messages — use `e.code`
- Do NOT mock `genai.Client` constructor — mock the module-level `client` instance

### Project Structure Notes

Files modified:
```
tests/imagen/test_config.py   # MODIFIED — update default model assertion
tests/imagen/test_server.py   # MODIFIED — full rewrite: new mock boundary, new test classes
```

No new files. No production code changes.

### References

- [Source: documents/planning-artifacts/architecture.md#Nano Banana Pro Migration — Testing Strategy Changes]
- [Source: documents/planning-artifacts/architecture.md#Error Handling Changes]
- [Source: documents/planning-artifacts/architecture.md#Session State Management]
- [Source: documents/planning-artifacts/epics.md#Story 3.3: Updated Tests & Regression]
- [Source: documents/planning-artifacts/prd.md#Non-Functional Requirements — NFR1-NFR3, NFR5]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- 57 imagen tests pass (10 config + 47 server), 115 total tests pass with zero regressions

### Completion Notes List

- **Task 1:** Default model assertion already updated in Story 3.1. 10/10 config tests pass.
- **Task 2:** Fixtures rewritten in Stories 3.1/3.2. `mock_vertex_stack` replaced with `mock_genai_stack` using `client.chats.create()` → `chat.send_message()` → `candidates[0].content.parts` mock chain. `_clear_sessions` autouse fixture added.
- **Task 3:** All 6 session management test scenarios covered in `TestSessionManagement` (4 tests covering all scenarios including multi-turn with 3 messages on same chat).
- **Task 4:** `TestResponseParsing` (3 tests) + `TestGenerateImageErrors` (save OSError, none parts) cover all 5 response parsing scenarios.
- **Task 5:** All 9 error mapping tests present across `TestGenerateImageErrors` (7 tests), `TestCredentialSafety` (2 tests), `TestNoTimeout` (1 test).
- **Task 6:** Full regression: 115/115 pass. No production code modified — test-only story.
- **Note:** All test requirements were fulfilled during Stories 3.1 and 3.2 implementation (test-driven development). Story 3.3 verified completeness and ran final regression.

### Change Log

- 2026-04-01: Story 3.3 verification complete — all test requirements met from Stories 3.1/3.2 TDD implementation. 115/115 tests pass, zero regressions.

### File List

- `tests/imagen/test_config.py` — VERIFIED: default model assertion updated (Story 3.1)
- `tests/imagen/test_server.py` — VERIFIED: full rewrite with google-genai mocks, session tests, response parsing, error mapping (Stories 3.1/3.2)
