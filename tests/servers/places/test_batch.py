"""Tests for the batch_score tool."""

import asyncio
from unittest.mock import AsyncMock, patch

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


def _search_hit(place_id="ChIJabc", name="Test", lat=49.7, lng=6.2):
    return {
        "place_id": place_id,
        "name": name,
        "address": "1 Test St",
        "latitude": lat,
        "longitude": lng,
        "rating": 4.5,
        "user_rating_count": 100,
        "primary_type": "restaurant",
        "price_level": "PRICE_LEVEL_MODERATE",
    }


def _score_result(place_id="ChIJabc", category="restaurant"):
    return {
        "place_id": place_id,
        "name": "Test",
        "latitude": 49.7,
        "longitude": 6.2,
        "category": category,
        "rating": 4.5,
        "review_count": 100,
        "bayesian_score": 4.30,
        "price_level": "PRICE_LEVEL_MODERATE",
        "is_open_now": True,
        "business_status": "OPERATIONAL",
        "primary_type": "restaurant",
        "types": ["restaurant"],
        "editorial_summary": None,
        "has_editorial": False,
        "google_maps_uri": "https://maps.example",
    }


@pytest.mark.asyncio
async def test_batch_score_runs_all_queries():
    from servers.places.server import batch_score

    async def fake_search(q, *a, **kw):
        return [_search_hit(name=f"hit-{q}")]

    async def fake_score(pid, cat):
        return _score_result(place_id=pid)

    with patch("servers.places.server._search_places_impl", new=fake_search), \
         patch("servers.places.server._score_place_impl", new=fake_score):
        result = await batch_score(["a", "b", "c"])
    assert isinstance(result, list)
    assert len(result) == 3
    for r in result:
        assert r["score_result"] is not None
        assert "query" in r


@pytest.mark.asyncio
async def test_batch_score_empty_result_for_query_surfaces_nulls():
    from servers.places.server import batch_score

    async def fake_search(q, *a, **kw):
        if q == "empty":
            return []
        return [_search_hit()]

    async def fake_score(pid, cat):
        return _score_result()

    with patch("servers.places.server._search_places_impl", new=fake_search), \
         patch("servers.places.server._score_place_impl", new=fake_score):
        result = await batch_score(["ok", "empty"])
    empty_row = next(r for r in result if r["query"] == "empty")
    assert empty_row["name"] is None
    assert empty_row["latitude"] is None
    assert empty_row["longitude"] is None
    assert empty_row["score_result"] is None


@pytest.mark.asyncio
async def test_batch_score_per_query_error_does_not_fail_batch():
    from servers.places.server import batch_score, PlaceNotFoundError

    async def fake_search(q, *a, **kw):
        if q == "bad":
            raise PlaceNotFoundError("Place not found")
        return [_search_hit()]

    async def fake_score(pid, cat):
        return _score_result()

    with patch("servers.places.server._search_places_impl", new=fake_search), \
         patch("servers.places.server._score_place_impl", new=fake_score):
        result = await batch_score(["good", "bad", "good2"])
    assert len(result) == 3
    bad = next(r for r in result if r["query"] == "bad")
    assert bad["score_result"] == {"error": "Place not found", "code": "NOT_FOUND"}
    good = [r for r in result if r["query"] != "bad"]
    assert all(r["score_result"] == _score_result() for r in good)


@pytest.mark.asyncio
async def test_batch_score_invalid_type_returns_unknown_error():
    from servers.places.server import batch_score
    result = await batch_score(["a", "b"], type="bogus")
    assert isinstance(result, dict)
    assert result["code"] == "UNKNOWN"


@pytest.mark.asyncio
async def test_batch_score_concurrency_capped_at_10():
    from servers.places.server import batch_score

    active = 0
    peak = 0

    async def fake_search(q, *a, **kw):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.005)
        active -= 1
        return [_search_hit()]

    async def fake_score(pid, cat):
        return _score_result()

    with patch("servers.places.server._search_places_impl", new=fake_search), \
         patch("servers.places.server._score_place_impl", new=fake_score):
        await batch_score([f"q{i}" for i in range(25)])

    assert peak <= 10


@pytest.mark.asyncio
async def test_batch_score_returns_result_per_query_in_order():
    from servers.places.server import batch_score

    async def fake_search(q, *a, **kw):
        return [_search_hit(name=q)]

    async def fake_score(pid, cat):
        return _score_result(place_id=pid)

    with patch("servers.places.server._search_places_impl", new=fake_search), \
         patch("servers.places.server._score_place_impl", new=fake_score):
        queries = ["alpha", "beta", "gamma", "delta"]
        result = await batch_score(queries)
    assert [r["query"] for r in result] == queries
