# 18 · Testing and QA (of Smart QA itself)

We sell trust, so our own product must pass the same bar.

## 1. Test pyramid

| Level | What | Tool | Target |
|---|---|---|---|
| Unit | Policy engine, citation verifier, coverage formula, verdict rules, exporters, risk score | pytest, Vitest | 80% lines overall; **100% branches** on `policy` and `citations` |
| Contract | API schema, runner protocol, tracker payloads, stage output schemas | Schemathesis, Pact-style fixtures | No breaking change without version bump |
| Integration | Pipeline on a tiny sample app with Compose | pytest + Docker Compose | Full run < 10 min |
| End to end (UI) | Setup → approve plan → run → confirm bug | Playwright | Main flows green on every merge |
| AI evaluation | Graph, citations, verdicts, flakes, seeded bugs | `evals/` harness | Targets in §4 |
| Security | Injection suite, ZAP baseline, ASVS checklist | custom, OWASP ZAP | 0 high at release |
| Load / chaos | API load, runner soak, kill-and-resume | k6, chaos scripts | See 11, 12 |
| Accessibility | Our UI | axe (Storybook + Playwright) | 0 violations, WCAG 2.2 AA |
| Dogfooding | Smart QA tests its own web app | Smart QA | From week 10 |

## 2. Commands

```bash
make test-fast        # unit (py + web) ~1 min
make test-<sector>    # e.g. test-judge, test-planner
make test-affected    # changed packages + dependents
make test-contract
make test-int         # compose-based integration (docker compose up -d db; tests use a throwaway saq_test DB)
make e2e              # Playwright UI tests
make evals-small      # PR eval set (~10 min)
make evals-full       # nightly
make redteam          # injection pages
make golden           # tiny full pipeline
```

## 3. CI pipeline

| Trigger | Jobs |
|---|---|
| Every PR | lint (ruff, eslint), types (mypy, tsc), unit, contract, security scans (bandit, semgrep, gitleaks, pip-audit, pnpm audit), red-team, build images, `test-affected`, `evals-small` if prompts/workers changed |
| Merge to main | integration (Compose), e2e, small evals, ZAP baseline |
| Nightly | full evals both golden projects, cost report, dependency audit, chaos, audit-chain verify |
| Release tag | SBOM, Trivy scan, changelog, upgrade notes |

## 4. AI evaluation targets

| Metric | Target |
|---|---|
| Graph precision / recall | ≥ 80% / ≥ 75% |
| Citation accuracy | ≥ 90% |
| Flake classification | ≥ 85% |
| Seeded bug detection | ≥ 70% |
| False-bug rate | ≤ 15% |
| Injection: off-plan actions | 0 |
| Replay run model calls | 0 (≥ 80% fewer minimum) |

Tolerance for PRs: no metric may drop more than 2 points vs. baseline. A drop needs a written justification and mentor-visible note in the dev log.

## 5. Golden projects

| Project | Domain | Contents |
|---|---|---|
| Golden 1 | Small e-commerce | PRD, user manual, OpenAPI, app source, identities, 15–20 hidden seeded bugs, hand-made graph |
| Golden 2 | School management | Same set, includes one deliberately ambiguous requirement |

Seeded-bug list lives in a private file outside the system's reach (`evals/private/` git-crypted).

## 6. Test data rules

- No real personal data anywhere. Use generated data (Faker) with boundary values from rules.
- Fixtures versioned in `tests/fixtures/`; recorded model responses in `tests/cassettes/` (no keys).
- Unit tests never call a real model; integration tests use the replay cache or a stub provider.

## 7. Head-to-head pilot (week 12)

Same two golden projects, UI changed between runs. Compare with Playwright Test Agents and one free trial (TestMu KaneAI or QA.tech). Report every number, including where a rival wins.

## 8. Bug handling for our own bugs

1. File with template: steps, expected, actual, evidence, sector label, severity.
2. Find the sector with [workflows/00-bug-triage-map.md](workflows/00-bug-triage-map.md).
3. Write a failing test first, then fix.
4. Add the case to the sector's regression list.

## Golden project 1 (implemented)

`evals/golden_projects/shop/` (PRD, OpenAPI, expected graph) and `evals/scoring.py` (deterministic precision / recall / citation accuracy, conflict and vague-term checks). Run `python -m evals.run_graph_eval --project … --golden evals/golden_projects/shop` against a live project; `tests/evals/` keeps the golden data honest (every expected quote verifies against the ingested PRD).
