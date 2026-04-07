"""Tests for Imagen MCP server transport and tool schema.

Verifies the server is configured for Streamable HTTP transport
and that the generate_image tool is properly exposed with correct schema.
"""

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from shared.errors import GenerationError


@pytest.fixture(autouse=True)
def _mock_config(monkeypatch):
    """Provide a valid config so server module can import without real env vars."""
    monkeypatch.setenv("IMAGEN_API_KEY", "test-api-key")


@pytest.fixture(autouse=True)
def _clear_sessions(_mock_config):
    """Clear the session store and reset metrics between tests."""
    import servers.imagen.server as srv
    srv._sessions.clear()
    srv._request_count = 0
    srv._error_count = 0
    srv._last_request_time = None
    yield
    srv._sessions.clear()
    srv._request_count = 0
    srv._error_count = 0
    srv._last_request_time = None


@pytest.fixture
def mock_pil_image():
    """Create a mock PIL Image returned by part.as_image()."""
    image = MagicMock()
    image.save = MagicMock()
    return image


def _make_mock_response(mock_pil_image):
    """Build a mock chat response with an image part."""
    mock_response = MagicMock()
    mock_image_part = MagicMock()
    mock_image_part.text = None
    mock_image_part.as_image.return_value = mock_pil_image
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content.parts = [mock_image_part]
    return mock_response


@pytest.fixture
def mock_genai_stack(mock_pil_image):
    """Patch genai client at the server module level with chat support."""
    mock_client = MagicMock()
    mock_chat = MagicMock()
    mock_response = _make_mock_response(mock_pil_image)
    mock_chat.send_message.return_value = mock_response
    mock_client.chats.create.return_value = mock_chat

    with patch("servers.imagen.server.client", mock_client):
        yield mock_client, mock_chat, mock_response


class TestTransportConfiguration:
    """Verify the server is configured for Streamable HTTP transport."""

    def test_mcp_server_host_is_all_interfaces(self):
        from servers.imagen.server import mcp
        assert mcp.settings.host == "0.0.0.0"

    def test_mcp_server_port_matches_config(self):
        from servers.imagen.server import mcp, config
        assert mcp.settings.port == config.port

    def test_mcp_server_default_port_is_8101(self):
        from servers.imagen.server import config
        assert config.port == 8101

    def test_streamable_http_app_is_starlette(self):
        from servers.imagen.server import mcp
        app = mcp.streamable_http_app()
        from starlette.applications import Starlette
        assert isinstance(app, Starlette)

    def test_no_stdio_references_in_server_module(self):
        import inspect
        import servers.imagen.server as mod
        source = inspect.getsource(mod)
        # The only acceptable reference is in the __name__ block which now uses streamable-http
        assert 'transport="stdio"' not in source


class TestToolSchema:
    """Verify generate_image tool is exposed with correct schema via MCP."""

    def test_tool_list_contains_generate_image(self):
        from servers.imagen.server import mcp
        tools = mcp._tool_manager.list_tools()
        tool_names = [t.name for t in tools]
        assert "generate_image" in tool_names

    def test_generate_image_schema_has_required_params(self):
        from servers.imagen.server import mcp
        tools = mcp._tool_manager.list_tools()
        gen_tool = next(t for t in tools if t.name == "generate_image")
        props = gen_tool.parameters.get("properties", {})
        expected_params = ["prompt", "width", "height", "style", "output_path", "session_id"]
        for param in expected_params:
            assert param in props, f"Missing parameter: {param}"

    def test_generate_image_prompt_is_required(self):
        from servers.imagen.server import mcp
        tools = mcp._tool_manager.list_tools()
        gen_tool = next(t for t in tools if t.name == "generate_image")
        required = gen_tool.parameters.get("required", [])
        assert "prompt" in required

    def test_generate_image_has_description(self):
        from servers.imagen.server import mcp
        tools = mcp._tool_manager.list_tools()
        gen_tool = next(t for t in tools if t.name == "generate_image")
        assert gen_tool.description
        assert "image" in gen_tool.description.lower()


