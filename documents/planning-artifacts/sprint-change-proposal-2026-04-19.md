---
date: 2026-04-19
author: John (PM)
project: MCP Mothership
trigger: Add Google Places MCP server for travel research
scope_classification: Minor
status: pending-approval
---

# Sprint Change Proposal — Add Google Places MCP Server

## 1. Issue Summary

Kamal requested a new MCP server that wraps the Google Places API (New) for travel research — tourist attractions, restaurants, and hotels — with Bayesian-weighted scoring for ranking.

The original request arrived as a standalone stdio MCP spec (with local disk caching) that conflicted with seven Mothership conventions. After clarification, the decision was made to:

1. Align the Places server with **Mothership architecture** (Streamable HTTP, shared config/errors, mothership.yaml registration, /metrics endpoint).
2. **Eliminate caching** for the MVP — every tool call hits the Places API directly. Caching deferred to a future phase if usage scales.

This is a net-additive scope change. No existing work is invalidated. Places MCP will also serve as the first real-world validation of the drop-in capability pattern (Journey 2 in the PRD).

## 2. Impact Analysis

### Epic Impact

| Epic | Status | Impact |
|---|---|---|
| Epic 1: Project Foundation & Configuration | done | None |
| Epic 2: Image Generation | done | None |
| Epic 3: Nano Banana Pro Migration | in review | None |
| Epic 4: Project Migration & Process Manager | in review | None — platform consumed as-is |
| Epic 5: Network Transport & Agent Connectivity | in review | None — Places uses established Streamable HTTP + /metrics pattern |
| Epic 6: Dashboard & Operational Visibility | in review | None — Places appears automatically via config discovery |
| **Epic 7: Google Places MCP Server** | **new — backlog** | **Added** |

### Story Impact

No existing stories modified. Three new stories added under Epic 7.

### Artifact Conflicts & Required Updates

| Artifact | Change |
|---|---|
| `prd.md` | Add Places-specific functional requirements (FR34-FR42) under a new section "Places MCP Capability". Add Places to Phase 1 MVP capability list. No change to vision, goals, or journeys (Journey 2 already covers drop-in MCPs generically). |
| `epics.md` | Add Epic 7 description with 3 stories. Update Requirements Inventory with Places FRs. Extend FR Coverage Map. |
| `architecture-mothership.md` | Minor addendum noting Places as the second managed server, confirming no architectural change is required for additional MCPs. |
| `sprint-status.yaml` | Add entries: `epic-7: backlog`, `7-1-places-mcp-foundation: backlog`, `7-2-search-and-details-tools: backlog`, `7-3-scoring-reviews-and-batch-tools: backlog`, `epic-7-retrospective: optional`. |

### Technical Impact

- **New dependencies:** `httpx` (may already be present), Google Places API credentials.
- **Removed from original spec:** `diskcache` (caching eliminated).
- **No changes to:** shared modules, mothership package, dashboard, Imagen server, existing tests.
- **Dashboard:** Places will appear automatically once `servers/places/mothership.yaml` is discovered — no dashboard code changes.

### Spec Reconciliation (Original Spec → Mothership-Aligned)

| Original spec item | Mothership-aligned version |
|---|---|
| stdio transport | Streamable HTTP on configured port |
| Single-file server | `servers/places/server.py` + `config.py` + `mothership.yaml` |
| Raw `os.getenv("GOOGLE_PLACES_API_KEY")` | `PlacesConfig` extends `BaseServerConfig`, pydantic-settings validates on startup |
| Return `{error, code}` dicts | Typed exceptions raised internally (`CredentialError`, `ApiUnavailableError`, `ConfigurationError`, new `PlacesApiError` if needed); MCP tool boundary surfaces them as `{error, code: "NOT_FOUND"\|"QUOTA"\|"AUTH"\|"UNKNOWN"}` to the client |
| `claude_desktop_config.json` snippet in README | Removed — agents connect via Mothership network endpoint; `mothership.yaml` handles registration |
| No metrics | `/metrics` endpoint exposing `request_count`, `error_count`, `last_request_time` (per Epic 5 Story 5.2 pattern) |
| `diskcache` — Place Details 30d, Text Search 24h | **Removed.** Every call hits API. Cost accepted for MVP. |
| `test_smoke.py` at project root | `tests/servers/places/test_smoke.py` following Mothership test convention |

