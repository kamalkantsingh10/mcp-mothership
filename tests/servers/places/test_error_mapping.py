"""Tests for the Places server's tool-boundary error translator."""

import pytest

from shared.errors import (
    ApiUnavailableError,
    ConfigurationError,
    CredentialError,
)


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")


def test_credential_error_maps_to_auth():
    """Story 7.2 AC #4: CredentialError at the tool boundary emits the exact contract string."""
    from servers.places.server import _to_error_response
    resp = _to_error_response(CredentialError("GOOGLE_PLACES_API_KEY"))
    assert resp == {"error": "Google Places authentication failed", "code": "AUTH"}


def test_credential_error_never_leaks_value():
    """Credential values must never appear in the AUTH payload, even with a reason set."""
    from servers.places.server import _to_error_response
    resp = _to_error_response(
        CredentialError("GOOGLE_PLACES_API_KEY", reason="anything with test-key in it")
    )
    assert "test-key" not in resp["error"]
    assert resp["code"] == "AUTH"


def test_place_not_found_maps_to_not_found():
    from servers.places.server import _to_error_response, PlaceNotFoundError
    resp = _to_error_response(PlaceNotFoundError("Place not found"))
    assert resp == {"error": "Place not found", "code": "NOT_FOUND"}


def test_quota_in_message_maps_to_quota():
    from servers.places.server import _to_error_response
    resp = _to_error_response(ApiUnavailableError("Google Places quota exceeded"))
    assert resp["code"] == "QUOTA"


def test_rate_limit_in_message_maps_to_quota():
    from servers.places.server import _to_error_response
    resp = _to_error_response(ApiUnavailableError("HTTP 429 rate limit"))
    assert resp["code"] == "QUOTA"


def test_generic_api_unavailable_maps_to_unknown():
    from servers.places.server import _to_error_response
    resp = _to_error_response(ApiUnavailableError("network unreachable"))
    assert resp["code"] == "UNKNOWN"


def test_configuration_error_maps_to_unknown():
    from servers.places.server import _to_error_response
    resp = _to_error_response(ConfigurationError("bad config"))
    assert resp["code"] == "UNKNOWN"


def test_bare_exception_logs_and_maps_to_unknown():
    from servers.places.server import _to_error_response
    resp = _to_error_response(RuntimeError("boom"))
    assert resp == {"error": "Unexpected error", "code": "UNKNOWN"}
    assert "boom" not in resp["error"]
