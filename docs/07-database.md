# 07 · Database

PostgreSQL 16 + pgvector · migrations with Alembic · evidence blobs in S3-compatible storage (SeaweedFS locally), only metadata in Postgres.

## 1. ER diagram

```mermaid
erDiagram
    APP_USER ||--o{ MEMBERSHIP : has
    PROJECT ||--o{ MEMBERSHIP : has
    PROJECT ||--o{ SOURCE : has
    PROJECT ||--o{ ENVIRONMENT : has
    PROJECT ||--o{ IDENTITY : has
    SOURCE ||--o{ CHUNK : split_into
    PROJECT ||--o{ GRAPH_VERSION : has
    GRAPH_VERSION ||--o{ NODE : contains
    NODE ||--o{ EDGE : from
    NODE ||--o{ NODE_CITATION : cited_by
    CHUNK ||--o{ NODE_CITATION : cites
    PROJECT ||--o{ PLAN : has
    PLAN ||--o{ SEGMENT : contains
    SEGMENT ||--o{ TEST_CASE : contains
    TEST_CASE ||--o{ STEP : has
    PROJECT ||--o{ RUN : has
    RUN ||--o{ RESULT : produces
    RESULT ||--o{ EVIDENCE : has
    RESULT ||--o| VERDICT : judged_as
    VERDICT ||--o| BUG : may_create
    PROJECT ||--o{ AUDIT_EVENT : logs
    PROJECT ||--o{ MODEL_CALL : bills
```

## 2. Tables (key columns)

Every table has `id`, `project_id` (except `app_user`), `created_at`, `updated_at`. Models: `apps/api/db/models/` (SQLAlchemy 2, typed). Status/kind columns are text + CHECK (not PG enums) so values can be added in an expand migration. References between project tables are composite `(ref_id, project_id)` foreign keys (ADR-011).

| Table | Key columns | Notes |
|---|---|---|
| `app_user` | email (unique, citext), password_hash (argon2id), totp_secret_enc, status, failed_logins, locked_until | |
| `auth_session` | user_id, family_id, refresh_hash (unique), expires_at, rotated_at, revoked_at, user_agent, ip | global (no RLS); one row per refresh token, rotation = new row in the family |
| `api_token` | user_id, name, token_hash (unique), scopes text[], expires_at, last_used_at, revoked_at | global (no RLS); `saq_pat_…`, hash only |
| `membership` | user_id, project_id, role (enum) | unique (user, project) |
| `project` | name, owner_id, model_policy jsonb, settings jsonb, retention_days | |
| `environment` | name, kind (local/staging/public/production), base_url, allowed_hosts[], safe_actions jsonb, runner_id | production blocked by default |
| `identity` | env_id, role_name, secret_ref | value lives in vault, never in this row |
| `source` | kind (pdf/docx/md/openapi/repo/har), uri, sha256, status | |
| `chunk` | source_id, text, start_offset, end_offset, page, line, embedding vector(1024) | HNSW index on embedding |
| `graph_version` | number, status (draft/approved/superseded), approved_by, approved_at | |
| `node` | graph_version_id, type (Role, Journey, Step, Screen, Field, Rule, Endpoint, Requirement, Conflict, Question), label, attrs jsonb, review_status | |
| `edge` | from_node, to_node, kind | |
| `node_citation` | node_id, chunk_id, start_offset, end_offset, quote, status | |
| `plan` | graph_version_id, status, cost_estimate jsonb, approved_by | |
| `segment` | plan_id, journey_node_id, techniques jsonb, suggested_count, approved_count, risk_score, priority | |
| `test_case` | segment_id, code (TC-CHK-007), role, technique, priority, preconditions jsonb, data jsonb, expected_text, citation jsonb, requirement_id, review_status, compiled_path | |
| `step` | test_case_id, n, action, node_id | |
| `run` | env_id, plan_id, status, started_at, finished_at, last_completed_case_id, totals jsonb | resume point (NFR-4) |
| `result` | run_id, test_case_id, attempt, status, duration_ms, browser | |
| `evidence` | result_id, step_n, kind (screenshot/trace/video/har/console/request), sha256, object_key, size | |
| `verdict` | result_id, verdict (enum), confidence, reason, rule | |
| `bug` | verdict_id, title, severity, body_md, status (draft/confirmed/dismissed/filed), tracker, tracker_ref, dedup_of | |
| `regression_memory` | journey_node_id, last_pass_at, flake_rate, bugs_found | |
| `project_rule` | kind, condition jsonb, action jsonb, source (human decision id) | v1 learning |
| `audit_event` | seq, actor, action, entity, payload jsonb, prev_hash, hash | append-only; no FK to `project` (kept after project delete) |
| `model_call` | stage, model, prompt_version, status, attempts, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cost_usd, latency_ms, from_cache, redactions, run_id | written by `PostgresRecorder` (T-603) |
| `replay_cache` | key (sha256 of model+prompt_version+inputs), output jsonb, approved | unique (project, key); first write wins; `approved_only` mode serves human-approved outputs only (`PostgresReplayCache`) |
| `pipeline_state` | run_id?, stage, status, payload_ref | |
| `feedback` | entity, entity_id, decision (confirm/reject/edit/heal_approve), before jsonb, after jsonb, actor | Human-confirmed labels: the only training data |
| `lesson` | kind, text, applies_to_node_id, source_feedback_id, embedding vector(1024), active | L2 in-context learning |
| `trained_model` | component (flake/risk/calibration/locator/dedup), version, data_snapshot_hash, metrics jsonb, status (candidate/active/retired), artifact_key | L3 model registry; artifact in company object storage |
| `outbox` | topic, payload, published_at | reliable events |

