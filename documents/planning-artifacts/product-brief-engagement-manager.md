---
title: "Product Brief: Engagement Manager"
status: "complete"
created: "2026-03-29"
updated: "2026-03-29"
inputs: ["user conversation", "API research"]
---

# Product Brief: Engagement Manager

## Executive Summary

Engagement Manager is an open-source personal brand content engine — a composable ecosystem of AI agents, MCP servers, and skills that automate the end-to-end social engagement workflow. From researching a topic, to generating platform-specific posts, to creating images, to publishing — each capability is a small, focused building block that any MCP-compatible tool (Claude Code, Copilot, etc.) can use.

This is a utility toolkit, not a SaaS product. Built for personal use first, designed to be shared.

## The Problem

Managing a personal brand across multiple platforms is a grind. You research a topic, write a post, adapt it for LinkedIn (in multiple formats), create a matching image, publish to WordPress, cross-post to other platforms — all manually, all context-switching between tools. Each step breaks your flow.

AI tools exist for individual pieces, but they're fragmented: one tool for writing, another for images, another for scheduling. None of them chain together. You end up being the orchestrator, copying and pasting between disconnected services.

## The Solution

A modular ecosystem where:

- **MCP servers** provide tool integrations — image generation, WordPress publishing, platform APIs. Portable across any AI-powered IDE or agent.
- **Skills** provide workflow orchestration — post generation logic, LinkedIn format templates, content pipelines. The brains that chain the tools together.
- **Agents** (like the existing Analyst) bring domain expertise and decision-making to the workflow.

Each piece is independently useful. Together, they form a content pipeline: research → generate → image → publish.

## Architecture

| Layer | Role | Examples |
|-------|------|----------|
| **MCP Servers** | Tool access, portable, least-privilege | Imagen (image gen), WordPress |
| **Skills** | Workflow orchestration, prompt logic | Post generator, LinkedIn post types (5-6 formats), content repurposer |
| **Agents** | Domain expertise, decision-making | Analyst (research), content strategist |

Each skill declares which MCPs it needs — agents only access what they should.

## Who This Serves

**Primary:** Kamal — personal brand content creation and publishing across LinkedIn, WordPress, and future platforms (X, Threads, Substack).

**Secondary:** Other content creators and solopreneurs who want an open-source, composable AI content engine they can fork and adapt.

## Scope

**v1 Workflows:**
1. Image creation (Google Imagen MCP) ← **first piece to build**
2. WordPress publishing (existing MCP adapter available)
3. Topic research (agent/skill)
4. Post generator (skill)
5. LinkedIn post creator — 5-6 format types (skill)

**Platforms — v1:** LinkedIn (manual copy/paste), WordPress (MCP)
**Platforms — Future:** LinkedIn API, X/Twitter, Threads, Substack

**Out of v1:** Platform API integrations (LinkedIn, X, Threads), scheduling/queue, analytics, multi-user support

## First Deliverable

**Google Imagen MCP Server** — accepts a text prompt, calls Vertex AI Imagen API, stores the image locally, returns the file path. One tool, one job. Any agent or IDE with MCP access can generate images on demand.

Prerequisites: GCP account with Vertex AI enabled.

## Vision

A toolkit where spinning up a new platform or content format means adding one MCP or one skill — not rebuilding the pipeline. The ecosystem grows one small, composable piece at a time, each independently useful, all shareable.
