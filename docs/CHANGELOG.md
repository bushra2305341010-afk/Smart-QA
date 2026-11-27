# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versioning: SemVer.
Sections: Added, Changed, Fixed, Security, Removed, Deprecated.

## [Unreleased]

### Security
- T-203 identity vault: test logins live only on the runner, in an AES-256-GCM encrypted file (`SAQ_VAULT_FILE`, key or scrypt passphrase in `SAQ_VAULT_KEY`; atomic 0600 writes; wrong key or tampering fails closed). `saq vault keygen|set|list|rm` (values never printed). The API now accepts only references for identities (`vault:<name>` or `env:<name>`), so a pasted password is refused.
- M03 safe-action policy (`packages/policy`, N18): the runner checks every action before it runs. Blocks delete/remove/close-account (text, aria-label, accessible name, title, routes, HTTP DELETE), payments (unless `payments: "test"`; real-looking card numbers always), money transfers (never relaxable), email/SMS/invites (unless `mail_sink`), off-domain URLs (host allow-list with wildcards and ports; `javascript:`/`data:`/`file:` refused) and uploads outside `evals/fixtures`. Production environments are blocked unless `allow_production`. 100% branch coverage.

### Fixed
- API docs page (`/api/v1/docs`) was blank: the strict Content-Security-Policy blocked Swagger UI's CDN script and inline start-up script. Only the docs page now allows them. `/` and `/docs` redirect to it, and the page has an "Authorize" dialog (CSRF token after login, or an API token).

### Changed
- Designer prompts carry only the segment's journey neighbourhood of the approved graph (`packages/graph/scope.py`) instead of the whole graph: smaller, cheaper prompts on big products; unlinked rules are always included.

