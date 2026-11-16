# 26 · Task Board

The living backlog. Update the status column in the same PR that changes the work. Status: `todo` · `doing` · `review` · `done` · `blocked` · `cut`.

Rule: at most **2 items in `doing` per person**. Finish before starting.

## Module plan (one PR per module, merge in order)

| Module | Scope | Owner | Status | PR |
|---|---|---|---|---|
| M01 | Foundation: repo skeleton, tooling, FastAPI health, Compose, CI, web scaffold, docs in repo, contributor guides | Nadia | review | #1 |
| M02 | Contracts + citations (normalise, chunk with offsets, quote verify) | Nadia | review | #2 |
| M03 | Safe-action policy + permissions | Stuti | todo | |
| M04 | Planning: techniques, risk, counts, cost | Nadia | review | #3 |
| M05 | Verdict rules, flake features, confidence | Stuti | todo | |
| M06 | Model gateway (Claude adapter, schema output, cost, budget, redaction, untrusted wrapping, replay cache) | Nadia | review | #4 |
| M07 | Web foundations (Tailwind, layout, stepper, API client) | Stuti | todo | |
| M08 | DB models + migrations, auth, projects/sources API, orchestrator state machine | Shared | todo | |
| M09 | Ingest + Product Understanding Graph (analyst, explorer) | Nadia | todo | |
| M10 | Runner + Judge worker | Stuti | todo | |
| M11 | Reporter: bug drafts, Excel, evidence pack, GitHub filing | Nadia | todo | |
| M12 | Run dashboard + bug review UI, CLI, MCP preview | Shared | todo | |

## Week 0 — Setup

| ID | Task | Story | Owner | Status | Notes |
|---|---|---|---|---|---|
| T-001 | Create repo, branch protection, issue/PR templates | — | Nadia | done | PR template + CI added in M01; branch protection to be set by repo owner |
| T-002 | CI skeleton (lint, types, unit) | — | Nadia | done | `.github/workflows/ci.yml` (python, web, secrets) |
| T-003 | Write ADR-001…008 | — | Shared | done | `docs/adr/` |
| T-004 | Golden project 1 (shop) requirements + seeded bugs | — | Nadia | todo | bug list private |
| T-005 | Golden project 2 (school) requirements + seeded bugs | — | Stuti | todo | |
| T-006 | QA lead interview script + schedule 10–15 interviews | — | Shared | todo | |
| T-007 | Replace Starlette TestClient httpx warning filter: verify the recommended replacement package is legitimate, then switch | — | Nadia | done | `httpx2` confirmed as the official anthropic SDK 2.x HTTP library; installed via `anthropic`, filter removed in M06 |
| T-602 | Local-model adapter for the Model Gateway (air-gapped mode, P4) + quality shown on the eval set | — | Nadia | review | adapter + policy factory done; eval-set quality comparison needs evals (M09+) |
| T-603 | Postgres-backed replay cache + `model_call` recorder | — | Shared | todo | with M08 DB |
| T-008 | Contributor guide for Stuti (`stuti.md`) + CONTRIBUTING.md | — | Nadia | done | M01 |

## Week 1 — Skeleton

| ID | Task | Story | Owner | Status | Notes |
|---|---|---|---|---|---|
| T-101 | Docker Compose: api, worker, orchestrator, runner, db, redis, s3, web | — | Nadia | doing | db, redis, api done in M01; s3 = SeaweedFS (MinIO image no longer published, ADR-010); worker/orchestrator/runner added with their modules |
| T-102 | Model Gateway: Claude adapter, schema output, cost log | — | Nadia | todo | |
| T-103 | Runner registration over mTLS | US-06 | Stuti | todo | |
| T-104 | Auth: register/login/session, RBAC skeleton | US-11 | Stuti | todo | |
| T-105 | Web shell: layout, stage stepper, tokens | — | Stuti | doing | Vite+React+TS scaffold, tokens and VerdictBadge in M01; layout/stepper in M07 |

## Week 2 — Ingest

| ID | Task | Story | Owner | Status | Notes |
|---|---|---|---|---|---|
| T-201 | Upload + parsers (PDF, DOCX, MD, OpenAPI) with offsets | US-01 | Nadia | todo | |
| T-202 | Git import read-only | US-01 | Nadia | todo | |
| T-203 | Environments + identity vault | US-01 | Stuti | todo | |

## Later weeks

Add a table per week from [16-project-implementation.md](16-project-implementation.md) §3 at the start of that week's sprint planning.

## Blocked / risks this week

| ID | Blocked by | Action | Owner |
|---|---|---|---|
| | | | |
