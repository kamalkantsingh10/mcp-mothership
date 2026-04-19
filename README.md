# MCP Mothership

A centralized MCP server manager for developers who build multiple agentic projects. Instead of duplicating MCP server setup across every project, Mothership runs all your MCP servers from a single location. Any agentic project connects to the Mothership over the network — no per-project MCP infrastructure needed.

## What It Does

- **Process management** — start, stop, and monitor MCP servers as isolated subprocesses from a single CLI command
- **Network transport** — all MCP servers run on Streamable HTTP, accessible from any project on your machine
- **Web dashboard** — see server status, metrics (uptime, requests, errors), and per-server logs at `http://localhost:8080`
- **Convention-based registration** — add a new MCP server by dropping a `mothership.yaml` config file
- **Crash detection** — automatic health monitoring with 3-second polling

The first managed server is **Imagen** — AI image generation via Google's Gemini (Nano Banana Pro) with multi-turn conversational refinement.

## Prerequisites

- Python 3.10+
- [Poetry](https://python-poetry.org/docs/#installation)
- For Imagen: a Google AI Studio API key OR a GCP project with Vertex AI enabled

## Quick Start

### 1. Clone and install

```bash
git clone <repo-url> mcp-mothership
cd mcp-mothership
poetry install
```

### 2. Configure credentials

```bash
cp .env.example .env
```

Edit `.env` and set your Imagen credentials:

```env
# Option A — AI Studio (easiest)
IMAGEN_API_KEY=your-api-key

# Option B — Vertex AI
# IMAGEN_GCP_PROJECT=your-gcp-project-id
```

For AI Studio, get a key at https://aistudio.google.com/api-keys. For Vertex AI setup details, see [Vertex AI Configuration](#vertex-ai-configuration) below.

### 3. Start the Mothership

```bash
poetry run python -m mothership
```

This starts the manager on port 8080. Open `http://localhost:8080` for the dashboard.

### 4. Verify

```bash
poetry run pytest -v
```

## Connecting From a Claude Code Project

The main value of Mothership is that your MCP servers are always running and accessible from any project. Here's how to connect from a Claude Code project.

### Step 1: Start the Mothership (if not already running)

In the Mothership directory:

```bash
poetry run python -m mothership
```

Then start the Imagen server from the dashboard at `http://localhost:8080`, or it can be started via the API:

```bash
curl -X POST http://localhost:8080/api/servers/imagen/start
```

### Step 2: Configure your Claude Code project

In your project directory, add the Mothership's servers to `.mcp.json`. Include every server you want this project to use:

```json
{
  "mcpServers": {
    "imagen": {
      "type": "streamable-http",
      "url": "http://localhost:8101/mcp"
    },
    "places": {
      "type": "streamable-http",
      "url": "http://localhost:8102/mcp"
    }
  }
}
```

Each entry points at a Mothership-managed server by port:

| Server | Port | URL |
|---|---|---|
| `imagen` | 8101 | `http://localhost:8101/mcp` |
| `places` | 8102 | `http://localhost:8102/mcp` |

Drop any entry you don't need. Claude Code will connect to whatever is running in the Mothership over HTTP — no need to install dependencies, configure credentials, or run anything in your project.

### Step 3: Use it

Ask Claude to generate images:

> "Generate an image of a sunset over mountains"

> "Make it more dramatic with darker clouds" (uses session-based refinement)

The `generate_image` tool is automatically available via MCP's `tools/list`.

### Adding to Multiple Projects

Every Claude Code project that needs image generation gets the same `.mcp.json` entry — they all connect to the same running Imagen server. No duplication.

## Dashboard

The web dashboard at `http://localhost:8080` shows:

- Summary cards (total servers, running count, request/error totals)
- Server table with status, port, uptime, request/error counts
- Start/Stop controls per server
- Expandable log viewer per server with color-coded log levels
- Auto-refreshes every 5 seconds

## REST API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/servers` | GET | List all servers with status and metrics |
| `/api/servers/{name}/start` | POST | Start a server |
| `/api/servers/{name}/stop` | POST | Stop a server |
| `/api/servers/{name}/logs?lines=100` | GET | Tail server log file |
| `/api/rescan` | POST | Rescan for new server configs |

## Adding a New MCP Server

1. Create `servers/<name>/` with `server.py`, `config.py`, and `__init__.py`
2. Add a `mothership.yaml` in the server directory:

```yaml
name: my-server
description: "What this server does"
entry_point: servers.my_server.server
port: 8102  # optional — auto-assigned if omitted
env_vars:
  - MY_API_KEY
```

3. Hit "Rescan" in the dashboard (or `POST /api/rescan`)
4. The new server appears in the dashboard, ready to start

## Configuration

### Operational Settings

Edit `config.yaml`:

```yaml
log_level: INFO

imagen:
  default_output_dir: ./output
  default_width: 1024
  default_height: 1024
```

### Manager Settings

Set via environment variables or `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `MOTHERSHIP_PORT` | `8080` | Dashboard/API port |
| `MOTHERSHIP_LOG_DIR` | `./logs` | Log file directory |

### Imagen Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `IMAGEN_API_KEY` | One of these | — | AI Studio API key |
| `IMAGEN_GCP_PROJECT` | is required | — | GCP project ID (Vertex AI) |
| `IMAGEN_GCP_REGION` | No | `us-central1` | GCP region |
| `IMAGEN_MODEL` | No | `gemini-3-pro-image-preview` | Model ID |

Config priority: env vars > `.env` file > `config.yaml` > defaults

### Places Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_PLACES_API_KEY` | Yes | — | Google Places API (New) key |

### Google Places API Key

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and select (or create) a project.
2. Enable billing on the project — Places API calls require a billing account even within the free tier.
3. Enable the **Places API (New)** — note the console lists two entries, legacy "Places API" and "Places API (New)". This server uses the **New** one only; enabling the legacy API is not required.
   ```bash
   gcloud services enable places.googleapis.com --project=YOUR_PROJECT_ID
   ```
   Or via the console: **APIs & Services → Library → "Places API (New)" → Enable**.
4. Create an API key: **APIs & Services → Credentials → Create Credentials → API key**.
5. Restrict the key (recommended): **Edit API key → API restrictions → Restrict key → select "Places API (New)"**.
6. Set it in `.env`:
   ```
   GOOGLE_PLACES_API_KEY=your-places-api-key
   ```

### Vertex AI Configuration

1. Enable the Vertex AI API:
   ```bash
   gcloud services enable aiplatform.googleapis.com --project=YOUR_PROJECT_ID
   ```
2. Grant IAM role:
   ```bash
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="user:YOUR_EMAIL@example.com" \
     --role="roles/aiplatform.user"
   ```
3. Authenticate:
   ```bash
   gcloud auth application-default login
   ```
4. Set in `.env`:
   ```
   IMAGEN_GCP_PROJECT=your-gcp-project-id
   ```

## Project Structure

```
mothership/              # Manager application
  __main__.py            # Entry point (python -m mothership)
  manager.py             # Process manager (start, stop, health, metrics)
  discovery.py           # Config scanner (mothership.yaml files)
  api.py                 # FastAPI REST API + static serving
  config.py              # MothershipConfig
  static/index.html      # Dashboard UI

servers/imagen/          # Imagen MCP server
  server.py              # FastMCP server + generate_image tool + /metrics
  config.py              # ImagenConfig
  mothership.yaml        # Registration config

shared/                  # Shared modules
  errors.py              # Error hierarchy (MothershipError, etc.)
  config.py              # Base config classes
  logging_config.py      # Per-server rotating log setup

logs/                    # Runtime log files (gitignored)
tests/                   # Mirrors source structure
```

## Running Tests

```bash
poetry run pytest -v
```

If you have ROS system packages installed:

```bash
PYTHONPATH="" poetry run pytest -v
```

## Troubleshooting

**"Credential ... is missing" on startup:**
Set either `IMAGEN_API_KEY` or `IMAGEN_GCP_PROJECT` in `.env`.

**"Permission denied" (Vertex AI):**
Run `gcloud auth application-default login` and verify `roles/aiplatform.user`.

**Server won't start from dashboard:**
Check `logs/<server_name>.log` for details. Common causes: missing credentials, port already in use.

**Dashboard shows "Disconnected":**
The Mothership process isn't running. Start it with `poetry run python -m mothership`.

**ROS/system Python conflicts in tests:**
Use `PYTHONPATH="" poetry run pytest`.
