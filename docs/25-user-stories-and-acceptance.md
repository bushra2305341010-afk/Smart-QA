# 25 · User Stories and Acceptance Criteria

Each story maps to features (F/N IDs) and requirements (FR/AIR/NFR) and has testable criteria in Given / When / Then form. A story is **done** only when every criterion has an automated test.

## Epic E1 · Connect and understand

**US-01** As a QA Lead, I want to connect my repo, documents and staging URL, so the system can learn my product. *(F01, F02, N01, FR-2, FR-3)*
- Given a PDF PRD, when I upload it, then every chunk shows its page and line within 60 s.
- Given a Git URL with a read-only token, when I connect it, then the repo is cloned read-only and code facts are listed.
- Given a staging URL, when the runner checks it, then I see "reachable" or a clear reason why not.

**US-02** As a QA Lead, I want to review the product graph and approve it, so tests are based on a correct understanding. *(F05, N09, FR-5)*
- Given a draft graph, when I open a Rule node, then I see the exact source quote and its location.
- Given unreviewed nodes, when I press Approve, then the API refuses with `GATE_NOT_APPROVED` and lists them.
- Given all nodes reviewed, when I approve, then an audit event records my user ID and time.

**US-03** As a QA Lead, I want to see spec conflicts and vague requirements before testing. *(N07, N08)*
- Given the PRD and code disagree on a rule, when the graph is built, then a Conflict node cites both sources.
- Given a requirement with "fast", when analysed, then a Question for the product owner is created.

## Epic E2 · Plan and design

**US-04** As a QA Lead, I want suggested test counts with reasons, so I can decide coverage quickly. *(F08, N12, N13, FR-6)*
- Given an approved journey with 2 roles and 1 length limit, when planned, then the count includes 2 happy-path and 2 boundary cases, and each row shows its technique.
- Given I edit a count, when I approve, then the approved number is used for design.
- Given a plan, then an estimated cost and time are shown before generation.

**US-05** As a Tester, I want test cases whose expected results cite the source, so I can trust them. *(F11–F13, N16, AIR-3, AIR-4)*
- Given a generated case, when its quote is not found in the source text, then it is marked *Unable to Verify*.
- Given the review screen, when I press `A`, then the case is approved and the next one opens.

## Epic E3 · Run and judge

**US-06** As a Developer, I want to run the approved suite against my local server. *(F15, F18, F21, FR-8, FR-9)*
- Given an approved plan and an online runner, when I start a run, then live progress appears without refreshing.
- Given a finished step, then screenshot, trace and HAR exist with SHA-256 hashes.
- Given a "Delete account" button, when the policy blocks it, then the step is marked Blocked (not Fail).

**US-07** As a QA Lead, I want honest verdicts, so I don't chase false bugs. *(N20, F22, F23, AIR-6)*
- Given a failure that passes on clean re-run with timing noise, then the verdict is Flaky and no bug is drafted.
- Given the same failure twice with a verified citation, then the verdict is Fail with High confidence and a bug draft.

## Epic E4 · Report and learn

**US-08** As a QA Lead, I want confirmed bugs filed to GitHub with evidence. *(F28, N21, FR-11, FR-12)*
- Given a bug draft, when I confirm, then a GitHub issue is created with steps, expected (with quote), actual and evidence links.
- Given a similar open issue, then a duplicate warning is shown before filing.

**US-09** As a QA Lead, I want an Excel workbook of cases and results. *(F29, N22, FR-10)*
- Given a finished run, when I export, then the workbook has the 6 sheets with fixed columns and no secrets.

**US-10** As a QA Lead, I want the system to learn from my decisions. *(N26, N27, doc 21)*
- Given I reject a bug as "expected behaviour", when the same pattern appears next run, then the Judge cites the lesson and does not draft a bug.
- Given ≥ 30 new confirmed labels, when the nightly trainer runs, then a candidate model is evaluated and promoted only if it beats the current one.

## Epic E5 · Trust and privacy

**US-11** As a company security officer, I want all data to stay in our infrastructure. *(F32, F33, N33, NFR-1, doc 21)*
- Given `SAQ_MODEL_POLICY=local-only`, when a full run completes, then no network call leaves the company network (verified by egress logs).
- Given external-redacted mode, then the data-sharing page lists every data type sent per run.

**US-12** As a coding agent, I want to ask Smart QA to verify my change via MCP. *(F31, FR-18)*
- Given a token with `mcp:read`, when I call `understand_change` with a diff, then affected journeys are returned.
- Given a token without `mcp:run`, when I call `run_journeys`, then it is refused.

## Traceability rule

Every PR names its story (`US-xx`). The task board ([26](26-task-board.md)) tracks story status.
