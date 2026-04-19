"""Tests for Places scoring: Bayesian formula, category inference, score_place."""

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


# -------------------- Bayesian formula --------------------


def test_bayesian_famous_landmark_close_to_rating():
    from servers.places.server import _bayesian_score
    score = _bayesian_score(4.6, 50000, "attraction")
    assert abs(score - 4.6) < 0.01


def test_bayesian_new_restaurant_shrinks_toward_C():
    from servers.places.server import _bayesian_score
    score = _bayesian_score(4.8, 3, "restaurant")
    # Expected: (3/103)*4.8 + (100/103)*4.1 ≈ 4.12
    assert abs(score - 4.12) < 0.01


def test_bayesian_missing_rating_returns_C_for_category():
    from servers.places.server import _bayesian_score
    assert _bayesian_score(None, None, "hotel") == 4.0
    assert _bayesian_score(None, None, "attraction") == 4.3
    assert _bayesian_score(None, None, "restaurant") == 4.1


def test_bayesian_missing_rating_only_returns_C():
    from servers.places.server import _bayesian_score
    # R defaults to 0, v=1000, m=100 for restaurant
    # score = (1000/1100)*0 + (100/1100)*4.1 ≈ 0.37
    score = _bayesian_score(None, 1000, "restaurant")
    assert abs(score - 0.37) < 0.01


def test_bayesian_unknown_category_uses_restaurant_constants():
    from servers.places.server import _bayesian_score
    # Unknown category falls back to restaurant (C=4.1, m=100)
    unknown = _bayesian_score(4.5, 50, "food_truck")
    restaurant = _bayesian_score(4.5, 50, "restaurant")
    assert unknown == restaurant


def test_bayesian_rounded_to_2dp():
    """Story 7.3 AC #2 — result is rounded to 2dp.

    Input chosen so raw formula yields a value with >2dp; assert the exact rounded
    expected value. This catches regressions where the `round(..., 2)` is removed.
    """
    from servers.places.server import _bayesian_score
    # raw: (1/101)*4.5 + (100/101)*4.1 = 4.10396... → rounded to 4.10
    score = _bayesian_score(4.5, 1, "restaurant")
    assert score == 4.10


# -------------------- Category inference --------------------


def test_infer_category_attraction_keywords():
    from servers.places.server import _infer_category
    for t in ["museum", "park", "landmark", "tourist_attraction", "zoo"]:
        assert _infer_category(t) == "attraction"


def test_infer_category_restaurant_keywords():
    from servers.places.server import _infer_category
    for t in ["cafe", "bar", "bakery", "restaurant", "food"]:
        assert _infer_category(t) == "restaurant"


def test_infer_category_hotel_keywords():
    from servers.places.server import _infer_category
    assert _infer_category("lodging") == "hotel"
    assert _infer_category("hotel") == "hotel"


def test_infer_category_unknown_defaults_to_restaurant():
    from servers.places.server import _infer_category
    assert _infer_category("car_dealer") == "restaurant"


def test_infer_category_none_defaults_to_restaurant():
    from servers.places.server import _infer_category
    assert _infer_category(None) == "restaurant"


# -------------------- score_place (mocking _get_place_details_impl) --------------------


_EXPECTED_SCORE_FIELDS = {
    "place_id",
    "name",
    "latitude",
    "longitude",
    "category",
    "rating",
    "review_count",
    "bayesian_score",
    "price_level",
    "is_open_now",
    "business_status",
    "primary_type",
    "types",
    "editorial_summary",
    "has_editorial",
    "google_maps_uri",
}


