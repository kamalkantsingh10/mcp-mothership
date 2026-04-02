---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-01b-continue', 'step-03-success-skipped', 'step-04-journeys', 'step-05-domain-skipped', 'step-06-innovation-skipped', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish', 'step-12-complete']
inputDocuments: ['documents/planning-artifacts/product-brief-engagement-manager.md']
workflowType: 'prd'
documentCounts:
  briefs: 1
  research: 0
  brainstorming: 0
  projectDocs: 0
classification:
  projectType: developer_tool
  domain: general
  complexity: low
  projectContext: greenfield
---

# Product Requirements Document - Engagement Manager

**Author:** Kamal
**Date:** 2026-03-29

## Executive Summary

Engagement Manager is a composable, open-source toolkit for personal brand content creation. Built as an ecosystem of MCP servers, skills, and AI agents, it provides building blocks for a complete content pipeline — from topic research to post generation to image creation to publishing — accessible from Claude Code.

The system is a creative amplifier, not an automation platform. The user maintains full authority at every step: the system proposes, the user decides. Every output reflects the creator's voice, image, and perspective. Nothing publishes without approval.

The first deliverable is a Google Imagen MCP server for AI image generation. The ecosystem grows one composable piece at a time: topic research, post generation, LinkedIn post formatting (5-6 content types), and WordPress publishing. LinkedIn publishing is manual copy/paste in v1; platform API integrations come later.

### What Makes This Special

Engagement Manager lives where the creator already works (IDE/CLI), not in another SaaS dashboard. Each piece — MCP server, skill, agent — works independently and chains together. The architecture enforces least-privilege access: each skill only connects to the MCPs it needs. Built for one person's personal brand first, designed to be forked and adapted by others.

## Success Criteria

### MVP Success (Phase 1: Imagen MCP Server)

- SC1: User can invoke the image generation tool from Claude Code and receive a locally saved image file
- SC2: Configuration validation catches and reports all missing or invalid settings before any API call is attempted
- SC3: Zero credential values appear in any log output, error message, or system response
- SC4: Image generation completes without the system imposing a timeout — the user receives either an image or an actionable error
- SC5: A developer can add a new MCP server to the project by following the established patterns without modifying existing shared modules

### Full Vision Success (Post-MVP)

- SC6: End-to-end content workflow (research → draft → image → publish-ready) completes within 30 minutes for a standard post
- SC7: Each new capability (research agent, post generator, LinkedIn formats, WordPress publishing) ships as an independent composable piece

## Project Classification

- **Project Type:** Developer Tool (MCP servers + skills ecosystem)
- **Domain:** General (content/social media)
- **Complexity:** Low (personal utility, no regulatory concerns)
- **Project Context:** Greenfield

## User Journeys

### Journey 1: Kamal — The Analysis Post (Primary Success Path)

Kamal has been thinking about how GitHub Copilot alone doesn't improve end-to-end development output. He's got a strong opinion and 30 minutes before his next meeting.

He opens Claude Code and tells Engagement Manager: "Analysis post — my take is that just using Copilot doesn't improve end-to-end dev output." The Analyst agent kicks in — pulls research papers, credible publications, poll data, industry stats. Comes back with a structured brief: supporting evidence, counterarguments, key data points.

Kamal scans it — "good, but find something on actual productivity metrics, not just adoption rates." Back-and-forth. Analyst refines. Once the research feels solid, the post generator drafts an analysis post in his voice.

He reads it. "Opening is too soft, make it provocative." Another round. Now it lands. Imagen generates an infographic — key stats visualized. He tweaks the prompt: "emphasize the gap between adoption and output." New graphic. Better.

Post is ready. He copies it, drops it into LinkedIn, schedules it. Done. 28 minutes.

### Journey 2: Kamal — The Iterative Edit Loop (Edge Case / Deeper Collaboration)

Sometimes the first research pass misses the mark entirely. Kamal says "this angle is wrong — I'm not arguing Copilot is bad, I'm arguing it's insufficient without process changes." The Analyst pivots. The post gets regenerated with a different framing. The infographic needs a complete redo. Three rounds of back-and-forth before it clicks.

This journey highlights that the system must support mid-stream direction changes without losing prior context or starting from scratch.

### Journey Requirements Summary

**MVP (Phase 1):**
- **Image generation** — infographics tied to post content, prompt-refinable

