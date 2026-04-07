---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain-skipped', 'step-06-innovation-skipped', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish', 'step-12-complete']
inputDocuments: ['documents/planning-artifacts/product-brief-engagement-manager.md', 'documents/planning-artifacts/mcp-capability-platform-brainstorm.md', 'documents/planning-artifacts/architecture.md', 'documents/planning-artifacts/epics.md']
workflowType: 'prd'
documentCounts:
  briefs: 1
  research: 0
  brainstorming: 1
  projectDocs: 2
classification:
  projectType: developer_tool
  domain: general
  complexity: medium
  projectContext: brownfield
---

# Product Requirements Document - MCP Mothership

**Author:** Kamal
**Date:** 2026-04-07

## Executive Summary

MCP Mothership is a centralized MCP server manager for developers who build multiple agentic projects. Instead of duplicating MCP server setup, configuration, and maintenance across every project, Mothership runs all MCP servers from a single location. Any agentic project connects to the Mothership — no per-project MCP infrastructure needed.

The system provides a lightweight web dashboard for starting and stopping MCP servers, monitoring their status (uptime, request counts, error counts, last request time), and viewing per-server logs. New MCP capabilities are added by dropping a configuration file — no code changes to the manager itself.

The existing Imagen MCP server (Vertex AI image generation via Nano Banana Pro) is the first managed capability, migrated from stdio to network transport. The project is built in Python, designed for single-user local operation.

### What Makes This Special

MCP Mothership is not a gateway, proxy, or capability framework. It is a purpose-built process manager with operational visibility for MCP servers. The core insight: MCP capabilities should be infrastructure you maintain in one place, not code you duplicate across projects. The value is immediate — spin up a new agentic project, point it at the Mothership, and every MCP capability you've ever built is already running.

## Project Classification

- **Project Type:** Developer Tool — infrastructure/platform tooling for MCP server management
- **Domain:** General — no regulated industry constraints
- **Complexity:** Medium — involves process management, network transport (SSE/HTTP), web dashboard, and structured logging
- **Project Context:** Brownfield — evolving an existing codebase with a working Imagen MCP server and shared Python modules (config, errors, logging)

## Success Criteria

### User Success

- New agentic project connects to an existing MCP capability with zero MCP server setup — just point to the Mothership
- Adding a new MCP capability requires only dropping a config file — no code changes to the manager
- Dashboard shows at a glance which MCPs are running, which are stopped, and which have crashed
- Logs for any MCP server are viewable independently without digging through combined output

### Business Success

- Single-user personal infrastructure tool — success means Kamal stops duplicating MCP servers across projects
- 10+ MCP servers manageable from one place without performance or usability degradation
- Time from "I want a new MCP capability" to "it's running and accessible" is measured in minutes, not hours

### Technical Success

- MCP servers run as independent processes — one crash does not take down others or the manager
- Crash events are logged with full error context and clearly surfaced on the dashboard
- Per-MCP logging is fully isolated — each server writes to its own log stream
- Network transport (SSE/HTTP) works reliably for multi-project connectivity
- Dashboard accurately reflects real-time server state (running, stopped, crashed, uptime, request count, error count, last request time)

### Measurable Outcomes

- All existing Imagen MCP functionality works identically after migration from stdio to network transport
- Dashboard loads and reflects accurate state within seconds
- Logs are queryable/viewable per MCP server from the UI
- 10+ MCP server configs can be registered and managed without UI or performance issues

## User Journeys

### Journey 1: The Operator — Daily Management

**Kamal, morning startup.** Opens the terminal, launches the Mothership. The web dashboard loads in the browser. He sees a list of all registered MCP servers — Imagen, Gmail, Notion, a few others he's added over the past months. All showing "Stopped." He clicks "Start" on the three he needs today: Imagen, Gmail, Notion. Within seconds, each flips to "Running" with uptime counters ticking. He minimizes the dashboard tab and gets to work.

**Mid-afternoon, something breaks.** He's working in his diary agent project when image generation stops responding. He switches to the Mothership dashboard. Imagen is showing "Crashed" in red with a timestamp. He clicks into Imagen's log view — the last entries show a `CredentialError: permission denied` with full stack context. His GCP token expired. He refreshes the token, hits "Start" on Imagen from the dashboard. Green again. Back to work in under a minute.

**End of day.** He glances at the dashboard. Imagen handled 23 requests today, Gmail 47, Notion 12. No errors on Gmail or Notion. He stops all servers and closes the Mothership.