def _details_fixture(**overrides):
    base = {
        "place_id": "ChIJabc",
        "name": "Test Place",
        "address": "1 Test St",
        "latitude": 49.7,
        "longitude": 6.2,
        "rating": 4.5,
        "user_rating_count": 500,
        "regular_opening_hours": None,
        "current_opening_hours": {"openNow": True},
        "website_uri": None,
        "international_phone_number": None,
        "price_level": "PRICE_LEVEL_MODERATE",
        "price_range": None,
        "business_status": "OPERATIONAL",
        "editorial_summary": "A lovely spot.",
        "primary_type": "restaurant",
        "types": ["restaurant", "food"],
        "reviews": [],
        "google_maps_uri": "https://maps.example",
        "dine_in": True,
        "takeout": True,
        "delivery": False,
        "reservable": True,
        "serves_breakfast": False,
        "serves_lunch": True,
        "serves_dinner": True,
        "outdoor_seating": True,
        "good_for_children": True,
        "allows_dogs": False,
    }
    base.update(overrides)
    return base


def _patch_details(details):
    return patch(
        "servers.places.server._get_place_details_impl",
        new=AsyncMock(return_value=details),
    )


@pytest.mark.asyncio
async def test_score_place_returns_exact_shape():
    from servers.places.server import score_place
    with _patch_details(_details_fixture()):
        result = await score_place("ChIJabc")
    assert set(result.keys()) == _EXPECTED_SCORE_FIELDS


@pytest.mark.asyncio
async def test_score_place_infers_category_from_primary_type():
    from servers.places.server import score_place
    with _patch_details(_details_fixture(primary_type="museum")):
        result = await score_place("ChIJabc")
    assert result["category"] == "attraction"


@pytest.mark.asyncio
async def test_score_place_uses_provided_category():
    from servers.places.server import score_place
    with _patch_details(_details_fixture(primary_type="museum")):
        result = await score_place("ChIJabc", category="hotel")
    assert result["category"] == "hotel"


@pytest.mark.asyncio
async def test_score_place_invalid_category_returns_unknown_error():
    from servers.places.server import score_place
    with _patch_details(_details_fixture()):
        result = await score_place("ChIJabc", category="food_truck")
    assert result["code"] == "UNKNOWN"


@pytest.mark.asyncio
async def test_score_place_has_editorial_true_when_summary_present():
    from servers.places.server import score_place
    with _patch_details(_details_fixture(editorial_summary="Nice place")):
        result = await score_place("ChIJabc")
    assert result["has_editorial"] is True


@pytest.mark.asyncio
async def test_score_place_has_editorial_false_when_summary_null():
    from servers.places.server import score_place
    with _patch_details(_details_fixture(editorial_summary=None)):
        result = await score_place("ChIJabc")
    assert result["has_editorial"] is False


@pytest.mark.asyncio
async def test_score_place_is_open_now_from_current_opening_hours():
    from servers.places.server import score_place
    with _patch_details(_details_fixture(current_opening_hours={"openNow": True})):
        result = await score_place("ChIJabc")
    assert result["is_open_now"] is True


@pytest.mark.asyncio
async def test_score_place_is_open_now_null_when_hours_missing():
    from servers.places.server import score_place
    with _patch_details(_details_fixture(current_opening_hours=None)):
        result = await score_place("ChIJabc")
    assert result["is_open_now"] is None


@pytest.mark.asyncio
async def test_score_place_not_found_propagates_error():
    from servers.places.server import score_place, PlaceNotFoundError
    with patch(
        "servers.places.server._get_place_details_impl",
        new=AsyncMock(side_effect=PlaceNotFoundError("Place not found")),
    ):
        result = await score_place("missing")
    assert result == {"error": "Place not found", "code": "NOT_FOUND"}


@pytest.mark.asyncio
async def test_score_place_metrics_increment_on_success():
    import servers.places.server as srv
    from servers.places.server import score_place
    with _patch_details(_details_fixture()):
        await score_place("ChIJabc")
    assert srv._request_count == 1
    assert srv._error_count == 0


@pytest.mark.asyncio
async def test_score_place_metrics_increment_on_error():
    import servers.places.server as srv
    from servers.places.server import score_place, PlaceNotFoundError
    with patch(
        "servers.places.server._get_place_details_impl",
        new=AsyncMock(side_effect=PlaceNotFoundError("Place not found")),
    ):
        await score_place("missing")
    assert srv._request_count == 1
    assert srv._error_count == 1
