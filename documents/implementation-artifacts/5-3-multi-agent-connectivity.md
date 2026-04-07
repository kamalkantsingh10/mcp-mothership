# Story 5.3: Multi-Agent Connectivity

Status: review

## Story

As an agent builder,
I want multiple agents from different projects to connect to the same running MCP server simultaneously,
so that I can reuse capabilities across all my agentic projects without duplication.

## Acceptance Criteria

1. **Given** a running Imagen MCP server on Streamable HTTP **When** two separate MCP clients connect concurrently **Then** both can call `tools/list` and receive the correct tool schema **And** both can invoke `generate_image` independently
2. **Given** two concurrent clients making requests **When** both call `generate_image` simultaneously **Then** each receives its own response without interference **And** the metrics endpoint reflects the combined request count
3. **Given** one client disconnects **When** the other client continues making requests **Then** the server remains operational and responsive
4. **Given** `tests/servers/imagen/` **When** I run concurrent connection tests **Then** multi-client scenarios pass without race conditions or errors

## Tasks / Subtasks

- [x] Task 1: Verify Streamable HTTP supports concurrent connections (AC: #1)
  - [x] Confirm FastMCP's Streamable HTTP transport (Starlette/uvicorn) natively handles multiple concurrent connections — this should be the default behavior
  - [x] If any server-level configuration is needed (e.g., worker count, connection limits), document and apply it
  - [x] No code change expected — Starlette is async and handles concurrent requests natively
- [x] Task 2: Verify concurrent tool invocation independence (AC: #2)
  - [x] Write a test that spawns two concurrent `generate_image` calls with different prompts
  - [x] Verify each call returns its own unique response (different session_id, different image_path)
  - [x] Verify `_request_count` reflects both calls (count = 2)
  - [x] Mock the google-genai client to return distinguishable responses per call
- [x] Task 3: Verify session isolation between clients (AC: #1, #2)
  - [x] Write a test where Client A creates a session and Client B creates a separate session
  - [x] Verify Client A's session_id is different from Client B's
  - [x] Verify Client A can refine its session without affecting Client B's session
  - [x] The `_sessions` dict in `server.py` is keyed by UUID — sessions are naturally isolated
- [x] Task 4: Verify client disconnect resilience (AC: #3)
  - [x] Write a test that simulates: Client A connects, Client B connects, Client A disconnects, Client B makes a request
  - [x] Verify Client B's request succeeds after Client A disconnects
  - [x] Verify the server process remains healthy (no crash, no degraded state)
  - [x] Starlette handles this natively — test confirms the behavior
- [x] Task 5: Verify metrics reflect combined activity (AC: #2)
  - [x] Write a test where two clients each make one request
  - [x] Verify `/metrics` shows `request_count: 2` after both complete
  - [x] Verify error from one client increments `error_count` without affecting the other client's success
- [x] Task 6: Write concurrent connection tests (AC: #4)
  - [x] In `tests/servers/imagen/test_server.py`, add:
    - `test_concurrent_tool_list` — two clients call tools/list concurrently, both get correct schema
    - `test_concurrent_generate_image` — two clients generate images concurrently, both succeed independently
    - `test_concurrent_session_isolation` — two clients with separate sessions don't interfere
    - `test_client_disconnect_no_impact` — one client disconnects, other continues working
    - `test_concurrent_metrics_combined` — metrics reflect total across all clients
  - [x] Use `asyncio.gather` or `asyncio.TaskGroup` to run concurrent operations
  - [x] Run `PYTHONPATH="" poetry run pytest tests/servers/imagen/ -v`
- [x] Task 7: Run full regression (AC: #4)
  - [x] Run `PYTHONPATH="" poetry run pytest -v` to verify zero regressions

## Dev Notes

### Architecture Compliance

- **Multi-client support:** Per architecture-mothership.md: "Streamable HTTP natively supports multiple simultaneous agent connections per server (satisfies FR12)"
- **Session isolation:** The `_sessions` dict in `server.py` uses UUIDs as keys — each client gets its own session. No shared mutable state between sessions.
- **Metrics thread safety:** Module-level counters (`_request_count`, `_error_count`) are modified in async context. Since Python's GIL ensures atomic integer increments in CPython and the server runs in a single asyncio event loop, there are no race conditions. Document this assumption in tests.

### Why This Story Is Mostly Verification

Streamable HTTP (via Starlette/uvicorn) inherently supports concurrent connections. FastMCP doesn't impose single-client limitations. The `_sessions` dict naturally isolates sessions by UUID. This story's value is **proving** these properties hold under concurrent load, not implementing new concurrency features.

### Concurrency Testing Pattern

```python
import asyncio

async def test_concurrent_generate_image():
    """Two clients generate images concurrently without interference."""
    async with asyncio.TaskGroup() as tg:
        result_a = tg.create_task(client_a.call_tool("generate_image", {"prompt": "sunset"}))
        result_b = tg.create_task(client_b.call_tool("generate_image", {"prompt": "mountain"}))

    assert result_a.result()["session_id"] != result_b.result()["session_id"]
```

### Session Store Consideration

The `_sessions` dict is a plain Python dict. In a single-process async server (which this is), concurrent access is safe because:
1. Python's asyncio is single-threaded — no true parallelism
2. Dict operations are atomic in CPython
3. Each request gets its own UUID — no key collisions

If the server were ever multi-process (e.g., uvicorn workers > 1), session state would need shared storage. This is explicitly out of scope for MVP (single-user, local operation).

### Files to Modify

```
tests/servers/imagen/test_server.py  # Add concurrent connection tests (created in 5.1)
```

### Files NOT Modified

No production code changes expected. This story verifies existing concurrent behavior.

### Dependencies on Previous Stories

- Story 5.1: Imagen running on Streamable HTTP (concurrent transport prerequisite)
- Story 5.2: Metrics endpoint exists (for combined metrics verification)

### Anti-Patterns to Avoid

- Do NOT add threading or multiprocessing — the server is single-process async
- Do NOT add connection pooling or limiting — Starlette handles this
- Do NOT add locks around the session dict — unnecessary in single-threaded asyncio
- Do NOT add WebSocket or SSE for client notifications — plain HTTP polling per architecture
- Do NOT test with actual network connections in unit tests — mock at the tool/handler level

### Previous Story Learnings

- Run tests with `PYTHONPATH=""` to avoid ROS plugin conflicts
- Use `tmp_path` and `monkeypatch` for test isolation
- `asyncio.gather` or `TaskGroup` for concurrent test assertions

### References

- [Source: documents/planning-artifacts/architecture-mothership.md#Network Transport]
- [Source: documents/planning-artifacts/epics.md#Story 5.3]
- [Source: documents/planning-artifacts/prd.md#FR12]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- None

### Completion Notes List

- Confirmed Starlette/uvicorn natively handles concurrent connections — no server config changes needed
- Added 6 concurrent connectivity tests using `asyncio.gather` for parallel execution
- Verified concurrent `generate_image` calls return independent results (different session_ids, different image_paths)
- Verified session isolation — concurrent clients create separate sessions, UUID-keyed dict prevents collisions
- Verified client disconnect resilience — removing one client's session doesn't affect other clients
- Verified combined metrics — concurrent requests from multiple clients correctly increment shared counters
- Verified concurrent tool listing — read-only schema access is naturally safe
- No production code changes — this story is pure verification through tests
- 184/186 total tests pass (2 pre-existing failures unrelated to this story)

### Change Log

- 2026-04-07: Story 5.3 implementation complete — concurrent connectivity verified through 6 new tests

### File List

- `tests/servers/imagen/test_server.py` — modified (added TestConcurrentConnectivity class with 6 tests, added asyncio import)
