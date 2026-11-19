# 20 · Continuous Update (living docs + dev log)

Docs are only useful if they match the code. This file sets the rules and holds the weekly development log.

## 1. Rules

| When you… | Update |
|---|---|
| Add/change an endpoint | [06-api.md](06-api.md) table |
| Add/change a table or column | [07-database.md](07-database.md) |
| Change an agent, prompt or model setting | [08-agent.md](08-agent.md) + prompt CHANGELOG |
| Touch a sector | Its file in [workflows/](workflows/) (flow, bug locator, change safety) |
| Make an architecture/security decision | New ADR in `docs/adr/` + one line in [02-architecture.md](02-architecture.md) §7 |
| Merge any PR | [CHANGELOG.md](CHANGELOG.md) under *Unreleased* |
| Finish a week | Dev-log entry below |
| Measure a metric | Validation table in §4 |

CI check `docs-guard`: if a PR changes `apps/api/routers/**`, `alembic/versions/**`, `apps/workers/**/prompts/**` or `packages/contracts/**` without touching `docs/`, the job warns and requires the label `docs-not-needed` to pass.

Each doc ends with a "Last reviewed" line; review every doc at milestones M1–M4.

## 2. Weekly dev-log template

Copy this block to the top of §3 every Friday.

```markdown
### Week N — YYYY-MM-DD
**Goal:** (from 16-project-implementation.md)
**Done:**
- [F13] quote verification merged (#42)
**Not done / moved:**
-
**Metrics this week:** graph P/R, citation acc., flake acc., cost per run
**Bugs found & fixed:** symptom → root cause → fix → prevention
**Decisions (ADR links):**
**Risks / blockers:**
**Next week:**
**Mentor feedback:**
```

## 3. Development log

### Week 3 — 2026-11-20 (M09b Product Understanding Graph)
**Goal:** US-02/US-03: a reviewable graph whose rules all cite a verified quote, with conflicts and vague requirements surfaced.
**Done:** Graph contract and package, analyst worker, gateway factory, graph API, node review with feedback, Gate 1.
**Tests:** 1,562 passed; scripted-model end-to-end: 2 sources → conflict citing both, vague-word Question, invented rule demoted, Gate 1 blocked then approved, pipeline at `plan`; 100% coverage.
**Bugs found & fixed:** (1) Citation line showed the chunk's first line, not the quote's → line = chunk line + newlines before the quote. (2) Approving a second draft while the pipeline was elsewhere must roll back the version flip too → approve and transition share one transaction (tested).
**Decisions:** One schema-bound call + code quote check instead of two model calls; graph routes nested under the project.
**Next:** M11 reporter (bug drafts, Excel, evidence pack), M09c explorer after M03 policy lands.

### Week 2 — 2026-11-20 (M09a ingest)
**Goal:** US-01: upload documents and get citable chunks with page and line.
**Done:** Upload API, magic-byte detection, PDF/DOCX/MD/OpenAPI parsers, content-addressed storage, ingest worker, Redis Streams consumer (ADR-013), worker process + Compose service, migration 0006.
**Tests:** 1,551 passed (parsers built from in-memory PDF/DOCX fixtures; every stored chunk re-verified against the stored text), 100% coverage; real SeaweedFS put/get checked.
**Bugs found & fixed:** (1) pypdf returns `""` for pages without a text layer → flagged "No text found" instead of an empty ready source. (2) Any ZIP starts with `PK`, so DOCX detection also requires `word/document.xml` (a plain ZIP is rejected with 415).
**Decisions:** pypdf (BSD) instead of PyMuPDF (AGPL); Redis Streams instead of Celery (ADR-013).
**Next:** M09b Product Understanding Graph.

### Week 1 — 2026-11-20 (T-603 model gateway on Postgres)
**Goal:** Pay for a model answer once, across processes; record every call for cost reports and budgets.
**Done:** Postgres replay cache, `model_call` recorder, shared month-spend budget (orchestrator guard reuses it), costs/budget endpoints, migration 0005.
**Tests:** 1,522 passed; a second gateway with an empty provider was served from Postgres with zero calls; 100% coverage.
**Next:** M09 ingest + Product Understanding Graph.

### Week 1 — 2026-11-20 (M08c orchestrator)
**Goal:** Drive the pipeline with gates enforced in the server, reliable job dispatch and resume after a crash.
**Done:** State machine table, engine, DB-backed gate and budget guards, outbox relay to Redis streams, recovery with stable job keys and resume point, pipeline API, `saq_system` role (ADR-012), orchestrator process + Compose service.
**Tests:** 1,517 passed (1,269 table cases for every stage × status × event), 100% line+branch coverage; real process relayed the test DB's outbox to Redis as `saq_worker`.
**Bugs found & fixed:** (1) Several outbox rows in one transaction share `now()` → relay order not guaranteed → wall-clock `created_at`. (2) Permission was checked after the stage, so a Tester got 409 instead of 403 → actor/permission first. (3) SQLAlchemy 2.1 deprecates `.distinct(cols)` → `postgresql.distinct_on`.
**Next:** T-603 (Postgres replay cache + `model_call` recorder), then M09 ingest + graph.

