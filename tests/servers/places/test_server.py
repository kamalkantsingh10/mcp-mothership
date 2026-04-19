"""Tests for Places MCP server transport configuration and /metrics endpoint."""

import sys

import pytest

from shared.errors import CredentialError


@pytest.fixture(autouse=True)
def _mock_config(monkeypatch):
    """Provide a valid API key so the server module imports without real env vars."""
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")


@pytest.fixture(autouse=True)
def _reset_metrics(_mock_config):
    """Reset metrics globals between tests."""
    import servers.places.server as srv
    srv._request_count = 0
    srv._error_count = 0
    srv._last_request_time = None
    yield
    srv._request_count = 0
    srv._error_count = 0
    srv._last_request_time = None


class TestTransportConfiguration:
    """Verify the server is configured for Streamable HTTP transport."""

    def test_mcp_server_host_is_all_interfaces(self):
        from servers.places.server import mcp
        assert mcp.settings.host == "0.0.0.0"

    def test_mcp_server_port_matches_config(self):
        from servers.places.server import mcp, config
        assert mcp.settings.port == config.port

    def test_mcp_server_default_port_is_8102(self):
        from servers.places.server import config
        assert config.port == 8102

    def test_streamable_http_app_is_starlette(self):
        from servers.places.server import mcp
        app = mcp.streamable_http_app()
        from starlette.applications import Starlette
        assert isinstance(app, Starlette)

    def test_no_stdio_references_in_server_module(self):
        import inspect
        import servers.places.server as mod
        source = inspect.getsource(mod)
        assert 'transport="stdio"' not in source

    def test_metrics_endpoint_initial_state(self):
        from servers.places.server import mcp
        from starlette.testclient import TestClient

        app = mcp.streamable_http_app()
        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data == {
            "request_count": 0,
            "error_count": 0,
            "last_request_time": None,
        }


class TestStartupCredentialValidation:
    """Story 7.1 AC #2 — missing GOOGLE_PLACES_API_KEY raises CredentialError at startup."""

    def test_missing_api_key_raises_credential_error_at_startup(self, monkeypatch, tmp_path):
        """Reimport `servers.places.server` with no API key set; startup must fail fast."""
        monkeypatch.chdir(tmp_path)  # no config.yaml, no .env in cwd
        monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("servers.places"):
                del sys.modules[mod_name]
        try:
            with pytest.raises(CredentialError) as exc_info:
                import servers.places.server  # noqa: F401
            assert "GOOGLE_PLACES_API_KEY" in str(exc_info.value)
        finally:
            # Force a fresh reimport for subsequent tests with the valid env var restored.
            for mod_name in list(sys.modules.keys()):
                if mod_name.startswith("servers.places"):
                    del sys.modules[mod_name]
