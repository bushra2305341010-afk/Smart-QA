# 01 · Project Requirements

## 1. Problem

A QA engineer joining a project spends days reading documents and clicking through the app before writing a single test. Then they write cases by hand, run them, record results in Excel and write bug reports. Every release repeats most of this.

Market research (57 tools profiled, 22 scored on 35 capabilities, Nov 2026) shows:

- **Execution is solved** (Playwright, Cypress, MCP browser servers).
- **Trust is not.** World Quality Report 2025-26: 67% worry about data privacy, 64% about accuracy, 60% about hallucination. Median trust in AI test output is 54/100.
- **The two ends are empty.** Tools start *after* a human has understood the product and stop *before* results are documented and bugs filed.
- **Closed clouds are risky.** Octomind shut down in 2026; pricing is credit-metered.

## 2. Goal

Build a web platform that takes a codebase and/or running server plus product documents and returns:

1. A reviewed **Product Understanding Graph** and brief in user language.
2. A **coverage plan** with test counts per segment and the reasons.
3. **Test cases** whose expected results cite a source line.
4. An **executed suite** with evidence for every step.
5. **Honest verdicts** and **bug reports** a developer can reproduce, filed to GitHub Issues / Jira after human confirmation.
6. An **Excel workbook** and an **HTML evidence pack**.

## 3. Scope

| In scope (MVP, 12 weeks) | Out of scope |
|---|---|
| Web apps: browser UI + REST APIs | Native mobile (v2 via plug-ins) |
| Local (tunnel / runner), staging or public servers the team owns | Testing systems the team does not own |
| PDF, DOCX, Markdown, OpenAPI inputs; Git repo or ZIP | Performance / load testing of the SUT |
| GitHub Issues (MVP), Jira (v1) | Penetration testing of the SUT |
| English UI and reports (Bangla in v1) | Visual AI diffing (v2 plug-in) |

## 4. Stakeholders

| Stakeholder | Need |
|---|---|
| QA Lead | Approve graph, plan and bugs; trust the verdicts |
| Tester | Fast case review, clear evidence |
| Developer | Reproducible bugs, CLI / CI access |
| Coding agent (Claude Code, Codex, Cursor) | An independent verifier via MCP |
| Project manager | Coverage and release readiness |
| Supervisor & SE331 panel | Measurable results, clean design |

## 5. Functional requirements (FR)

| ID | Requirement | Release |
|---|---|---|
| FR-1 | Register, log in, belong to a team workspace with roles (Owner, QA Lead, Tester, Developer, Viewer) | MVP |
| FR-2 | Create a project from a Git URL, ZIP upload, or server URL (local via runner/tunnel, staging, public) | MVP |
| FR-3 | Accept PDF, DOCX, Markdown and OpenAPI documents; keep page/line offsets per chunk | MVP |
| FR-4 | Run an uploaded project in an isolated Docker sandbox with a start command and health check | MVP |
| FR-5 | Show the Product Understanding Graph + brief; approve / edit / reject each node (Gate 1) | MVP |
| FR-6 | Show segments with suggested counts, techniques, reasons and cost estimate; user edits then approves (Gate 2) | MVP |
| FR-7 | View, edit, add, delete, tag test cases; batch approve (Gate 3, optional for low risk) | MVP |
| FR-8 | Execute an approved suite and stream live progress per case | MVP |
| FR-9 | Store per step: screenshot, URL, trace, HAR, console, request/response, SHA-256 hash | MVP |
| FR-10 | Export `.xlsx` with sheets Test Cases, Run Results, Bugs, Traceability, Coverage, Evidence Index | MVP |
| FR-11 | Create a bug draft per confirmed failure; confirm / edit / dismiss before filing (Gate 4) | MVP |
| FR-12 | Push confirmed bugs to GitHub Issues (MVP) or Jira (v1) | MVP / v1 |
| FR-13 | Re-run a saved suite; show pass-rate trend and regression memory | MVP |
| FR-14 | Per-project safe-action allow-list (no delete, pay, transfer, email unless env marked safe) | MVP |
| FR-15 | Spec conflict finder and ambiguity questions before testing | MVP |
| FR-16 | Cost and time estimate before plan generation and run; budget caps | MVP |
| FR-17 | CLI `saq plan / run / report` with JSON output | MVP |
| FR-18 | MCP server tools `understand_change`, `plan_tests`, `run_journeys`, `get_verdicts` | MVP preview |
| FR-19 | Accessibility scan (axe-core) as a default segment | MVP |
| FR-20 | HTML evidence pack (requirement → test → evidence → bug chain) | MVP |

