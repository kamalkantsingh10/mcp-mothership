# Story 7.3: Scoring, Reviews & Batch Tools

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an agent,
I want to score places with Bayesian weighting, read reviews as-is, and batch-score multiple queries concurrently,
so that I can rank travel options and surface curated context without forcing the caller to parse raw Google responses.

## Acceptance Criteria

1. **Given** `score_place(place_id: str, category: "attraction"|"restaurant"|"hotel" | None = None)` **When** the tool is invoked with a valid place_id and no category **Then** it fetches details via `get_place_details` **And** infers category from `primaryType`: values matching attraction keywords (`tourist_attraction`, `museum`, `park`, `landmark`, `historical_landmark`, `art_gallery`, `zoo`, `aquarium`, `amusement_park`, `stadium`) → attraction; values matching restaurant keywords (`restaurant`, `cafe`, `bar`, `bakery`, `meal_takeaway`, `meal_delivery`, `food`) → restaurant; values matching lodging keywords (`lodging`, `hotel`) → hotel; **And** when inference is ambiguous (no match), defaults to `restaurant`

2. **Given** rating R, user_rating_count v, category mean C, confidence threshold m **When** the Bayesian score is computed **Then** it uses the formula `score = (v / (v + m)) * R + (m / (v + m)) * C` **And** constants are: attractions `C=4.3 / m=500`, restaurants `C=4.1 / m=100`, hotels `C=4.0 / m=200` **And** the result is rounded to 2 decimal places

3. **Given** a place with no rating and/or no user_rating_count **When** `score_place` is called **Then** `bayesian_score` is still returned (treating missing R or v as 0 — formula shrinks fully toward C) **And** `rating` and `review_count` are surfaced as `null` where absent in the source

4. **Given** the `score_place` response shape **When** returned **Then** it contains exactly: `place_id, name, latitude, longitude, category, rating, review_count, bayesian_score, price_level, is_open_now, business_status, primary_type, types, editorial_summary, has_editorial, google_maps_uri` **And** no tiering, no "value/overpriced" judgments, no recommendation flags are included **And** `has_editorial` is `true` iff `editorial_summary` is non-null

5. **Given** `summarize_reviews(place_id: str)` **When** the tool is invoked **Then** it fetches Place Details and extracts the `reviews` field **And** returns up to 5 reviews as `[{author, rating, text, relative_time}]` **And** no LLM summarization occurs at this layer — the caller summarizes if desired

6. **Given** `batch_score(queries: list[str], type: str = "any")` **When** the tool is invoked with N queries **Then** it runs `search_places` for each query, takes the top result, then `score_place` on that place_id **And** execution is concurrent via `httpx.AsyncClient` with `asyncio.Semaphore(10)` **And** the response is `[{query, name, latitude, longitude, score_result}]` **And** queries returning no results surface with `score_result: null` and `name: null` — not an exception

7. **Given** `tests/servers/places/test_smoke.py` **When** I run it with a live `GOOGLE_PLACES_API_KEY` in `.env` **Then** all 5 Places tools execute end-to-end **And** smoke-test targets are: attraction → "Vianden Castle", restaurant → "Chiggeri Luxembourg", hotel → "Le Place d'Armes Luxembourg" **And** each target returns a non-null Bayesian score and flattened coordinates **And** the smoke test is marked `@pytest.mark.live` (or equivalent) so it is SKIPPED by default in the unit-test run

8. **Given** `tests/servers/places/test_scoring.py` **When** I run it **Then** all Bayesian tests pass: famous landmark (high R, large v) scores close to R; new restaurant (R=4.8, v=3) shrinks toward C=4.1; missing rating shrinks fully to C for the category; category inference resolves correctly for each keyword group

9. **Given** the full test suite **When** I run `PYTHONPATH="" poetry run pytest -v` (excluding live smoke) **Then** all Story 7.1, 7.2, and 7.3 tests pass **And** zero regressions against Epics 1-6 tests

## Tasks / Subtasks

