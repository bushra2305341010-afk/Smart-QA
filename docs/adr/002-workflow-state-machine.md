# ADR-002: Explicit workflow state machine with gates, not a free agent or LangGraph

**Status:** Accepted · **Date:** 2026-11-16

## Context
Stages have different inputs and failure modes; humans must approve at gates; runs must resume after a crash and be auditable.

## Decision
Implement an explicit state machine stored in PostgreSQL (pipeline_state), driving Celery jobs. Only Explorer and Healer run bounded tool loops.

## Consequences
Deterministic, testable transitions, easy resume and audit. More code than a framework.

## Alternatives considered
LangGraph (proposal v0): extra dependency, harder to persist and audit our own gate semantics.
