# 17 · Feature Development

How to take a feature (an `F..` or `N..` ID from the plan) from idea to merged, without breaking anything else.

## 1. Workflow

```
Issue ─▶ Design note ─▶ Branch ─▶ Tests first (contract + unit) ─▶ Code ─▶ Evals (if AI)
     ─▶ Docs ─▶ PR ─▶ Review ─▶ CI green ─▶ Merge ─▶ Dev-log entry ─▶ Demo
```

### Step by step

1. **Issue.** Title `[F13] Cited expected results with quote verification`. Fill: user story, acceptance criteria, module label, release (MVP/v1/v2).
2. **Find the sector.** Open [workflows/00-bug-triage-map.md](workflows/00-bug-triage-map.md) to see which sector owns it and what depends on it.
3. **Design note** (≤ 1 page in the issue): data changes, API changes, UI changes, which contracts are touched. If it is security-relevant or changes an interface → write an ADR.
4. **Branch:** `feat/F13-quote-verification` (also `fix/`, `docs/`, `chore/`, `refactor/`).
5. **Tests first** for contracts and pure logic.
6. **Implement** in this order: schema/migration → domain service → API → worker → UI.
7. **AI change?** Bump prompt version, update eval cases, run `make evals-small`.
8. **Docs:** update the sector file in `workflows/`, any changed API table in `06-api.md`, DB table in `07-database.md`.
9. **PR** with the template (below). Keep PRs < 400 changed lines where possible.
10. **Merge** (squash) when CI is green and one review approves.
11. **Dev-log** entry + CHANGELOG line ([20-continuous-update.md](20-continuous-update.md)).

## 2. Commit messages (Conventional Commits)

```
feat(citations): verify expected-result quotes against source text (F13)
fix(judge): treat 429 from SUT as flaky noise, not failure
docs(workflows): add change-safety list for planner
```

## 3. PR template

```markdown
## What & why
Feature/bug ID, one paragraph.

## Sector(s) touched
- [ ] 01 Ingest  - [ ] 02 Graph  - [ ] 03 Planner  - [ ] 04 Designer  - [ ] 05 Executor
- [ ] 06 Judge   - [ ] 07 Reporter - [ ] 08 Learn  - [ ] 09 Integrations/MCP
- [ ] 10 Governance/Auth - [ ] 11 Frontend

## Contracts changed?
API / DB / schema / runner protocol / prompt version — list them or "none".

## Change safety (copied from the sector doc)
- [ ] Ran the sector's regression tests: `make test-<sector>`
- [ ] Ran downstream sectors' contract tests
- [ ] Evals (if AI) — attach diff

## Screenshots / evidence
```

## 4. Definition of done

- [ ] Code reviewed and merged with green CI
- [ ] Unit tests + integration tests where data crosses a boundary
- [ ] Evals pass, no drop beyond tolerance
- [ ] Security checks pass; any new external call listed on the data-flow page
- [ ] User-facing text in plain English, in the i18n file
- [ ] Docs updated (sector file + API/DB if changed)
- [ ] Audit events for any approval or external action
- [ ] Dev-log + CHANGELOG updated

## 5. Feature flags

New user-visible features start behind a flag in `settings.features` (`mcp_preview`, `ai_oracle_preview`, `change_impact`). Flags are listed in `/me` so the UI can hide them. Remove the flag one release after it is stable.

## 6. Not breaking other sectors

1. **Contracts are frozen interfaces.** Pydantic schemas in `packages/contracts/` are the only thing sectors share. Changing one = version bump + contract tests for every consumer.
2. **Expand, then contract** for DB and API: add new, migrate callers, remove old in a later PR.
3. **Run downstream tests.** Each sector doc lists its consumers; `make test-affected` runs tests for changed packages and their dependents (based on import graph).
4. **Golden runs.** `make golden` runs the full pipeline on the tiny sample app (< 10 min) — required on PRs that touch orchestrator, contracts, or runner.

## 7. Example: adding the "Must/Should/Could priority" (N14)

| Layer | Change |
|---|---|
| DB | `segment.priority` enum (expand: nullable) |
| Planner | Priority from risk score thresholds (pure function + unit tests) |
| Contract | `SegmentOut.priority` (additive, no version bump) |
| API | Returned in `GET /plans/{id}` |
| UI | Badge in plan table, filter |
| Excel | Priority column already exists — fill it |
| Docs | `workflows/03-coverage-planner.md`, `07-database.md` |
