# 16 · Project Implementation Plan

## 1. Team and ownership

| Area | Lead | Support |
|---|---|---|
| Product Understanding Graph, Analyst, Explorer | Nadia | Stuti |
| Planner, Designer, citation verifier, eval harness | Nadia | Stuti |
| Runner, Executor, evidence store, sandbox | Stuti | Nadia |
| Judge and verdict rules | Stuti | Nadia |
| Web app (all screens) | Stuti | Nadia |
| Reporter, Excel, GitHub Issues, evidence pack | Nadia | Stuti |
| Security, CI/CD, documentation | Shared | Shared |

Mentor: Md. Mahedi Hassan, Lecturer (Senior Scale), Dept. of SWE, DIU — demo every two weeks.

Rhythm: one-week sprints · 15-min check-in 3×/week · weekly dev-log entry ([20-continuous-update.md](20-continuous-update.md)).

## 2. Week 0 (3–5 days)

- Repo, CI, branch protection, issue templates.
- ADR-001…005.
- Two golden projects (e-commerce, school management) with requirement docs and 15–20 hidden seeded bugs.
- Start 10–15 QA-lead interviews (Excel, Bangla, counts demand).

## 3. Twelve-week plan

| Wk | Goal | Deliverables | Exit check |
|---|---|---|---|
| 1 | Skeleton end to end | Compose stack, runner registers over mTLS, Model Gateway + cost log, web shell | `docker compose up` works on both laptops |
| 2 | Ingest | Upload + chunk with offsets, repo import, environments, identity vault | Chunks show page + line in UI |
| 3 | Understand (docs + code) | Doc Analyzer with citations + quote check, tree-sitter Code Analyzer | 80% of hand-mapped rules found (golden 1) |
| 4 | Understand (UI) | Explorer with safe-action policy, allow-list, step budget; graph merge | 90% screens mapped; red-team page can't trigger blocked action |
| 5 | Review & conflicts | Graph review screen, conflict finder, ambiguity questions, brief | Gate 1 enforced in API |
| 6 | **Milestone 1 demo** | Hardening, eval on both golden projects | Precision ≥ 80%, recall ≥ 75%, every rule cited |
| 7 | Plan | Planner (techniques, risk, counts, reasons, cost), Gate 2 | Golden 1 plan approved < 10 min |
| 8 | Design | Designer with cited expected results, quote check, dedup, case review, Excel export | Citation accuracy ≥ 90% (50-case sample) |
| 9 | Execute | Compiler → Playwright, sandbox, evidence, replay cache, axe scan | 50 cases with full evidence; 2nd run 0 model calls |
| 10 | Judge | Verdict rules, clean re-run, flake classifier, confidence, UV queue; start dogfooding | Flake classification ≥ 85% |
| 11 | Report | Bug drafts, dedup, Gate 4, GitHub push, Excel workbook, HTML evidence pack, audit ledger | Confirmed bug in GitHub with steps, screenshot, HAR, requirement |
| 12 | **Final proof** | Full eval, head-to-head pilot, MCP preview, AI-feature oracle preview, security checklist, final report | All Validation Plan numbers recorded, including failures |

## 4. Cut order (cut from top if late)

1. MCP preview · 2. AI-feature oracle preview · 3. Accessibility scan · 4. Duplicate detection · 5. Spec conflict finder

**Never cut:** graph review · cited expected results · approval gates · honest verdicts · evidence capture · Excel output · local runner.

## 5. Milestones and deliverables

| Milestone | Week | Evidence for evaluators |
|---|---|---|
| M0 Proposal | done | Proposal, gap analysis, market workbook |
| M1 Understanding | 6 | Graph demo + eval report |
| M2 Plan & design | 8 | Excel test-case workbook with citations |
| M3 Execute & judge | 10 | Run dashboard, verdict mix, flake report |
| M4 Final | 12 | Live demo (script below), final report, poster, metrics table |

## 6. Final demo script (10 min)

1. One-command start (30 s).
2. Connect golden 2 (repo, PRD, localhost) — data-sharing summary shown.
3. Brief + graph; click a rule → exact quote; show one spec conflict.
4. Coverage plan; change a count; approve.
5. A case citing a PRD line; one *Unable to Verify* case.
6. Run: live verdicts, one Flaky resolved by re-run, one Blocked by CAPTCHA.
7. Confirm a bug → open in GitHub.
8. Excel workbook + evidence pack.
9. Run again: zero model calls.
10. Measured results table, including what did not work.

## 7. After the capstone

| Phase | Months | Goals |
|---|---|---|
| v1 | 4–6 | Jira, Bangla reports, change-impact selection, CI gate, full MCP, full AI-feature oracle, learning from decisions, OIDC, Helm, PDF evidence pack, model upgrade check, open-source release |
| v2 | 7–12 | Mobile plug-ins, hosted control plane + local runner, agent-as-user testing, visual plug-in, signed releases, ASVS L2 |

## 8. Risk register (top)

| Risk | L | I | Response |
|---|---|---|---|
| Scope too large | High | High | Cut order, weekly scope check |
| Weak graph extraction | Med | High | Gate 1, evals from week 3, tree-sitter facts |
| Model invents expected results | Med | High | Code quote check, Unable to Verify |
| Prompt injection | Med | High | 09-security §4, red-team CI |
| Test damages real server | Low | High | Safe-action policy, prod block, test identities |
| Cost overrun | Med | Med | Estimates, caps, caching, batch, replay |
| Login/CAPTCHA blocks runs | High | Med | Team identities, Blocked verdict, seed scripts |
| Team member unavailable | Med | High | Shared ownership, weekly docs, pairing |
