# ADR-009: Self-learning stays inside the company deployment

**Status:** Accepted · **Date:** 2026-11-16

## Context
The system must improve from its own testing while keeping company data private.

## Decision
Learn via memory, lessons and small trained models on human-confirmed labels only, stored in the company DB; promote only through an eval gate; no cross-company learning.

## Consequences
Improves over time with full data control; requires label discipline and eval sets.

## Alternatives considered
Central cloud training on pooled customer data.