class TestImageGenerationViaTransport:
    """Verify image generation works correctly (transport-agnostic tool tests)."""

    @pytest.mark.asyncio
    async def test_generate_image_returns_session_and_path(self, tmp_path, mock_genai_stack, mock_pil_image):
        mock_client, mock_chat, _ = mock_genai_stack
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            result_json = await generate_image(prompt="a sunset over mountains")
        finally:
            config.default_output_dir = original_dir

        result = json.loads(result_json)
        assert "session_id" in result
        assert "image_path" in result
        assert len(result["session_id"]) == 36  # UUID format
        mock_client.chats.create.assert_called_once()
        mock_chat.send_message.assert_called_once()
        mock_pil_image.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_image_session_refinement(self, tmp_path, mock_genai_stack, mock_pil_image):
        mock_client, mock_chat, _ = mock_genai_stack
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            r1 = json.loads(await generate_image(
                prompt="draw a cat", output_path=str(tmp_path / "img1.png")
            ))
            sid = r1["session_id"]
            r2 = json.loads(await generate_image(
                prompt="make it blue", session_id=sid, output_path=str(tmp_path / "img2.png")
            ))
        finally:
            config.default_output_dir = original_dir

        assert r2["session_id"] == sid
        mock_client.chats.create.assert_called_once()
        assert mock_chat.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_image_empty_prompt_raises(self, mock_genai_stack):
        from servers.imagen.server import generate_image

        with pytest.raises(GenerationError, match="empty"):
            await generate_image(prompt="")

    @pytest.mark.asyncio
    async def test_generate_image_invalid_dimensions_raises(self, mock_genai_stack):
        from servers.imagen.server import generate_image

        with pytest.raises(GenerationError, match="must be positive"):
            await generate_image(prompt="test", width=0, height=100)


class TestUtilityFunctions:
    """Verify utility functions used by the server."""

    def test_sanitize_filename(self):
        from servers.imagen.server import _sanitize_filename
        assert _sanitize_filename("a cat on a rainbow") == "a_cat_on_a_rainbow"
        assert _sanitize_filename("") == "untitled"
        assert _sanitize_filename("!@#$%") == "untitled"
        result = _sanitize_filename("a" * 100, max_len=50)
        assert len(result) == 50

    def test_map_dimensions_to_aspect_ratio(self):
        from servers.imagen.server import _map_dimensions_to_aspect_ratio
        assert _map_dimensions_to_aspect_ratio(1024, 1024) == "1:1"
        assert _map_dimensions_to_aspect_ratio(1920, 1080) == "16:9"
        assert _map_dimensions_to_aspect_ratio(1080, 1920) == "9:16"
        assert _map_dimensions_to_aspect_ratio(800, 600) == "4:3"
        assert _map_dimensions_to_aspect_ratio(600, 800) == "3:4"

    def test_map_dimensions_invalid_raises(self):
        from servers.imagen.server import _map_dimensions_to_aspect_ratio
        with pytest.raises(GenerationError):
            _map_dimensions_to_aspect_ratio(0, 100)
        with pytest.raises(GenerationError):
            _map_dimensions_to_aspect_ratio(100, -1)


class TestMetricsTracking:
    """Verify request/error counters and /metrics endpoint."""

    @pytest.mark.asyncio
    async def test_metrics_initial_state(self):
        import servers.imagen.server as srv
        assert srv._request_count == 0
        assert srv._error_count == 0
        assert srv._last_request_time is None

    @pytest.mark.asyncio
    async def test_metrics_increment_on_success(self, tmp_path, mock_genai_stack, mock_pil_image):
        import servers.imagen.server as srv
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            await generate_image(prompt="test", output_path=str(tmp_path / "img.png"))
        finally:
            config.default_output_dir = original_dir

        assert srv._request_count == 1
        assert srv._error_count == 0
        assert srv._last_request_time is not None

    @pytest.mark.asyncio
    async def test_metrics_increment_on_error(self, mock_genai_stack):
        import servers.imagen.server as srv
        from servers.imagen.server import generate_image

        with pytest.raises(GenerationError):
            await generate_image(prompt="")

        assert srv._request_count == 1
        assert srv._error_count == 1
        assert srv._last_request_time is not None

    @pytest.mark.asyncio
    async def test_metrics_multiple_calls(self, tmp_path, mock_genai_stack, mock_pil_image):
        import servers.imagen.server as srv
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            await generate_image(prompt="first", output_path=str(tmp_path / "1.png"))
            await generate_image(prompt="second", output_path=str(tmp_path / "2.png"))
        finally:
            config.default_output_dir = original_dir

        assert srv._request_count == 2
        assert srv._error_count == 0

    def test_metrics_endpoint_returns_json(self):
        from servers.imagen.server import mcp
        from starlette.testclient import TestClient

        app = mcp.streamable_http_app()
        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "request_count" in data
        assert "error_count" in data
        assert "last_request_time" in data
        assert data["request_count"] == 0
        assert data["error_count"] == 0
        assert data["last_request_time"] is None

    def test_metrics_endpoint_coexists_with_mcp(self):
        from servers.imagen.server import mcp

        app = mcp.streamable_http_app()
        # Verify both /metrics and /mcp routes are registered on the same app
        route_paths = [r.path for r in app.routes]
        assert "/metrics" in route_paths
        assert "/mcp" in route_paths