- [x] **Task 1: Add scoring constants and helpers to `servers/places/server.py`** (AC: #1, #2)
  - [x] Add module-level constants (near the type-mapping constants from 7.2):
    ```python
    _SCORING_CONSTANTS: dict[str, tuple[float, int]] = {
        # category: (C mean, m confidence threshold)
        "attraction": (4.3, 500),
        "restaurant": (4.1, 100),
        "hotel": (4.0, 200),
    }

    _CATEGORY_KEYWORDS: dict[str, frozenset[str]] = {
        "attraction": frozenset({
            "tourist_attraction", "museum", "park", "landmark",
            "historical_landmark", "art_gallery", "zoo", "aquarium",
            "amusement_park", "stadium",
        }),
        "restaurant": frozenset({
            "restaurant", "cafe", "bar", "bakery",
            "meal_takeaway", "meal_delivery", "food",
        }),
        "hotel": frozenset({"lodging", "hotel"}),
    }
    ```
  - [x] Add `_infer_category(primary_type: str | None) -> str`:
    ```python
    def _infer_category(primary_type: str | None) -> str:
        """Infer scoring category from Google primaryType. Defaults to 'restaurant'."""
        if primary_type:
            for category, keywords in _CATEGORY_KEYWORDS.items():
                if primary_type in keywords:
                    return category
        return "restaurant"
    ```
  - [x] Add `_bayesian_score(rating: float | None, review_count: int | None, category: str) -> float`:
    ```python
    def _bayesian_score(
        rating: float | None,
        review_count: int | None,
        category: str,
    ) -> float:
        """Compute (v/(v+m))*R + (m/(v+m))*C, rounded to 2 decimal places.

        Missing R or v → treat as 0. With v=0, result equals C (full shrinkage).
        Unknown category → fall back to restaurant constants.
        """
        C, m = _SCORING_CONSTANTS.get(category, _SCORING_CONSTANTS["restaurant"])
        R = float(rating) if rating is not None else 0.0
        v = int(review_count) if review_count is not None else 0
        denom = v + m
        # denom is m + v, m >= 100 always → never zero
        score = (v / denom) * R + (m / denom) * C
        return round(score, 2)
    ```

- [x] **Task 2: Implement `score_place` tool** (AC: #1, #2, #3, #4)
  - [x] Tool wrapper follows the 7.1 pattern exactly:
    ```python
    @mcp.tool()
    async def score_place(
        place_id: str,
        category: str | None = None,
    ) -> dict:
        """Score a place with Bayesian-weighted ranking — raw signals only.

        Places API SKU tier: Place Details (New) — Advanced. One API call per invocation.
        Returns raw scoring signals. Tiering and value judgments are the caller's job.

        Args:
            place_id: Google place_id (with or without 'places/' prefix).
            category: Optional scoring category. If None, inferred from primaryType.
                One of "attraction", "restaurant", "hotel".

        Returns:
            Dict with: place_id, name, latitude, longitude, category, rating,
            review_count, bayesian_score, price_level, is_open_now, business_status,
            primary_type, types, editorial_summary, has_editorial, google_maps_uri.
            On error: {"error": "...", "code": "NOT_FOUND|QUOTA|AUTH|UNKNOWN"}
        """
        global _request_count, _error_count, _last_request_time
        _request_count += 1
        _last_request_time = datetime.now(timezone.utc).isoformat()
        try:
            return await _score_place_impl(place_id, category)
        except Exception as exc:
            _error_count += 1
            return _to_error_response(exc)
    ```
  - [x] Implement `_score_place_impl(place_id, category)`:
    1. Validate `category` if provided — if not in `{"attraction", "restaurant", "hotel", None}`, raise `ConfigurationError(f"Invalid category: {category}")`
    2. Fetch details by calling `_get_place_details_impl(place_id)` directly (NOT the `get_place_details` tool wrapper — that would double-increment metrics). If `_get_place_details_impl` raises, it bubbles up to the tool wrapper's `except` and becomes an error response
    3. Infer category if not provided: `category = category or _infer_category(details.get("primary_type"))`
    4. Compute Bayesian score: `score = _bayesian_score(details.get("rating"), details.get("user_rating_count"), category)`
    5. Extract `is_open_now` from `current_opening_hours`:
       ```python
       coh = details.get("current_opening_hours") or {}
       is_open_now = coh.get("openNow") if isinstance(coh, dict) else None
       ```
    6. Build and return the exact response shape (see below — order doesn't matter for JSON but field set is fixed):
       ```python
       return {
           "place_id": details["place_id"],
           "name": details["name"],
           "latitude": details["latitude"],
           "longitude": details["longitude"],
           "category": category,
           "rating": details.get("rating"),
           "review_count": details.get("user_rating_count"),
           "bayesian_score": score,
           "price_level": details.get("price_level"),
           "is_open_now": is_open_now,
           "business_status": details.get("business_status"),
           "primary_type": details.get("primary_type"),
           "types": details.get("types") or [],
           "editorial_summary": details.get("editorial_summary"),
           "has_editorial": details.get("editorial_summary") is not None,
           "google_maps_uri": details.get("google_maps_uri"),
       }
       ```
  - [x] Do NOT add any field that isn't in the AC #4 list. No tiering. No `"recommended": True`. No value flags.

- [x] **Task 3: Implement `summarize_reviews` tool** (AC: #5)
  - [x] Tool wrapper (same pattern):
    ```python
    @mcp.tool()
    async def summarize_reviews(place_id: str) -> dict | list:
        """Return up to 5 Google reviews as-is (no LLM summarization).

        Places API SKU tier: Place Details (New) — Advanced. One API call per invocation.

        Args:
            place_id: Google place_id (with or without 'places/' prefix).

        Returns:
            List of review dicts with keys: author, rating, text, relative_time.
            On error: {"error": "...", "code": "NOT_FOUND|QUOTA|AUTH|UNKNOWN"}
        """
        global _request_count, _error_count, _last_request_time
        _request_count += 1
        _last_request_time = datetime.now(timezone.utc).isoformat()
        try:
            return await _summarize_reviews_impl(place_id)
        except Exception as exc:
            _error_count += 1
            return _to_error_response(exc)
    ```
  - [x] Implement `_summarize_reviews_impl(place_id)`:
    1. Call `_get_place_details_impl(place_id)` — reuse the existing helper
    2. Extract reviews: `raw_reviews = details.get("reviews") or []`
    3. Reshape up to the first 5 (Google already caps at 5 when reviews are requested via FieldMask, but slice defensively):
       ```python
       reshaped = []
       for r in raw_reviews[:5]:
           text_obj = r.get("text") or {}
           author_obj = r.get("authorAttribution") or {}
           reshaped.append({
               "author": author_obj.get("displayName"),
               "rating": r.get("rating"),
               "text": text_obj.get("text") if isinstance(text_obj, dict) else text_obj,
               "relative_time": r.get("relativePublishTimeDescription"),
           })
       return reshaped
       ```
  - [x] Return an empty list (not an error) if the place has zero reviews — that's valid data, not a failure

- [x] **Task 4: Implement `batch_score` tool with concurrency** (AC: #6)
  - [x] Tool wrapper:
    ```python
    @mcp.tool()
    async def batch_score(
        queries: list[str],
        type: str = "any",
    ) -> dict | list:
        """Run search + score concurrently for a list of queries.

        Places API SKU tier: Text Search (New) + Place Details (New). TWO API calls per
        non-empty query. With no cache, this hits the API N*2 times per batch.

        Args:
            queries: List of free-text search queries (e.g., ["ramen Luxembourg", "sushi Paris"]).
            type: Filter applied to every search — "attraction", "restaurant", "hotel", "any".

        Returns:
            List of dicts: {query, name, latitude, longitude, score_result}. If a query
            returns no results, score_result is null and name/coordinates are null.
            Top-level errors (invalid type, etc.) return {"error": "...", "code": "..."}.
        """
        global _request_count, _error_count, _last_request_time
        _request_count += 1
        _last_request_time = datetime.now(timezone.utc).isoformat()
        try:
            return await _batch_score_impl(queries, type)
        except Exception as exc:
            _error_count += 1
            return _to_error_response(exc)
    ```
  - [x] Implement `_batch_score_impl(queries, type)`:
    1. Validate `type` as `_search_places_impl` does — invalid type raises `ConfigurationError` which propagates to the wrapper
    2. Create `semaphore = asyncio.Semaphore(10)` — module-local, not module-level (per-call isolation is cleaner)
    3. Define inner coro:
       ```python
       async def _one(query: str) -> dict:
           async with semaphore:
               try:
                   results = await _search_places_impl(query, type, None, 1)
                   if not results:
                       return {"query": query, "name": None, "latitude": None, "longitude": None, "score_result": None}
                   top = results[0]
                   # score_result's own error handling returns a dict; never raises here
                   score = await _score_place_impl(top["place_id"], None)
                   return {
                       "query": query,
                       "name": top.get("name"),
                       "latitude": top.get("latitude"),
                       "longitude": top.get("longitude"),
                       "score_result": score,
                   }
               except Exception as exc:
                   # Per-query failure must not fail the batch. Log and return a per-query error stub.
                   logger.warning("batch_score query failed: %r (%s)", query, exc)
                   return {
                       "query": query,
                       "name": None,
                       "latitude": None,
                       "longitude": None,
                       "score_result": _to_error_response(exc),
                   }
       ```
    4. Execute: `return await asyncio.gather(*[_one(q) for q in queries])`
  - [x] Each concurrent branch catches its own exception. The batch as a whole only fails if the `type` validation raises — that's an up-front caller error, correct to surface as a single error response

- [x] **Task 5: Write `tests/servers/places/test_scoring.py`** (AC: #1, #2, #3, #4, #8)
  - [x] Unit-level tests (no HTTP):
    - `test_bayesian_famous_landmark_close_to_rating` — `_bayesian_score(4.6, 50000, "attraction")` → close to 4.6 (v >> m)
    - `test_bayesian_new_restaurant_shrinks_toward_C` — `_bayesian_score(4.8, 3, "restaurant")` → approaches 4.12 (≈ (3/103)*4.8 + (100/103)*4.1)
    - `test_bayesian_missing_rating_returns_C_for_category` — `_bayesian_score(None, None, "hotel")` → 4.0 (m/m * C = C)
    - `test_bayesian_missing_rating_only_returns_C` — `_bayesian_score(None, 1000, "restaurant")` → (1000/1100)*0 + (100/1100)*4.1 ≈ 0.37 (documents the edge case — R defaults to 0, so missing rating + high review count shrinks toward 0; this is intentional per AC #3)
    - `test_bayesian_unknown_category_uses_restaurant_constants`
    - `test_bayesian_rounded_to_2dp`
  - [x] Category inference tests:
    - `test_infer_category_attraction_keywords` — `museum`, `park`, `landmark` → `"attraction"`
    - `test_infer_category_restaurant_keywords` — `cafe`, `bar`, `bakery` → `"restaurant"`
    - `test_infer_category_hotel_keywords` — `lodging`, `hotel` → `"hotel"`
    - `test_infer_category_unknown_defaults_to_restaurant` — `"car_dealer"` → `"restaurant"`
    - `test_infer_category_none_defaults_to_restaurant`
  - [x] `score_place` integration tests (mock `_get_place_details_impl` at that boundary):
    - `test_score_place_returns_exact_shape` — assert the returned dict's keys are EXACTLY the 16 documented fields in AC #4 (no more, no fewer)
    - `test_score_place_infers_category_from_primary_type` — mock details with `primary_type: "museum"` → returned `category == "attraction"`
    - `test_score_place_uses_provided_category` — explicit `category="hotel"` overrides primaryType inference
    - `test_score_place_invalid_category_returns_unknown_error` — `category="food_truck"` → `{"code": "UNKNOWN", ...}`
    - `test_score_place_has_editorial_true_when_summary_present`
    - `test_score_place_has_editorial_false_when_summary_null`
    - `test_score_place_is_open_now_from_current_opening_hours`
    - `test_score_place_is_open_now_null_when_hours_missing`
    - `test_score_place_not_found_propagates_error` — mock `_get_place_details_impl` to raise `PlaceNotFoundError` → `{"code": "NOT_FOUND", ...}`
    - `test_score_place_metrics_increment_on_success`
    - `test_score_place_metrics_increment_on_error`

- [x] **Task 6: Write `tests/servers/places/test_reviews.py`** (AC: #5)
  - [x] Tests:
    - `test_summarize_reviews_reshapes_to_four_fields` — mock details with 3 reviews, assert each item has exactly `{author, rating, text, relative_time}` keys
    - `test_summarize_reviews_extracts_author_from_attribution` — mock `authorAttribution: {displayName: "Jane", uri: "..."}` → returned `author: "Jane"`
    - `test_summarize_reviews_extracts_text_from_text_object` — mock `text: {text: "Great place", languageCode: "en"}` → returned `text: "Great place"`
    - `test_summarize_reviews_uses_relative_publish_time_description` → returned `relative_time: "a month ago"`
    - `test_summarize_reviews_caps_at_5` — mock 8 reviews, returned list length is 5
    - `test_summarize_reviews_empty_when_no_reviews` — mock details with no `reviews` field → returns `[]`
    - `test_summarize_reviews_not_found_returns_error_dict`
    - `test_summarize_reviews_metrics_increment`

- [x] **Task 7: Write `tests/servers/places/test_batch.py`** (AC: #6)
  - [x] Tests:
    - `test_batch_score_runs_all_queries` — mock `_search_places_impl` and `_score_place_impl`, pass 3 queries, assert 3 results
    - `test_batch_score_empty_result_for_query_surfaces_nulls` — mock `_search_places_impl` to return `[]` for one query, assert that query's result has `name: null`, `score_result: null`
    - `test_batch_score_per_query_error_does_not_fail_batch` — mock `_search_places_impl` to raise `PlaceNotFoundError` for one query → that query's `score_result` is an error dict, but OTHER queries complete normally
    - `test_batch_score_invalid_type_returns_unknown_error` — passes validation failure up as a batch-level error (single dict response, not list)
    - `test_batch_score_concurrency_capped_at_10` — spy on the semaphore OR use a concurrency-counting mock (increment a counter in the mocked impl, assert peak count ≤ 10). Use `asyncio.Event` for deterministic synchronization if needed
    - `test_batch_score_returns_result_per_query_in_order` — results list length equals input queries length; `asyncio.gather` preserves order
  - [x] Testing concurrency: you can use a simple counter + `asyncio.Event` pattern, e.g.:
    ```python
    active = 0
    peak = 0
    event = asyncio.Event()
    async def fake_search(*a, **k):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return [...]
    ```

- [x] **Task 8: Write `tests/servers/places/test_smoke.py`** (AC: #7)
  - [x] Structure:
    ```python
    """Live end-to-end smoke tests against the real Google Places API.

    Requires GOOGLE_PLACES_API_KEY in .env. Skipped by default — run with:
        PYTHONPATH="" poetry run pytest tests/servers/places/test_smoke.py -v -m live
    """
    import os
    import pytest

    pytestmark = pytest.mark.skipif(
        not os.getenv("GOOGLE_PLACES_API_KEY"),
        reason="GOOGLE_PLACES_API_KEY not set — skipping live Places API smoke tests",
    )
    ```
  - [x] Register the `live` marker in `pyproject.toml` `[tool.pytest.ini_options]`:
    ```toml
    markers = ["live: marks tests that hit live external APIs (deselect with '-m \"not live\"')"]
    ```
    Also update `addopts` to include `-m "not live"` so the default test run skips live tests. Alternatively, rely on the `skipif` gate above and skip the marker setup — that's simpler and is the preferred approach unless markers are already established elsewhere. **Recommended: use `skipif` only, no marker changes to pyproject.toml.**
  - [x] Tests (three targets):
    - `test_smoke_attraction_vianden_castle`:
      1. `search_places("Vianden Castle", type="attraction", max_results=1)` → assert at least 1 result, get the place_id
      2. `get_place_details(place_id)` → assert `latitude` between 49.9 and 50.0, `longitude` between 6.1 and 6.3, `name` contains "Vianden"
      3. `score_place(place_id)` → assert `bayesian_score` is a float, `category == "attraction"`, `has_editorial` is a bool
      4. `summarize_reviews(place_id)` → assert ≤ 5 reviews, each has the 4 required keys
    - `test_smoke_restaurant_chiggeri_luxembourg`:
      - Similar flow, target "Chiggeri Luxembourg", category "restaurant"
    - `test_smoke_hotel_le_place_darmes_luxembourg`:
      - Similar flow, target "Le Place d'Armes Luxembourg", category "hotel"
    - `test_smoke_batch_all_three`:
      - `batch_score(["Vianden Castle", "Chiggeri Luxembourg", "Le Place d'Armes Luxembourg"])` → assert 3 results, each with a non-null `score_result`
  - [x] These tests make live API calls and will cost SKU credits. Keep the count minimal; don't loop or retry.

- [x] **Task 9: Regression and finalization** (AC: #9)
  - [x] `PYTHONPATH="" poetry run pytest tests/servers/places/ -v` — all non-live Places tests pass (smoke tests SKIPPED if no live API key)
  - [x] `PYTHONPATH="" poetry run pytest -v` — zero regressions; record totals
  - [x] Optional: if live API key is configured, run `PYTHONPATH="" poetry run pytest tests/servers/places/test_smoke.py -v` and record results in Completion Notes
  - [x] End-to-end dashboard validation: start Mothership, start Places server via dashboard, invoke all 5 tools from an MCP client (Claude Code, Claude Desktop, or MCP inspector), confirm dashboard metrics increment and `/metrics` endpoint reflects the counts

## Dev Notes

### Architecture Compliance

All constraints from Stories 7.1 and 7.2 carry forward. Story 7.3 adds:

- **Concurrency:** Pure `asyncio` with `asyncio.Semaphore(10)` — no threads, no external concurrency libraries. FastMCP's event loop handles the rest
- **Scoring ownership:** All Bayesian math lives in `servers/places/server.py`. Do NOT externalize to `shared/` — this is Places-specific domain logic [Source: architecture-mothership.md#Architectural Boundaries]
- **No persistent state:** In-memory metrics only, no persisted scoring cache. Every `score_place` call hits the API once (for details). Every `batch_score` of N queries hits the API 2N times. Costs documented in `PRD#PFR8` docstring requirement [Source: Sprint Change Proposal 2026-04-19]

### The Big Picture of 7.3's Three Tools

- `score_place` = 1 Place Details call + local math
- `summarize_reviews` = 1 Place Details call + reshape (uses same FieldMask; full details, but caller only sees reviews)
- `batch_score` = N Text Search calls + N Place Details calls, concurrent

Wasteful? A little — `summarize_reviews` fetches 27 FieldMask fields when it only uses reviews. Acceptable for MVP (no caching means we can't amortize across `score_place` + `summarize_reviews` for the same place). Phase 2 will revisit with caching + narrower FieldMask for `summarize_reviews`.

### Bayesian Formula — Concrete Examples

- Vianden Castle (hypothetical): R=4.6, v=9876, attraction (C=4.3, m=500)
  - score = (9876/10376)*4.6 + (500/10376)*4.3 = 0.9518*4.6 + 0.0482*4.3 ≈ 4.58
  - Famous landmark stays close to its rating — correct behavior
- New restaurant: R=4.8, v=3, restaurant (C=4.1, m=100)
  - score = (3/103)*4.8 + (100/103)*4.1 = 0.0291*4.8 + 0.9709*4.1 ≈ 4.12
  - Low-volume review set heavily shrunk — correct behavior (one five-star review isn't proof of excellence)
- Unrated hotel: R=None→0, v=None→0, hotel (C=4.0, m=200)
  - score = (0/200)*0 + (200/200)*4.0 = 4.0
  - Full shrinkage to category mean — correct, signals "we have no information"

### Why `score_place` Calls `_get_place_details_impl` Not `get_place_details`

Calling the tool wrapper from within another tool wrapper would double-increment `_request_count` and potentially double-count errors. Always call the `_*_impl` layer internally:

- `score_place` → `_get_place_details_impl`
- `summarize_reviews` → `_get_place_details_impl`
- `batch_score` → `_search_places_impl` + `_score_place_impl`

The tool wrapper's ONLY job is: increment metrics → call impl → translate errors.

### Google Places Data Shapes (Reminder From 7.2)

- `current_opening_hours.openNow` is a `bool | null` (Google sends `true`, `false`, or omits the field)
- `reviews[].text` is an object `{text, languageCode}` — flatten to the string
- `reviews[].authorAttribution.displayName` is the author's name
- `reviews[].relativePublishTimeDescription` is the human-readable time ago (e.g., "a month ago")
- `reviews[].rating` is an integer 1-5
- `priceLevel` is an enum string like `"PRICE_LEVEL_MODERATE"` — pass through as-is

### Files to Modify

```
servers/places/server.py       # Add scoring constants, helpers, score_place, summarize_reviews, batch_score
```

### Files to Create

```
tests/servers/places/test_scoring.py
tests/servers/places/test_reviews.py
tests/servers/places/test_batch.py
tests/servers/places/test_smoke.py
```

### Files to NOT Modify

- `pyproject.toml` — no new deps unless the `live` marker is added (recommendation: use `skipif`, don't add the marker)
- `shared/*` — scoring is Places-specific
- `servers/places/config.py` — no new config fields needed
- `servers/imagen/*`, `mothership/*` — no cross-touch

### Anti-Patterns to Avoid

- Do NOT implement caching — `functools.lru_cache`, `diskcache`, in-memory dicts keyed by place_id → all explicitly rejected
- Do NOT add tiering (`"tier": "excellent"`), value judgments (`"overpriced": True`), or recommendation flags to `score_place` output — that belongs in a downstream layer
- Do NOT loop sequentially in `batch_score` — concurrency is a hard requirement, not an optimization
- Do NOT use `asyncio.Semaphore(N)` with N > 10 — Google Places rate limits apply, and MVP wants to stay well within them
- Do NOT add LLM calls to `summarize_reviews` — the tool returns raw reviews; summarization is the agent's job
- Do NOT hold a module-level `httpx.AsyncClient` inside `batch_score` — `_places_request` from 7.2 already creates per-request clients; reusing the same pattern keeps the concurrency simple
- Do NOT log full review text or editorial summaries at INFO — these can be long and sometimes contain user-generated content
- Do NOT let a single failing `batch_score` query fail the batch — per-query `try/except` is mandatory
- Do NOT run the live smoke test in CI or default test runs — gate with `skipif` on `GOOGLE_PLACES_API_KEY`
- Do NOT add `place_id` normalization differently from 7.2 — reuse the `_flatten_*` helpers that already strip the `places/` prefix

### Previous Story Intelligence

From Story 7.2 (Search & Details):
- `_places_request` is the HTTP boundary — never call `httpx` directly in tools
- `_flatten_place_details` returns keys like `rating`, `user_rating_count`, `editorial_summary` (strings, not objects), `current_opening_hours` (dict as-returned by Google), etc.
- Tool wrapper pattern: metrics increment → try → impl → except → `_to_error_response`
- `_get_place_details_impl` and `_search_places_impl` are the non-metrics-incrementing entry points for internal reuse

From Story 7.1 (Foundation):
- `_to_error_response(exc)` handles: `CredentialError` → AUTH, `PlaceNotFoundError` → NOT_FOUND, `ApiUnavailableError` with quota/rate/429 → QUOTA, other `ApiUnavailableError` → UNKNOWN, `ConfigurationError` → UNKNOWN, else → UNKNOWN (sanitized)
- Module-level metrics counters — do NOT create new ones for 7.3
- `PYTHONPATH=""` for pytest

### Testing Standards

- **Mock boundary for unit tests:** `_get_place_details_impl` and `_search_places_impl`. Do NOT mock `httpx` in scoring/batch tests — that's 7.2's concern and already covered
- **Concurrency testing:** Use counter + peak-tracking pattern, NOT `time.sleep`. Tests must be deterministic and fast
- **Bayesian math:** Test edge cases (missing R, missing v, v=0, huge v) — the formula is the spec, so prove it explicitly
- **Smoke tests:** Live API, gated by `skipif`. Assert on ranges (e.g., Vianden latitude between 49.9 and 50.0) not exact values — Google may drift
- **Run commands:**
  - Default (skips live): `PYTHONPATH="" poetry run pytest -v`
  - Places only: `PYTHONPATH="" poetry run pytest tests/servers/places/ -v`
  - Live smoke (requires API key): `PYTHONPATH="" GOOGLE_PLACES_API_KEY=... poetry run pytest tests/servers/places/test_smoke.py -v`

### End-of-Story Validation Checklist (for Dev)

Before marking 7.3 as `review`, confirm:

1. [ ] All 5 tools (`search_places`, `get_place_details`, `score_place`, `summarize_reviews`, `batch_score`) appear in `tools/list` over Streamable HTTP
2. [ ] `/metrics` endpoint increments `request_count` once per tool invocation (success or failure)
3. [ ] Places server appears on the Mothership dashboard with live status and metrics
4. [ ] Full `pytest` suite passes (excluding live smoke) with zero regressions
5. [ ] If live API key available: `test_smoke.py` passes for all 3 targets
6. [ ] No credential values appear in any log file under `logs/`
7. [ ] `score_place` response has EXACTLY the 16 fields in AC #4

### Project Structure Notes

No deviations. All new code in `servers/places/server.py` (single file grows — acceptable, matches `servers/imagen/server.py`'s size). All new tests under `tests/servers/places/` mirroring source.

### References

- [Source: documents/planning-artifacts/epics.md#Story 7.3 — Scoring, Reviews & Batch Tools]
- [Source: documents/planning-artifacts/prd.md#Places MCP Capability — PFR36 (score_place), PFR37 (Bayesian formula), PFR38 (summarize_reviews), PFR39 (batch_score)]
- [Source: documents/planning-artifacts/architecture-mothership.md#Architectural Boundaries]
- [Source: documents/planning-artifacts/sprint-change-proposal-2026-04-19.md — no-caching decision, smoke test targets]
- [Source: documents/implementation-artifacts/7-1-places-mcp-foundation.md — `_to_error_response`, `PlaceNotFoundError`, metrics counter pattern]
- [Source: documents/implementation-artifacts/7-2-search-and-details-tools.md — `_places_request`, `_flatten_*`, `_get_place_details_impl`, `_search_places_impl`]
- [Source: servers/imagen/server.py — wrapper/impl split precedent]
- [Source: shared/errors.py — exception hierarchy]

### Review Findings

Adversarial code review (2026-04-19) — Blind Hunter + Edge Case Hunter + Acceptance Auditor.

- [x] [Review][Decision] **Per-query failures in `batch_score` do not increment `_error_count`.** Resolved 2026-04-19: keep tool-level metrics semantics (1 batch call = 1 `_request_count` delta, regardless of inner per-query outcomes). Consistent with every other tool in the server; per-query failures are surfaced to the caller via the `score_result` error dict. Dashboard fidelity revisit is logged in `deferred-work.md`.
- [x] [Review][Patch] **[MEDIUM]** `test_bayesian_rounded_to_2dp` rewritten — uses `_bayesian_score(4.5, 1, "restaurant")` (raw ≈ 4.10396), asserts exact `== 4.10`. Non-tautological and catches `round(..., 2)` removal.
- [x] [Review][Patch] **[LOW]** Restaurant and hotel smoke tests now assert `isinstance(score["latitude"], float)` and `isinstance(score["longitude"], float)` (AC #7 coord contract).
- [x] [Review][Patch] **[LOW]** `_score_place_impl` now uses `details.get("place_id")` / `get("name")` / `get("latitude")` / `get("longitude")` for consistency with the rest of the function. `_flatten_place_details` editorial extraction now uses `isinstance(editorial, dict)` as the guard instead of truthiness.
- [x] [Review][Defer] Semaphore held across both `_search_places_impl` and `_score_place_impl` inside `_one` — effective concurrency cap is split between search+score pairs, not 10 of each — deferred, matches spec Task 4 pattern; changing splits the semantic.
- [x] [Review][Defer] `batch_score` with duplicate queries fires duplicate API calls; no dedup — deferred, enhancement.
- [x] [Review][Defer] `batch_score` does not short-circuit on persistent AUTH/QUOTA failures; on bad credentials, all N queries fire and all fail identically — deferred, acceptable under concurrency=10 + observability decision D1.
- [x] [Review][Defer] `_summarize_reviews_impl` does `r.get("text")` assuming each review entry is a dict; a non-dict entry raises AttributeError → UNKNOWN — deferred, defensive; Google schema is stable.
- [x] [Review][Defer] `_bayesian_score` divides by `v + m`; future `m = 0` in `_SCORING_CONSTANTS` would raise ZeroDivisionError — deferred, no such constant today.
- [x] [Review][Defer] `current_opening_hours` silently resolves to `None` if Google returns a non-dict (e.g., a list of periods); no warning log — deferred, defensive.
- [x] [Review][Defer] `ConfigurationError` (raised for `type="car"` or `category="food_truck"`) maps to `UNKNOWN` rather than a distinct validation code — deferred, architectural refactor (add a `ValidationError` class to `shared/errors.py`).

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context)

### Debug Log References

- `PYTHONPATH="" poetry run pytest tests/servers/places/ -v` — 80 passed, 4 smoke tests SKIPPED (no live `GOOGLE_PLACES_API_KEY`)
- `PYTHONPATH="" poetry run pytest` — 280 passed, 4 skipped (smoke), 2 pre-existing unrelated imagen-config failures (`.env`-leak documented in Story 5.1)
- Tool registration verified: `mcp._tool_manager.list_tools()` returns `['search_places', 'get_place_details', 'score_place', 'summarize_reviews', 'batch_score']` — all 5 Places tools live

### Completion Notes List

- Added scoring constants: `_SCORING_CONSTANTS` (attractions C=4.3/m=500, restaurants C=4.1/m=100, hotels C=4.0/m=200), `_CATEGORY_KEYWORDS` for primaryType → category inference, and `_VALID_SCORING_CATEGORIES`.
- Implemented pure helpers `_infer_category` (defaults to `restaurant` when ambiguous) and `_bayesian_score` (formula `(v/(v+m))*R + (m/(v+m))*C`, missing R/v treated as 0, rounded to 2 decimals, unknown category falls back to restaurant constants).
- Implemented `_score_place_impl`, `_summarize_reviews_impl`, `_batch_score_impl` — each calls the `_*_impl` layer internally (never the tool wrapper) to avoid double metric increments.
- `score_place` returns EXACTLY the 16 fields in AC #4 (no tiering, no value judgments, no recommendation flags). `has_editorial` is `true` iff `editorial_summary` is non-null. `is_open_now` pulled from `current_opening_hours.openNow` if present, else `null`.
- `summarize_reviews` reshapes raw Google reviews to `{author, rating, text, relative_time}`, caps at 5 (slices defensively on top of Google's cap), returns `[]` when no reviews.
- `batch_score` uses a per-call `asyncio.Semaphore(10)` to cap concurrency, preserves input order via `asyncio.gather`, and catches per-query exceptions so one failure never fails the whole batch. Invalid `type` bubbles up as a single `{"code": "UNKNOWN"}` response (batch-level failure).
- Live smoke tests gated by `skipif` on `GOOGLE_PLACES_API_KEY` (and also skip when the CI placeholder `"test-key"` is in place). Targets: Vianden Castle (attraction), Chiggeri Luxembourg (restaurant), Le Place d'Armes Luxembourg (hotel), plus a `batch_score` of all three. No `pyproject.toml` marker changes — `skipif` is simpler and is what's recommended in the story notes.
- 33 new unit tests across `test_scoring.py` (21), `test_reviews.py` (8), `test_batch.py` (6), plus 4 live smoke tests. Total Places suite: 80 non-live + 4 skippable smoke = 84 tests.
- No new dependencies, no changes to `shared/`, `pyproject.toml`, `mothership/`, `servers/imagen/`, or `servers/places/config.py`.

### File List

- `servers/places/server.py` (modified — added scoring constants, `_infer_category`, `_bayesian_score`, `_score_place_impl`, `_summarize_reviews_impl`, `_batch_score_impl`, and the three tools)
- `tests/servers/places/test_scoring.py` (new)
- `tests/servers/places/test_reviews.py` (new)
- `tests/servers/places/test_batch.py` (new)
- `tests/servers/places/test_smoke.py` (new — live tests gated by skipif)
- `documents/implementation-artifacts/sprint-status.yaml` (modified — status transition)
