# ADR-008: Hash-chained audit ledger in PostgreSQL

**Status:** Accepted · **Date:** 2026-11-16

## Context
Approvals, verdicts and filings must be non-repudiable for audits.

## Decision
audit_event rows carry prev_hash and hash = sha256(prev_hash || canonical_json(row)); app role cannot UPDATE/DELETE.

## Consequences
Tamper-evident history; verify job needed.

## Alternatives considered
External ledger service (more ops).