class TestConcurrentConnectivity:
    """Verify multiple concurrent clients can use the server without interference.

    Starlette/uvicorn handle concurrency natively via asyncio's single-threaded
    event loop. These tests prove the properties hold for our server implementation.
    """

    @pytest.mark.asyncio
    async def test_concurrent_generate_image(self, tmp_path, mock_genai_stack, mock_pil_image):
        """Two clients generate images concurrently, each gets independent results."""
        import servers.imagen.server as srv
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            result_a, result_b = await asyncio.gather(
                generate_image(prompt="sunset", output_path=str(tmp_path / "a.png")),
                generate_image(prompt="mountain", output_path=str(tmp_path / "b.png")),
            )
        finally:
            config.default_output_dir = original_dir

        a = json.loads(result_a)
        b = json.loads(result_b)
        assert a["session_id"] != b["session_id"]
        assert a["image_path"] != b["image_path"]
        assert srv._request_count == 2
        assert srv._error_count == 0

    @pytest.mark.asyncio
    async def test_concurrent_session_isolation(self, tmp_path, mock_genai_stack, mock_pil_image):
        """Two clients create separate sessions that don't interfere."""
        mock_client, mock_chat, _ = mock_genai_stack
        from servers.imagen.server import generate_image, config, _sessions

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            # Both clients create sessions concurrently
            r_a, r_b = await asyncio.gather(
                generate_image(prompt="client A image", output_path=str(tmp_path / "a.png")),
                generate_image(prompt="client B image", output_path=str(tmp_path / "b.png")),
            )
        finally:
            config.default_output_dir = original_dir

        sid_a = json.loads(r_a)["session_id"]
        sid_b = json.loads(r_b)["session_id"]
        assert sid_a != sid_b
        assert sid_a in _sessions
        assert sid_b in _sessions
        assert len(_sessions) == 2

    @pytest.mark.asyncio
    async def test_client_disconnect_no_impact(self, tmp_path, mock_genai_stack, mock_pil_image):
        """After client A finishes (simulated disconnect), client B still works."""
        from servers.imagen.server import generate_image, config, _sessions

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            # Client A creates session and "disconnects" (just completes)
            r_a = json.loads(await generate_image(
                prompt="client A", output_path=str(tmp_path / "a.png")
            ))
            sid_a = r_a["session_id"]

            # Simulate disconnect: remove client A's session
            del _sessions[sid_a]

            # Client B should still work fine
            r_b = json.loads(await generate_image(
                prompt="client B", output_path=str(tmp_path / "b.png")
            ))
        finally:
            config.default_output_dir = original_dir

        assert r_b["session_id"] is not None
        assert r_b["image_path"].endswith("b.png")

    @pytest.mark.asyncio
    async def test_concurrent_metrics_combined(self, tmp_path, mock_genai_stack, mock_pil_image):
        """Metrics reflect combined activity from multiple concurrent clients."""
        import servers.imagen.server as srv
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            await asyncio.gather(
                generate_image(prompt="one", output_path=str(tmp_path / "1.png")),
                generate_image(prompt="two", output_path=str(tmp_path / "2.png")),
                generate_image(prompt="three", output_path=str(tmp_path / "3.png")),
            )
        finally:
            config.default_output_dir = original_dir

        assert srv._request_count == 3
        assert srv._error_count == 0
        assert srv._last_request_time is not None

    @pytest.mark.asyncio
    async def test_concurrent_error_does_not_affect_success(self, tmp_path, mock_genai_stack, mock_pil_image):
        """An error from one client doesn't prevent another from succeeding."""
        import servers.imagen.server as srv
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)

        async def error_call():
            with pytest.raises(GenerationError):
                await generate_image(prompt="")

        async def success_call():
            return await generate_image(prompt="valid", output_path=str(tmp_path / "ok.png"))

        try:
            await asyncio.gather(error_call(), success_call())
        finally:
            config.default_output_dir = original_dir

        assert srv._request_count == 2
        assert srv._error_count == 1

    def test_concurrent_tool_list(self):
        """Multiple clients can list tools concurrently (schema access is read-only)."""
        from servers.imagen.server import mcp

        tools_a = mcp._tool_manager.list_tools()
        tools_b = mcp._tool_manager.list_tools()

        names_a = [t.name for t in tools_a]
        names_b = [t.name for t in tools_b]
        assert names_a == names_b == ["generate_image"]
