# 00 · Bug Triage Map

Start here when something is wrong. Find the symptom, go to the sector, open its **Bug locator** table.

## 1. Symptom → sector

| What you see | Sector | Folder to open |
|---|---|---|
| Upload fails, chunks missing, wrong page/line numbers | [01 Connect & Ingest](01-connect-and-ingest.md) | `packages/citations/parsers`, `apps/api/routers/sources.py` |
| Repo import fails, runner can't reach app, identity not filled | [01 Connect & Ingest](01-connect-and-ingest.md) | `analyzers/code/git_source.py`, `apps/runner` |
| Graph missing roles/screens/rules, wrong merge, brief nonsense | [02 Graph](02-product-understanding-graph.md) | `apps/workers/analyst`, `apps/workers/explorer`, `packages/graph` |
| Counts look wrong, risk score odd, cost estimate off | [03 Planner](03-coverage-planner.md) | `apps/workers/planner`, `packages/planning` |
| Cases lack citations, quote check fails, duplicates | [04 Designer](04-test-designer.md) | `apps/workers/designer`, `packages/citations/verify.py` |
| Tests don't run, evidence missing, sandbox errors, policy blocks | [05 Executor & Runner](05-executor-and-runner.md) | `apps/workers/compiler`, `apps/runner` |
| Wrong verdict, too many Flaky/UV, confidence odd | [06 Judge](06-judge.md) | `apps/workers/judge`, `packages/verdicts/rules.py` |
| Bug draft wrong, Excel broken, GitHub filing fails, evidence pack | [07 Reporter](07-reporter-and-handoff.md) | `apps/workers/reporter`, `packages/exporters` |
| Regression memory/flake rate wrong, change-impact selects wrong | [08 Learn](08-learn-and-maintain.md) | `packages/memory`, `packages/impact` |
| MCP tools fail, CLI errors, webhooks, CI gate | [09 Integrations & MCP](09-integrations-and-mcp.md) | `apps/mcp`, `apps/cli`, `exporters/trackers` |
| Login, 403, RBAC, audit chain broken, budget, redaction | [10 Governance & Auth](10-governance-and-auth.md) | `apps/api/auth`, `packages/policy`, `apps/api/audit` |
| Screen broken, UI not updating, layout/colour issues | [11 Frontend](11-frontend.md) | `apps/web/src/features/*` |
| Job stuck, stage never advances, gate not enforced | [12 Orchestrator](12-orchestrator.md) | `apps/orchestrator` |
| Model errors, cost spikes, cache misses | [08-agent.md](../08-agent.md) + sector of the stage | `packages/model_gateway` |

## 2. Dependency map (who breaks whom)

```
01 Ingest ─▶ 02 Graph ─▶ 03 Planner ─▶ 04 Designer ─▶ 05 Executor ─▶ 06 Judge ─▶ 07 Reporter ─▶ 08 Learn
     │            │                          ▲              │              ▲
     └── citations package used by 02, 04, 06, 07 ──────────┘              │
12 Orchestrator drives all stages · 10 Governance guards all · 11 Frontend reads all · 09 exposes 02/03/05/06
```

| If you change… | Also run tests for |
|---|---|
| `packages/citations` | 01, 02, 04, 06, 07 |
| `packages/contracts` (any schema) | every consumer listed in the schema docstring |
| `packages/policy` | 05, 02 (Explorer), 10 |
| `packages/model_gateway` | all AI stages + `evals-small` |
| `apps/runner` protocol | 05, 06, 12 |
| Graph schema | 02, 03, 04, 08, 09, 11 |
| Verdict enum | 06, 07, 08, 11, Excel exporter |
| DB migration | all sectors owning touched tables |

## 3. Triage steps

1. Copy `trace_id` → `saq debug trace <id>` → which service/span failed?
2. Match to a sector above; open its file.
3. Use its **Bug locator** to go to the exact file.
4. Write a failing test, fix, run the sector's **Change safety** list.
5. Log it in the dev log.

## 4. Severity guide (for our own bugs)

| Severity | Example |
|---|---|
| Critical | Destructive action reached SUT; secret leaked; audit chain broken; false Pass shown |
| High | Gate bypass; run can't complete; wrong verdict class systematically |
| Medium | Wrong count/reason; export column wrong; UI flow blocked with workaround |
| Low | Cosmetic, copy text, minor layout |