## 6. AI requirements (AIR)

| ID | Requirement |
|---|---|
| AIR-1 | Analyst builds graph nodes (Role, Journey, Step, Screen, Field, Rule, Endpoint, Requirement, Conflict, Question), each with a source link |
| AIR-2 | Planner proposes segments covering every approved journey, with a count derived from named techniques and a one-line reason per technique |
| AIR-3 | Designer writes positive, negative, boundary, permission and state cases with numbered steps, data, and a **cited** expected result |
| AIR-4 | Every cited quote must match the source text exactly (code check, not model); otherwise the case is *Unable to Verify* |
| AIR-5 | Executor runs compiled Playwright code; Healer may only propose locator diffs, never change expected results |
| AIR-6 | Judge returns one of six verdicts with reason, confidence (High/Medium/Low) and the rule that decided |
| AIR-7 | Reporter writes bug drafts with title, severity, environment, steps, expected (with quote), actual, evidence, duplicate check |
| AIR-8 | All agent output is JSON validated against a schema; invalid output is rejected and regenerated (max 2 retries) |
| AIR-9 | Page text, document text and logs are treated as untrusted data, never as instructions |

## 7. Non-functional requirements (NFR)

| ID | Area | Requirement |
|---|---|---|
| NFR-1 | Security | Code, docs, credentials encrypted at rest; credentials never logged, never sent to the model, never exported |
| NFR-2 | Isolation | Each sandbox / test runs in its own container, egress limited to allowed hosts |
| NFR-3 | Usability | A new user connects a project and sees a brief within 10 minutes |
| NFR-4 | Reliability | A run resumes from the last completed case after a crash or restart |
| NFR-5 | Transparency | Every AI decision shows its evidence and source |
| NFR-6 | Cost | Estimated tokens and money shown before generation or execution |
| NFR-7 | Performance | UI page load < 2 s; plan < 2 min; 50 replayed tests < 10 min on 4 browsers |
| NFR-8 | Accessibility | Our own UI meets WCAG 2.2 AA, full keyboard support |
| NFR-9 | Portability | Whole stack starts with `docker compose up` on one laptop |
| NFR-10 | Auditability | Every approval, verdict and filed bug is hash-chained in the audit ledger |

## 8. Success metrics (agree final values with the mentor)

| Metric | Target |
|---|---|
| Requirement coverage | ≥ 90% |
| Citation accuracy | ≥ 90% |
| Graph precision / recall | ≥ 80% / ≥ 75% |
| Seeded bug detection | ≥ 70% |
| False-bug rate | ≤ 15% |
| Flake classification | ≥ 85% |
| Review time vs manual | ≤ 50% |
| First-run cost (golden project) | < $5 |
| Replay run model calls | ≥ 80% fewer, aim for 0 |

## 9. Constraints and assumptions

- Two-person team, 12-week build.
- Default model: Claude Opus 5.5 (`claude-opus-5-5`); cheaper models per stage only after evals hold.
- Wording rule: say "none found in public documentation as of November 2026", never "first" or "only".
- Bangladesh-specific demand (Excel, Bangla, counts) is validated by 10–15 QA lead interviews before week 7.
