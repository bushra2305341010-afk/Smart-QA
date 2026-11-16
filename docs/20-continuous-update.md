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
