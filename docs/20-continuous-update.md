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

### Week 5 — 2026-11-25 (M03 safe-action policy)
**Done:** `packages/policy/{domains,actions}.py`, one test per row of docs/09 §6 plus relaxations and production; 100% branches.
**Decisions:** Transfers can never be relaxed; in `payments: "test"` only published test card numbers may be typed; keyword rules apply to interactions and route rules to links/requests, so a "Payment history" link is not a payment.
**Next:** M05 verdict rules.

### Week 5 — 2026-11-24 (scoped design context)
**Done:** `journey_scope` + designer context per journey. 1,668 tests, 100% coverage.
**Next:** waiting on Stuti's runner/judge; model-key eval on golden project 1.

### Week 5 — 2026-11-24 (N26 learning L2-lite)
**Done:** `apps/api/learning.py`, decision hooks (bugs, plans, graph), consumers (draft_bugs, planner, designer, analyst), lessons API, migration 0008. 1,665 tests, 100% coverage.
**Decisions:** Count hints are shown, not applied (no eval gate yet, docs/21 A5); suppression is a code rule keyed on case code + normalised failure, so the model cannot override it.
**Next:** embedding-based lesson retrieval (v1); retrieval for long documents in the analyst.

### Week 5 — 2026-11-24 (T-105b breached passwords)
**Done:** online / offline / off checker, sign-up refusal, settings, docs; task board tidied (T-102 delivered in M06). 1,662 tests, 100% coverage.
**Decisions:** Default `off` because air-gapped installs must not call out; `online` sends only a 5-character hash prefix and fails open.
**Next:** learning L2-lite (lessons from human decisions, US-10).

### Week 4 — 2026-11-20 (T-004 golden project 1)
**Done:** Shop PRD + OpenAPI, expected graph, scorer, eval runner, docs. 1,657 tests, 100% coverage.
**Bugs found & fixed:** The seeded conflict (API `maxLength 128`) was invisible to the analyst because the OpenAPI renderer skipped body schemas → body fields with constraints are rendered now.
**Next:** run the real analyst on the golden project with a model key and record precision/recall in §4; Stuti's runner for the seeded-bug app.

### Week 4 — 2026-11-20 (T-204 embeddings)
**Done:** Local embedder, ingest wiring, retrieval helper. 1,651 tests, 100% coverage.
**Decisions:** Embedding server must be internal (documents never leave the network for retrieval); embeddings are optional for correctness because every quote is still verified exactly.
**Next:** golden project 1 (T-004) for evals; integrate retrieval into the analyst/designer prompts when documents exceed one window.

### Week 4 — 2026-11-20 (T-202 Git import)
**Done:** URL guard, safe shallow clone, file walk, code facts, repo ingest path, API endpoint, git in the image. 1,644 tests, 100% coverage (real local repos; no network).
**Bugs found & fixed:** CI failures on #22–#25: tests read the developer's `.env` and used the local SeaweedFS; CI has no S3 → API fixtures now inject in-memory storage, and pre-push runs use empty S3 vars.
**Decisions:** Pattern-based code facts now (deterministic, cited by `file:line`); tree-sitter can replace them behind `extract_facts`.
**Next:** T-204 embeddings (local model), golden project 1 (T-004).

### Week 4 — 2026-11-20 (T-105a TOTP)
**Done:** TOTP (RFC vectors), AES-GCM secret box, MFA login step, enrol/disable, replay protection, lockout. 1,618 tests, 100% coverage.
**Decisions:** No TOTP library: the algorithm is 30 lines and testable against RFC 6238 directly. MFA token is a separate JWT purpose, so it can never act as an access token (and vice versa).
**Next:** T-204 embeddings or golden project 1 (T-004).

### Week 4 — 2026-11-20 (T-105c rate limits)
**Done:** `apps/api/ratelimit.py` (fixed window, memory/Redis), login per IP, requests per user, job starts per project. 1,607 tests, 100% coverage.
**Decisions:** Memory backend by default so the shared test Redis and single-process laptops behave predictably; Redis for multi-replica team mode.
**Next:** T-105a TOTP second factor.

