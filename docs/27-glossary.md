# 27 · Glossary

| Term | Meaning |
|---|---|
| **SUT** | System Under Test: the user's web app that Smart QA tests |
| **Product Understanding Graph (PUG)** | Human-approved map of roles, journeys, steps, screens, fields, rules, endpoints and requirements, each linked to its source |
| **Journey** | A user goal through the app (e.g., Checkout); unit of planning and coverage |
| **Segment** | A slice of a journey planned with specific techniques (e.g., Payment validation) |
| **Technique** | Test-design method: happy path, equivalence class, boundary value, negative/permission, state transition, accessibility |
| **Citation** | `source_id + offsets + quote` proving where an expected result comes from |
| **Quote verification** | Code check that the cited quote exists exactly in the source text |
| **Ground truth** | The expected result a test is judged against, from documents or approved rules (not from current behaviour) |
| **Gate** | Human approval point: G1 graph, G2 plan, G3 cases (optional), G4 bugs |
| **Verdict** | Judge's result: Pass, Fail, Flaky, Blocked, Test Error, Unable to Verify (UV) |
| **Flaky** | Failed once, passed on clean re-run, with noise in the evidence |
| **Test Error** | Our test script/locator is wrong, not the product |
| **Blocked** | Could not test: CAPTCHA, MFA, policy block, environment down |
| **Unable to Verify (UV)** | No verified source or weak evidence; goes to a human queue |
| **Evidence** | Screenshot, trace, video, HAR, console, request/response captured per step, hashed with SHA-256 |
| **Evidence pack** | HTML/PDF export linking requirement → test → evidence → bug |
| **Runner** | Sandboxed Playwright executor inside the team network; connects outbound only |
| **Control plane** | API, orchestrator, workers, DB and storage |
| **Model Gateway** | Single interface for all LLM calls (providers, caching, cost, redaction) |
| **Replay cache** | Reuses approved model outputs; passing re-runs make zero model calls |
| **Safe-action policy** | Code rules that block destructive or off-domain actions |
| **Healer** | Agent that proposes locator-only fixes as a diff for approval |
| **Lesson** | Stored learning from a human decision, retrieved into prompts (L2) |
| **Trained component** | Small project-owned ML model (flake, risk, calibration, locator, dedup) retrained on confirmed labels (L3) |
| **Eval gate** | A new prompt/model/component goes live only if it matches or beats the current one on the eval set |
| **Golden project** | Sample app with hand-made graph and hidden seeded bugs, used for evaluation |
| **ADR** | Architecture Decision Record in `docs/adr/` |
| **RLS** | Postgres row-level security, isolating projects |
| **MCP** | Model Context Protocol: how coding agents call Smart QA tools |
| **BYO model / BYO DB** | Company brings its own LLM or database; data stays in-house |
