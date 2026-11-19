# Smart Autonomous QA — Engineering Docs

> A QA teammate that first understands your product the way a user does, then plans, writes, runs and reports tests. It shows the source of every expected result, keeps a human in charge at key gates, and keeps your code and data inside your team.

SE331 Design Capstone · Daffodil International University · Batch 41, Section C2 (DS)
Team: Nadia Sultana Bushra (232-35-010), Somprity Roy Stuti (232-35-637)
Mentor: Md. Mahedi Hassan, Lecturer (Senior Scale), Department of SWE, DIU

These docs turn the research files in the parent folder into a build manual:

- `Smart Autonomous QA - Project Proposal.docx`
- `Smart Autonomous QA - Features, Architecture and Development Plan.md` (the main source; it wins on any conflict)
- `Smart Autonomous QA - Gap Analysis and Irreplaceable Offering.md`
- `Smart Autonomous QA - Market Comparison and Strategy.xlsx`

---

## Where to start

| You want to… | Read |
|---|---|
| Understand what we build and why | [01-project-requirements.md](01-project-requirements.md) |
| See how the system fits together | [02-architecture.md](02-architecture.md), [03-system-workflow.md](03-system-workflow.md) |
| Run it on your laptop | [15-setup-and-initialization.md](15-setup-and-initialization.md) |
| Build a feature | [17-feature-development.md](17-feature-development.md) |
| Fix a bug | [workflows/00-bug-triage-map.md](workflows/00-bug-triage-map.md), then [19-debugging.md](19-debugging.md) |
| Change something without breaking others | The **Change safety** section in each file in [workflows/](workflows/) |
| Record what changed this week | [20-continuous-update.md](20-continuous-update.md), [CHANGELOG.md](CHANGELOG.md) |

## Full index

| # | File | What it covers |
|---|---|---|
| 01 | [project-requirements](01-project-requirements.md) | Problem, goals, scope, FR / AIR / NFR, success metrics |
| 02 | [architecture](02-architecture.md) | Components, control plane vs runner, tech stack, repo layout, ADRs |
| 03 | [system-workflow](03-system-workflow.md) | The 4-gate pipeline, state machine, run sequence |
| 04 | [design](04-design.md) | Software design: modules, interfaces, patterns, data contracts |
| 05 | [frontend-ui-design](05-frontend-ui-design.md) | Tool analysis, chosen stack, colour system, screens, UX rules |
| 06 | [api](06-api.md) | REST endpoints, SSE events, errors, versioning |
| 07 | [database](07-database.md) | Schema, how data moves, migrations, indexes, backup |
| 08 | [agent](08-agent.md) | The 8 AI stage workers, prompts, model gateway, evaluation |
| 09 | [security](09-security.md) | Threat model, prompt-injection defence, sandbox, supply chain |
| 10 | [authentication-and-security](10-authentication-and-security.md) | Login, sessions, RBAC, secrets, runner mTLS |
| 11 | [load-balancing](11-load-balancing.md) | Scaling API, workers, runners and model calls |
| 12 | [reliability](12-reliability.md) | Retries, resume, idempotency, backups, SLOs |
| 13 | [mcp-connection](13-mcp-connection.md) | MCP server for Claude Code / Codex / Cursor, CLI |
| 14 | [integration](14-integration.md) | GitHub, Jira, Git repos, tunnels, CI, Excel |
| 15 | [setup-and-initialization](15-setup-and-initialization.md) | Prereqs, first run, env vars, seed data |
| 16 | [project-implementation](16-project-implementation.md) | 12-week plan, ownership, milestones, cut order |
| 17 | [feature-development](17-feature-development.md) | How to add a feature end to end, definition of done |
| 18 | [testing-and-qa](18-testing-and-qa.md) | Test pyramid for Smart QA itself, AI evals, red-team |
| 19 | [debugging](19-debugging.md) | Tools, logs, traces, common failures and fixes |
| 20 | [continuous-update](20-continuous-update.md) | How docs and the dev log stay current |
| 21 | [self-learning-and-data-privacy](21-self-learning-and-data-privacy.md) | How the system learns from its own testing; all data stays in the company's database |
| 22 | [coding-standards](22-coding-standards.md) | Python / TypeScript / SQL / prompt / git style, review checklist |
| 23 | [deployment-and-release](23-deployment-and-release.md) | Environments, CI/CD, versioning, release checklist, rollback |
| 24 | [operations-runbook](24-operations-runbook.md) | Incident playbooks, kill switch, routine ops, post-mortem template |
| 25 | [user-stories-and-acceptance](25-user-stories-and-acceptance.md) | Stories with Given/When/Then acceptance criteria |
| 26 | [task-board](26-task-board.md) | Living backlog with status per task |
| 27 | [glossary](27-glossary.md) | Shared vocabulary |
| — | [adr/](adr/) | Architecture decision records (template + ADR-001…011) |
| — | [workflows/](workflows/) | One file per sector: flow, bug locator, change safety |

## The six pillars (never cut)

| # | Pillar | One line |
|---|---|---|
| P1 | Cited ground truth | Every expected result quotes its source, checked word for word |
| P2 | Product Understanding Graph | One human-approved map of roles, journeys, screens, rules, APIs |
| P3 | Honest verdicts | Pass, Fail, Flaky, Blocked, Test Error, Unable to Verify |
| P4 | Local-first, bring your own model | Runs inside the team network; Claude or a local model |
| P5 | Independent verifier for coding agents | MCP + CLI so coding agents can ask for an outside check |
| P6 | Open artifacts | Playwright code, Excel, tracker tickets — usable without us |

## Quick start (target)

```bash
git clone <repo> smart-autonomous-qa && cd smart-autonomous-qa
cp .env.example .env          # add ANTHROPIC_API_KEY or LOCAL_MODEL_URL
docker compose up -d          # api, postgres, redis, s3 (worker, runner, web added with their modules)
open http://localhost:5173    # web app
```

Details in [15-setup-and-initialization.md](15-setup-and-initialization.md).