**Preserved from original spec unchanged:**
- All 5 tool signatures (`search_places`, `get_place_details`, `score_place`, `summarize_reviews`, `batch_score`)
- FieldMask for `get_place_details` (exact fields listed)
- Flatten `location.latitude/longitude` to top-level keys
- Decimal degrees, WGS84, 6 decimal places
- Bayesian scoring formula and per-category constants (attractions C=4.3/m=500, restaurants C=4.1/m=100, hotels C=4.0/m=200)
- `score_place` returns raw signals only — no tiers, no value judgments
- `batch_score` concurrency with `httpx.AsyncClient` + semaphore=10
- Smoke test targets: Vianden Castle, Chiggeri Luxembourg, Le Place d'Armes Luxembourg
- `type → includedType` mapping: attraction→tourist_attraction, restaurant→restaurant, hotel→lodging
- Docstring cost discipline (document SKU tier per tool)

## 3. Recommended Approach

**Selected path:** Option 1 — Direct Adjustment. Add Epic 7 to the existing plan.

**Rationale:**
- **Additive, not disruptive.** No existing stories change. No platform code changes. The Places server is purely a consumer of the Mothership platform.
- **Proof of the pattern.** Mothership Epic 4 Story 4.2 (Config Discovery & Registration) was designed for exactly this flow — drop a config file, new MCP appears. Until now, Imagen has been the only test case and Imagen was migrated, not added. Places will be the first true drop-in.
- **Small scope.** Three stories, estimated ~1 developer-week. Each story has clear boundaries.
- **No blockers.** Can start as soon as Epics 4-6 are signed off from review (recommended) or can begin in parallel if Kamal accepts the risk of building on code still under review.

**Alternative paths considered and rejected:**

- *Option 2 — Rollback:* N/A, no completed work to roll back.
- *Option 3 — MVP Review:* MVP scope is unaffected. Places is additive to the existing MVP, not a replacement.

**Risk assessment:**
- **Effort:** Low-Medium (~1 dev-week, 3 stories)
- **Technical risk:** Low — pattern established by Imagen migration
- **Cost risk:** Low — Places API billed per-call, no cache means higher call volume, but at personal-use scale (<$5/month expected). Flagged for Phase 2 revisit.
- **Timeline impact:** None on existing epics; adds one week if sequential after Epic 6 sign-off.

## 4. Detailed Change Proposals

### 4.1 New Epic — Epic 7

Add to `epics.md`:

> **Epic 7: Google Places MCP Server**
> Operator can add a Google Places-based travel research capability to the Mothership by dropping a config file. Agents can search for attractions, restaurants, and hotels, retrieve detailed place information, score places via Bayesian-weighted ranking, read reviews, and run batch queries — all through the managed Mothership platform.
> **PFRs covered:** PFR1-PFR9
> **MFRs/MNFRs covered (via platform consumption):** MFR7, MFR10, MFR11, MFR29-analogue
> **Architecture ref:** No changes required

### 4.2 New Stories

**Story 7.1 — Places MCP Server Foundation**
> As a developer,
> I want a Places MCP server skeleton registered with the Mothership,
> So that it appears on the dashboard and receives network traffic over Streamable HTTP.
>
> Key ACs: `servers/places/` package exists; `PlacesConfig` extends `BaseServerConfig` and validates `GOOGLE_PLACES_API_KEY` on startup (raises `CredentialError` if missing); `servers/places/mothership.yaml` is discovered by the manager; server starts on Streamable HTTP on its configured port; `/metrics` endpoint returns the standard JSON shape; tool boundary error translation maps typed exceptions to `{error, code}` dicts; unit tests cover config validation and error mapping.

**Story 7.2 — Search & Details Tools**
> As an agent,
> I want to search for places by query and fetch full details for any place,
> So that I can surface tourist attractions, restaurants, and hotels with structured, flattened data.
>
> Key ACs: `search_places(query, type, location_bias, max_results)` calls Text Search (New) with `type → includedType` mapping and returns the specified fields; `get_place_details(place_id)` calls Place Details (New) with the exact FieldMask; `location.latitude/longitude` is flattened to top-level `latitude/longitude` in 6-decimal WGS84; Google API errors map to typed exceptions (auth → `CredentialError`, quota/5xx → `ApiUnavailableError`, 404 → surfaces as `{error, code: "NOT_FOUND"}`); tests mock `httpx.AsyncClient` and assert FieldMask is set on every call.

