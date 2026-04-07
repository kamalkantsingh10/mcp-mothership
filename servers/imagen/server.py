"""Imagen MCP server — generates images via Vertex AI Nano Banana Pro.

Exposes a single `generate_image` tool over MCP Streamable HTTP transport.
"""

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from google import genai
from google.genai import types, errors

from mcp.server.fastmcp import FastMCP

from servers.imagen.config import ImagenConfig
from shared.errors import ApiUnavailableError, CredentialError, GenerationError
from shared.logging_config import setup_logging

# Gemini supported aspect ratios and their decimal values
SUPPORTED_ASPECT_RATIOS: list[tuple[str, float]] = [
    ("1:1", 1.0),
    ("9:16", 9 / 16),
    ("16:9", 16 / 9),
    ("4:3", 4 / 3),
    ("3:4", 3 / 4),
]

logger = logging.getLogger(__name__)

config = ImagenConfig.from_yaml(config_path="config.yaml")
setup_logging(config.log_level, log_name="imagen")

logger.info("Imagen MCP server starting up")
logger.info("Config: model=%s, region=%s, output_dir=%s", config.imagen_model, config.imagen_gcp_region, config.default_output_dir)

# Initialize google-genai client once at startup
# AI Studio mode: IMAGEN_API_KEY set → use api_key auth
# Vertex AI mode: IMAGEN_GCP_PROJECT set → use vertexai auth
try:
    if config.imagen_api_key:
        logger.info("Using AI Studio auth (API key)")
        client = genai.Client(api_key=config.imagen_api_key)
    elif config.imagen_gcp_project:
        logger.info("Using Vertex AI auth (project=%s, region=%s)", config.imagen_gcp_project, config.imagen_gcp_region)
        client = genai.Client(
            vertexai=True,
            project=config.imagen_gcp_project,
            location=config.imagen_gcp_region,
        )
    else:
        raise CredentialError(
            "IMAGEN_API_KEY",
            reason="is missing — set IMAGEN_API_KEY (AI Studio) or IMAGEN_GCP_PROJECT (Vertex AI)",
        )
    logger.info("API client initialized successfully")
except CredentialError:
    logger.error("Credential error during initialization")
    raise
except (ConnectionError, TimeoutError) as e:
    logger.error("Network error during API initialization: %s", e)
    raise ApiUnavailableError(
        "Network error during API initialization"
    ) from e
except Exception as e:
    logger.error("Failed to initialize API client: %s", e)
    raise CredentialError(
        "IMAGEN_API_KEY",
        reason="failed to initialize API client — check credentials",
    ) from e

mcp = FastMCP("imagen", host="0.0.0.0", port=config.port)
logger.info("MCP server created, ready to accept connections")

# In-memory session store for multi-turn conversational image generation
_sessions: dict[str, Any] = {}

# In-memory metrics counters
_request_count: int = 0
_error_count: int = 0
_last_request_time: str | None = None


def _sanitize_filename(text: str, max_len: int = 50) -> str:
    """Sanitize a prompt string into a safe filename fragment."""
    sanitized = re.sub(r"[^\w\s-]", "", text.lower())
    sanitized = re.sub(r"[\s_]+", "_", sanitized).strip("_")
    return sanitized[:max_len] or "untitled"


def _map_dimensions_to_aspect_ratio(width: int, height: int) -> str:
    """Map width/height to the closest supported aspect ratio.

    Supported ratios: 1:1, 9:16, 16:9, 4:3, 3:4.
    """
    if width <= 0 or height <= 0:
        raise GenerationError(
            f"Invalid dimensions: width ({width}) and height ({height}) must be positive integers"
        )
    target_ratio = width / height
    closest_label = SUPPORTED_ASPECT_RATIOS[0][0]
    closest_diff = abs(target_ratio - SUPPORTED_ASPECT_RATIOS[0][1])
    for label, ratio in SUPPORTED_ASPECT_RATIOS[1:]:
        diff = abs(target_ratio - ratio)
        if diff < closest_diff:
            closest_diff = diff
            closest_label = label
    return closest_label


@mcp.tool()
async def generate_image(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    style: str = "natural",
    output_path: str | None = None,
    session_id: str | None = None,
) -> str:
    """Generate an image from a text prompt using Vertex AI Nano Banana Pro.

    Supports multi-turn conversational refinement. Omit session_id for a new
    session, or pass a previous session_id to refine an existing image.

    Args:
        prompt: Text description of the image to generate, or refinement instruction.
        width: Image width in pixels (mapped to closest supported aspect ratio).
        height: Image height in pixels (mapped to closest supported aspect ratio).
        style: Artistic style direction (e.g., "natural", "digital art").
            Applied via prompt engineering — prepended to the prompt text.
        output_path: Custom file path for the generated image.
            Must resolve within the configured output directory.
        session_id: ID of an existing chat session for iterative refinement.
            Omit to start a new session.

    Returns:
        JSON string with session_id and image_path:
        {"session_id": "...", "image_path": "/path/to/image.png"}
    """
    global _request_count, _error_count, _last_request_time
    _request_count += 1
    _last_request_time = datetime.now(timezone.utc).isoformat()

    try:
        return await _generate_image_impl(prompt, width, height, style, output_path, session_id)
    except Exception:
        _error_count += 1
        raise


