# ADR-011: Project isolation with row-level security, composite foreign keys and two DB roles

**Status:** Accepted · **Date:** 2026-11-20

## Context
Every table except users belongs to one project, and data from one project must never be visible to, or linked from, another (docs/07 §4, sector 10 "Data from another project visible" = Critical). Row-level security (RLS) filters reads and writes, but PostgreSQL checks foreign keys **without** RLS, so a row in project B could still reference a row id from project A. RLS is also bypassed by superusers, and the dev Compose stack ran the app as the superuser `saq_app`.

## Decision
1. **Two roles.** `saq_migrator` (owner, runs Alembic) and `saq_app` (runtime: DML only, no DDL, not superuser, no BYPASSRLS). Compose creates `saq_app` in `deploy/postgres/init/01-roles.sql`; migration 0002 creates it `NOLOGIN` if missing (CI) and grants table rights.
2. **RLS on every project table, forced.** Policy `project_isolation`: `project_id = app_current_project()`, which reads the transaction-local setting `app.project_id` (set by `apps/api/db/session.py:set_scope`). `project` and `membership` also allow rows of the signed-in user's projects via `app.user_id`, for "my projects" lists.
3. **Composite foreign keys.** Every reference between project tables is `(ref_id, project_id) -> (id, project_id)`, so a cross-project link is rejected by the schema itself. A unit test asserts this for every FK.
4. **Audit ledger outside the cascade.** `audit_event.project_id` has no FK so the ledger survives project deletion (docs/07 §7); the hash chain is computed by a `SECURITY DEFINER` trigger, and updates/deletes/truncates are revoked and rejected by trigger.
5. **Synchronous SQLAlchemy 2 + psycopg 3** for now (workers and orchestrator are synchronous; FastAPI runs sync dependencies in its thread pool). Revisit if API latency needs async.
6. **Text + CHECK instead of PostgreSQL enum types**, so values can be added in an ordinary expand migration.

## Consequences
- Isolation holds even if application code forgets a `WHERE project_id = ...`.
- Settings are `is_local`, so a pooled connection never carries one request's project into the next.
- Background jobs that must read across projects (outbox relay, nightly learning) need an explicit scope per project or a dedicated BYPASSRLS role; M08c decides.
- Existing dev volumes created before this ADR have `saq_app` as the bootstrap superuser, which cannot be demoted: recreate the volume once (`docker compose down -v`).

## Alternatives considered
- Schema- or database-per-project: stronger walls but heavy migrations and pooling for a 12-week MVP.
- App-side filtering only: one missed filter leaks data.