**This journey reveals:** Dashboard UI (server list, start/stop controls, status indicators), real-time state updates, crash detection and display, per-MCP log viewing, metrics display (request count, uptime, error count, last request time).

### Journey 2: The MCP Developer — Adding a New Capability

**Kamal decides to add a Playwright MCP.** He creates a new server file under `servers/playwright/`, writes the MCP server code using FastMCP, and drops a config file for Playwright into the config directory. The config specifies the server's entry point, port, and any environment variables it needs.

He opens the Mothership dashboard. Playwright appears in the server list — status "Stopped," picked up automatically from the config file. He hits "Start." The server spins up, status flips to "Running." He checks the Playwright log stream to confirm clean startup — no errors.

He switches to one of his agent projects, and calls `tools/list` against the Mothership. Playwright's tools show up alongside Imagen and the rest. Done — new capability live in minutes.

**This journey reveals:** Convention-based config registration (drop a file, it appears), config format requirements, server discovery/scan on dashboard load, new MCP log stream auto-creation, tool discovery via MCP protocol.

### Journey 3: The Agent Builder — Connecting a Project

**Kamal starts a new agentic project — a research assistant.** In the project's MCP configuration, he adds a single entry pointing to the Mothership's address and port. No MCP server code in this project. No dependencies to install. No credentials to configure here.

The agent starts up and calls `tools/list` on the Mothership. It discovers `generate_image`, `send_email`, `search_notion`, `browse_page` — all the capabilities Kamal has ever registered. He configures the agent to use `search_notion` and `browse_page` for this project.

A week later, he adds Imagen capability to this same agent. No Mothership changes needed — Imagen is already running. He just updates his agent's config to also use `generate_image`. Instant capability expansion.

**This journey reveals:** Single connection endpoint for agents, MCP tool discovery, no per-project MCP infrastructure, capability reuse across projects, agent-side configuration is minimal (just a URL).

### Journey 4: The Agent — Runtime Interaction

**An agent in Kamal's diary project needs to generate an image.** It connects to the Mothership endpoint, calls `tools/list` to discover available tools, finds `generate_image`, and invokes it with a prompt. The Mothership routes the request to the running Imagen MCP server. The image is generated, saved, and the file path is returned to the agent.

The Mothership logs the request — which MCP handled it, when, how long it took. The request counter for Imagen increments. If the Imagen server had been stopped or crashed, the agent would receive a clear error indicating the capability is unavailable.

**This journey reveals:** Request routing to correct MCP server, per-request logging and metrics tracking, clear error responses for unavailable capabilities, MCP protocol compliance (`tools/list`, tool invocation).

### Journey Requirements Summary

| Capability | Revealed By |
|---|---|
| Dashboard with server list and status | Journey 1, 2 |
| Start/Stop controls per MCP | Journey 1, 2 |
| Real-time status (running/stopped/crashed) | Journey 1, 2 |
| Crash detection and error surfacing | Journey 1 |
| Per-MCP log viewing in UI | Journey 1, 2 |
| Metrics display (uptime, requests, errors, last request) | Journey 1 |
| Convention-based config registration | Journey 2 |
| Auto-discovery of new config files | Journey 2 |
| Network transport (SSE/HTTP) endpoint | Journey 3, 4 |
| MCP tool discovery via `tools/list` | Journey 3, 4 |
| Request routing to correct MCP server | Journey 4 |
| Per-request logging and metrics | Journey 4 |
| Clear error for unavailable MCP | Journey 4 |

## Developer Tool Specific Requirements

### Project-Type Overview

MCP Mothership is a Python developer tool that manages MCP server processes and exposes them over network transport. It runs directly from a cloned repository using Poetry — no package distribution. The primary interface is a CLI command to start the manager and a web dashboard for operational control.

### Technical Architecture Considerations

**Language & Runtime:**
- Python >=3.10 (MCP SDK requirement), development target 3.12
- Poetry for dependency management, consistent with existing codebase
- No compiled extensions — pure Python

**Single Entry Point:**
- Start the entire system (manager + dashboard) with one command: `python -m mothership` or equivalent Poetry script
- The manager process handles MCP server lifecycle and serves the web dashboard on a single port

**Transport Architecture:**
- Each managed MCP server runs as an independent subprocess exposed via SSE or Streamable HTTP
- The manager assigns ports to MCP servers from a configurable range or uses config-specified ports
- The dashboard runs on its own port (default configurable) served by the manager process