async def _generate_image_impl(
    prompt: str,
    width: int,
    height: int,
    style: str,
    output_path: str | None,
    session_id: str | None,
) -> str:
    """Internal implementation of generate_image (metrics tracked by wrapper)."""
    if not prompt or not prompt.strip():
        raise GenerationError("Prompt must not be empty or whitespace-only")

    logger.info("generate_image called: prompt=%r, width=%d, height=%d, style=%s, session_id=%s", prompt[:100], width, height, style, session_id)
    aspect_ratio = _map_dimensions_to_aspect_ratio(width, height)

    # Nano Banana Pro has no native style parameter — apply via prompt engineering
    if style and style.lower() != "natural":
        effective_prompt = f"{style} style: {prompt}"
    else:
        effective_prompt = prompt

    logger.info(
        "Generating image for prompt: %s (aspect_ratio=%s, style=%s, session_id=%s)",
        prompt[:100],
        aspect_ratio,
        style,
        session_id,
    )

    # Session management: look up existing or create new
    if session_id is not None:
        if session_id not in _sessions:
            raise GenerationError("Invalid session ID — session not found or expired")
        chat = _sessions[session_id]
    else:
        chat = client.chats.create(
            model=config.imagen_model,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )
        session_id = str(uuid.uuid4())
        _sessions[session_id] = chat

    logger.debug("Sending request to model %s with aspect_ratio=%s", config.imagen_model, aspect_ratio)
    try:
        response = chat.send_message(
            effective_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                ),
            ),
        )
    except errors.ClientError as e:
        if e.code == 403:
            raise CredentialError(
                "IMAGEN_GCP_PROJECT",
                reason="permission denied — check IAM roles",
            ) from e
        elif e.code == 404:
            raise CredentialError(
                "IMAGEN_GCP_PROJECT",
                reason="project not found or API not enabled",
            ) from e
        elif e.code == 429:
            raise GenerationError("Quota exceeded — try again later") from e
        else:
            raise GenerationError("Invalid request — check prompt and parameters") from e
    except errors.ServerError as e:
        raise ApiUnavailableError("Vertex AI API unavailable") from e
    except errors.APIError as e:
        raise GenerationError("Image generation failed") from e
    except (ConnectionError, TimeoutError) as e:
        raise ApiUnavailableError(
            "Network error during image generation"
        ) from e

    # Resolve output path — sandbox custom paths to output directory
    allowed_dir = os.path.abspath(config.default_output_dir)
    if output_path:
        output_path_resolved = os.path.abspath(output_path)
        if not output_path_resolved.startswith(allowed_dir + os.sep) and output_path_resolved != allowed_dir:
            raise GenerationError(
                f"Output path must be within the configured output directory: {allowed_dir}"
            )
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{_sanitize_filename(prompt)}.png"
        output_path_resolved = os.path.join(allowed_dir, filename)

    parent_dir = os.path.dirname(output_path_resolved) or "."
    os.makedirs(parent_dir, exist_ok=True)

    if not os.access(parent_dir, os.W_OK):
        raise GenerationError(
            f"Output directory is not writable: {parent_dir}"
        )

    # Extract image from response parts
    try:
        image_saved = False
        for part in response.candidates[0].content.parts:
            if part.text is not None:
                logger.info("Model response: %s", part.text[:200])
            elif image := part.as_image():
                image.save(output_path_resolved)
                image_saved = True
                break
        if not image_saved:
            raise GenerationError("No image was returned by the API")
    except GenerationError:
        raise
    except (AttributeError, TypeError) as e:
        raise GenerationError("No image was returned by the API") from e
    except OSError as e:
        raise GenerationError(f"Failed to save image: {e}") from e

    logger.info("Image saved to: %s", output_path_resolved)
    return json.dumps({"session_id": session_id, "image_path": output_path_resolved})


@mcp.custom_route("/metrics", methods=["GET"])
async def metrics(request):
    """Expose server metrics as JSON."""
    from starlette.responses import JSONResponse
    return JSONResponse({
        "request_count": _request_count,
        "error_count": _error_count,
        "last_request_time": _last_request_time,
    })


if __name__ == "__main__":
    logger.info("Starting MCP Streamable HTTP transport on port %d", config.port)
    mcp.run(transport="streamable-http")