### Week 1 — 2026-11-20 (M08b auth + projects API)
**Goal:** Sign-in, roles and the first project endpoints, all enforced server-side.
**Done:** Auth (Argon2id, lockout, EdDSA access JWT, rotating refresh with reuse detection, CSRF, API tokens), RBAC matrix + `require()`, projects/members/sources/chunks/environments/identities/audit endpoints, error envelope, prefixed IDs, security headers, migration 0003.
**Tests:** 231 passed (46 new: 19 unit, 27 integration), 100% line+branch coverage; smoke-tested with uvicorn connected as the real `saq_app` login.
**Bugs found & fixed:** (1) `email-validator` rejects the reserved `.test` TLD → tests use `example.com`. (2) Re-setting a cookie in the httpx jar adds a second cookie instead of replacing it, so the reuse test sent the new token → replay sent from a separate client. (3) A dependency error (503) masked body validation in a unit test → inject a factory.
**Decisions:** RBAC matrix lives in `apps/api/auth/permissions.py` (auth needs it now); M03 keeps the safe-action policy. Non-members get 404 rather than 403.
**Next:** M08c orchestrator state machine + gates + outbox relay + recovery.

### Week 1 — 2026-11-20 (M08a database)
**Goal:** Persist everything in docs/07 with project isolation and a tamper-evident audit ledger.
**Done:** 30 SQLAlchemy models, Alembic `0001` (schema) + `0002` (grants, forced RLS on 29 tables, audit chain + append-only triggers, HNSW indexes). Composite `(id, project_id)` FKs, transaction-local project scope, `audit.verify_chain`, outbox helpers. Separate `saq_migrator` / `saq_app` roles (ADR-011).
**Tests:** 185 passed (26 new: 5 unit, 21 integration on a throwaway `saq_test` DB), 100% line+branch coverage; ruff, mypy --strict and `alembic check` clean; API image runs `alembic`.
**Bugs found & fixed:** (1) Dev Compose ran the app as the bootstrap superuser, which silently bypasses RLS and cannot be demoted → owner/app role split; old volumes must be recreated. (2) Postgres checks FKs without RLS, so a child row could reference another project's parent → composite FKs + invariant test. (3) Alembic 1.20 deprecation warning (no `path_separator`) failed `-W error` runs → set `path_separator = os`.
**Next:** M08b auth + RBAC + projects/sources/environments API; T-603 replay cache/`model_call` recorder on the new tables.

