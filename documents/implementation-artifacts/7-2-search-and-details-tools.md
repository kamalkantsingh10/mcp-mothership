# Story 7.2: Search & Details Tools

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an agent,
I want to search for places by query and fetch full details for any place,
so that I can surface tourist attractions, restaurants, and hotels with structured, flattened data ready for downstream scoring and review tools.

## Acceptance Criteria

1. **Given** `search_places(query: str, type: "attraction"|"restaurant"|"hotel"|"any" = "any", location_bias: str | None = None, max_results: int = 10)` **When** the tool is invoked with a query and a type **Then** it calls Google Places Text Search (New) with a tight FieldMask **And** `type` is mapped to `includedType`: attraction→`tourist_attraction`, restaurant→`restaurant`, hotel→`lodging`, any→no `includedType` **And** `location_bias` (when provided) is passed through to the request **And** the response is a list of up to `max_results` items with `{place_id, name, address, latitude, longitude, rating, user_rating_count, primary_type, price_level}` **And** `latitude` / `longitude` are top-level, decimal degrees WGS84, 6 decimal places

2. **Given** `get_place_details(place_id: str)` **When** the tool is invoked **Then** it calls Google Place Details (New) with the exact FieldMask: `id, displayName, formattedAddress, location, rating, userRatingCount, regularOpeningHours, currentOpeningHours, websiteUri, internationalPhoneNumber, priceLevel, priceRange, businessStatus, editorialSummary, primaryType, types, reviews, googleMapsUri, dineIn, takeout, delivery, reservable, servesBreakfast, servesLunch, servesDinner, outdoorSeating, goodForChildren, allowsDogs` **And** `location.latitude` / `location.longitude` are flattened to top-level `latitude` / `longitude` **And** the nested `location` object is not returned **And** missing optional fields (e.g., rating, hours, editorialSummary) are returned as `null`

3. **Given** each tool's docstring **When** it is displayed to the caller **Then** it documents the Google Places SKU tier consumed (Text Search, Advanced Place Details)

4. **Given** a Google API auth error (e.g., 401/403) **When** surfaced to the tool boundary **Then** the response is `{"error": "Google Places authentication failed", "code": "AUTH"}`

5. **Given** a Google quota/rate-limit error (e.g., 429, `RESOURCE_EXHAUSTED`) **When** surfaced to the tool boundary **Then** the response is `{"error": "Google Places quota exceeded", "code": "QUOTA"}`

6. **Given** a Place Details call for a non-existent place_id (404) **When** surfaced to the tool boundary **Then** the response is `{"error": "Place not found", "code": "NOT_FOUND"}`

7. **Given** `tests/servers/places/test_search.py` and `tests/servers/places/test_details.py` **When** I run them **Then** all tests pass with `httpx.AsyncClient` mocked at the request boundary **And** tests assert FieldMask is set on every outbound call **And** tests assert coordinate flattening and 6-decimal formatting **And** the full suite produces zero regressions against Stories 5.x and 7.1

## Tasks / Subtasks

