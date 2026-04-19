"""Tests for the Places search_places tool."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


@pytest.fixture(autouse=True)
def _mock_config(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")


@pytest.fixture(autouse=True)
def _reset_metrics(_mock_config):
    import servers.places.server as srv
    srv._request_count = 0
    srv._error_count = 0
    srv._last_request_time = None
    yield
    srv._request_count = 0
    srv._error_count = 0
    srv._last_request_time = None


def _mock_response(status_code: int, json_data: dict | None = None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    return resp


class _FakeAsyncClient:
    """Replacement for httpx.AsyncClient used inside `async with`."""

    def __init__(self, response, captured: dict):
        self._response = response
        self._captured = captured

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, method, url, headers=None, json=None):
        self._captured["method"] = method
        self._captured["url"] = url
        self._captured["headers"] = headers
        self._captured["json"] = json
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _patch_httpx(response_or_exc, captured: dict):
    def factory(*args, **kwargs):
        captured["client_kwargs"] = kwargs
        return _FakeAsyncClient(response_or_exc, captured)
    return patch("servers.places.server.httpx.AsyncClient", side_effect=factory)


@pytest.mark.asyncio
async def test_search_places_returns_flattened_items():
    from servers.places.server import search_places
    api_response = {
        "places": [
            {
                "id": "places/ChIJTestId",
                "displayName": {"text": "Vianden Castle", "languageCode": "en"},
                "formattedAddress": "Montée du Château, Vianden",
                "location": {"latitude": 49.9352819, "longitude": 6.2015422},
                "rating": 4.6,
                "userRatingCount": 9876,
                "primaryType": "tourist_attraction",
                "priceLevel": "PRICE_LEVEL_MODERATE",
            }
        ]
    }
    captured: dict = {}
    with _patch_httpx(_mock_response(200, api_response), captured):
        result = await search_places("Vianden Castle", type="attraction")
    assert isinstance(result, list)
    assert len(result) == 1
    item = result[0]
    assert item["place_id"] == "ChIJTestId"
    assert item["name"] == "Vianden Castle"
    assert item["latitude"] == 49.935282
    assert item["longitude"] == 6.201542
    assert item["rating"] == 4.6
    assert item["user_rating_count"] == 9876
    assert item["primary_type"] == "tourist_attraction"
    assert item["price_level"] == "PRICE_LEVEL_MODERATE"
    assert "location" not in item


@pytest.mark.asyncio
async def test_search_places_type_mapping_attraction():
    from servers.places.server import search_places
    captured: dict = {}
    with _patch_httpx(_mock_response(200, {"places": []}), captured):
        await search_places("museum", type="attraction")
    assert captured["json"]["includedType"] == "tourist_attraction"


@pytest.mark.asyncio
async def test_search_places_type_mapping_restaurant():
    from servers.places.server import search_places
    captured: dict = {}
    with _patch_httpx(_mock_response(200, {"places": []}), captured):
        await search_places("ramen", type="restaurant")
    assert captured["json"]["includedType"] == "restaurant"


@pytest.mark.asyncio
async def test_search_places_type_mapping_hotel():
    from servers.places.server import search_places
    captured: dict = {}
    with _patch_httpx(_mock_response(200, {"places": []}), captured):
        await search_places("spa", type="hotel")
    assert captured["json"]["includedType"] == "lodging"


@pytest.mark.asyncio
async def test_search_places_type_any_omits_included_type():
    from servers.places.server import search_places
    captured: dict = {}
    with _patch_httpx(_mock_response(200, {"places": []}), captured):
        await search_places("anything", type="any")
    assert "includedType" not in captured["json"]


@pytest.mark.asyncio
async def test_search_places_invalid_type_returns_unknown_error():
    from servers.places.server import search_places
    captured: dict = {}
    with _patch_httpx(_mock_response(200, {"places": []}), captured):
        result = await search_places("x", type="car")
    assert isinstance(result, dict)
    assert result["code"] == "UNKNOWN"
    # Validation must fail before any outbound API call — guard against a regression
    # where invalid type is silently passed through to Google.
    assert "method" not in captured


@pytest.mark.asyncio
async def test_search_places_location_bias_folds_into_query():
    from servers.places.server import search_places
    captured: dict = {}
    with _patch_httpx(_mock_response(200, {"places": []}), captured):
        await search_places("ramen", type="any", location_bias="Luxembourg")
    body = captured["json"]
    assert "ramen" in body["textQuery"]
    assert "Luxembourg" in body["textQuery"]


@pytest.mark.asyncio
async def test_search_places_max_results_capped_at_20():
    from servers.places.server import search_places
    captured: dict = {}
    with _patch_httpx(_mock_response(200, {"places": []}), captured):
        await search_places("many", max_results=50)
    assert captured["json"]["maxResultCount"] == 20


@pytest.mark.asyncio
async def test_search_places_empty_result_returns_empty_list():
    from servers.places.server import search_places
    captured: dict = {}
    with _patch_httpx(_mock_response(200, {}), captured):
        result = await search_places("zero results")
    assert result == []


@pytest.mark.asyncio
async def test_search_places_fieldmask_header_set():
    from servers.places.server import search_places, _PLACES_SEARCH_FIELDMASK
    captured: dict = {}
    with _patch_httpx(_mock_response(200, {"places": []}), captured):
        await search_places("anything")
    assert captured["headers"]["X-Goog-FieldMask"] == _PLACES_SEARCH_FIELDMASK
    assert "places.id" in captured["headers"]["X-Goog-FieldMask"]
    assert "places.displayName" in captured["headers"]["X-Goog-FieldMask"]


@pytest.mark.asyncio
async def test_search_places_auth_header_set():
    from servers.places.server import search_places
    captured: dict = {}
    with _patch_httpx(_mock_response(200, {"places": []}), captured):
        await search_places("anything")
    assert captured["headers"]["X-Goog-Api-Key"] == "test-key"


@pytest.mark.asyncio
async def test_search_places_401_returns_auth_error():
    """Story 7.2 AC #4 — exact error dict shape."""
    from servers.places.server import search_places
    captured: dict = {}
    with _patch_httpx(_mock_response(401, {}), captured):
        result = await search_places("anything")
    assert result == {"error": "Google Places authentication failed", "code": "AUTH"}