### Added
- Runs API and live events (M12): `POST /projects/{id}/runs` (regression run of approved cases once the pipeline is done: new `run_requested` transition DONE → COMPILE, `run.start` + Gate-3 precondition; optional `env_id` and `journeys`), `GET /runs`, `GET /runs/{run}` (per-case latest attempt, verdict, rule, confidence level, failure, evidence), `GET /evidence/{sha256}`, `GET /cases/{tc}/compiled.py` (the generated Playwright file), `GET /events` (SSE `pipeline` / `run` snapshots + pings). MCP `get_verdicts` (SUT text wrapped as untrusted) and `run_journeys` (refused unless `settings.mcp.allow_runs`). CLI `saq run [--journey] [--env] [--wait]` (exit 1 on Fail / Test Error) and `saq verdicts`.
- M10b Judge worker (`job.judge`, US-07): applies the M05 rules per case, queues a clean re-run (attempt 2) for first failures and sends the pipeline back to Execute, then writes one verdict per case with its rule id, reason and confidence, drafts bugs for Fail verdicts (learned suppressions apply) and moves to Gate 4. `verdict.rule` is now NOT NULL (migration `0010`). Flake eval `python -m evals.run_flake_eval` on a 35-pair seed set: 91.4% accuracy, 0% false-bug rate (target ≥ 85%).
- M10 runner (F15, F21, N18, N19) + T-103: runner registration (`POST /projects/{id}/runners`, token shown once, optional client-certificate pin `cert_sha256` checked against the proxy's `X-Client-Cert-Sha256`), runner protocol (`/runner/heartbeat`, `/runner/jobs/pull` lease, `PUT /runner/evidence/{sha256}` hash-checked, `/runner/jobs/{id}/result` idempotent), `job.execute` scheduler (one job per compiled case; not-compiled cases → error result), lease expiry and re-lease (killed runner), and the runner process `apps/runner` (fresh context + trace per job, policy check on the live element and every request, CAPTCHA/MFA/bot/login/env-down detectors, screenshot per step, secrets resolved and masked on the runner). Migration `0009` (`runner`, `runner_job`, `result.details`). Playwright Python dependency; CI installs Chromium for `-m browser` tests.
- Compiler (F20, M10a): `job.compile` turns Gate-3 approved cases into plan-locked typed actions (`compiled/<case>.json`, what the runner executes) and a readable Playwright test file (`compiled/<case>.py`, `test_case.compiled_path`), then creates the `run` row and moves to execute. A deterministic step grammar (`packages/compiler`) handles the Designer's phrasing; the model is asked only for steps the grammar cannot map and may not change the others. Secrets stay `{{secret:name}}` and are read from the environment by generated code; imports are allow-listed. Target environment: `settings.default_env_id`, else the first non-production environment.
- M05 verdict rules (`packages/verdicts`, N20/F22/F23): `decide(first, rerun, citation_verified)` applies J0-J7 in a fixed guard order (Blocked, Test Error, missing quote, then pass/fail/flaky) and stores the deciding rule id; a Pass without a verified quote and a checked expectation is impossible (exhaustive grid test). Flake features need noise evidence (timing, network, console), not just pass-on-retry. Confidence from fixed weighted signals. Shared execution contracts in `packages/contracts/run.py` (`CompiledCase`, `AttemptResult`, `VerdictDecision`).
- N26 learning L2-lite (US-10): human decisions become lessons and code-enforced rules — dismissed bugs suppress the same failure's next draft (audited, citing the lesson), edited counts become hints on the next plan (never applied automatically), rejected graph nodes are told to the analyst, expected-behaviour lessons go to the designer. Lessons API with deactivate. Migration `0008`.

### Added
- T-105b breached-password check at sign-up: `BREACH_CHECK_MODE` off / online (HIBP range API with k-anonymity and padding, fails open on outage) / offline (local SHA-1 file for air-gapped installs).

### Added
- T-004 golden project 1 (shop): `PRD.md`, `openapi.yaml` (seeded PRD/API conflict on password length), hand-made `expected_graph.json`; `evals/scoring.py` (precision, recall, citation accuracy, conflict and vague-term checks) and `evals/run_graph_eval.py` (scores a live project through the API; exit 0 when docs/08 §6 targets are met).

### Changed
- OpenAPI rendering now lists inline JSON request-body fields with their constraints (`Body field password (string, optional, minLength 8, maxLength 128)`), so API limits can be cited and compared with documents. Offsets of OpenAPI sources ingested before this change differ; re-ingest them.

### Added
- T-204 embeddings: `LocalEmbedder` for OpenAI-compatible `/v1/embeddings` servers (Ollama, vLLM, llama.cpp, LM Studio), internal hosts only, 1024-d check, batching; the ingest worker stores chunk embeddings (failure keeps the source ready with a note); `similar_chunks` pgvector cosine search. Settings `EMBEDDING_URL`, `EMBEDDING_MODEL`.

### Added
- T-202 read-only Git import: `POST /projects/{id}/sources/repo`; worker shallow-clones (https only, no prompts, symlinks as plain files, token via git env config never argv, 120 s timeout), reads only regular text files inside the clone (size/count caps), extracts code facts (routes for FastAPI/Flask/Express/Django, HTML forms and inputs with limits, Pydantic `Field` limits, each with `file:line`) and Markdown docs into one citable source. SSRF guard in API and worker. `git` added to the image. Setting `GIT_READ_TOKEN`.

### Added
- T-105a two-factor sign-in: RFC 6238 TOTP, secrets encrypted with AES-256-GCM (`SAQ_ENCRYPTION_KEY`), `/auth/totp/setup|enable|disable`, login challenge with a 5-minute purpose-bound `mfa_token`, `/auth/login/mfa`; replayed codes refused; wrong codes count towards lockout. Migration `0007`.

### Added
- T-105c rate limits: 20 logins/min per IP, 600 requests/min per user, 30 job starts/min per project; 429 `RATE_LIMITED` with `Retry-After`. Memory backend (per process) or Redis (`RATE_LIMIT_BACKEND=redis`, shared across replicas). Limits configurable in settings.

### Added
- MCP preview (P5): `apps/mcp/server.py` with read-only tools `get_brief`, `plan_tests`, `understand_change` (diff → affected journeys with reasons), `saq mcp serve` (stdio); product brief `GET /projects/{id}/brief` (`packages/graph/brief.py`), change impact `packages/graph/impact.py`. MCP Python SDK 2.x.

### Fixed
- Diff parsing: `"" in "+-"` is true in Python, so blank lines were treated as changed lines; prefixes are now compared as a tuple.

### Added
- `saq` CLI (FR-17, `apps/cli/main.py`, Typer): `login` (token checked, config file 0600), `status`, `upload`, `event`, `plan`, `cases`, `bugs`, `report` (workbook / evidence pack), `audit verify` (exit 1 if broken); `--json` everywhere; `SAQ_URL` / `SAQ_TOKEN` env.

### Added
- N23 evidence pack: one self-contained HTML file per run (no script, every value redacted and HTML-escaped, verdict badges, expected-result quotes, SHA-256 evidence index); `GET /projects/{id}/runs/{run}/evidence-pack` (attachment) and stored by the report stage.

### Added
- M11 reporter: bug drafts from Fail verdicts (`packages/exporters/bug.py`, redacted, quote-cited), six-sheet run workbook (`packages/exporters/excel.py`: frozen headers, autofilter, verdict colours, formula-injection escaping, redaction), GitHub tracker adapter with duplicate search, bugs API (edit, duplicates, confirm, dismiss, Gate 4, `export.xlsx`), `job.report` worker (workbook to object storage, filing confirmed bugs). Setting `GITHUB_TOKEN`.

### Added
- Designer stage: case contract (`packages/contracts/case.py`), dedupe + case codes (`packages/cases`), `job.design` worker (approved facts only, exact count with one shortfall re-request, code quote check → `verified` or `unable_to_verify`), case API with edits, batch review (422 `CITATION_UNVERIFIED` for unverified cases) and Gate 3.

### Changed
- Gate 3 guard counts only cases of the approved plan and requires at least one approved case.

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