**Story 7.3 — Scoring, Reviews & Batch Tools**
> As an agent,
> I want to score places with Bayesian weighting, read reviews as-is, and batch-score multiple queries concurrently,
> So that I can rank travel options without overloading the caller with raw Google responses.
>
> Key ACs: `score_place(place_id, category)` fetches details and returns the raw-signals shape (place_id, name, lat/long, category, rating, review_count, bayesian_score, price_level, is_open_now, business_status, primary_type, types, editorial_summary, has_editorial, google_maps_uri); category inferred from `primaryType` when `None`; Bayesian formula `(v/(v+m))*R + (m/(v+m))*C` applied with attractions C=4.3/m=500, restaurants C=4.1/m=100, hotels C=4.0/m=200; missing rating/review-count handled gracefully (score shrinks toward C); `summarize_reviews(place_id)` returns up to 5 reviews as `[{author, rating, text, relative_time}]`; `batch_score(queries, type)` runs concurrently with semaphore=10 via `httpx.AsyncClient`; `tests/servers/places/test_smoke.py` exercises all 5 tools end-to-end against Vianden Castle, Chiggeri Luxembourg, and Le Place d'Armes Luxembourg (requires live API key).

### 4.3 New Places Functional Requirements (add to PRD)

- **PFR1:** `search_places` tool returns up to N places filtered by type (attraction/restaurant/hotel/any) with place_id, name, address, lat/long, rating, user_rating_count, primary_type, price_level.
- **PFR2:** `get_place_details` tool returns place details using the specified FieldMask with top-level flattened lat/long.
- **PFR3:** `score_place` tool returns raw-signals response with Bayesian-weighted score per category.
- **PFR4:** `summarize_reviews` tool returns up to 5 Google reviews in `{author, rating, text, relative_time}` shape.
- **PFR5:** `batch_score` tool accepts a list of queries and runs search+score concurrently with semaphore=10.
- **PFR6:** All coordinates returned as decimal-degree WGS84 at 6 decimal places; always top-level `latitude`/`longitude`, never a nested `location` object.
- **PFR7:** Places server validates `GOOGLE_PLACES_API_KEY` on startup and fails fast with a clear error if missing.
- **PFR8:** Every Places API call includes a tight FieldMask for cost discipline; each tool's docstring documents its Places SKU tier.
- **PFR9:** Places API errors map to `{error, code: "NOT_FOUND"|"QUOTA"|"AUTH"|"UNKNOWN"}` at the MCP tool boundary, with credentials never appearing in error messages or logs.

## 5. Implementation Handoff

**Scope classification:** Minor — direct implementation by development team.

**Handoff plan:**

| Role | Agent | Deliverable | When |
|---|---|---|---|
| PM | John | Update `prd.md` (add Places FRs + Phase 1 capability entry); update `epics.md` (add Epic 7 + 3 stories + FR coverage map); update `architecture-mothership.md` (minor addendum) | Immediately after approval |
| SM | Bob | Create story files `7-1-places-mcp-foundation.md`, `7-2-search-and-details-tools.md`, `7-3-scoring-reviews-and-batch-tools.md` via `bmad-create-story` | After PRD/epics updated |
| SM/PM | — | Update `sprint-status.yaml` with new epic-7 and story entries (status: backlog) | With story creation |
| Dev | Amelia / Barry | Implement stories 7.1 → 7.2 → 7.3 sequentially | After Epic 4-6 sign-off (recommended) or in parallel if risk accepted |
| QA | Quinn | Smoke test validation against Vianden Castle, Chiggeri Luxembourg, Le Place d'Armes Luxembourg | After Story 7.3 complete |

**Success criteria:**
1. `servers/places/mothership.yaml` is discovered automatically; no manager code changes required.
2. Places server appears on the dashboard with live status, metrics, and logs.
3. All 5 tools return correct shapes for the 3 smoke-test targets.
4. Bayesian scoring produces sensible rankings (famous landmark with many ratings scores close to raw rating; obscure restaurant with <5 reviews shrinks toward C=4.1).
5. No credential leakage in logs or error responses.
6. Missing `GOOGLE_PLACES_API_KEY` produces a clear startup error naming the missing variable.

---

**Approval required from Kamal before PRD/epics/architecture updates are made.**