@pytest.mark.asyncio
async def test_search_places_403_returns_auth_error():
    """Story 7.2 AC #4 — 403 maps to the same AUTH contract as 401."""
    from servers.places.server import search_places
    captured: dict = {}
    with _patch_httpx(_mock_response(403, {}), captured):
        result = await search_places("anything")
    assert result == {"error": "Google Places authentication failed", "code": "AUTH"}


@pytest.mark.asyncio
async def test_search_places_429_returns_quota_error():
    """Story 7.2 AC #5 — exact error dict shape."""
    from servers.places.server import search_places
    captured: dict = {}
    with _patch_httpx(_mock_response(429, {}), captured):
        result = await search_places("anything")
    assert result == {"error": "Google Places quota exceeded", "code": "QUOTA"}


@pytest.mark.asyncio
async def test_search_places_network_error_returns_unknown_error():
    from servers.places.server import search_places
    captured: dict = {}
    with _patch_httpx(httpx.ConnectError("dns fail"), captured):
        result = await search_places("anything")
    assert isinstance(result, dict)
    assert result["code"] == "UNKNOWN"
    assert "Network error" in result["error"]


@pytest.mark.asyncio
async def test_search_places_max_results_invalid_returns_unknown_error():
    """max_results must be a positive integer; validation happens before the API call."""
    from servers.places.server import search_places
    captured: dict = {}
    with _patch_httpx(_mock_response(200, {"places": []}), captured):
        result = await search_places("anything", max_results=0)
    assert isinstance(result, dict)
    assert result["code"] == "UNKNOWN"
    assert "method" not in captured


@pytest.mark.asyncio
async def test_search_places_docstring_mentions_sku_tier():
    """Story 7.2 AC #3 — docstring documents the Google Places SKU tier."""
    from servers.places.server import search_places
    doc = search_places.__doc__ or ""
    assert "SKU tier" in doc
    assert "Text Search" in doc


@pytest.mark.asyncio
async def test_search_places_metrics_increment_on_success():
    import servers.places.server as srv
    from servers.places.server import search_places
    captured: dict = {}
    with _patch_httpx(_mock_response(200, {"places": []}), captured):
        await search_places("anything")
    assert srv._request_count == 1
    assert srv._error_count == 0
    assert srv._last_request_time is not None


@pytest.mark.asyncio
async def test_search_places_metrics_increment_on_error():
    import servers.places.server as srv
    from servers.places.server import search_places
    captured: dict = {}
    with _patch_httpx(_mock_response(429, {}), captured):
        await search_places("anything")
    assert srv._request_count == 1
    assert srv._error_count == 1