### Week 4 — 2026-11-20 (MCP preview)
**Goal:** P5: coding agents can ask Smart QA which journeys a change touches and what to test, without any power over gates.
**Done:** Brief endpoint, impact analysis, MCP server with three read-only tools over the API, `saq mcp serve`; real stdio handshake checked (initialize + tools/list).
**Tests:** 1,602 passed, 100% coverage.
**Bugs found & fixed:** (1) Empty-string membership (`"" in "+-"`) made blank lines "changed". (2) MCP SDK 2.x renamed FastMCP → `MCPServer` and uses snake_case annotation fields.
**Next:** waiting on Stuti's M03 / M05 / M10 to connect compile → execute → judge; meanwhile T-105a TOTP and T-105c rate limits are open shared tasks.

### Week 4 — 2026-11-20 (CLI)
**Done:** `saq` CLI with JSON output and API-error exit codes; tested through Typer's runner against the real API. 1,597 tests, 100% coverage.
**Bugs found & fixed:** A doc-update script asserted on a heading that did not exist and stopped after the commit step; docs followed in a second commit. Lesson: run doc edits before `git commit`, in a separate step.
**Next:** MCP preview (read-only tools: plan_tests, get_verdicts, get_brief; runs disabled by default).

### Week 4 — 2026-11-20 (N23 evidence pack)
**Done:** HTML evidence pack + endpoint + stored by the report stage. 1,593 tests, 100% coverage.
**Decisions:** Served as an attachment, never rendered on the app origin (it contains untrusted page text, escaped anyway).
**Next:** CLI (`saq`, Typer) for CI and the MCP preview (M12, shared).

### Week 4 — 2026-11-20 (M11 reporter)
**Goal:** US-08/US-09: confirmed bugs filed with evidence after Gate 4; a run workbook.
**Done:** Bug template, workbook, GitHub adapter, reporter worker, bugs API + Gate 4 + export.
**Tests:** 1,592 passed, 100% coverage; workbook checked cell by cell (formula injection, redaction, colours, traceability).
**Decisions:** Only Fail verdicts become drafts; tracker token only from the environment; a filing error fails the stage (retry files the rest, filed bugs are never re-filed).
**Next:** evidence pack (HTML with hashes), then support Stuti's M10 runner/judge integration (`draft_bugs` before `verdicts_ready`).

### Week 3 — 2026-11-20 (Designer stage + Gate 3)
**Goal:** US-05: test cases whose expected results cite the source; unverifiable ones are flagged, never approved.
**Done:** Case contract, dedupe/codes, designer worker, case API, Gate 3; first end-to-end test from upload through Gates 1–3.
**Tests:** 1,582 passed, 100% coverage.
**Bugs found & fixed:** Gate 3 guard counted pending cases of superseded plans (would block forever) → scoped to the approved plan. Tests learned that the replay cache (correctly) answers identical requests and that cached answers ignore the budget (they cost nothing).
**Next:** M11 reporter (bug drafts, Gate 4 API, Excel, evidence pack); compile/execute/judge belong to Stuti (M10) and the M05 verdict rules.

### Week 3 — 2026-11-20 (Planner stage + Gate 2)
**Goal:** US-04: suggested counts with reasons from the approved graph; human sets approved counts at Gate 2.
**Done:** `from_graph`, planner worker, plan API, Gate 2 with budget check, pricing module.
**Tests:** 1,578 passed, 100% coverage; US-04 example (2 roles + 1 limit → 2 happy + 2 boundary) tested end to end.
**Bugs found & fixed:** (1) "8-64" parsed as 8 and -64 → range-dash-aware number pattern. (2) **Cross-project settings read**: `select(Project.settings)` without a filter returned another project's row for users in several projects (RLS on `project` allows all of a user's projects) → filter by id everywhere + regression test.
**Next:** designer stage (`job.design`: cited expected results, Gate 3), then M11 reporter.

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
