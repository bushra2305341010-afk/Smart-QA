# ADR-005: Citation format and code-level quote verification

**Status:** Accepted · **Date:** 2026-11-16

## Context
Expected results must be trustworthy; models can hallucinate citations.

## Decision
Store source_id, start_offset, end_offset, quote; verify by exact string comparison in packages/citations.

## Consequences
Deterministic trust check independent of the model. Normalisation must match ingest.

## Alternatives considered
Trusting the model's citation output alone.
