# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versioning: SemVer.
Sections: Added, Changed, Fixed, Security, Removed, Deprecated.

## [Unreleased]

### Added
- Planner stage: `packages/planning/from_graph.py` (approved graph → `JourneySpec` + `RiskInputs`), `job.plan` worker (deterministic counts, no model call, cost estimate from settings prices), plan API with segment edits (feedback rows) and Gate 2 (refuses empty plans, stale graphs, estimates above the remaining budget; transition in the same transaction).

### Fixed
- Project settings (budget cap, `gate3_auto`) were read with an unfiltered `select(Project.settings)`; in a user-scoped session RLS shows all of the user's projects, so a member of two projects could get the wrong budget. Every lookup now filters by project id (regression test added).

### Added
- M09b Product Understanding Graph: extraction contract (`packages/contracts/graph.py`), `packages/graph` (merge by type + label, code quote verification that demotes uncited rules to Questions, conflict finder citing both sources, ambiguity Questions), Analyst worker on `job.understand` through the ModelGateway (`analyst@1.0.0`), gateway wiring from settings (`MODEL_PRICE_*` required for external models), graph API with node review (feedback rows for learning) and Gate 1 approve (refuses with pending node IDs, supersedes the old version, moves the pipeline in the same transaction).

### Added
- M09a ingest: `POST /projects/{id}/sources/upload` (≤ 50 MB, type from magic bytes, sha256 dedupe), parsers for PDF (pypdf), DOCX (paragraphs + tables in order), Markdown and OpenAPI JSON/YAML (stable text rendering), content-addressed object store (`apps/api/storage.py`, S3 + in-memory), ingest worker (normalised text stored, chunks with offsets/page/line, failed files flagged with a reason, `sources_parsed` / `job_failed` transitions), Redis Streams job consumer with consumer groups, idempotent `job_key`, reclaim of failed jobs (ADR-013), `python -m apps.workers` + Compose `worker` service. Migration `0006`.

### Changed
- Job dispatch uses Redis Streams consumer groups instead of Celery (ADR-013).

