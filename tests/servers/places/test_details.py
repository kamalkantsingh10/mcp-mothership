"""Tests for the Places get_place_details tool."""

from unittest.mock import MagicMock, patch

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
        return _FakeAsyncClient(response_or_exc, captured)
    return patch("servers.places.server.httpx.AsyncClient", side_effect=factory)


@pytest.mark.asyncio
async def test_get_place_details_flattens_coordinates():
    from servers.places.server import get_place_details
    api_response = {
        "id": "places/ChIJabc",
        "displayName": {"text": "Test Place"},
        "location": {"latitude": 49.7, "longitude": 6.2},
    }
    captured: dict = {}
    with _patch_httpx(_mock_response(200, api_response), captured):
        result = await get_place_details("ChIJabc")
    assert result["latitude"] == 49.7
    assert result["longitude"] == 6.2
    assert "location" not in result


@pytest.mark.asyncio
async def test_get_place_details_rounds_coordinates_to_6dp():
    from servers.places.server import get_place_details
    api_response = {
        "id": "places/x",
        "displayName": {"text": "T"},
        "location": {"latitude": 49.71234567890, "longitude": 6.12345678},
    }
    captured: dict = {}
    with _patch_httpx(_mock_response(200, api_response), captured):
        result = await get_place_details("x")
    assert result["latitude"] == 49.712346
    assert result["longitude"] == 6.123457


@pytest.mark.asyncio
async def test_get_place_details_strips_places_prefix_from_id():
    from servers.places.server import get_place_details
    api_response = {"id": "places/ChIJabc", "displayName": {"text": "T"}}
    captured: dict = {}
    with _patch_httpx(_mock_response(200, api_response), captured):
        result = await get_place_details("ChIJabc")
    assert result["place_id"] == "ChIJabc"


@pytest.mark.asyncio
async def test_get_place_details_handles_prefix_in_input():
    from servers.places.server import get_place_details
    captured: dict = {}
    with _patch_httpx(_mock_response(200, {"id": "places/ChIJxyz"}), captured):
        await get_place_details("places/ChIJxyz")
    assert captured["url"].endswith("/places/ChIJxyz")
    assert "/places/places/" not in captured["url"]


@pytest.mark.asyncio
async def test_get_place_details_missing_optionals_become_none():
    from servers.places.server import get_place_details
    captured: dict = {}
    api_response = {"id": "places/x", "displayName": {"text": "Sparse"}}
    with _patch_httpx(_mock_response(200, api_response), captured):
        result = await get_place_details("x")
    assert result["rating"] is None
    assert result["editorial_summary"] is None
    assert result["website_uri"] is None
    assert result["price_level"] is None
    assert result["business_status"] is None
    assert result["types"] == []
    assert result["reviews"] == []


@pytest.mark.asyncio
async def test_get_place_details_editorial_summary_extracted_from_text_field():
    from servers.places.server import get_place_details
    api_response = {
        "id": "places/x",
        "displayName": {"text": "T"},
        "editorialSummary": {"text": "A grand historic castle.", "languageCode": "en"},
    }
    captured: dict = {}
    with _patch_httpx(_mock_response(200, api_response), captured):
        result = await get_place_details("x")
    assert result["editorial_summary"] == "A grand historic castle."


@pytest.mark.asyncio
async def test_get_place_details_fieldmask_header_set():
    from servers.places.server import get_place_details, _PLACES_DETAILS_FIELDMASK
    captured: dict = {}
    with _patch_httpx(_mock_response(200, {"id": "places/x"}), captured):
        await get_place_details("x")
    assert captured["headers"]["X-Goog-FieldMask"] == _PLACES_DETAILS_FIELDMASK


@pytest.mark.asyncio
async def test_get_place_details_404_returns_not_found_error():
    from servers.places.server import get_place_details
    captured: dict = {}
    with _patch_httpx(_mock_response(404, {}), captured):
        result = await get_place_details("no-such-place")
    assert isinstance(result, dict)
    assert result == {"error": "Place not found", "code": "NOT_FOUND"}


@pytest.mark.asyncio
async def test_get_place_details_docstring_mentions_sku_tier():
    """Story 7.2 AC #3 — docstring documents the Google Places SKU tier."""
    from servers.places.server import get_place_details
    doc = get_place_details.__doc__ or ""
    assert "SKU tier" in doc
    assert "Place Details" in doc


@pytest.mark.asyncio
async def test_get_place_details_malformed_json_returns_unknown_error():
    """Malformed 200 body → ApiUnavailableError → UNKNOWN (no raw JSONDecodeError leak)."""
    from servers.places.server import get_place_details
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.side_effect = ValueError("malformed")
    captured: dict = {}
    with _patch_httpx(resp, captured):
        result = await get_place_details("x")
    assert isinstance(result, dict)
    assert result["code"] == "UNKNOWN"
    assert "Malformed" in result["error"]


@pytest.mark.asyncio
async def test_get_place_details_metrics_increment_on_success():
    import servers.places.server as srv
    from servers.places.server import get_place_details
    captured: dict = {}
    with _patch_httpx(_mock_response(200, {"id": "places/x"}), captured):
        await get_place_details("x")
    assert srv._request_count == 1
    assert srv._error_count == 0


@pytest.mark.asyncio
async def test_get_place_details_metrics_increment_on_error():
    import servers.places.server as srv
    from servers.places.server import get_place_details
    captured: dict = {}
    with _patch_httpx(_mock_response(404, {}), captured):
        await get_place_details("x")
    assert srv._request_count == 1
    assert srv._error_count == 1