### Week 0 — 2026-11-17 (Docker verification + ADR-010)
**Goal:** Verify `docker compose up` from M01 now that Docker Desktop runs.
**Done:** API, Postgres + pgvector and Redis start; `/readyz` ready; API runs as uid 10001. CI fixed (pnpm esbuild approval, gitleaks allowlist for fake fixtures). PRs moved to the main repo as Lokkhita (#6–#10, stacked), Claude attribution removed.
**Bugs found & fixed:** (1) `minio/minio` image no longer exists → SeaweedFS (ADR-010). (2) AWS CLI 2.22 uploads to SeaweedFS then GET/HEAD 404 → use boto3 with checksums "when required" (documented in 19-debugging).
**Next:** M08 DB + auth + projects API + orchestrator.

### Week 0 — 2026-11-17 (T-602 local model)
**Goal:** Pillar P4: run with a local model so nothing leaves the network.
**Done:** OpenAI-compatible local adapter over plain HTTP; provider factory that enforces `local-only` (never Claude, internal hosts only); new settings.
**Tests:** 159 passed, 100% line + branch coverage; adapter tested with `httpx.MockTransport` (no server needed).
**Bugs found & fixed:** none.
**Decisions:** OpenAI-compatible protocol (covers Ollama, llama.cpp, vLLM, LM Studio); token count is an estimate; local cost $0.
**Next:** M08 DB + auth + orchestrator (shared). Stuti: M03, M05.

### Week 0 — 2026-11-17 (M06 model gateway)
**Goal:** One safe, cheap, testable path for every model call (ADR-003).
**Done:** gateway with redaction, untrusted wrapping, replay cache, budget pre-check, schema validation and retries; Claude adapter using structured outputs, explicit effort, cached context and server-side refusal fallbacks.
**Tests:** 128 passed with warnings as errors; whole codebase 100% line + branch coverage. Adapter tested against a fake SDK client (no network, no cost).
**Bugs found & fixed:** mypy narrowed the client to the concrete SDK type and rejected dict params → client attribute typed `Any` on purpose (real client or test double).
**Decisions:** SDK 2.x; `fallbacks="default"` on by default; local-model adapter split out as T-602.
**Next:** Stuti: M03 policy, M05 verdicts. Nadia: T-602 local adapter, then M08 DB/auth/orchestrator with Stuti.

### Week 0 — 2026-11-17 (M04 planning)
**Goal:** Suggested test counts with visible reasons (F08, N12, N13, N14; US-04).
**Done:** planning contracts; technique rows; transparent risk score and priority; suggested count with half-up rounding and a happy-path floor; design cost estimate with budget check.
**Tests:** 88 passed overall; planning + contracts 100% line and branch coverage; the Login example from docs/04 gives exactly 10.
**Bugs found & fixed:** a test wrongly required reasons to start with a capital letter (they start with "1 per ...") → test now checks reason content.
**Decisions:** numbers are code-only, the LLM only explains; prices are passed in, never hard-coded.
**Next:** M06 model gateway (Nadia); Stuti: M03 policy, M05 verdict rules.

### Week 0 — 2026-11-17 (M02 citations)
**Goal:** Pillar P1 in code: quotes are accepted only if they match the source exactly.
**Done:** contracts for citations and chunks; normaliser; chunker with exact offsets, page and line; quote verifier with offset correction and short-quote rejection.
**Tests:** 51 passed overall; `packages/citations` and `packages/contracts` 100% line + branch coverage; property-style test verifies 300 random substrings.
**Bugs found & fixed:** (1) two unreachable branches in the chunker's long-paragraph split → simplified the loop instead of testing dead code. (2) Non-ASCII characters written into source files were flagged by ruff RUF001 → stored as `\uXXXX` escapes.
**Decisions:** minimum quote length 12 characters; wrong offsets are corrected rather than failed.
**Next:** M03 policy (Stuti), M04 planning (Nadia).

### Week 0 — 2026-11-17 (M01 foundation)
**Goal:** Working repository skeleton everyone can clone, test and extend.
**Done:**
- Fork-based workflow set up (contributors push to forks, PR into `bushra2305341010-afk/Smart-QA`).
- Repo skeleton for every app/package with owner + design-doc READMEs.
- FastAPI health/readiness endpoints, settings, Compose stack, CI, pre-commit, Makefile.
- Web scaffold (Vite + React + TS) with tokens and `VerdictBadge`.
- `stuti.md` and `CONTRIBUTING.md`.
**Tests:** Python 7 passed, 100% line+branch coverage; web 3 passed; typecheck and production build OK.
**Bugs found & fixed:** Starlette TestClient deprecation warning broke `-W error` runs → filtered by message in pytest config; replacement package to be verified first (T-007).
**Decisions:** Fork-and-PR contribution model (upstream account grants read access only).
**Risks / blockers:** Docker Compose stack still to be verified on Docker Desktop.
**Next:** M02 contracts + citations; Stuti starts M03 policy.

### Week 0 — 2026-11-16
**Goal:** Turn research into an engineering doc set and the capstone poster.
**Done:**
- Created `docs/` with 20 core docs, sector workflow files and bug-triage map.
- Chose frontend stack (React + Vite + TS + Tailwind + shadcn/ui) and "Verified Indigo" colour system.
- Poster produced for submission.
**Decisions:** ADR-002 (explicit state machine instead of LangGraph), ADR-006 (Vite SPA instead of Next.js) — to be written.
**Next week:** repo + CI skeleton, ADR-001…008, golden project 1 docs, interview script.
**Mentor feedback:** —

## 4. Validation results (fill as measured)

| Metric | Target | Week measured | Result | Notes |
|---|---|---|---|---|
| Graph precision | ≥ 80% | | | |
| Graph recall | ≥ 75% | | | |
| Citation accuracy | ≥ 90% | | | |
| Requirement coverage | ≥ 90% | | | |
| Seeded bug detection | ≥ 70% | | | |
| False-bug rate | ≤ 15% | | | |
| Flake classification | ≥ 85% | | | |
| Review time vs manual | ≤ 50% | | | |
| First-run cost | < $5 | | | |
| Replay model calls | 0 | | | |

## 5. Release notes process

1. Move *Unreleased* in CHANGELOG to a version heading (`## [0.3.0] - 2026-12-20`).
2. Add upgrade notes (migrations, new env vars, breaking changes).
3. Tag `v0.3.0`; CI builds images + SBOM.