### Added
- T-603: `PostgresReplayCache` (per project, first write wins, `approved_only` for zero-call regression replays, `approve()`), `PostgresRecorder` (one `model_call` row per gateway call, including cache hits and budget refusals), `project_budget()` (cap includes this month's spend from every process). Cost meter `GET /projects/{id}/costs` and `PUT /projects/{id}/budget`. Migration `0005`.

### Added
- M08c orchestrator: explicit state machine (`apps/orchestrator/machine.py`, every stage × event tested), `engine.transition` (per-project lock; state + audit + outbox in one transaction), server-side gate guards (approved graph, approved plan, no pending case, no bug draft; Gate 3 auto-skip only with `gate3_auto`), monthly budget guard for model stages, retry/cancel/restart, outbox relay to Redis streams, crash recovery that re-dispatches with the same job key and `resume_after_case_id`. `python -m apps.orchestrator` + Compose `orchestrator` service. Pipeline API (`GET /projects/{id}/pipeline`, `POST …/pipeline/events`). Migration `0004` + ADR-012 (`saq_system` role, `saq_worker` login). New permission `pipeline.manage`, setting `WORKER_DATABASE_URL`.

### Fixed
- Outbox events written in one transaction shared `now()` and could be relayed out of order; `enqueue` now stamps the wall clock.

### Added
- M08b auth + projects API: register/login/refresh/logout, `/me`, personal API tokens (`apps/api/auth/`, `routers/auth.py`); Argon2id, per-account lockout with backoff, EdDSA access JWT (15 min), rotating refresh tokens with reuse detection, CSRF double-submit, security headers. RBAC matrix (docs/10 §4) + `require()` (404 for non-members, 403 with the missing permission). Projects, members, sources (+ chunks), environments (production needs Owner), write-only identities, audit with `?verify=true` (`routers/projects.py`). Error envelope and prefixed IDs for every route. Migration `0003` (`auth_session`, `api_token`, lockout columns). New setting `JWT_PRIVATE_KEY`.

### Added
- M08a database: SQLAlchemy 2 models for all 30 tables in docs/07 (`apps/api/db/models/`), Alembic migrations `0001` (schema) and `0002` (grants, forced row-level security, audit hash-chain and append-only triggers, HNSW indexes). Composite `(id, project_id)` foreign keys block cross-project links (ADR-011). `apps/api/db/session.py` (transaction-local project scope), `audit.py` (`record`, `verify_chain`), `outbox.py` (`enqueue`, `claim_unpublished`, `mark_published`). 26 new tests (21 integration on a throwaway `saq_test` DB), 100% coverage.

### Changed
- Postgres roles: Compose now runs as owner `saq_migrator` and creates runtime role `saq_app` (not superuser) via `deploy/postgres/init/01-roles.sql`; new `MIGRATION_DATABASE_URL`. Old dev volumes need `docker compose down -v` once. The `user` table is named `app_user` (`user` is reserved in PostgreSQL).

### Fixed
- Local dev S3: the `minio/minio` image is no longer published on Docker Hub or quay.io; Compose now runs SeaweedFS 4.00 (`s3` service, port 8333, keys in `deploy/seaweedfs/s3.json`). Verified with boto3: bucket create, put, head, get (hash match), list, presigned GET, wrong-key rejection (ADR-010).
- Removed the Starlette TestClient warning filter (T-007): the official SDK brings `httpx2`, so tests run with warnings as errors and no exceptions.
- CI `web`: pnpm 12 fails on unapproved build scripts in CI; esbuild's build is now approved in `apps/web/pnpm-workspace.yaml`.
- CI `secrets`: `.gitleaks.toml` keeps default rules and allowlists only the fake secret-shaped redaction-test fixtures.

### Added
- T-602 local model: `LocalProvider` for OpenAI-compatible local servers (Ollama, llama.cpp, vLLM, LM Studio) and `build_provider()` that enforces the `local-only` policy in code (no Claude provider, internal hosts only). New settings `LOCAL_MODEL_URL`, `LOCAL_MODEL_NAME`.
- M06 model gateway: `packages/model_gateway` with the Claude adapter (official `anthropic` SDK 2.x; structured JSON output, explicit effort, prompt caching of stable context, server-side refusal fallbacks), redaction of PII/secrets, untrusted-data wrapping, replay cache, cost accounting, budget pre-check, schema validation with up to 2 retries. 100% branch coverage.
- M04 planning: `packages/contracts/plan.py` and `packages/planning` (`technique_rows`, `risk_score`, `priority_for`, `suggest_segment`, `estimate_design_cost`). Counts are deterministic code with a reason per technique; risk multiplier 0.7-1.5; Must/Should/Could; cost estimate with budget check. 100% branch coverage.
- M02 citations: `packages/contracts/citation.py` (`Citation`, `Chunk`, `Location`), `packages/citations` with `normalize_text`, `chunk_pages` (offsets, page, line) and `verify_quote` / `verify_citation` (exact match after normalisation, offset correction, short-quote rejection). 100% branch coverage.
- M01 foundation: repo skeleton (apps/, packages/, evals/ with READMEs), uv/ruff/mypy/pytest config, FastAPI app with `/api/v1/healthz` and `/api/v1/readyz`, Docker Compose (Postgres+pgvector, Redis, MinIO, API), CI (python, web, gitleaks), pre-commit, Makefile, `.env.example`.
- Web scaffold: React 18 + TypeScript + Vite, design tokens, `VerdictBadge` with tests.
- `CONTRIBUTING.md` and `stuti.md` contributor guide (fork, setup, workflow, module plan, testing and documentation plan).
- Engineering documentation set (`docs/`), sector workflows, bug-triage map.
- Frontend design system "Verified Indigo" (tokens in `05-frontend-ui-design.md`).

## [0.0.0] - 2026-10-07
### Added
- Project proposal, gap analysis, market comparison workbook (research phase).
