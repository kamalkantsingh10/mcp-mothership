"""Places MCP server — Google Places API (New) travel research.

Skeleton only: exposes no tools in Story 7.1 — Stories 7.2 and 7.3 add
search, details, scoring, reviews, and batch tools. Serves Streamable HTTP
transport and a `/metrics` endpoint.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from servers.places.config import PlacesConfig
from shared.errors import (
    ApiUnavailableError,
    ConfigurationError,
    CredentialError,
    MothershipError,
)
from shared.logging_config import setup_logging

logger = logging.getLogger(__name__)

config = PlacesConfig.from_yaml(config_path="config.yaml")
setup_logging(config.log_level, log_name="places")

logger.info("Places MCP server starting up")

if not config.google_places_api_key:
    raise CredentialError(
        "GOOGLE_PLACES_API_KEY",
        reason="is missing — set GOOGLE_PLACES_API_KEY in .env",
    )
logger.info("Places API credential loaded")

mcp = FastMCP("places", host="0.0.0.0", port=config.port)
logger.info("MCP server created, ready to accept connections")

# In-memory metrics counters — Mothership polls /metrics for request/error counts.
_request_count: int = 0
_error_count: int = 0
_last_request_time: str | None = None


class PlaceNotFoundError(MothershipError):
    """Raised when a Google Places lookup returns 404 for a place_id or query."""


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
_VALID_SEARCH_TYPES = frozenset({"attraction", "restaurant", "hotel", "any"})

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

_VALID_SCORING_CATEGORIES = frozenset({"attraction", "restaurant", "hotel"})


def _to_error_response(exc: Exception) -> dict[str, str]:
    """Translate a typed exception into the MCP tool error response shape.

    Shape: {"error": "<message>", "code": "NOT_FOUND"|"QUOTA"|"AUTH"|"UNKNOWN"}
    Credential values never appear — CredentialError carries only the credential NAME.
    """
    if isinstance(exc, CredentialError):
        return {"error": "Google Places authentication failed", "code": "AUTH"}
    if isinstance(exc, PlaceNotFoundError):
        return {"error": str(exc), "code": "NOT_FOUND"}
    if isinstance(exc, ApiUnavailableError):
        msg = str(exc).lower()
        if "quota" in msg or "rate" in msg or "429" in msg:
            return {"error": str(exc), "code": "QUOTA"}
        return {"error": str(exc), "code": "UNKNOWN"}
    if isinstance(exc, ConfigurationError):
        return {"error": str(exc), "code": "UNKNOWN"}
    logger.exception("Unexpected error in Places tool")
    return {"error": "Unexpected error", "code": "UNKNOWN"}


async def _places_request(
    method: str,
    path: str,
    *,
    field_mask: str,
    json_body: dict | None = None,
) -> dict:
    """Call Google Places API with auth + FieldMask headers. Map status → typed errors."""
    url = config.places_api_base_url + path
    headers = {
        _PLACES_AUTH_HEADER: config.google_places_api_key or "",
        _PLACES_FIELDMASK_HEADER: field_mask,
    }
    logger.info(
        "places api %s %s (fields=%d)",
        method,
        path,
        field_mask.count(",") + 1,
    )
    try:
        async with httpx.AsyncClient(timeout=config.places_http_timeout_seconds) as client:
            response = await client.request(method, url, headers=headers, json=json_body)
    except httpx.TransportError as e:
        raise ApiUnavailableError("Network error calling Google Places API") from e

    status = response.status_code
    if status == 200:
        try:
            return response.json()
        except ValueError as e:
            raise ApiUnavailableError("Malformed response from Google Places API") from e
    if status in (401, 403):
        raise CredentialError(
            "GOOGLE_PLACES_API_KEY",
            reason="Google Places authentication failed",
        )
    if status == 404:
        raise PlaceNotFoundError("Place not found")
    if status == 429:
        raise ApiUnavailableError("Google Places quota exceeded")
    raise ApiUnavailableError(f"Google Places API error: HTTP {status}")


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
    editorial = item.get("editorialSummary")
    editorial_text = editorial.get("text") if isinstance(editorial, dict) else None
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
        "editorial_summary": editorial_text,
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


async def _search_places_impl(
    query: str,
    type: str,
    location_bias: str | None,
    max_results: int,
) -> list[dict]:
    if type not in _VALID_SEARCH_TYPES:
        raise ConfigurationError(f"Invalid type: {type}")
    if not isinstance(max_results, int) or max_results < 1:
        raise ConfigurationError(f"max_results must be a positive integer, got {max_results!r}")
    body: dict = {
        "textQuery": query,
        "maxResultCount": min(max_results, 20),
    }
    if location_bias:
        body["textQuery"] = f"{query} near {location_bias}"
    included_type = _TYPE_TO_INCLUDED_TYPE.get(type)
    if included_type:
        body["includedType"] = included_type
    data = await _places_request(
        "POST",
        "/places:searchText",
        field_mask=_PLACES_SEARCH_FIELDMASK,
        json_body=body,
    )
    places = data.get("places") or []
    return [_flatten_search_result(p) for p in places]


async def _get_place_details_impl(place_id: str) -> dict:
    normalized_id = place_id.removeprefix("places/")
    data = await _places_request(
        "GET",
        f"/places/{normalized_id}",
        field_mask=_PLACES_DETAILS_FIELDMASK,
    )
    return _flatten_place_details(data)


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
        location_bias: Optional free-text bias (e.g., "Luxembourg"). Folded into
            the query text when provided.
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


def _infer_category(primary_type: str | None) -> str:
    """Infer scoring category from Google primaryType. Defaults to 'restaurant'."""
    if primary_type:
        for category, keywords in _CATEGORY_KEYWORDS.items():
            if primary_type in keywords:
                return category
    return "restaurant"


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
    score = (v / denom) * R + (m / denom) * C
    return round(score, 2)


async def _score_place_impl(place_id: str, category: str | None) -> dict:
    if category is not None and category not in _VALID_SCORING_CATEGORIES:
        raise ConfigurationError(f"Invalid category: {category}")
    details = await _get_place_details_impl(place_id)
    category = category or _infer_category(details.get("primary_type"))
    score = _bayesian_score(
        details.get("rating"),
        details.get("user_rating_count"),
        category,
    )
    coh = details.get("current_opening_hours") or {}
    is_open_now = coh.get("openNow") if isinstance(coh, dict) else None
    return {
        "place_id": details.get("place_id"),
        "name": details.get("name"),
        "latitude": details.get("latitude"),
        "longitude": details.get("longitude"),
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


async def _summarize_reviews_impl(place_id: str) -> list[dict]:
    details = await _get_place_details_impl(place_id)
    raw_reviews = details.get("reviews") or []
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


async def _batch_score_impl(queries: list[str], type: str) -> list[dict]:
    if type not in _VALID_SEARCH_TYPES:
        raise ConfigurationError(f"Invalid type: {type}")
    semaphore = asyncio.Semaphore(10)

    async def _one(query: str) -> dict:
        async with semaphore:
            try:
                results = await _search_places_impl(query, type, None, 1)
                if not results:
                    return {
                        "query": query,
                        "name": None,
                        "latitude": None,
                        "longitude": None,
                        "score_result": None,
                    }
                top = results[0]
                score = await _score_place_impl(top["place_id"], None)
                return {
                    "query": query,
                    "name": top.get("name"),
                    "latitude": top.get("latitude"),
                    "longitude": top.get("longitude"),
                    "score_result": score,
                }
            except Exception as exc:
                logger.warning("batch_score query failed: %r (%s)", query, exc)
                return {
                    "query": query,
                    "name": None,
                    "latitude": None,
                    "longitude": None,
                    "score_result": _to_error_response(exc),
                }

    return await asyncio.gather(*[_one(q) for q in queries])


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


@mcp.tool()
async def batch_score(
    queries: list[str],
    type: str = "any",
) -> dict | list:
    """Run search + score concurrently for a list of queries.

    Places API SKU tier: Text Search (New) + Place Details (New). TWO API calls per
    non-empty query. With no cache, this hits the API N*2 times per batch.

    Args:
        queries: List of free-text search queries.
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


@mcp.custom_route("/metrics", methods=["GET"])
async def metrics(request: Any):
    """Expose server metrics as JSON."""
    from starlette.responses import JSONResponse
    return JSONResponse({
        "request_count": _request_count,
        "error_count": _error_count,
        "last_request_time": _last_request_time,
    })


if __name__ == "__main__":
    logger.info("Starting MCP Streamable HTTP transport on port %d", config.port)
    mcp.run(transport="streamable-http")
