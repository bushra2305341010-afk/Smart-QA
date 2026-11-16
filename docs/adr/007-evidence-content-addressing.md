# ADR-007: Evidence stored content-addressed by SHA-256

**Status:** Accepted · **Date:** 2026-11-16

## Context
Evidence must be tamper-evident and deduplicated.

## Decision
Object key = sha256 of content; hash stored in DB and verified on read.

## Consequences
Tampering detectable; identical screenshots stored once.

## Alternatives considered
Random object keys.
