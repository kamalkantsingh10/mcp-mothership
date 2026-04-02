# MCP Capability Platform — Brainstorm

**Date:** 2026-04-03
**Status:** Idea / Future Build

## The Idea

A self-hosted cluster of MCP servers running as a central capability platform. When creating AI agents, you point them at this server and grant access to the specific capabilities they need. One platform, many agents, scoped access.

```
MCP Capability Platform (always-on box on local network)
│
├── Agent A (diary)     → [gmail, calendar, notion]
├── Agent B (health)    → [notion, web-search]
├── Agent C (assistant) → [gmail, calendar, finance, playwright]
└── Agent D (research)  → [web-search, playwright, notion]
```

## Why Build This

- **Build once, reuse everywhere** — any agent you spin up gets capabilities by config, not by rebuilding integrations
- **Credentials in one place** — API keys and tokens live on the platform, not scattered across agents
- **Traceability** — centralized logging of who connected, what tools were called, inputs/outputs
- **Capability scoping** — each agent only sees the tools you grant it
- **Nothing like this exists yet** — open source ecosystem has pieces (individual MCPs, proxies, transport bridges) but no unified self-hosted capability platform with access control

## Capability Catalog

### Communication
- **Gmail** — read, send, search, label emails
- **Google Calendar** — events, scheduling, reminders
- **Slack** (future) — messaging, channel ops
- **SMS/WhatsApp** (future) — notifications, messaging

### Knowledge & Data
- **Notion** — weight goals, journals, structured data, notes
- **Finance/Stocks** — stock prices, portfolio tracking (Yahoo Finance / Alpha Vantage API)
- **Web Search** — general question answering, lookups

### Automation
- **Playwright** — headless browser automation, form filling, scraping, screenshots
- **Imagen** — image generation (already built, uses Vertex AI)

### Future Ideas
- Home automation (Home Assistant integration)
- Local LLM inference (Ollama)
- File/document management
- RAG/vector search over personal docs
- Voice/TTS

## Architecture

### Core Components

```
Platform
├── Gateway Layer
│   ├── Auth — API key per agent
│   ├── Capability scoping — agent-to-tool mapping
│   └── Routing — directs calls to correct MCP backend
│
├── Tracing / Observability
│   ├── SQLite log of all tool calls
│   ├── Fields: agent_id, tool, input, output, timestamp, duration
│   └── Dashboard (future) for reviewing activity
│
├── MCP Servers (the actual capabilities)
│   ├── Each is a Python module (same pattern as imagen)
│   ├── Transport: SSE or streamable HTTP (network accessible)
│   └── Can run as one merged FastMCP process or separate services
│
└── Config
    ├── Agent registry (who can connect)
    ├── Capability profiles (what each agent can access)
    └── Server config (credentials, API keys, defaults)
```

### Deployment Options

Single process (simplest):
```python
main = FastMCP("capabilities")
main.mount("imagen", imagen_mcp)
main.mount("gmail", gmail_mcp)
main.mount("notion", notion_mcp)
main.run(transport="sse", host="0.0.0.0", port=3000)
```

Systemd services (per-MCP isolation):
```
imagen-mcp.service  → :3001
gmail-mcp.service   → :3002
notion-mcp.service  → :3003
```

### Tracing Middleware

```python
@main.middleware
async def trace(request, next):
    log(agent=request.auth, tool=request.tool, input=request.params)
    result = await next(request)
    log(result=result, duration=elapsed)
    return result
```

## Hardware

Any always-on box on the local network. Options considered:

| Option | Verdict |
|---|---|
| Raspberry Pi 5 | Cheap, low power, but ARM + Playwright is friction |
| Low-power i7 PC | Good if already owned — more than enough |
| Mac Mini M-series | Best buy if purchasing — low power, silent, Apple Silicon for future local AI |

**Decision:** Use whatever's available. Code is portable Python, can migrate later.

## Existing Open Source (Pieces, Not Solutions)

- **Smithery / mcp.run** — MCP registries, cloud-hosted, not self-hosted
- **mcp-proxy** — routes multiple MCPs behind one endpoint, no access control
- **Docker MCP Toolkit** — containerized MCPs, no capability management
- **Supergateway** — stdio-to-SSE bridge, transport only
- **Playwright MCP** — open source, ready to use
- **Notion MCP** — community-built, plug and play

None of these combine into the full platform vision. The gateway + auth + scoping + tracing layer is the novel part.

## MVP Scope (When Ready to Build)

1. Take existing imagen MCP, switch to SSE transport
2. Add Notion MCP (community server, config only)
3. Add Finance MCP (thin wrapper over free stock API)
4. Add Playwright MCP (open source)
5. Build gateway with API key auth + agent-to-tool scoping
6. Add tracing middleware with SQLite storage
7. Deploy on chosen hardware, expose on local network
8. Define agent capability profiles in a simple YAML config

## Open Questions

- Should the gateway be its own MCP that proxies to backends, or a reverse proxy (nginx/Caddy) with middleware?
- How to handle MCP servers that need OAuth flows (Gmail, Calendar) — token refresh on the platform side?
- Should capability profiles live in YAML config or a small DB?
- Remote access — VPN/Tailscale for using agents outside the home network?
- Monitoring/alerting if an MCP server goes down?