## 3. How data moves (lifecycle)

1. **Ingest** writes `source` → parser writes `chunk` (+ embedding).
2. **Understand** writes a new `graph_version` (draft) + `node`, `edge`, `node_citation`.
3. **Gate 1** flips `graph_version.status = approved`; previous approved → `superseded`.
4. **Plan** writes `plan` + `segment`; **Gate 2** sets `approved_count`, `plan.status`.
5. **Design** writes `test_case` + `step`; quote check sets `citation.status`.
6. **Run** writes `run`, then one `result` per attempt, `evidence` per step; updates `run.last_completed_case_id` after each case.
7. **Judge** writes `verdict`; Reporter writes `bug` drafts.
8. **Gate 4** sets `bug.status = confirmed`, tracker adapter sets `filed` + `tracker_ref`.
9. Every gate and filing appends `audit_event`.

## 4. Isolation & security

- **Row-level security** (enabled and forced) on every table except `app_user`, policy `project_isolation`: `project_id = app_current_project()`. `app_current_project()` / `app_current_user()` read the transaction-local settings `app.project_id` / `app.user_id`, set by `apps/api/db/session.py` (`project_session`, `set_scope`). No scope set → no rows. `project` and `membership` also show the signed-in user's own projects (`app.user_id`).
- **Composite foreign keys** `(ref_id, project_id) -> (id, project_id)`: Postgres checks FKs without RLS, so this is what stops a row in project B pointing at project A (ADR-011).
- **Roles:** app connects as `saq_app` (DML only, no DDL, not superuser). Background processes log in as `saq_worker` (member of `saq_system`, ADR-012). Migrations run as `saq_migrator` (`MIGRATION_DATABASE_URL`). Compose creates `saq_app` in `deploy/postgres/init/01-roles.sql`.
- `audit_event`: only `SELECT, INSERT` granted to `saq_app`; a trigger also rejects UPDATE/DELETE/TRUNCATE for every role. The `audit_event_chain` trigger (SECURITY DEFINER, per-project advisory lock) sets `seq`, `prev_hash` (genesis = 64 zeros), `created_at` and
  `hash = sha256(prev_hash|project_id|seq|actor|action|entity|payload::text|created_at UTC with µs)`. Client values for these columns are ignored. `apps/api/db/audit.py:verify_chain` recomputes the chain in Python and reports the first broken `seq` (edited row, broken link or gap).
- `outbox`: `apps/api/db/outbox.py` — `enqueue` in the domain transaction; the relay uses `claim_unpublished` (`FOR UPDATE SKIP LOCKED`) and `mark_published`.
- Secrets (`totp_secret_enc`, tracker tokens) encrypted with AES-256-GCM, key from env / KMS.

## 5. Indexes

| Index | Why |
|---|---|
| `chunk USING hnsw (embedding vector_cosine_ops)` | Retrieval for Analyst/Designer |
| `chunk (source_id, start_offset)` | Quote verification lookups |
| `node (graph_version_id, type)` | Graph screen |
| `test_case (segment_id, review_status)` | Case review queue |
| `result (run_id, test_case_id, attempt)` unique | Idempotent result writes |
| `evidence (sha256)` | Dedup |
| `audit_event (project_id, seq)` unique | Chain order |
| `model_call (project_id, created_at)` | Cost reports |

## 6. Migrations

- Location `apps/api/alembic/` (config `alembic.ini`), run `uv run alembic upgrade head` with `MIGRATION_DATABASE_URL` set. `0001` = tables (autogenerated, reviewed), `0002` = security layer (grants, RLS, audit triggers, HNSW indexes; hand-written), `0003` = auth sessions, API tokens, lockout columns, `0005` = `model_call` details (status, attempts, cache hit, cache-write tokens, redactions), `0004` = `saq_system` role + `system_access` policies on `outbox`, `pipeline_state`, `run` (ADR-012).
- `uv run alembic check` must report no drift; the integration suite runs downgrade → upgrade → check on a throwaway `saq_test` database (never the dev DB).

- `alembic revision --autogenerate -m "add regression_memory"` → review the file by hand.
- Expand → migrate → contract: add column nullable, backfill, then make NOT NULL in a later release. Never rename in one step.
- Each migration has a `downgrade()` and is tested in CI against a snapshot of golden-project data.

## 7. Backup & retention

| Item | Policy |
|---|---|
| Postgres | Nightly `pg_dump` (laptop), WAL archiving + PITR (team mode) |
| Evidence | Retention per project (default 90 days); lifecycle rule deletes objects; audit keeps hashes |
| Restore test | Monthly restore into a scratch DB + `audit verify` |
| Project delete | Deletes rows (cascade) and evidence objects; audit event kept with hashes only |

## 8. Useful queries

```sql
-- requirement coverage for latest run
SELECT n.label AS requirement, count(tc.id) AS cases,
       count(*) FILTER (WHERE v.verdict='pass') AS passed
FROM node n
LEFT JOIN test_case tc ON tc.requirement_id = n.attrs->>'req_id'
LEFT JOIN result r ON r.test_case_id = tc.id AND r.run_id = :run
LEFT JOIN verdict v ON v.result_id = r.id
WHERE n.type='Requirement' AND n.graph_version_id = :gv
GROUP BY n.label;

-- where did the money go?
SELECT stage, sum(cost_usd) FROM model_call WHERE run_id=:run GROUP BY stage ORDER BY 2 DESC;
```