- [x] **Task 1: Add module-level HTTP client helpers to `servers/places/server.py`** (AC: #1, #2, #4, #5, #6)
  - [x] Import: `import httpx` (already transitively available — see Dev Notes)
  - [x] Add two module-level constants near the top (after existing config/logging setup from 7.1):
    ```python
    _PLACES_AUTH_HEADER = "X-Goog-Api-Key"
    _PLACES_FIELDMASK_HEADER = "X-Goog-FieldMask"
    _PLACES_DETAILS_FIELDMASK = (
        "id,displayName,formattedAddress,location,rating,userRatingCount,"
        "regularOpeningHours,currentOpeningHours,websiteUri,internationalPhoneNumber,"
        "priceLevel,priceRange,businessStatus,editorialSummary,primaryType,types,"
        "reviews,googleMapsUri,dineIn,takeout,delivery,reservable,servesBreakfast,"
        "servesLunch,servesDinner,outdoorSeating,goodForChildren,allowsDogs"
    )
    _PLACES_SEARCH_FIELDMASK = (
        "places.id,places.displayName,places.formattedAddress,places.location,"
        "places.rating,places.userRatingCount,places.primaryType,places.priceLevel"
    )
    _TYPE_TO_INCLUDED_TYPE = {
        "attraction": "tourist_attraction",
        "restaurant": "restaurant",
        "hotel": "lodging",
    }
    ```
  - [x] Add an `async def _places_request(method: str, path: str, *, field_mask: str, json_body: dict | None = None) -> dict` helper that:
    1. Builds the full URL from `config.places_api_base_url + path`
    2. Sets headers: `X-Goog-Api-Key: config.google_places_api_key`, `X-Goog-FieldMask: field_mask`
    3. Uses `async with httpx.AsyncClient(timeout=config.places_http_timeout_seconds) as client:` (do NOT hold a module-level client — short-lived is simpler and avoids connection state leaks during tests)
    4. Calls `await client.request(method, url, headers=headers, json=json_body)`
    5. Maps HTTP status to typed exceptions:
       - `200` → return `response.json()`
       - `401` or `403` → raise `CredentialError("GOOGLE_PLACES_API_KEY", reason="Google Places authentication failed")`
       - `404` → raise `PlaceNotFoundError("Place not found")`
       - `429` → raise `ApiUnavailableError("Google Places quota exceeded")`
       - Any other non-2xx → raise `ApiUnavailableError(f"Google Places API error: HTTP {status}")`
       - `httpx.ConnectError` / `httpx.ReadTimeout` / `httpx.NetworkError` → raise `ApiUnavailableError("Network error calling Google Places API")`
  - [x] Do NOT log the API key. Log the URL, method, status, and FieldMask keys — never header values.

- [x] **Task 2: Implement `search_places` tool** (AC: #1, #3)
  - [x] Add this tool to `servers/places/server.py` using the wrapper pattern established in 7.1:
    ```python
    @mcp.tool()
    async def search_places(
        query: str,
        type: str = "any",
        location_bias: str | None = None,
        max_results: int = 10,
    ) -> dict | list:
        """Search Google Places by text query.

        Places API SKU tier: Text Search (New) — Essentials tier with this FieldMask.

        Args:
            query: Free-text search (e.g., "ramen in Luxembourg City").
            type: One of "attraction", "restaurant", "hotel", "any". Maps to Google
                includedType: tourist_attraction, restaurant, lodging, or unset.
            location_bias: Optional free-text bias (e.g., "Luxembourg"). Passed through
                as Google's locationBias.circle or text bias depending on input shape —
                for Story 7.2, pass as-is inside the request body's `locationBias.
                rectangle` / `.circle` ONLY if already a structured dict; for plain
                strings, prepend to the query text and leave locationBias unset.
            max_results: Max items to return, capped at 20 by Google.

        Returns:
            List of place dicts or an error dict on failure.
        """
        global _request_count, _error_count, _last_request_time
        _request_count += 1
        _last_request_time = datetime.now(timezone.utc).isoformat()
        try:
            return await _search_places_impl(query, type, location_bias, max_results)
        except Exception as exc:
            _error_count += 1
            return _to_error_response(exc)
    ```
  - [x] Implement `_search_places_impl`:
    1. Validate `type` is in `{"attraction", "restaurant", "hotel", "any"}` — if not, raise `ConfigurationError(f"Invalid type: {type}")`
    2. Build request body:
       ```python
       body: dict = {"textQuery": query, "maxResultCount": min(max_results, 20)}
       included_type = _TYPE_TO_INCLUDED_TYPE.get(type)
       if included_type:
           body["includedType"] = included_type
       if location_bias:
           # Location bias as plain string → fold into query text (simplest correct behavior)
           body["textQuery"] = f"{query} near {location_bias}"
       ```
    3. Call `data = await _places_request("POST", "/places:searchText", field_mask=_PLACES_SEARCH_FIELDMASK, json_body=body)`
    4. Flatten and normalize each result via `_flatten_search_result` (Task 4)
    5. Return the list (empty list if API returns `{}` with no `places` key — that's normal for zero-result queries)

- [x] **Task 3: Implement `get_place_details` tool** (AC: #2, #3, #4, #5, #6)
  - [x] Add tool with identical wrapper pattern:
    ```python
    @mcp.tool()
    async def get_place_details(place_id: str) -> dict:
        """Fetch full place details from Google Places.

        Places API SKU tier: Place Details (New) — Advanced tier with this FieldMask.

        Args:
            place_id: Google place_id (with or without the 'places/' prefix).

        Returns:
            Place dict with flattened latitude/longitude, or an error dict on failure.
        """
        global _request_count, _error_count, _last_request_time
        _request_count += 1
        _last_request_time = datetime.now(timezone.utc).isoformat()
        try:
            return await _get_place_details_impl(place_id)
        except Exception as exc:
            _error_count += 1
            return _to_error_response(exc)
    ```
  - [x] Implement `_get_place_details_impl`:
    1. Normalize place_id: strip leading `"places/"` if present (Google accepts both forms in URLs but not consistently; strip once and construct path as `/places/{place_id}`)
    2. Call `data = await _places_request("GET", f"/places/{place_id}", field_mask=_PLACES_DETAILS_FIELDMASK)`
    3. Pass through `_flatten_place_details` (Task 4) and return

- [x] **Task 4: Implement shape-normalization helpers** (AC: #1, #2, #7)
  - [x] Add two pure-function helpers in `servers/places/server.py`:
    ```python
    def _round_coord(value: float | None) -> float | None:
        return round(value, 6) if value is not None else None


    def _flatten_search_result(item: dict) -> dict:
        """Normalize a Text Search result into the tool's response shape."""
        loc = item.get("location") or {}
        display_name = item.get("displayName") or {}
        return {
            "place_id": (item.get("id") or "").removeprefix("places/"),
            "name": display_name.get("text"),
            "address": item.get("formattedAddress"),
            "latitude": _round_coord(loc.get("latitude")),
            "longitude": _round_coord(loc.get("longitude")),
            "rating": item.get("rating"),
            "user_rating_count": item.get("userRatingCount"),
            "primary_type": item.get("primaryType"),
            "price_level": item.get("priceLevel"),
        }


    def _flatten_place_details(item: dict) -> dict:
        """Normalize Place Details into the tool's response shape.

        Flattens location.latitude/longitude to top-level. Preserves all other
        FieldMask fields as-returned by Google. Missing optionals become None.
        """
        loc = item.get("location") or {}
        display_name = item.get("displayName") or {}
        editorial = item.get("editorialSummary") or {}
        return {
            "place_id": (item.get("id") or "").removeprefix("places/"),
            "name": display_name.get("text"),
            "address": item.get("formattedAddress"),
            "latitude": _round_coord(loc.get("latitude")),
            "longitude": _round_coord(loc.get("longitude")),
            "rating": item.get("rating"),
            "user_rating_count": item.get("userRatingCount"),
            "regular_opening_hours": item.get("regularOpeningHours"),
            "current_opening_hours": item.get("currentOpeningHours"),
            "website_uri": item.get("websiteUri"),
            "international_phone_number": item.get("internationalPhoneNumber"),
            "price_level": item.get("priceLevel"),
            "price_range": item.get("priceRange"),
            "business_status": item.get("businessStatus"),
            "editorial_summary": editorial.get("text") if editorial else None,
            "primary_type": item.get("primaryType"),
            "types": item.get("types") or [],
            "reviews": item.get("reviews") or [],
            "google_maps_uri": item.get("googleMapsUri"),
            "dine_in": item.get("dineIn"),
            "takeout": item.get("takeout"),
            "delivery": item.get("delivery"),
            "reservable": item.get("reservable"),
            "serves_breakfast": item.get("servesBreakfast"),
            "serves_lunch": item.get("servesLunch"),
            "serves_dinner": item.get("servesDinner"),
            "outdoor_seating": item.get("outdoorSeating"),
            "good_for_children": item.get("goodForChildren"),
            "allows_dogs": item.get("allowsDogs"),
        }
    ```
  - [x] The nested `location` object is intentionally NOT included in either output — consumers read the flat `latitude` / `longitude` keys
  - [x] `place_id` is always stripped of the `places/` prefix so Story 7.3's `batch_score` can feed it back into `get_place_details` without double-prefix bugs

- [x] **Task 5: Write `tests/servers/places/test_search.py`** (AC: #1, #3, #7)
  - [x] Use `respx` if available, otherwise mock `httpx.AsyncClient` directly via `unittest.mock.patch` — check `tests/mothership/test_manager.py` for the established pattern (Story 5.2 used `httpx` mocked via `patch`)
  - [x] Tests to write:
    - `test_search_places_returns_flattened_items` — mock response with one place, assert returned list has `latitude`/`longitude` as top-level 6-decimal floats, no nested `location`
    - `test_search_places_type_mapping_attraction` → `includedType: tourist_attraction` in request body
    - `test_search_places_type_mapping_restaurant` → `restaurant`
    - `test_search_places_type_mapping_hotel` → `lodging`
    - `test_search_places_type_any_omits_included_type` — no `includedType` key in request body
    - `test_search_places_invalid_type_returns_unknown_error` — type=`"car"` → `{"code": "UNKNOWN", ...}`
    - `test_search_places_location_bias_folds_into_query` — assert request body's `textQuery` contains both query and bias text
    - `test_search_places_max_results_capped_at_20` — call with `max_results=50`, assert `maxResultCount: 20` in body
    - `test_search_places_empty_result_returns_empty_list` — API returns `{}`, tool returns `[]`
    - `test_search_places_fieldmask_header_set` — inspect mock call args, assert `X-Goog-FieldMask` header contains `places.id,places.displayName,...`
    - `test_search_places_auth_header_set` — assert `X-Goog-Api-Key` header present, value matches config key
    - `test_search_places_401_returns_auth_error` — mock 401 response, tool returns `{"code": "AUTH", ...}`
    - `test_search_places_429_returns_quota_error`
    - `test_search_places_network_error_returns_unknown_error` — `httpx.ConnectError` → `{"code": "UNKNOWN", "error": "Network error calling Google Places API"}`
    - `test_search_places_metrics_increment_on_success` — `_request_count == 1`, `_error_count == 0`
    - `test_search_places_metrics_increment_on_error` — after error path, `_request_count == 1`, `_error_count == 1`

- [x] **Task 6: Write `tests/servers/places/test_details.py`** (AC: #2, #3, #6, #7)
  - [x] Tests to write:
    - `test_get_place_details_flattens_coordinates` — mock response with `location: {latitude: 49.7, longitude: 6.2}`, tool returns `latitude: 49.7`, no nested `location`
    - `test_get_place_details_rounds_coordinates_to_6dp` — mock `latitude: 49.71234567890` → returned as `49.712346`
    - `test_get_place_details_strips_places_prefix_from_id` — mock response with `id: "places/ChIJ..."` → tool returns `place_id: "ChIJ..."`
    - `test_get_place_details_handles_prefix_in_input` — input place_id `"places/ChIJxyz"` calls URL `/places/ChIJxyz` (not `/places/places/ChIJxyz`)
    - `test_get_place_details_missing_optionals_become_none` — sparse response (only `id` and `displayName`), assert `rating`, `editorial_summary`, `website_uri` etc. are all `None`
    - `test_get_place_details_editorial_summary_extracted_from_text_field` — Google returns `editorialSummary: {text: "...", languageCode: "en"}`, tool returns `editorial_summary: "..."` (the string, not the dict)
    - `test_get_place_details_fieldmask_header_set` — assert exact full FieldMask string is sent (compare against `_PLACES_DETAILS_FIELDMASK`)
    - `test_get_place_details_404_returns_not_found_error` — mock 404, tool returns `{"code": "NOT_FOUND", "error": "Place not found"}`
    - `test_get_place_details_metrics_increment_on_success`
    - `test_get_place_details_metrics_increment_on_error`
  - [x] Reuse autouse fixtures from 7.1's `test_server.py` — set API key via `monkeypatch.setenv`, reset metrics module globals between tests

- [x] **Task 7: Regression and full test run** (AC: #7)
  - [x] `PYTHONPATH="" poetry run pytest tests/servers/places/ -v` — all 7.1 + 7.2 tests pass
  - [x] `PYTHONPATH="" poetry run pytest -v` — zero regressions; record totals in Completion Notes
  - [x] Spot-check: start Mothership (`poetry run python -m mothership`), hit `POST /api/servers/places/start`, then make a live call against a real Google Places API key IF available in local `.env`:
    ```bash
    # Manual smoke (not a test, just developer sanity check)
    curl -X POST http://localhost:8102/mcp  # or however MCP Streamable HTTP clients hit it
    ```
    Live-API validation is NOT a hard requirement for 7.2 — the full end-to-end smoke test lives in Story 7.3's `test_smoke.py`. If you want to confirm, use the MCP inspector or a minimal client script.

## Dev Notes

### Architecture Compliance (the hard constraints)

All constraints from Story 7.1 carry forward. Story 7.2 adds:

- **HTTP client:** `httpx.AsyncClient` used short-lived (one per request). Do NOT hold a module-level client — Story 5.2 precedent in `mothership/manager.py` also uses short-lived clients for the same reason (test isolation, no connection-pool lifecycle management)
- **FieldMask discipline:** Every outbound request sets `X-Goog-FieldMask` — enforced in `_places_request`, never bypassed. Missing the header would cause Google to return everything and bill the highest SKU tier [Source: PRD PFR42]
- **Credential safety:** API key goes in `X-Goog-Api-Key` header ONLY. Never logged. Never in error messages. `CredentialError("GOOGLE_PLACES_API_KEY", ...)` carries only the NAME per `shared/errors.py:27-29` [Source: architecture-mothership.md#Error Handling Patterns]
- **Response shape:** `snake_case` JSON keys, ISO 8601 for any timestamps (reviews carry their own timestamps — preserved as-returned by Google in 7.2; Story 7.3's `summarize_reviews` uses `relative_time` instead)

### Tool Return Shape — Success vs Error

The tool signature is declared as `-> dict | list` for `search_places` and `-> dict` for `get_place_details`. The union is deliberate:

- `search_places` success: `list[dict]` — each dict is a flattened place
- `search_places` error: `dict` — `{"error": "...", "code": "..."}`
- `get_place_details` success: `dict` — flattened place details
- `get_place_details` error: `dict` — `{"error": "...", "code": "..."}`

The caller (agent or Story 7.3) distinguishes by shape. FastMCP serializes both to JSON; MCP clients see a JSON array for search success and a JSON object for everything else.

### The `_to_error_response` Contract From 7.1

Story 7.1 delivered:

```python
def _to_error_response(exc: Exception) -> dict[str, str]:
    # CredentialError          → AUTH
    # PlaceNotFoundError       → NOT_FOUND
    # ApiUnavailableError w/ "quota" or "rate" or "429" in message → QUOTA
    # ApiUnavailableError (other)                                  → UNKNOWN
    # ConfigurationError       → UNKNOWN
    # anything else            → UNKNOWN (with "Unexpected error" message)
```

Stories 7.2's `_places_request` raises `ApiUnavailableError` with explicit messages:
- `"Google Places quota exceeded"` → matches `"quota"` → QUOTA ✅
- `"Google Places API error: HTTP 500"` → no match → UNKNOWN ✅
- `"Network error calling Google Places API"` → no match → UNKNOWN ✅

The message text matters. Do NOT change the `_to_error_response` mapping in 7.2 — 7.1's helper is the contract.

### Google Places API (New) — Request/Response Cheat Sheet

- **Base URL:** `https://places.googleapis.com/v1` (set via `config.places_api_base_url` default in 7.1)
- **Auth header:** `X-Goog-Api-Key: {key}`
- **FieldMask header:** `X-Goog-FieldMask: {comma-separated field list}`

**Text Search request:**
```
POST https://places.googleapis.com/v1/places:searchText
Headers: X-Goog-Api-Key, X-Goog-FieldMask, Content-Type: application/json
Body: {"textQuery": "...", "includedType": "...", "maxResultCount": 10, "locationBias": {...}}
```

**Text Search response shape (what `_flatten_search_result` consumes):**
```json
{
  "places": [
    {
      "id": "places/ChIJ...",
      "displayName": {"text": "Vianden Castle", "languageCode": "en"},
      "formattedAddress": "Montée du Château, 9408 Vianden, Luxembourg",
      "location": {"latitude": 49.935..., "longitude": 6.201...},
      "rating": 4.6,
      "userRatingCount": 9876,
      "primaryType": "tourist_attraction",
      "priceLevel": "PRICE_LEVEL_MODERATE"
    }
  ]
}
```

Note: `displayName` is an object `{text, languageCode}`. Flatten to the `text` string.

**Place Details request:**
```
GET https://places.googleapis.com/v1/places/{place_id}
Headers: X-Goog-Api-Key, X-Goog-FieldMask
```

**Place Details response shape:** same field names as Text Search, but at top level (no `places` array wrapper). The `reviews` field is a list of review objects:
```json
"reviews": [
  {
    "name": "places/ChIJ.../reviews/...",
    "relativePublishTimeDescription": "a month ago",
    "rating": 5,
    "text": {"text": "Amazing castle", "languageCode": "en"},
    "originalText": {"text": "Amazing castle", "languageCode": "en"},
    "authorAttribution": {"displayName": "John D", "uri": "...", "photoUri": "..."}
  }
]
```

Story 7.2 passes `reviews` through as-returned by Google inside `get_place_details` output. Story 7.3's `summarize_reviews` will do the `{author, rating, text, relative_time}` re-shaping.

**Price level enum values:**
`PRICE_LEVEL_UNSPECIFIED`, `PRICE_LEVEL_FREE`, `PRICE_LEVEL_INEXPENSIVE`, `PRICE_LEVEL_MODERATE`, `PRICE_LEVEL_EXPENSIVE`, `PRICE_LEVEL_VERY_EXPENSIVE`. Return as-is — Story 7.3 will reference them but the MCP exposes the raw enum string.

### `httpx` Availability

Already available as a transitive dependency via `google-genai` and `mcp`. Story 5.2 consumed it inside `mothership/manager.py` with no pyproject.toml change. Follow the same pattern — no dependency changes for 7.2. [Source: 5-2-metrics-endpoint-and-tracking.md — Completion Notes, line 158]

### Files to Modify

```
servers/places/server.py       # Add _places_request, _flatten_*, search_places, get_place_details
tests/servers/places/          # Add test_search.py, test_details.py (alongside existing test_config.py, test_error_mapping.py, test_server.py from 7.1)
```

### Files to NOT Modify

- `servers/places/config.py` — no new config fields needed; `places_api_base_url` and `places_http_timeout_seconds` already exist from 7.1
- `servers/places/mothership.yaml` — no change
- `shared/*` — no new shared utilities
- `pyproject.toml` — no new dependencies
- `mothership/*` — no manager changes

### Anti-Patterns to Avoid

- Do NOT hold a module-level `httpx.AsyncClient` — short-lived `async with` per call
- Do NOT use synchronous `httpx.Client` — server is async, tools are `async def`
- Do NOT cache responses — explicitly out of scope per Sprint Change Proposal 2026-04-19
- Do NOT log request/response bodies — could leak user queries and place details that grow unexpectedly
- Do NOT log the API key value — ever, under any log level
- Do NOT add Google's error `code` strings into the error message text if they contain any credential echo
- Do NOT return the raw Google response — always pass through `_flatten_*` to produce the documented tool shape
- Do NOT keep the nested `location: {latitude, longitude}` object in tool output — flatten and drop
- Do NOT let `httpx.HTTPStatusError` escape — map it in `_places_request`; everything that hits the tool wrapper should be a typed `MothershipError`
- Do NOT implement `score_place`, `summarize_reviews`, `batch_score` — they belong to Story 7.3

### Previous Story Intelligence

From Story 7.1 (Places foundation):
- `_to_error_response` and `PlaceNotFoundError` live in `servers/places/server.py` — import/reference from within the same module
- Module-level metrics counters: `_request_count`, `_error_count`, `_last_request_time` — increment in the tool wrapper, not in `_*_impl`
- Autouse fixture pattern sets `GOOGLE_PLACES_API_KEY=test-key` before importing the server module
- `PYTHONPATH=""` required when running pytest

From Story 5.2 (metrics + httpx precedent):
- `httpx.AsyncClient` is the async HTTP client of choice — already used in `mothership/manager.py`
- Short timeouts (2s for health checks; 10s for Places calls is reasonable given ~500ms typical response)
- When mocking `httpx`, `unittest.mock.patch` on the call site works; `respx` is optional if the team already uses it

From Story 5.1 (FastMCP transport):
- Host/port set on `FastMCP(...)` constructor — `mcp.run(...)` takes only `transport`
- `@mcp.custom_route` is the public API for non-MCP endpoints (used for `/metrics` in 7.1)

### Testing Standards

- **Mock boundary:** Mock `httpx.AsyncClient.request` (or the `_places_request` helper directly) — do NOT mock at the tool level, since you lose coverage of the flattening logic
- **Fixture:** Extend 7.1's autouse fixtures to reset metrics counters between tests
- **Assertions:** Every test must verify either (a) the request shape sent OR (b) the response shape returned. Tests that only check "no exception raised" are insufficient.
- **Coverage expectation:** Every AC has ≥1 explicit test. FieldMask assertion must appear in at least one test per tool.
- **No live API calls in 7.2.** Smoke test is Story 7.3.

### Project Structure Notes

No deviations from `architecture-mothership.md#Project Structure`. `tests/servers/places/test_search.py` and `test_details.py` mirror `tests/servers/imagen/test_server.py` structure (class-based suites grouping related tests).

### References

- [Source: documents/planning-artifacts/epics.md#Story 7.2 — Search & Details Tools]
- [Source: documents/planning-artifacts/prd.md#Places MCP Capability — PFR34 (search_places), PFR35 (get_place_details), PFR40 (coordinate format), PFR42 (FieldMask + structured errors)]
- [Source: documents/planning-artifacts/architecture-mothership.md#Error Handling Patterns]
- [Source: documents/planning-artifacts/architecture-mothership.md#MCP Tool Patterns]
- [Source: documents/implementation-artifacts/7-1-places-mcp-foundation.md — `_to_error_response` contract, `PlaceNotFoundError`, metrics counter pattern]
- [Source: documents/implementation-artifacts/5-2-metrics-endpoint-and-tracking.md — `httpx.AsyncClient` precedent, mocking pattern]
- [Source: servers/imagen/server.py — wrapper/impl split, metrics counter increment pattern]
- [Source: mothership/manager.py — short-lived `httpx.AsyncClient` pattern from Story 5.2]
- [Source: shared/errors.py — CredentialError, ApiUnavailableError, ConfigurationError]

### Review Findings

Adversarial code review (2026-04-19) — Blind Hunter + Edge Case Hunter + Acceptance Auditor.

- [x] [Review][Patch] **[HIGH]** `_to_error_response` for `CredentialError` now emits the AC #4 exact contract `{"error": "Google Places authentication failed", "code": "AUTH"}`. [servers/places/server.py]
- [x] [Review][Patch] **[HIGH]** Full-dict equality assertions added for both 401 and 403 paths (new `test_search_places_403_returns_auth_error`, strengthened `test_search_places_401_returns_auth_error`) and for `test_credential_error_maps_to_auth`. Separate `test_credential_error_never_leaks_value` preserves the value-leak guard.
- [x] [Review][Patch] **[MEDIUM]** `_places_request` now catches `httpx.TransportError` (base of NetworkError, TimeoutException, ProxyError, DecodingError, ProtocolError, etc.) — full transport-error class caught.
- [x] [Review][Patch] **[MEDIUM]** 200 responses now wrap `response.json()` in try/except `ValueError`; malformed JSON → `ApiUnavailableError("Malformed response from Google Places API")` → UNKNOWN at the tool boundary. Test: `test_get_place_details_malformed_json_returns_unknown_error`.
- [x] [Review][Patch] **[MEDIUM]** `test_search_places_429_returns_quota_error` now asserts the full dict equals the AC #5 contract string.
- [x] [Review][Patch] **[LOW]** Added `test_search_places_docstring_mentions_sku_tier` and `test_get_place_details_docstring_mentions_sku_tier` asserting `"SKU tier"` substring plus the Google tool name.
- [x] [Review][Patch] **[LOW]** `test_search_places_invalid_type_returns_unknown_error` now asserts `"method" not in captured` — proves validation happens before the HTTP call.
- [x] [Review][Patch] **[LOW]** `_search_places_impl` now validates `isinstance(max_results, int) and max_results >= 1`, raising `ConfigurationError`. New test `test_search_places_max_results_invalid_returns_unknown_error`.
- [x] [Review][Defer] Per-request `httpx.AsyncClient` has no connection pooling — every call is a fresh TLS handshake — deferred, Story 7.2 Task 1 explicitly prescribes short-lived clients to "avoid connection state leaks during tests".
- [x] [Review][Defer] Substring match for `"quota"` / `"rate"` / `"429"` in `_to_error_response` can false-positive on unrelated errors — deferred, fix is to raise a typed `PlacesQuotaError` at source, larger refactor.
- [x] [Review][Defer] 3xx redirects fall into the catch-all "HTTP {status}" branch; `httpx` does not follow by default — deferred, Google Places API (New) does not redirect today.
- [x] [Review][Defer] HTTP 400 INVALID_ARGUMENT body `{"error": {"message": "..."}}` is discarded; generic UNKNOWN surfaced — deferred, enhancement for phase 2.
- [x] [Review][Defer] `_flatten_*` will `AttributeError` if Google returns `id` as non-string (e.g., int) — deferred, defensive hardening.
- [x] [Review][Defer] Return type union `dict | list` is undiscriminated; callers must runtime-type-check — deferred, by design per spec.
- [x] [Review][Defer] Metrics counter mutation across async tools has weak ordering guarantees; `last_request_time` set BEFORE work, not after — deferred, GIL makes `+=` atomic-enough for Python ints; not a correctness bug.
- [x] [Review][Defer] `/metrics` endpoint can report torn values when read during a tool invocation — deferred, low-risk under GIL.
- [x] [Review][Defer] SKU-tier docstrings may mis-state Essentials vs Advanced given the FieldMask in use — deferred, docstring accuracy debate with Google's pricing tiers.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context)

### Debug Log References

- `PYTHONPATH="" poetry run pytest tests/servers/places/ -v` — 44/44 passed (18 from 7.1 + 26 new for 7.2)
- `PYTHONPATH="" poetry run pytest` — 244 passed, 2 pre-existing unrelated imagen-config failures (`.env` leaking IMAGEN_API_KEY; documented in Story 5.1 completion notes)

### Completion Notes List

- Added HTTP helper `_places_request` that holds per-request `httpx.AsyncClient` (short-lived), sets `X-Goog-Api-Key` + `X-Goog-FieldMask` on every outbound call, and maps HTTP status → typed exceptions (`CredentialError` for 401/403, `PlaceNotFoundError` for 404, `ApiUnavailableError` for 429 with "quota exceeded" message, `ApiUnavailableError` for other non-2xx and network errors).
- Added FieldMask constants: `_PLACES_DETAILS_FIELDMASK` (27 fields per AC #2 spec) and `_PLACES_SEARCH_FIELDMASK` (8 places.* fields) — never bypassed.
- Added `_TYPE_TO_INCLUDED_TYPE` map (attraction→`tourist_attraction`, restaurant→`restaurant`, hotel→`lodging`, any→omit) and `_VALID_SEARCH_TYPES` set for validation.
- Added `_flatten_search_result` and `_flatten_place_details` pure helpers: flatten `location.latitude/longitude` to top-level decimal-degrees 6dp WGS84, strip `places/` prefix from `id`, extract `displayName.text` and `editorialSummary.text` strings, and `snake_case` all keys. No nested `location` leaks through.
- Added `_search_places_impl` and `_get_place_details_impl` internal entry points — Story 7.3 will reuse them without triggering the tool-wrapper metrics increment.
- Added `search_places` and `get_place_details` tools with the established wrapper pattern (metrics increment → try → impl → except → `_to_error_response`). Return shapes: `list[dict] | dict` and `dict`.
- Tests use a `_FakeAsyncClient` that replaces `httpx.AsyncClient` inside `async with` to deterministically inject responses and capture outbound headers/body/URL. Covers FieldMask discipline, auth-header pass-through, type mapping, coord flattening + 6dp rounding, prefix stripping, 401/404/429 error mapping, network-error mapping, empty-result handling, and metrics increments for success & failure paths.
- No changes to `pyproject.toml`, `shared/`, `mothership/`, `servers/imagen/`, or `servers/places/config.py`. `httpx` is a transitive dependency already used in `mothership/manager.py` (Story 5.2 precedent).

### File List

- `servers/places/server.py` (modified — added constants, HTTP helper, flatten helpers, tools)
- `tests/servers/places/test_search.py` (new — 16 tests)
- `tests/servers/places/test_details.py` (new — 10 tests)
- `documents/implementation-artifacts/sprint-status.yaml` (modified — status transition)