**MCP Server Config Format (YAML):**
Each MCP server is registered by dropping a YAML config file into a designated directory (e.g., `servers/<name>/mothership.yaml`). Required fields:

```yaml
name: imagen                          # Display name for dashboard
description: "Image generation via Vertex AI Nano Banana Pro"
entry_point: servers.imagen.server     # Python module path
port: 8101                             # Port to expose this MCP on (or auto-assign)
env_vars:                              # Environment variables needed (names only, not values)
  - IMAGEN_GCP_PROJECT
  - IMAGEN_API_KEY
```

- `name` — Human-readable identifier shown in dashboard
- `description` — What this MCP does, shown in dashboard
- `entry_point` — Python module path to the FastMCP server
- `port` — Network port for this MCP (optional, auto-assigned if omitted)
- `env_vars` — List of required environment variable names (values come from `.env`, not this file)

**Tool Discovery:**
- Agents connect to individual MCP server ports directly via SSE/HTTP
- Each MCP server natively supports `tools/list` via the MCP protocol — no custom discovery layer needed
- The dashboard shows which tools each MCP server exposes for operator reference

### Implementation Considerations

**Process Management:**
- Manager spawns each MCP server as a child subprocess
- Monitors subprocess health — detects crashes via process exit codes
- Maintains in-memory state: PID, status (running/stopped/crashed), start time, metrics
- Clean shutdown: stops all child processes when manager exits

**Logging Architecture:**
- Each MCP server logs to a dedicated log file (e.g., `logs/imagen.log`)
- Manager maintains its own log file (e.g., `logs/mothership.log`)
- Log files are rotated or size-limited to prevent disk fill
- Dashboard reads log files for real-time viewing

**Metrics Collection:**
- Request count, error count, last request time tracked per MCP server
- Uptime calculated from process start time
- Metrics stored in-memory by the manager (no persistent metrics store for MVP)

**Migration from Engagement Manager:**
- Rename project and repository to MCP Mothership
- Existing `shared/` modules (config, errors, logging) retained and evolved
- Imagen server migrated from stdio to SSE/HTTP transport
- Old planning artifacts remain as historical reference

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Complete operational tool — the MVP delivers the full management experience because the value proposition only works when all pieces connect. A dashboard without process management is useless; process management without logging is blind; logging without a UI is just files on disk.

**Resource Requirements:** Solo developer (Kamal), Python full-stack, existing codebase to build on.

### MVP Feature Set (Phase 1)

**Core User Journeys Supported:**
- Journey 1 (Operator): Full dashboard with start/stop, status, metrics, logs
- Journey 2 (MCP Developer): Drop config file, see it appear, start it up
- Journey 3 (Agent Builder): Connect to Mothership endpoint, discover tools
- Journey 4 (Agent Runtime): Request routing, metrics tracking, error handling

**Must-Have Capabilities:**
- Process manager that spawns/monitors/stops MCP server subprocesses
- Convention-based MCP registration via YAML config files
- SSE/HTTP transport for all managed MCP servers
- Web dashboard: server list, start/stop controls, real-time status (running/stopped/crashed)
- Dashboard metrics: uptime, request count, error count, last request time
- Per-MCP dedicated log files with dashboard log viewer
- Imagen MCP migrated from stdio to network transport as first managed server
- Single CLI command to start the entire system
- MCP protocol compliance including `tools/list` discovery
- Project renamed to MCP Mothership (repo, pyproject.toml, references)

### Phase 2 — Growth

- Auto-restart on crash (configurable per MCP)
- Log search and filtering in dashboard
- Health check endpoints per MCP server
- MCP dependency management (ordered startup)
- Dashboard authentication (basic, for when exposed beyond localhost)

### Phase 3 — Expansion

- Remote access via Tailscale/VPN
- Plugin system for community MCP servers
- Centralized credential management across all MCPs
- Capability scoping — per-agent access control to specific MCPs
- Persistent metrics with historical trends

### Risk Mitigation Strategy

**Technical Risks:**
- *Transport migration (stdio to SSE/HTTP):* FastMCP natively supports `transport="sse"`, so the migration is a config change per server, not an architectural rewrite. Test Imagen end-to-end with SSE before building the manager around it.
- *Process management reliability:* Use Python's `subprocess` module with proper signal handling. Monitor child processes via polling or `asyncio` subprocess APIs. Keep it simple — no custom process supervisors.
- *Dashboard real-time updates:* Streamlit's auto-refresh or a lightweight framework with polling/WebSocket. Evaluate Streamlit first for speed of development; fall back to FastAPI + simple HTML if Streamlit creates too much overhead or doesn't fit the UX.

