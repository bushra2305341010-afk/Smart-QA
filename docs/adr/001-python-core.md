# ADR-001: Python core, TypeScript only for the web UI

**Status:** Accepted · **Date:** 2026-11-16

## Context
The team's background is data science; the AI, runner (Playwright), data and Excel tooling are strongest in Python.

## Decision
Use Python 3.12 for API, orchestrator, workers, runner, CLI and MCP. Use TypeScript only in apps/web.

## Consequences
One language for most code and tests. Two toolchains overall (uv + pnpm).

## Alternatives considered
Node.js everywhere (weaker data/ML ecosystem); Java (slower iteration).
