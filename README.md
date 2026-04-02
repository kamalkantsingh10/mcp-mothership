# Engagement Manager

MCP server for AI-powered image generation via Google's Nano Banana Pro (Gemini 3 Pro Image). Supports conversational multi-turn image refinement through Claude Code.

## Features

- Generate images from text prompts via MCP tool
- Iterative image refinement through multi-turn chat sessions
- Style control via prompt engineering
- Automatic aspect ratio mapping from width/height dimensions
- Output path sandboxing for safe file writes
- Credential-safe error handling (no secrets in error messages)

## Prerequisites

- Python 3.10+
- [Poetry](https://python-poetry.org/docs/#installation) (Python package manager)
- **AI Studio** (easiest): A Google AI Studio API key, OR
- **Vertex AI**: A GCP project + [gcloud CLI](https://cloud.google.com/sdk/docs/install)

## Setup

### 1. Install Dependencies

```bash
poetry install
```

### 2. Configure API Credentials

```bash
cp .env.example .env
```

**Option A — AI Studio (recommended for getting started):**

1. Get an API key from https://aistudio.google.com/api-keys
2. Edit `.env`:
   ```
   IMAGEN_API_KEY=your-api-key
   ```

That's it — no GCP project or gcloud auth needed.

**Option B — Vertex AI (for production/enterprise):**

1. Create or select a GCP project at https://console.cloud.google.com
2. Enable the Vertex AI API:
   ```bash
   gcloud services enable aiplatform.googleapis.com --project=YOUR_PROJECT_ID
   ```
3. Grant the required IAM role:
   ```bash
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="user:YOUR_EMAIL@example.com" \
     --role="roles/aiplatform.user"
   ```
4. Authenticate:
   ```bash
   gcloud auth application-default login
   ```
5. Edit `.env`:
   ```
   IMAGEN_GCP_PROJECT=your-gcp-project-id
   ```

If both `IMAGEN_API_KEY` and `IMAGEN_GCP_PROJECT` are set, AI Studio takes priority.

### 5. Configure Operational Settings (Optional)

Edit `config.yaml` to customize defaults:

```yaml
log_level: INFO

imagen:
  default_output_dir: ./output      # Where generated images are saved
  default_width: 1024               # Default image width
  default_height: 1024              # Default image height
```

Config priority: env vars > `.env` file > `config.yaml` > defaults

### 6. Register MCP Server in Claude Code

**Option A** - Project-level `.mcp.json`:

```json
{
  "mcpServers": {
    "imagen": {
      "type": "stdio",
      "command": "poetry",
      "args": ["run", "python", "servers/imagen/server.py"],
      "env": {
        "IMAGEN_GCP_PROJECT": "${IMAGEN_GCP_PROJECT}"
      }
    }
  }
}
```

**Option B** - Via CLI:
```bash
claude mcp add imagen -- poetry run python servers/imagen/server.py
```

### 7. Verify Setup

```bash
poetry run pytest -v
```

## Usage

The `generate_image` MCP tool accepts:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | string | (required) | Text description or refinement instruction |
| `width` | int | 1024 | Image width (mapped to nearest aspect ratio) |
| `height` | int | 1024 | Image height (mapped to nearest aspect ratio) |
| `style` | string | `"natural"` | Style direction (e.g., `"digital art"`, `"watercolor"`) |
| `output_path` | string | auto-generated | Custom output path (must be within output dir) |
| `session_id` | string | `null` | Pass a previous session_id to refine an existing image |

**Returns** JSON:
```json
{"session_id": "uuid", "image_path": "/absolute/path/to/image.png"}
```

### Multi-turn Refinement

1. First call (no `session_id`) creates a new chat session and returns a `session_id`
2. Subsequent calls with the same `session_id` refine the image conversationally
3. The model maintains visual consistency across turns

Supported aspect ratios: `1:1`, `9:16`, `16:9`, `4:3`, `3:4`

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `IMAGEN_API_KEY` | One of these | — | AI Studio API key |
| `IMAGEN_GCP_PROJECT` | is required | — | GCP project ID (Vertex AI mode) |
| `IMAGEN_GCP_REGION` | No | `us-central1` | GCP region (Vertex AI only) |
| `IMAGEN_MODEL` | No | `gemini-3-pro-image-preview` | Model ID |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Project Structure

```
servers/imagen/
  config.py          # ImagenConfig (pydantic-settings, loads from env/.env/yaml)
  server.py          # MCP server with generate_image tool
shared/
  config.py          # BaseServerConfig with YAML support
  errors.py          # Typed error hierarchy
  logging.py         # stderr-only logging setup
tests/
  imagen/            # Server and config tests
  shared/            # Shared module tests
```

## Running Tests

```bash
poetry run pytest -v
```

If you have ROS system packages installed, prefix with:
```bash
PYTHONPATH="" poetry run pytest -v
```

## Troubleshooting

**"Credential ... is missing" on startup:**
- Set either `IMAGEN_API_KEY` (AI Studio) or `IMAGEN_GCP_PROJECT` (Vertex AI) in `.env`

**"Permission denied" or credential errors (Vertex AI):**
- Run `gcloud auth application-default login`
- Verify your account has `roles/aiplatform.user` on the project

**"API not enabled" errors (Vertex AI):**
```bash
gcloud services enable aiplatform.googleapis.com --project=YOUR_PROJECT_ID
```

**"ConfigurationError" on startup:**
- Check that `config.yaml` is valid YAML

**ROS/system Python conflicts in tests:**
- Use `PYTHONPATH="" poetry run pytest` — the `pyproject.toml` already disables ROS pytest plugins
