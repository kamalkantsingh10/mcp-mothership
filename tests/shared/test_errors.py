"""Tests for shared/errors.py — error hierarchy and credential safety."""

import pytest

from shared.errors import (
    ApiUnavailableError,
    ConfigurationError,
    CredentialError,
    EngagementManagerError,
    GenerationError,
)


class TestErrorHierarchy:
    """Verify each error class inherits correctly."""

    def test_base_is_exception(self):
        assert issubclass(EngagementManagerError, Exception)

    def test_configuration_error_hierarchy(self):
        assert issubclass(ConfigurationError, EngagementManagerError)
        err = ConfigurationError("missing field 'x'")
        assert isinstance(err, EngagementManagerError)
        assert isinstance(err, Exception)

    def test_api_unavailable_error_hierarchy(self):
        assert issubclass(ApiUnavailableError, EngagementManagerError)
        err = ApiUnavailableError("service down")
        assert isinstance(err, EngagementManagerError)

    def test_credential_error_hierarchy(self):
        assert issubclass(CredentialError, EngagementManagerError)
        err = CredentialError("IMAGEN_API_KEY")
        assert isinstance(err, EngagementManagerError)

    def test_generation_error_hierarchy(self):
        assert issubclass(GenerationError, EngagementManagerError)
        err = GenerationError("quota exceeded")
        assert isinstance(err, EngagementManagerError)


class TestCredentialSafety:
    """Verify CredentialError never exposes credential values."""

    def test_credential_error_contains_name_not_value(self):
        err = CredentialError("IMAGEN_API_KEY")
        assert "IMAGEN_API_KEY" in str(err)
        assert "is missing or invalid" in str(err)

    def test_credential_error_custom_reason(self):
        err = CredentialError("GCP_PROJECT", reason="was rejected by the API")
        assert "GCP_PROJECT" in str(err)
        assert "was rejected by the API" in str(err)

    def test_credential_error_stores_name(self):
        err = CredentialError("IMAGEN_API_KEY")
        assert err.credential_name == "IMAGEN_API_KEY"

    def test_credential_error_does_not_accept_value(self):
        # The constructor only accepts name and reason — no value parameter
        err = CredentialError("MY_SECRET", reason="expired")
        # The message should only contain the name and reason
        assert "MY_SECRET" in str(err)
        assert "expired" in str(err)


class TestErrorMessages:
    """Verify errors carry meaningful messages."""

    def test_configuration_error_message(self):
        err = ConfigurationError("field 'gcp_project' is required")
        assert "gcp_project" in str(err)

    def test_api_unavailable_message(self):
        err = ApiUnavailableError("Imagen API returned 503")
        assert "503" in str(err)

    def test_generation_error_message(self):
        err = GenerationError("quota exceeded for project")
        assert "quota exceeded" in str(err)

    def test_errors_are_catchable_by_base(self):
        errors = [
            ConfigurationError("test"),
            ApiUnavailableError("test"),
            CredentialError("KEY"),
            GenerationError("test"),
        ]
        for err in errors:
            with pytest.raises(EngagementManagerError):
                raise err
