# Deferred Work

## Deferred from: code review of story 2-2 (2026-04-01)

- **Global `_yaml_config_path` concurrency hazard** — `shared/config.py` uses a module-level global to pass YAML path to settings source. Concurrent `from_yaml()` calls with different paths will clobber each other. Refactor to thread-safe approach when adding multi-server process support.
- **Module-level config in `servers/imagen/server.py`** — Config loaded at import time. Makes module impossible to import without valid environment. Consider moving to a startup function for testability.
- **`.env` and `config.yaml` resolved relative to CWD** — If server launched from different directory, config files won't be found. Consider resolving relative to `__file__` or project root.
- **Unpinned dependency versions** — `pydantic-settings = "*"` and `pyyaml = "*"` in pyproject.toml. Mitigated by poetry.lock but could break on `poetry update`.
- **`config.yaml` missing optional field documentation** — `imagen_model` and `imagen_gcp_region` not listed in config.yaml, reducing discoverability.

## Deferred from: code review of Epic 7 stories 7-1 / 7-2 / 7-3 (2026-04-19)

### Architecture (Mothership + shared)
- **Mothership status=misconfigured** — startup `CredentialError` causes subprocess crash; manager reports `status="crashed"`, indistinguishable from runtime crash. (from 7-1)
- **ValidationError class** — add to `shared/errors.py` distinct from `ConfigurationError`; map to a dedicated `code="VALIDATION"` at the tool boundary. Currently invalid tool arguments masquerade as `UNKNOWN`. (from 7-2 / 7-3)
- **PlacesQuotaError subclass** — substring match in `_to_error_response` for QUOTA is fragile; raise a typed error at the HTTP source instead. (from 7-2)

### HTTP robustness (servers/places/server.py)
- **3xx redirects** — enable `follow_redirects=True` on the `httpx.AsyncClient` or surface a dedicated error. (from 7-2)
- **HTTP 400 message passthrough** — Google returns `{"error": {"message": "..."}}` on 400; surface that instead of swallowing. (from 7-2)
- **Non-string `id` defensive coercion** — `_flatten_search_result` / `_flatten_place_details` `AttributeError` if Google returns `id` as int. (from 7-2)
- **Non-dict review entries** — `_summarize_reviews_impl` crashes on non-dict `reviews[i]`. Skip malformed. (from 7-3)
- **Non-dict `current_opening_hours`** — `_score_place_impl` silently returns `is_open_now=None`; log a warning. (from 7-3)

### Concurrency / observability
- **batch_score semaphore** — held across search+score; effective cap 10 pairs, not 10 of each. Revisit for throughput. (from 7-3)
- **batch_score AUTH short-circuit** — on bad credentials, all N queries fire and fail identically. Cancel pending tasks after first AUTH/QUOTA. (from 7-3)
- **batch_score dedup** — duplicate queries are fired as separate API calls. (from 7-3)
- **last_request_time semantics** — set BEFORE the request; should reflect END. GIL makes current behaviour correct, not accurate. (from 7-2 / 7-3)
- **Torn /metrics reads** — `/metrics` can report inconsistent `request_count > error_count + successes` during a tool call. Low risk under GIL. (from 7-2)
- **SKU-tier docstring accuracy** — `search_places` says Essentials, `get_place_details` says Advanced — verify against Google's current billing for the FieldMasks. (from 7-2)

### Test isolation
- **`test_mcp_server_default_port_is_8102` cwd-sensitive** — a local `config.yaml` with `places.port` overrides the default. Use `tmp_path` + cwd. (from 7-1)

### Connection pooling
- **Per-request `httpx.AsyncClient`** — spec-prescribed short-lived client wastes TLS handshakes. Revisit after persistent e2e tests exist. (from 7-2)

### Defensive numeric
- **Bayesian divide-by-zero** — if `_SCORING_CONSTANTS` added a category with `m=0`, `_bayesian_score` crashes. No such constant today. (from 7-3)