**Resource Risks:**
- Solo developer — scope is intentionally contained to process management + UI + one MCP migration. No auth, no multi-user, no distribution. If time-constrained, the dashboard can start minimal (status + start/stop) and add log viewing and metrics in a fast follow.

## Functional Requirements

### MCP Server Lifecycle Management

- FR1: Operator can start an individual MCP server from the dashboard
- FR2: Operator can stop a running MCP server from the dashboard
- FR3: System detects when a managed MCP server process crashes and updates its status
- FR4: System stops all running MCP servers when the manager process exits
- FR5: Operator can start the entire Mothership system (manager + dashboard) with a single CLI command

### MCP Registration & Discovery

- FR6: System discovers MCP server configurations by scanning for YAML config files in the designated directory
- FR7: Operator can register a new MCP server by dropping a YAML config file without modifying manager code
- FR8: Config file specifies server name, description, entry point, port, and required environment variable names
- FR9: System validates MCP config files on discovery and reports errors for malformed configs
- FR10: Agents can discover available tools on a running MCP server via the MCP protocol `tools/list` method

### Network Transport

- FR11: Each managed MCP server is exposed via SSE or Streamable HTTP transport on its configured port
- FR12: Multiple agents from different projects can connect to the same MCP server simultaneously
- FR13: System assigns ports to MCP servers based on config or auto-assigns from a configurable range

### Dashboard — Server Overview

- FR14: Dashboard displays a list of all registered MCP servers with their current status (running, stopped, crashed)
- FR15: Dashboard displays per-server metrics: uptime, request count, error count, last request time
- FR16: Dashboard shows which tools each MCP server exposes
- FR17: Dashboard updates server status in near real-time without manual page refresh

### Dashboard — Log Viewing

- FR18: Dashboard provides a log viewer for each MCP server showing its dedicated log output
- FR19: Operator can select which MCP server's logs to view
- FR20: Log viewer displays recent log entries with timestamps and log levels

### Logging System

- FR21: Each MCP server writes logs to a dedicated log file separate from other servers
- FR22: Manager writes its own logs to a separate dedicated log file
- FR23: Crash events are logged with full error context (exit code, stderr output, timestamp)
- FR24: Log files are size-limited or rotated to prevent unbounded disk usage

### Metrics & Monitoring

- FR25: System tracks request count per MCP server
- FR26: System tracks error count per MCP server
- FR27: System tracks last request timestamp per MCP server
- FR28: System calculates uptime per MCP server from process start time

### Imagen MCP Migration

- FR29: Existing Imagen MCP server operates over SSE/HTTP transport instead of stdio
- FR30: All existing Imagen functionality (image generation, session-based refinement) works identically after transport migration
- FR31: Imagen is registered as the first managed MCP server via a config file

### Project Migration

- FR32: Project is renamed from Engagement Manager to MCP Mothership across repository, pyproject.toml, and code references
- FR33: Existing shared modules (config, errors, logging) are retained and available for MCP servers

## Non-Functional Requirements

### Reliability

- NFR1: A crash in any managed MCP server must not affect other running MCP servers or the manager process
- NFR2: Manager must detect child process termination within 5 seconds and update status accordingly
- NFR3: Manager shutdown must cleanly terminate all child MCP server processes (no orphaned processes)
- NFR4: Dashboard must remain operational and accessible even when all MCP servers are stopped or crashed

### Security

- NFR5: API keys and credentials must be stored in `.env` files only, never in MCP config YAML files or source code
- NFR6: `.env` files must be included in `.gitignore` to prevent accidental commit
- NFR7: Log output must never contain credential values, API keys, or secrets
- NFR8: Error messages surfaced to agents or the dashboard must not expose credential values

### Performance

- NFR9: Dashboard must load and display current server states within 3 seconds
- NFR10: MCP server start/stop actions from the dashboard must initiate within 1 second
- NFR11: Dashboard status updates must reflect actual server state within 5 seconds of a change
- NFR12: The manager must support 10+ registered MCP servers without degradation in dashboard responsiveness

### Integration

- NFR13: All managed MCP servers must be fully compliant with the MCP protocol specification (tools/list, tool invocation, error responses)
- NFR14: SSE/HTTP transport must work with standard MCP clients (Claude Code, Claude Desktop, and other MCP-compatible agents)
- NFR15: Existing Imagen MCP functionality must pass identical test coverage after transport migration from stdio to SSE/HTTP
