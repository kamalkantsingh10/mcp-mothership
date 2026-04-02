"""Tests for servers/imagen/server.py — generate_image tool with mocked google-genai."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from shared.errors import ApiUnavailableError, CredentialError, GenerationError


@pytest.fixture(autouse=True)
def _mock_config(monkeypatch):
    """Provide a valid config so server module can import without real env vars."""
    monkeypatch.setenv("IMAGEN_API_KEY", "test-api-key")


@pytest.fixture(autouse=True)
def _clear_sessions(_mock_config):
    """Clear the session store between tests (depends on _mock_config for env var)."""
    from servers.imagen.server import _sessions
    _sessions.clear()
    yield
    _sessions.clear()


@pytest.fixture
def mock_pil_image():
    """Create a mock PIL Image returned by part.as_image()."""
    image = MagicMock()
    image.save = MagicMock()
    return image


def _make_mock_response(mock_pil_image):
    """Build a mock chat response with candidates[0].content.parts."""
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


class TestGenerateImageSuccess:
    """Verify successful image generation paths."""

    @pytest.mark.asyncio
    async def test_generate_with_default_path(self, tmp_path, mock_genai_stack, mock_pil_image):
        mock_client, mock_chat, _ = mock_genai_stack

        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            result_json = await generate_image(prompt="a cat on a rainbow")
        finally:
            config.default_output_dir = original_dir

        result = json.loads(result_json)
        assert "session_id" in result
        assert "image_path" in result
        mock_client.chats.create.assert_called_once()
        mock_chat.send_message.assert_called_once()
        mock_pil_image.save.assert_called_once()
        assert os.path.isabs(result["image_path"])
        assert "a_cat_on_a_rainbow" in result["image_path"]
        assert result["image_path"].endswith(".png")

    @pytest.mark.asyncio
    async def test_generate_with_custom_path(self, tmp_path, mock_genai_stack, mock_pil_image):
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            custom_path = str(tmp_path / "custom" / "my_image.png")
            result_json = await generate_image(prompt="test prompt", output_path=custom_path)
        finally:
            config.default_output_dir = original_dir

        result = json.loads(result_json)
        mock_pil_image.save.assert_called_once_with(custom_path)
        assert os.path.isabs(result["image_path"])

    @pytest.mark.asyncio
    async def test_output_directory_created(self, tmp_path, mock_genai_stack, mock_pil_image):
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            nested_dir = tmp_path / "deep" / "nested"
            custom_path = str(nested_dir / "image.png")
            await generate_image(prompt="test", output_path=custom_path)
        finally:
            config.default_output_dir = original_dir

        assert nested_dir.exists()


class TestSessionManagement:
    """Verify session creation, continuation, and invalid session handling."""

    @pytest.mark.asyncio
    async def test_new_session_created_without_session_id(self, tmp_path, mock_genai_stack, mock_pil_image):
        mock_client, mock_chat, _ = mock_genai_stack
        from servers.imagen.server import generate_image, config, _sessions

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            result_json = await generate_image(prompt="test", output_path=str(tmp_path / "img.png"))
        finally:
            config.default_output_dir = original_dir

        result = json.loads(result_json)
        assert result["session_id"] is not None
        assert len(result["session_id"]) == 36  # UUID format
        mock_client.chats.create.assert_called_once()
        assert result["session_id"] in _sessions

    @pytest.mark.asyncio
    async def test_session_continuation_with_valid_session_id(self, tmp_path, mock_genai_stack, mock_pil_image):
        mock_client, mock_chat, _ = mock_genai_stack
        from servers.imagen.server import generate_image, config, _sessions

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            # First call — create session
            result1_json = await generate_image(prompt="draw a cat", output_path=str(tmp_path / "img1.png"))
            result1 = json.loads(result1_json)
            sid = result1["session_id"]

            # Second call — continue session
            result2_json = await generate_image(prompt="make it blue", session_id=sid, output_path=str(tmp_path / "img2.png"))
            result2 = json.loads(result2_json)
        finally:
            config.default_output_dir = original_dir

        assert result2["session_id"] == sid
        # chats.create called only once (for first call)
        mock_client.chats.create.assert_called_once()
        # send_message called twice (once per call)
        assert mock_chat.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_invalid_session_id_raises_generation_error(self, mock_genai_stack):
        from servers.imagen.server import generate_image

        with pytest.raises(GenerationError, match="Invalid session ID"):
            await generate_image(prompt="test", session_id="nonexistent-id")

    @pytest.mark.asyncio
    async def test_multi_turn_uses_same_chat(self, tmp_path, mock_genai_stack, mock_pil_image):
        mock_client, mock_chat, _ = mock_genai_stack
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            r1 = json.loads(await generate_image(prompt="a house", output_path=str(tmp_path / "1.png")))
            sid = r1["session_id"]
            await generate_image(prompt="add a garden", session_id=sid, output_path=str(tmp_path / "2.png"))
            await generate_image(prompt="make it sunset", session_id=sid, output_path=str(tmp_path / "3.png"))
        finally:
            config.default_output_dir = original_dir

        # Only one chat created
        mock_client.chats.create.assert_called_once()
        # Three messages sent on same chat
        assert mock_chat.send_message.call_count == 3


class TestResponseParsing:
    """Verify response handling for various part combinations."""

    @pytest.mark.asyncio
    async def test_text_and_image_parts(self, tmp_path, mock_pil_image):
        mock_client = MagicMock()
        mock_chat = MagicMock()

        mock_response = MagicMock()
        text_part = MagicMock()
        text_part.text = "Here's your image"
        text_part.as_image.return_value = None
        image_part = MagicMock()
        image_part.text = None
        image_part.as_image.return_value = mock_pil_image
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [text_part, image_part]
        mock_chat.send_message.return_value = mock_response
        mock_client.chats.create.return_value = mock_chat

        with patch("servers.imagen.server.client", mock_client):
            from servers.imagen.server import generate_image, config

            original_dir = config.default_output_dir
            config.default_output_dir = str(tmp_path)
            try:
                result_json = await generate_image(prompt="test", output_path=str(tmp_path / "img.png"))
            finally:
                config.default_output_dir = original_dir

        result = json.loads(result_json)
        assert result["image_path"] == str(tmp_path / "img.png")
        mock_pil_image.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_image_only_response(self, tmp_path, mock_pil_image):
        mock_client = MagicMock()
        mock_chat = MagicMock()

        mock_response = MagicMock()
        image_part = MagicMock()
        image_part.text = None
        image_part.as_image.return_value = mock_pil_image
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [image_part]
        mock_chat.send_message.return_value = mock_response
        mock_client.chats.create.return_value = mock_chat

        with patch("servers.imagen.server.client", mock_client):
            from servers.imagen.server import generate_image, config

            original_dir = config.default_output_dir
            config.default_output_dir = str(tmp_path)
            try:
                result_json = await generate_image(prompt="test", output_path=str(tmp_path / "img.png"))
            finally:
                config.default_output_dir = original_dir

        result = json.loads(result_json)
        assert result["image_path"] == str(tmp_path / "img.png")

    @pytest.mark.asyncio
    async def test_no_image_in_response_raises_error(self, tmp_path):
        mock_client = MagicMock()
        mock_chat = MagicMock()

        mock_response = MagicMock()
        text_part = MagicMock()
        text_part.text = "Sorry, I can't generate that"
        text_part.as_image.return_value = None
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [text_part]
        mock_chat.send_message.return_value = mock_response
        mock_client.chats.create.return_value = mock_chat

        with patch("servers.imagen.server.client", mock_client):
            from servers.imagen.server import generate_image, config

            original_dir = config.default_output_dir
            config.default_output_dir = str(tmp_path)
            try:
                with pytest.raises(GenerationError, match="No image was returned"):
                    await generate_image(prompt="test", output_path=str(tmp_path / "img.png"))
            finally:
                config.default_output_dir = original_dir


class TestDimensionMapping:
    """Verify width/height are mapped to correct aspect ratios and passed via image_config."""

    @pytest.mark.asyncio
    async def test_square_maps_to_1_1(self, tmp_path, mock_genai_stack, mock_pil_image):
        _, mock_chat, _ = mock_genai_stack
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            await generate_image(prompt="test", width=1024, height=1024, output_path=str(tmp_path / "img.png"))
        finally:
            config.default_output_dir = original_dir
        call_kwargs = mock_chat.send_message.call_args
        gen_config = call_kwargs.kwargs["config"]
        assert gen_config.image_config.aspect_ratio == "1:1"

    @pytest.mark.asyncio
    async def test_landscape_maps_to_16_9(self, tmp_path, mock_genai_stack, mock_pil_image):
        _, mock_chat, _ = mock_genai_stack
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            await generate_image(prompt="test", width=1920, height=1080, output_path=str(tmp_path / "img.png"))
        finally:
            config.default_output_dir = original_dir
        call_kwargs = mock_chat.send_message.call_args
        gen_config = call_kwargs.kwargs["config"]
        assert gen_config.image_config.aspect_ratio == "16:9"

    @pytest.mark.asyncio
    async def test_portrait_maps_to_9_16(self, tmp_path, mock_genai_stack, mock_pil_image):
        _, mock_chat, _ = mock_genai_stack
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            await generate_image(prompt="test", width=1080, height=1920, output_path=str(tmp_path / "img.png"))
        finally:
            config.default_output_dir = original_dir
        call_kwargs = mock_chat.send_message.call_args
        gen_config = call_kwargs.kwargs["config"]
        assert gen_config.image_config.aspect_ratio == "9:16"

    @pytest.mark.asyncio
    async def test_4_3_aspect(self, tmp_path, mock_genai_stack, mock_pil_image):
        _, mock_chat, _ = mock_genai_stack
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            await generate_image(prompt="test", width=800, height=600, output_path=str(tmp_path / "img.png"))
        finally:
            config.default_output_dir = original_dir
        call_kwargs = mock_chat.send_message.call_args
        gen_config = call_kwargs.kwargs["config"]
        assert gen_config.image_config.aspect_ratio == "4:3"

    @pytest.mark.asyncio
    async def test_3_4_aspect(self, tmp_path, mock_genai_stack, mock_pil_image):
        _, mock_chat, _ = mock_genai_stack
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            await generate_image(prompt="test", width=600, height=800, output_path=str(tmp_path / "img.png"))
        finally:
            config.default_output_dir = original_dir
        call_kwargs = mock_chat.send_message.call_args
        gen_config = call_kwargs.kwargs["config"]
        assert gen_config.image_config.aspect_ratio == "3:4"

    @pytest.mark.asyncio
    async def test_invalid_zero_width_raises_generation_error(self, mock_genai_stack):
        from servers.imagen.server import generate_image

        with pytest.raises(GenerationError, match="must be positive"):
            await generate_image(prompt="test", width=0, height=100)

    @pytest.mark.asyncio
    async def test_invalid_negative_height_raises_generation_error(self, mock_genai_stack):
        from servers.imagen.server import generate_image

        with pytest.raises(GenerationError, match="must be positive"):
            await generate_image(prompt="test", width=100, height=-1)


class TestDimensionPassThrough:
    """Verify width/height are passed to Gemini via image_config aspect_ratio."""

    @pytest.mark.asyncio
    async def test_dimensions_converted_to_aspect_ratio_in_config(self, tmp_path, mock_genai_stack, mock_pil_image):
        _, mock_chat, _ = mock_genai_stack
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            await generate_image(prompt="test", width=1920, height=1080, output_path=str(tmp_path / "img.png"))
        finally:
            config.default_output_dir = original_dir

        call_kwargs = mock_chat.send_message.call_args
        gen_config = call_kwargs.kwargs["config"]
        assert gen_config.response_modalities == ["TEXT", "IMAGE"]
        assert gen_config.image_config.aspect_ratio == "16:9"

    @pytest.mark.asyncio
    async def test_default_dimensions_produce_square_ratio(self, tmp_path, mock_genai_stack, mock_pil_image):
        _, mock_chat, _ = mock_genai_stack
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            await generate_image(prompt="test", output_path=str(tmp_path / "img.png"))
        finally:
            config.default_output_dir = original_dir

        call_kwargs = mock_chat.send_message.call_args
        gen_config = call_kwargs.kwargs["config"]
        assert gen_config.image_config.aspect_ratio == "1:1"


class TestStyleParameter:
    """Verify style is applied via prompt engineering."""

    @pytest.mark.asyncio
    async def test_natural_style_does_not_modify_prompt(self, tmp_path, mock_genai_stack, mock_pil_image):
        _, mock_chat, _ = mock_genai_stack
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            await generate_image(prompt="a cat", style="natural", output_path=str(tmp_path / "img.png"))
        finally:
            config.default_output_dir = original_dir
        call_args = mock_chat.send_message.call_args
        assert call_args.args[0] == "a cat"

    @pytest.mark.asyncio
    async def test_custom_style_prepended_to_prompt(self, tmp_path, mock_genai_stack, mock_pil_image):
        _, mock_chat, _ = mock_genai_stack
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            await generate_image(prompt="a cat", style="digital art", output_path=str(tmp_path / "img.png"))
        finally:
            config.default_output_dir = original_dir
        call_args = mock_chat.send_message.call_args
        assert call_args.args[0] == "digital art style: a cat"

    @pytest.mark.asyncio
    async def test_empty_style_does_not_modify_prompt(self, tmp_path, mock_genai_stack, mock_pil_image):
        _, mock_chat, _ = mock_genai_stack
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            await generate_image(prompt="a cat", style="", output_path=str(tmp_path / "img.png"))
        finally:
            config.default_output_dir = original_dir
        call_args = mock_chat.send_message.call_args
        assert call_args.args[0] == "a cat"


class TestOutputPathHandling:
    """Verify custom output path validation and edge cases."""

    @pytest.mark.asyncio
    async def test_parent_directories_created(self, tmp_path, mock_genai_stack, mock_pil_image):
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            nested_dir = tmp_path / "a" / "b" / "c"
            custom_path = str(nested_dir / "img.png")
            await generate_image(prompt="test", output_path=custom_path)
        finally:
            config.default_output_dir = original_dir

        assert nested_dir.exists()

    @pytest.mark.asyncio
    async def test_existing_file_overwritten(self, tmp_path, mock_genai_stack, mock_pil_image):
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            existing = tmp_path / "existing.png"
            existing.write_text("old content")
            result_json = await generate_image(prompt="test", output_path=str(existing))
        finally:
            config.default_output_dir = original_dir

        result = json.loads(result_json)
        mock_pil_image.save.assert_called_once_with(str(existing.resolve()))
        assert result["image_path"] == str(existing.resolve())

    @pytest.mark.asyncio
    async def test_unwritable_directory_raises_generation_error(self, tmp_path, mock_genai_stack, mock_pil_image):
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        config.default_output_dir = str(readonly_dir)
        readonly_dir.chmod(0o444)
        try:
            with pytest.raises(GenerationError, match="not writable"):
                await generate_image(prompt="test", output_path=str(readonly_dir / "img.png"))
        finally:
            readonly_dir.chmod(0o755)
            config.default_output_dir = original_dir

    @pytest.mark.asyncio
    async def test_path_traversal_outside_output_dir_rejected(self, tmp_path, mock_genai_stack, mock_pil_image):
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path / "output")
        try:
            with pytest.raises(GenerationError, match="must be within"):
                await generate_image(prompt="test", output_path="/tmp/evil/image.png")
        finally:
            config.default_output_dir = original_dir

    @pytest.mark.asyncio
    async def test_relative_traversal_rejected(self, tmp_path, mock_genai_stack, mock_pil_image):
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        config.default_output_dir = str(output_dir)
        try:
            with pytest.raises(GenerationError, match="must be within"):
                await generate_image(prompt="test", output_path=str(output_dir / ".." / "escaped.png"))
        finally:
            config.default_output_dir = original_dir


class TestPromptValidation:
    """Verify empty/whitespace prompts are rejected."""

    @pytest.mark.asyncio
    async def test_empty_prompt_raises_generation_error(self, mock_genai_stack):
        from servers.imagen.server import generate_image

        with pytest.raises(GenerationError, match="empty"):
            await generate_image(prompt="")

    @pytest.mark.asyncio
    async def test_whitespace_prompt_raises_generation_error(self, mock_genai_stack):
        from servers.imagen.server import generate_image

        with pytest.raises(GenerationError, match="empty"):
            await generate_image(prompt="   ")


class TestSanitizeFilename:
    """Verify _sanitize_filename handles adversarial input."""

    def test_normal_text(self):
        from servers.imagen.server import _sanitize_filename

        assert _sanitize_filename("a cat on a rainbow") == "a_cat_on_a_rainbow"

    def test_special_characters_stripped(self):
        from servers.imagen.server import _sanitize_filename

        assert _sanitize_filename("hello!@#$%^&*()world") == "helloworld"

    def test_all_special_characters_returns_untitled(self):
        from servers.imagen.server import _sanitize_filename

        assert _sanitize_filename("!@#$%^&*()") == "untitled"

    def test_empty_string_returns_untitled(self):
        from servers.imagen.server import _sanitize_filename

        assert _sanitize_filename("") == "untitled"

    def test_long_text_truncated(self):
        from servers.imagen.server import _sanitize_filename

        result = _sanitize_filename("a" * 100, max_len=50)
        assert len(result) == 50

    def test_unicode_characters(self):
        from servers.imagen.server import _sanitize_filename

        result = _sanitize_filename("cute cat 🐱")
        assert result  # Should produce some non-empty result
        assert "cute_cat" in result


class TestGenerateImageErrors:
    """Verify error handling for various failure scenarios."""

    @pytest.mark.asyncio
    async def test_credential_error_on_permission_denied(self):
        from google.genai import errors as genai_errors
        mock_client = MagicMock()
        mock_chat = MagicMock()
        exc = genai_errors.ClientError.__new__(genai_errors.ClientError)
        exc.code = 403
        exc.message = "Permission denied"
        mock_chat.send_message.side_effect = exc
        mock_client.chats.create.return_value = mock_chat

        with patch("servers.imagen.server.client", mock_client):
            from servers.imagen.server import generate_image

            with pytest.raises(CredentialError, match="permission denied"):
                await generate_image(prompt="test")

    @pytest.mark.asyncio
    async def test_credential_error_on_not_found(self):
        from google.genai import errors as genai_errors
        mock_client = MagicMock()
        mock_chat = MagicMock()
        exc = genai_errors.ClientError.__new__(genai_errors.ClientError)
        exc.code = 404
        exc.message = "Not found"
        mock_chat.send_message.side_effect = exc
        mock_client.chats.create.return_value = mock_chat

        with patch("servers.imagen.server.client", mock_client):
            from servers.imagen.server import generate_image

            with pytest.raises(CredentialError, match="project not found"):
                await generate_image(prompt="test")

    @pytest.mark.asyncio
    async def test_generation_error_on_quota_exceeded(self):
        from google.genai import errors as genai_errors
        mock_client = MagicMock()
        mock_chat = MagicMock()
        exc = genai_errors.ClientError.__new__(genai_errors.ClientError)
        exc.code = 429
        exc.message = "Quota exceeded"
        mock_chat.send_message.side_effect = exc
        mock_client.chats.create.return_value = mock_chat

        with patch("servers.imagen.server.client", mock_client):
            from servers.imagen.server import generate_image

            with pytest.raises(GenerationError, match="Quota exceeded"):
                await generate_image(prompt="test")

    @pytest.mark.asyncio
    async def test_generation_error_on_bad_request(self):
        from google.genai import errors as genai_errors
        mock_client = MagicMock()
        mock_chat = MagicMock()
        exc = genai_errors.ClientError.__new__(genai_errors.ClientError)
        exc.code = 400
        exc.message = "Bad request"
        mock_chat.send_message.side_effect = exc
        mock_client.chats.create.return_value = mock_chat

        with patch("servers.imagen.server.client", mock_client):
            from servers.imagen.server import generate_image

            with pytest.raises(GenerationError, match="Invalid request"):
                await generate_image(prompt="test")

    @pytest.mark.asyncio
    async def test_api_unavailable_on_server_error(self):
        from google.genai import errors as genai_errors
        mock_client = MagicMock()
        mock_chat = MagicMock()
        exc = genai_errors.ServerError.__new__(genai_errors.ServerError)
        exc.code = 500
        exc.message = "Internal server error"
        mock_chat.send_message.side_effect = exc
        mock_client.chats.create.return_value = mock_chat

        with patch("servers.imagen.server.client", mock_client):
            from servers.imagen.server import generate_image

            with pytest.raises(ApiUnavailableError, match="Vertex AI API unavailable"):
                await generate_image(prompt="test")

    @pytest.mark.asyncio
    async def test_generation_error_on_api_error_fallback(self):
        from google.genai import errors as genai_errors
        mock_client = MagicMock()
        mock_chat = MagicMock()
        exc = genai_errors.APIError.__new__(genai_errors.APIError)
        exc.code = 999
        exc.message = "Unknown"
        mock_chat.send_message.side_effect = exc
        mock_client.chats.create.return_value = mock_chat

        with patch("servers.imagen.server.client", mock_client):
            from servers.imagen.server import generate_image

            with pytest.raises(GenerationError, match="Image generation failed"):
                await generate_image(prompt="test")

    @pytest.mark.asyncio
    async def test_connection_error_maps_to_api_unavailable(self):
        mock_client = MagicMock()
        mock_chat = MagicMock()
        mock_chat.send_message.side_effect = ConnectionError("Connection refused")
        mock_client.chats.create.return_value = mock_chat

        with patch("servers.imagen.server.client", mock_client):
            from servers.imagen.server import generate_image

            with pytest.raises(ApiUnavailableError, match="Network error"):
                await generate_image(prompt="test")

    @pytest.mark.asyncio
    async def test_generation_error_on_none_parts(self, tmp_path):
        mock_client = MagicMock()
        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = None
        mock_chat.send_message.return_value = mock_response
        mock_client.chats.create.return_value = mock_chat

        with patch("servers.imagen.server.client", mock_client):
            from servers.imagen.server import generate_image, config

            original_dir = config.default_output_dir
            config.default_output_dir = str(tmp_path)
            try:
                with pytest.raises(GenerationError, match="No image was returned"):
                    await generate_image(prompt="test", output_path=str(tmp_path / "test.png"))
            finally:
                config.default_output_dir = original_dir

    @pytest.mark.asyncio
    async def test_save_oserror_maps_to_generation_error(self, tmp_path):
        mock_client = MagicMock()
        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_pil_image = MagicMock()
        mock_pil_image.save.side_effect = OSError("Disk full")
        mock_image_part = MagicMock()
        mock_image_part.text = None
        mock_image_part.as_image.return_value = mock_pil_image
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [mock_image_part]
        mock_chat.send_message.return_value = mock_response
        mock_client.chats.create.return_value = mock_chat

        with patch("servers.imagen.server.client", mock_client):
            from servers.imagen.server import generate_image, config

            original_dir = config.default_output_dir
            config.default_output_dir = str(tmp_path)
            try:
                with pytest.raises(GenerationError, match="Failed to save"):
                    await generate_image(prompt="test", output_path=str(tmp_path / "test.png"))
            finally:
                config.default_output_dir = original_dir


class TestCredentialSafety:
    """Verify no credential values appear in error messages."""

    @pytest.mark.asyncio
    async def test_permission_denied_does_not_expose_project_id(self):
        from google.genai import errors as genai_errors
        mock_client = MagicMock()
        mock_chat = MagicMock()
        exc = genai_errors.ClientError.__new__(genai_errors.ClientError)
        exc.code = 403
        exc.message = "denied"
        mock_chat.send_message.side_effect = exc
        mock_client.chats.create.return_value = mock_chat

        with patch("servers.imagen.server.client", mock_client):
            from servers.imagen.server import generate_image, config

            with pytest.raises(CredentialError) as exc_info:
                await generate_image(prompt="test")

            error_msg = str(exc_info.value)
            assert "test-api-key" not in error_msg

    @pytest.mark.asyncio
    async def test_error_does_not_leak_raw_exception_content(self):
        from google.genai import errors as genai_errors
        mock_client = MagicMock()
        mock_chat = MagicMock()
        exc = genai_errors.ClientError.__new__(genai_errors.ClientError)
        exc.code = 403
        exc.message = "secret-token-12345"
        mock_chat.send_message.side_effect = exc
        mock_client.chats.create.return_value = mock_chat

        with patch("servers.imagen.server.client", mock_client):
            from servers.imagen.server import generate_image

            with pytest.raises(CredentialError) as exc_info:
                await generate_image(prompt="test")

            error_msg = str(exc_info.value)
            assert "secret-token-12345" not in error_msg


class TestNoTimeout:
    """Verify no timeout is imposed on API calls (NFR5)."""

    @pytest.mark.asyncio
    async def test_send_message_called_without_timeout(self, tmp_path, mock_genai_stack, mock_pil_image):
        _, mock_chat, _ = mock_genai_stack
        from servers.imagen.server import generate_image, config

        original_dir = config.default_output_dir
        config.default_output_dir = str(tmp_path)
        try:
            await generate_image(prompt="test", output_path=str(tmp_path / "img.png"))
        finally:
            config.default_output_dir = original_dir
        call_kwargs = mock_chat.send_message.call_args
        assert "timeout" not in (call_kwargs.kwargs or {})
