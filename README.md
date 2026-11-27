# Smart Autonomous QA

**An AI multi-agent QA teammate for web apps.** It understands your product the way a user does (from documents, code and the live UI), then plans, writes, runs and reports the tests. Every expected result **cites its source**, a human approves each key step, it **learns from every run**, and your code and data **stay inside your company**.

> SE331 Design Capstone · Daffodil International University · Department of Software Engineering
> Team: **Nadia Sultana Bushra** (232-35-010) · **Somprity Roy Stuti** (232-35-637) · Batch 41, Section C2 (DS)
> Mentor: **Md. Mahedi Hassan**, Lecturer (Senior Scale), Department of SWE, DIU

---

## Why

AI testing tools today automate the middle of QA (clicking through screens). Nobody covers both ends well: **understanding the product** before testing, and **handing documented results and bugs** to the team after. Teams also don't trust black-box AI verdicts: 64% worry about accuracy and 60% about hallucination (World Quality Report 2025-26).

## How it works

```
Connect & Ingest → Understand → [Gate 1] → Plan → [Gate 2] → Design → [Gate 3]
   → Execute ⇄ Judge → [Gate 4] → Report & Hand-off → Learn (next run is smarter)
```

| Pillar | What it means |
|---|---|
| Cited ground truth | Every expected result quotes a requirement line, checked word for word in code |
| Product Understanding Graph | One human-approved map of roles, journeys, screens, rules and APIs |
| Honest verdicts | Pass · Fail · Flaky · Blocked · Test Error · Unable to Verify, each with evidence |
| Local-first, any model | Runs on your servers with Claude or a local model; data stays in your database |
| Verifier for coding agents | MCP server + CLI so Claude Code / Codex / Cursor can ask for an outside check |
| Open artifacts | Standard Playwright code, Excel workbooks, GitHub/Jira tickets |

## Repository layout

```
apps/       api · orchestrator · workers · runner · web · mcp · cli
packages/   contracts · citations · policy · planning · verdicts · model_gateway · graph
            analyzers · exporters · learning · memory
evals/      golden projects + labelled datasets for AI evaluation
deploy/     Dockerfiles
docs/       full engineering manual (start at docs/README.md)
```

Each folder has a `README.md` with its purpose, design doc and owner.

## Quick start

Prerequisites: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 20 + pnpm, Docker Desktop.

```bash
cp .env.example .env
make install            # Python deps + git hooks
make test               # lint + type check + unit tests
docker compose up -d    # Postgres (pgvector), Redis, S3 (SeaweedFS), API
curl localhost:8000/api/v1/readyz

cd apps/web && pnpm install && pnpm dev   # http://localhost:5173
```

Full setup: [docs/15-setup-and-initialization.md](docs/15-setup-and-initialization.md).

Run tests in a browser locally: register a runner (`POST /api/v1/projects/{id}/runners`), then
`SAQ_API_URL=http://127.0.0.1:8000/api/v1 SAQ_RUNNER_TOKEN=saq_run_... SAQ_BROWSER_CHANNEL=chrome uv run python -m apps.runner`.

## Deploy to production

```bash
cp .env.production.example .env.production   # fill every value (passwords, JWT key, S3, model)
make prod-config && make prod-up             # migrations run first; TLS via Caddy
make smoke URL=https://qa.example.com
```

Images are published to GHCR by `.github/workflows/release.yml` on `vX.Y.Z` tags. Processes refuse
to start in `SAQ_ENV=prod` with unsafe settings. Runners connect with mTLS from your team network.
Guide: [docs/23-deployment-and-release.md](docs/23-deployment-and-release.md) §9–§11; operations:
[docs/24-operations-runbook.md](docs/24-operations-runbook.md).

## Contributing

- Start with [CONTRIBUTING.md](CONTRIBUTING.md).
- Stuti's onboarding, module plan and testing/documentation plan: [stuti.md](stuti.md).
- Working rules for AI-assisted development: [CLAUDE.md](CLAUDE.md).

## Status

All MVP modules are built and in review: understand (graph, Gate 1), plan (Gate 2), design with
cited expected results (Gate 3), compile, run (Playwright runner with safe-action policy and
Blocked detectors), judge (six honest verdicts with clean re-runs), bug drafts (Gate 4), reports,
web app, CLI and MCP. See [docs/26-task-board.md](docs/26-task-board.md) and
[docs/CHANGELOG.md](docs/CHANGELOG.md).
