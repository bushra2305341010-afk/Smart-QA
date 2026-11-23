# 26 · Task Board

The living backlog. Update the status column in the same PR that changes the work. Status: `todo` · `doing` · `review` · `done` · `blocked` · `cut`.

Rule: at most **2 items in `doing` per person**. Finish before starting.

## Module plan (one PR per module, merge in order)

| Module | Scope | Owner | Status | PR |
|---|---|---|---|---|
| M01 | Foundation: repo skeleton, tooling, FastAPI health, Compose, CI, web scaffold, docs in repo, contributor guides | Nadia | review | #6 (+ S3 fix #11) |
| M02 | Contracts + citations (normalise, chunk with offsets, quote verify) | Nadia | review | #7 |
| M03 | Safe-action policy (the RBAC matrix itself shipped in M08b: `apps/api/auth/permissions.py`) | Stuti | todo | |
| M04 | Planning: techniques, risk, counts, cost | Nadia | review | #8 |
| M05 | Verdict rules, flake features, confidence | Stuti | todo | |
| M06 | Model gateway (Claude adapter, schema output, cost, budget, redaction, untrusted wrapping, replay cache) + T-602 local model | Nadia | review | #9, #10 |
| M07 | Web foundations (Tailwind, layout, stepper, API client) | Stuti | todo | |
| M08 | Split: M08a DB models + migrations + RLS + audit/outbox; M08b auth + RBAC + projects/sources/environments API; M08c orchestrator state machine + gates + recovery | Shared | M08a, M08b, M08c review | M08a #12, M08b #13, M08c #14 |
| M09 | Split: M09a ingest (upload, parsers, chunks, ingest worker); M09b Product Understanding Graph (analyst, merge, conflicts, ambiguity, graph API, Gate 1); M09c explorer | Nadia | M09a, M09b review | M09a #16, M09b #17 |
| F08 | Planner stage: graph → plan worker, plan API, Gate 2 | Nadia | review | #18 |
| F11 | Designer stage: cited cases, review, Gate 3 | Nadia | review | #19 |
| M10 | Runner + Judge worker | Stuti | todo | |
| M11 | Reporter: bug drafts, Excel, evidence pack, GitHub filing | Nadia | review | #20, evidence pack #21 |
| M12 | Run dashboard + bug review UI, CLI, MCP preview | Shared | CLI + MCP preview review; UI is Stuti | #22, #23 |

## Week 0 — Setup

| ID | Task | Story | Owner | Status | Notes |
|---|---|---|---|---|---|
| T-001 | Create repo, branch protection, issue/PR templates | — | Nadia | done | PR template + CI added in M01; branch protection to be set by repo owner |
| T-002 | CI skeleton (lint, types, unit) | — | Nadia | done | `.github/workflows/ci.yml` (python, web, secrets) |
| T-003 | Write ADR-001…008 | — | Shared | done | `docs/adr/` |
| T-004 | Golden project 1 (shop) requirements + seeded bugs | — | Nadia | review | #28: PRD, OpenAPI with a seeded conflict, expected graph, scorer; seeded-bug app + private bug list wait for the runner (M10) |
| T-005 | Golden project 2 (school) requirements + seeded bugs | — | Stuti | todo | |
| T-006 | QA lead interview script + schedule 10–15 interviews | — | Shared | todo | |
| T-007 | Replace Starlette TestClient httpx warning filter: verify the recommended replacement package is legitimate, then switch | — | Nadia | done | `httpx2` confirmed as the official anthropic SDK 2.x HTTP library; installed via `anthropic`, filter removed in M06 |
| T-602 | Local-model adapter for the Model Gateway (air-gapped mode, P4) + quality shown on the eval set | — | Nadia | review | adapter + policy factory done; eval-set quality comparison needs evals (M09+) |
| T-603 | Postgres-backed replay cache + `model_call` recorder | — | Nadia | review | #15: `apps/api/db/model_store.py`, cost/budget API, migration 0005 |
| T-008 | Contributor guide for Stuti (`stuti.md`) + CONTRIBUTING.md | — | Nadia | done | M01 |

## Week 1 — Skeleton

| ID | Task | Story | Owner | Status | Notes |
|---|---|---|---|---|---|
| T-101 | Docker Compose: api, worker, orchestrator, runner, db, redis, s3, web | — | Nadia | doing | db, redis, api done in M01; s3 = SeaweedFS (MinIO image no longer published, ADR-010); worker/orchestrator/runner added with their modules |
| T-102 | Model Gateway: Claude adapter, schema output, cost log | — | Nadia | todo | |
| T-103 | Runner registration over mTLS | US-06 | Stuti | todo | |
| T-104 | Auth: register/login/session, RBAC skeleton | US-11 | Nadia | review | Done in M08b (#13) because the API needed it; TOTP → T-105a, breached-password check → T-105b, per-IP/user rate limits → T-105c |
| T-105a | TOTP second factor (`/auth/login/mfa`) | US-11 | Nadia | review | #25 |
| T-105b | Breached-password check (k-anonymity) in `check_password_rule` | US-11 | Shared | todo | |
| T-105c | Rate limits: 600 req/min per user, 30 job starts/min per project, per-IP login backoff (Redis) | — | Nadia | review | #24; memory or Redis backend |
| T-105 | Web shell: layout, stage stepper, tokens | — | Stuti | doing | Vite+React+TS scaffold, tokens and VerdictBadge in M01; layout/stepper in M07 |

## Week 2 — Ingest

| ID | Task | Story | Owner | Status | Notes |
|---|---|---|---|---|---|
| T-201 | Upload + parsers (PDF, DOCX, MD, OpenAPI) with offsets | US-01 | Nadia | review | M09a #16; embeddings (T-204) and OCR not yet |
| T-204 | Chunk embeddings (`chunk.embedding`, HNSW) via a local embedding model | US-01 | Nadia | review | #27; retrieval helper ready for analyst/designer use |
| T-202 | Git import read-only | US-01 | Nadia | review | #26: shallow clone, SSRF guard, pattern-based code facts (tree-sitter later) |
| T-203 | Environments + identity vault | US-01 | Stuti | todo | Environment/identity API done in M08b (identity stores a vault *reference*, write-only); the encrypted vault itself remains |

## Later weeks

Add a table per week from [16-project-implementation.md](16-project-implementation.md) §3 at the start of that week's sprint planning.

## Blocked / risks this week

| ID | Blocked by | Action | Owner |
|---|---|---|---|
| | | | |
