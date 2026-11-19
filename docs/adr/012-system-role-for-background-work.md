# ADR-012: A system role with narrow RLS policies for cross-project background work

**Status:** Accepted · **Date:** 2026-11-20

## Context
The outbox relay and crash recovery must see every project's unpublished events and stalled pipelines, but row-level security (ADR-011) shows nothing without a project scope. Options: BYPASSRLS, SECURITY DEFINER functions, or per-role policies. FORCE RLS applies to the table owner too, and BYPASSRLS needs a superuser to grant, which a company's managed Postgres may not allow.

## Decision
Role `saq_system` (NOLOGIN) inherits `saq_app` and gets permissive policies `system_access TO saq_system` only on: `outbox` (all), `pipeline_state` (select), `run` (select). The login `saq_worker` (Compose: `deploy/postgres/init/01-roles.sql`, setting `WORKER_DATABASE_URL`) is granted `saq_system` by migration 0004. Every write the system does to other tables (audit, re-dispatched jobs) goes through a normal project scope.

## Consequences
- Background processes can scan exactly what they need, nothing more; no superuser or BYPASSRLS anywhere.
- Adding a new cross-project job means adding a named policy in a migration (reviewable).

## Alternatives considered
BYPASSRLS role (too broad, needs superuser); SECURITY DEFINER functions (owner is subject to FORCE RLS unless superuser).
