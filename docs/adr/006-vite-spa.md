# ADR-006: React + Vite SPA instead of Next.js

**Status:** Accepted · **Date:** 2026-11-16

## Context
The UI is behind login; SEO and SSR bring no value; simpler deploy is preferred.

## Decision
Build apps/web as a Vite SPA served by nginx, talking to the FastAPI API.

## Consequences
Simpler build and hosting; no server rendering.

## Alternatives considered
Next.js (proposal v0).
