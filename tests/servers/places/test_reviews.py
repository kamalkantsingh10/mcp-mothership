"""Tests for the summarize_reviews tool."""

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


def _review(author="Jane", rating=5, text="Great", relative="a month ago"):
    return {
        "authorAttribution": {"displayName": author, "uri": "", "photoUri": ""},
        "rating": rating,
        "text": {"text": text, "languageCode": "en"},
        "originalText": {"text": text, "languageCode": "en"},
        "relativePublishTimeDescription": relative,
    }


def _details_with_reviews(reviews):
    return {
        "place_id": "ChIJabc",
        "name": "Test",
        "latitude": 0.0,
        "longitude": 0.0,
        "reviews": reviews,
    }


def _patch_details(details):
    return patch(
        "servers.places.server._get_place_details_impl",
        new=AsyncMock(return_value=details),
    )


@pytest.mark.asyncio
async def test_summarize_reviews_reshapes_to_four_fields():
    from servers.places.server import summarize_reviews
    with _patch_details(_details_with_reviews([_review(), _review(), _review()])):
        result = await summarize_reviews("ChIJabc")
    assert len(result) == 3
    for r in result:
        assert set(r.keys()) == {"author", "rating", "text", "relative_time"}


@pytest.mark.asyncio
async def test_summarize_reviews_extracts_author_from_attribution():
    from servers.places.server import summarize_reviews
    with _patch_details(_details_with_reviews([_review(author="Jane Doe")])):
        result = await summarize_reviews("ChIJabc")
    assert result[0]["author"] == "Jane Doe"


@pytest.mark.asyncio
async def test_summarize_reviews_extracts_text_from_text_object():
    from servers.places.server import summarize_reviews
    with _patch_details(_details_with_reviews([_review(text="Great place")])):
        result = await summarize_reviews("ChIJabc")
    assert result[0]["text"] == "Great place"


@pytest.mark.asyncio
async def test_summarize_reviews_uses_relative_publish_time_description():
    from servers.places.server import summarize_reviews
    with _patch_details(_details_with_reviews([_review(relative="2 weeks ago")])):
        result = await summarize_reviews("ChIJabc")
    assert result[0]["relative_time"] == "2 weeks ago"


@pytest.mark.asyncio
async def test_summarize_reviews_caps_at_5():
    from servers.places.server import summarize_reviews
    eight_reviews = [_review(author=f"r{i}") for i in range(8)]
    with _patch_details(_details_with_reviews(eight_reviews)):
        result = await summarize_reviews("ChIJabc")
    assert len(result) == 5


@pytest.mark.asyncio
async def test_summarize_reviews_empty_when_no_reviews():
    from servers.places.server import summarize_reviews
    with _patch_details(_details_with_reviews([])):
        result = await summarize_reviews("ChIJabc")
    assert result == []


@pytest.mark.asyncio
async def test_summarize_reviews_not_found_returns_error_dict():
    from servers.places.server import summarize_reviews, PlaceNotFoundError
    with patch(
        "servers.places.server._get_place_details_impl",
        new=AsyncMock(side_effect=PlaceNotFoundError("Place not found")),
    ):
        result = await summarize_reviews("missing")
    assert result == {"error": "Place not found", "code": "NOT_FOUND"}


@pytest.mark.asyncio
async def test_summarize_reviews_metrics_increment():
    import servers.places.server as srv
    from servers.places.server import summarize_reviews
    with _patch_details(_details_with_reviews([])):
        await summarize_reviews("ChIJabc")
    assert srv._request_count == 1
    assert srv._error_count == 0
