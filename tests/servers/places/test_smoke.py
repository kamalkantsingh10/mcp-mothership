"""Live end-to-end smoke tests against the real Google Places API.

Requires GOOGLE_PLACES_API_KEY in .env. Skipped by default — run with:
    PYTHONPATH="" poetry run pytest tests/servers/places/test_smoke.py -v
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("GOOGLE_PLACES_API_KEY")
    or os.getenv("GOOGLE_PLACES_API_KEY") == "test-key",
    reason="GOOGLE_PLACES_API_KEY not set — skipping live Places API smoke tests",
)


async def _pick_place_id(results):
    assert isinstance(results, list), f"expected list, got {results!r}"
    assert results, "expected at least 1 result"
    return results[0]["place_id"]


@pytest.mark.asyncio
async def test_smoke_attraction_vianden_castle():
    from servers.places.server import (
        search_places,
        get_place_details,
        score_place,
        summarize_reviews,
    )
    results = await search_places("Vianden Castle", type="attraction", max_results=1)
    place_id = await _pick_place_id(results)
    details = await get_place_details(place_id)
    assert isinstance(details, dict)
    assert 49.9 <= details["latitude"] <= 50.0
    assert 6.1 <= details["longitude"] <= 6.3
    assert "Vianden" in (details["name"] or "")
    score = await score_place(place_id)
    assert isinstance(score["bayesian_score"], float)
    assert score["category"] == "attraction"
    assert isinstance(score["has_editorial"], bool)
    reviews = await summarize_reviews(place_id)
    if isinstance(reviews, list):
        assert len(reviews) <= 5
        for r in reviews:
            assert set(r.keys()) == {"author", "rating", "text", "relative_time"}


@pytest.mark.asyncio
async def test_smoke_restaurant_chiggeri_luxembourg():
    from servers.places.server import search_places, score_place, summarize_reviews
    results = await search_places("Chiggeri Luxembourg", type="restaurant", max_results=1)
    place_id = await _pick_place_id(results)
    score = await score_place(place_id)
    assert isinstance(score["bayesian_score"], float)
    assert score["category"] == "restaurant"
    # AC #7 — flattened coordinates non-null
    assert isinstance(score["latitude"], float)
    assert isinstance(score["longitude"], float)
    reviews = await summarize_reviews(place_id)
    assert isinstance(reviews, list)


@pytest.mark.asyncio
async def test_smoke_hotel_le_place_darmes_luxembourg():
    from servers.places.server import search_places, score_place
    results = await search_places("Le Place d'Armes Luxembourg", type="hotel", max_results=1)
    place_id = await _pick_place_id(results)
    score = await score_place(place_id)
    assert isinstance(score["bayesian_score"], float)
    assert score["category"] == "hotel"
    # AC #7 — flattened coordinates non-null
    assert isinstance(score["latitude"], float)
    assert isinstance(score["longitude"], float)


@pytest.mark.asyncio
async def test_smoke_batch_all_three():
    from servers.places.server import batch_score
    results = await batch_score([
        "Vianden Castle",
        "Chiggeri Luxembourg",
        "Le Place d'Armes Luxembourg",
    ])
    assert isinstance(results, list)
    assert len(results) == 3
    for r in results:
        assert r["score_result"] is not None
