# 15 · Setup and Initialization

## 1. Prerequisites

| Tool | Version | Check |
|---|---|---|
| Docker Desktop / Engine + Compose v2 | 24+ | `docker compose version` |
| Python | 3.12 | `python3 --version` |
| uv (Python packages) | latest | `uv --version` |
| Node.js | 20 LTS | `node -v` |
| pnpm | 9 | `pnpm -v` |
| Git | 2.40+ | `git --version` |
| Playwright browsers (for local dev without Docker) | — | `uv run playwright install --with-deps chromium` |

Hardware: 8 vCPU / 16 GB RAM recommended.

## 2. First-time repository setup (team lead, once)

```bash
mkdir smart-autonomous-qa && cd smart-autonomous-qa && git init
# create the folder layout from 02-architecture.md §6
gh repo create smart-autonomous-qa --private --source=. --push
```
Then on GitHub: branch protection on `main` (PR + 1 review + green CI), issue templates (bug, feature, ADR), labels (`module:*`, `type:*`, `priority:*`).

Write ADR-001…005 before writing feature code.

## 3. Clone and run

```bash
git clone git@github.com:<org>/smart-autonomous-qa.git && cd smart-autonomous-qa
cp .env.example .env
# edit .env (see §4)
docker compose up -d --build
docker compose exec api alembic upgrade head   # uses MIGRATION_DATABASE_URL (owner role)
docker compose exec api python -m scripts.seed --demo
open http://localhost:5173
```
Login: `owner@demo.local` / password printed by the seed script.

## 4. Environment variables

| Variable | Example | Notes |
|---|---|---|
| `SAQ_ENV` | `dev` | dev / test / prod |
| `DATABASE_URL` | `postgresql+psycopg://saq_app:…@localhost:5432/saq` | Runtime role: DML only, row-level security applies |
| `WORKER_DATABASE_URL` | `postgresql+psycopg://saq_worker:…@localhost:5432/saq` | Orchestrator relay/recovery (system role, ADR-012) |
| `MIGRATION_DATABASE_URL` | `postgresql+psycopg://saq_migrator:…@localhost:5432/saq` | Owner role for Alembic and integration tests. A DB volume created before 2026-11-20 has `saq_app` as superuser: run `docker compose down -v` once (ADR-011) |
| `DATABASE_URL` | `postgresql+psycopg://saq_app:***@db:5432/saq` | |
| `REDIS_URL` | `redis://redis:6379/0` | |
| `S3_ENDPOINT` / `S3_BUCKET` / `S3_ACCESS_KEY` / `S3_SECRET_KEY` | `http://localhost:8333` / `evidence` / `saq_s3` / dev password | Local SeaweedFS keys live in `deploy/seaweedfs/s3.json`; companies point these at their own S3 |
| `ANTHROPIC_API_KEY` | `sk-ant-…` | Only if the Claude provider is used. Alternatively run `ant auth login`; the SDK picks up the profile automatically |
| `SAQ_DEFAULT_MODEL` | `claude-opus-5-5` | Per-stage overrides in project settings |
| `LOCAL_MODEL_URL` | `http://host.docker.internal:11434/v1` | OpenAI-compatible local server (Ollama, llama.cpp, vLLM, LM Studio). **Required** when `SAQ_MODEL_POLICY=local-only`, and must be an internal host |
| `LOCAL_MODEL_NAME` | `qwen3:8b` | Model name on the local server |
| `SAQ_MODEL_POLICY` | `external-redacted` | `local-only` · `external-redacted` · `external-code` (see docs/21 §B3) |
| `SAQ_SECRET_KEY` | 32+ random bytes (base64) | Encryption envelope key |
| `JWT_PRIVATE_KEY_FILE` | `/run/secrets/jwt.pem` | |
| `GITHUB_TOKEN` | fine-grained PAT | Optional, for bug filing |
| `SAQ_BUDGET_MONTHLY_USD` | `20` | Default cap |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel:4317` | Optional tracing |

Generate secrets: `python -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())"`. **Never commit `.env`.**

## 5. docker-compose services

| Service | Port | Purpose |
|---|---|---|
| `web` | 5173 | Vite dev server (nginx in prod) |
| `api` | 8000 | FastAPI |
| `worker` | — | Celery workers (all queues in dev) |
| `orchestrator` | — | State machine + scheduler + outbox relay |
| `runner` | — | Playwright runner (registers itself in dev) |
| `db` | 5432 | Postgres 16 + pgvector |
| `redis` | 6379 | Queue, rate limits, pub/sub |
| `s3` | 8333 | S3-compatible evidence store (SeaweedFS 4.00, ADR-010) |
| `mailpit` | 8025 | Mail sink for safe email tests |

## 6. Local development without Docker (faster loops)

```bash
docker compose up -d db redis s3        # infra only
uv sync                                  # Python deps
uv run alembic upgrade head              # needs MIGRATION_DATABASE_URL (see .env.example)
uv run uvicorn apps.api.main:app --reload
uv run celery -A apps.workers worker -Q q.understand,q.plan,q.design,q.judge,q.report -l info
uv run python -m apps.orchestrator      # recovery + outbox relay (needs WORKER_DATABASE_URL, REDIS_URL)
uv run python -m apps.runner --dev
cd apps/web && pnpm i && pnpm gen:api && pnpm dev
```

## 7. Initialize a first project (demo)

1. Settings → Model policy: Claude or Local. Read the data-sharing summary.
2. New project → name "Golden 1 – Shop".
3. Sources: upload `evals/golden_projects/shop/PRD.pdf`, connect `evals/golden_projects/shop/app` repo.
4. Environment: `local`, URL `http://shop:3000`, allowed host `shop`, runner `dev-runner`.
5. Identities: `customer_basic`, `admin` (from `evals/golden_projects/shop/identities.example.yaml`).
6. Click **Understand** → review graph → **Approve (Gate 1)**.
7. **Plan** → edit counts → **Approve (Gate 2)** → **Design** → review → **Run**.

## 8. Pre-commit & tooling

```bash
uv run pre-commit install
# hooks: ruff, ruff-format, mypy, bandit, gitleaks, eslint, prettier, tsc --noEmit
```

## 9. Verify the install

```bash
make doctor      # checks docker, ports, env vars, DB migration, S3 bucket, runner registered, model reachable
make test-fast   # unit tests (Python + web)
```

## 10. Common setup problems

| Problem | Fix |
|---|---|
| Port 5432 busy | Stop local Postgres or change `DB_PORT` in `.env` |
| Runner "unregistered" | `docker compose logs runner`; re-run `saq runner create --env local --dev` |
| `ANTHROPIC_API_KEY` missing | Set it or switch project to local model |
| Playwright browser missing (non-Docker) | `uv run playwright install chromium` |
| Apple Silicon image issue | `DOCKER_DEFAULT_PLATFORM=linux/arm64` and use multi-arch images |