**Post-MVP (Full Vision):**
- **Idea intake** — conversational, no forms or templates
- **Deep research** — credible sources only (papers, publications, polls)
- **Iterative collaboration** — back-and-forth on research, post content, and image generation
- **Context persistence** — direction changes mid-flow don't reset the session
- **Post generation** — voice-aware, perspective-first, not generic AI content
- **Manual publish** — copy-ready output, no platform integration in v1
- **Speed target** — 30 minutes end-to-end for a standard post (see SC6)

## Developer Tool Specific Requirements

### Project-Type Overview

Python-based developer tool built as an ecosystem of stdio MCP servers, skills, and AI agents. All components run locally via Claude Code — no web servers, no package distribution, no multi-IDE support in v1.

### Technical Architecture Considerations

- **MCP Transport:** stdio (local process communication, no HTTP/SSE)
- **Language:** Python for all MCP servers
- **Host Environment:** Claude Code as the sole MCP client
- **Distribution:** Runs directly from the repository — no pip package, no npm, no Docker
- **Configuration:** YAML config files for settings, .env for credentials, MCP server declarations in Claude Code config

### Language & Runtime Requirements

- Python 3.x (specific version TBD during architecture)
- Dependencies managed via pip/requirements.txt or pyproject.toml
- Pure Python — no compiled extensions

### Implementation Considerations

- Each MCP server is a standalone Python process communicating via stdio
- Skills are Claude Code skill files (markdown-based prompt workflows)
- Agents orchestrate skills and MCP tools within Claude Code sessions
- Least-privilege: each skill declares only the MCP tools it needs
- Documentation lives in `documents/`

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Ship the smallest composable piece that delivers standalone value and validates the MCP-based architecture.

### MVP Feature Set (Phase 1): Google Imagen MCP Server

- Single stdio MCP server in Python
- Accepts a text prompt, calls Vertex AI Imagen API
- Stores generated image locally, returns the file path
- Prerequisite: GCP account with Vertex AI enabled

### Post-MVP Features

**Phase 2 (TBD):** Content pipeline direction — Analyst agent for deep research, post generator skills, LinkedIn post types. Details to be defined after MVP validation.

**Phase 3 (TBD):** Publishing & expansion direction — WordPress publishing, LinkedIn API integration, additional platforms. Details to be defined.

### Risk Mitigation Strategy

**Technical Risks:** Vertex AI Imagen API availability and rate limits — mitigated by keeping the server simple with clear error reporting.
**Resource Risks:** Solo developer — mitigated by composable architecture where each piece is small and independent.

## Functional Requirements

### Image Generation

- FR1: User can submit a text prompt to generate an image via the Imagen MCP tool
- FR2: User can specify image dimensions (width/height) when generating an image
- FR3: User can specify an output style or artistic direction for the generated image
- FR4: User can specify a custom output location for the generated image
- FR5: System generates a single image per prompt request
- FR6: System stores the generated image locally and returns the file path to the user

### Configuration

- FR7: User can configure MCP server settings via a YAML configuration file
- FR8: User can configure sensitive credentials (API keys, GCP project) via environment variables (.env)
- FR9: System validates configuration on startup and reports missing or invalid settings

### Error Reporting

- FR10: System reports an actionable error message when the image generation API is unavailable or returns an error — message includes an error category, human-readable description, and suggested resolution; message never includes credential values
- FR11: System reports an actionable error message when credentials are missing or invalid — message identifies the specific missing or invalid credential by name without revealing its value
- FR12: System reports an actionable error message when image generation fails (bad prompt, quota exceeded, etc.) — message includes the failure reason from the API and a suggested resolution

## Non-Functional Requirements

### Security

- NFR1: Credentials must never appear in version-controlled files — verified by ensuring no API keys, tokens, or secrets exist in any committed file
- NFR2: Credential files must be excluded from version control — verified by the presence of `.env` in `.gitignore` and absence of credential files in the repository
- NFR3: Credentials must never appear in system output — verified by confirming no log entries, error messages, or tool responses contain credential values

### Integration

- NFR4: The system must use a single image generation backend — verified by confirming all image generation requests route through one API provider
- NFR5: The system must not impose a timeout on image generation — the user waits for the API response; if the API fails, an actionable error is returned
- NFR6: API error responses must be surfaced to the user without exposing credentials — verified by confirming error messages contain the API error reason but no credential values
