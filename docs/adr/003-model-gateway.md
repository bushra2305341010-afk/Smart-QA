# ADR-003: All model calls through one Model Gateway

**Status:** Accepted · **Date:** 2026-11-16

## Context
Need provider choice (Claude, local), caching, cost caps, redaction and replay in one place.

## Decision
Every LLM call goes through packages/model_gateway with a ModelProvider protocol.

## Consequences
Swap providers without touching workers; single point for budgets and privacy.

## Alternatives considered
Calling SDKs directly from workers.
