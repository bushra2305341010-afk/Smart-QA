# 23 · Deployment and Release

## 1. Environments

| Env | Purpose | Who deploys | Data |
|---|---|---|---|
| `local` | Developer laptop (Docker Compose) | Developer | Seed + golden projects |
| `ci` | Ephemeral, per PR | GitHub Actions | Fixtures only |
| `staging` | Integration + demo rehearsal | Auto on merge to `main` | Golden projects, anonymised |
| `demo` | Capstone demo / mentor reviews | Manual from a release tag | Golden projects |
| `customer` (v1+) | Company self-hosted | Company admin | Company data (stays in company, see [21](21-self-learning-and-data-privacy.md)) |

## 2. CI/CD pipeline

| Workflow | Trigger | Jobs |
|---|---|---|
| `.github/workflows/ci.yml` | every PR, push to `main` | ruff, mypy --strict, pytest (unit + integration + `-m browser` with Chromium, Postgres + Redis services), web typecheck/test/build, gitleaks, **build the api/web/runner images**, validate `deploy/compose.prod.yml` |
| `.github/workflows/release.yml` | tag `vX.Y.Z` (or manual) | build and push `ghcr.io/<owner>/smart-qa-{api,web,runner}` tagged `X.Y.Z`, `X.Y`, `sha-…`, with provenance |

Planned additions: Trivy scan + CycloneDX SBOM on release, ZAP baseline on staging, nightly evals.

## 3. Build artifacts

| Image | Dockerfile | Runs |
|---|---|---|
| `smart-qa-api` | `deploy/api.Dockerfile` (python:3.12-slim, non-root uid 10001, healthcheck) | API (`uvicorn`, `WEB_CONCURRENCY` workers), and with other commands: `alembic upgrade head` (migrate job), `python -m apps.orchestrator`, `python -m apps.workers` |
| `smart-qa-web` | `deploy/web.Dockerfile` (Vite build → Caddy 2.8) | TLS (automatic certificates), SPA, reverse proxy to the API (SSE unbuffered), security headers, runner mTLS listener |
| `smart-qa-runner` | `deploy/runner.Dockerfile` (Playwright Chromium, non-root uid 10002) | `python -m apps.runner` inside the team network; `python -m apps.runner.explorer` |

## 4. Versioning

SemVer. `MAJOR` = breaking API/DB/runner-protocol change · `MINOR` = new feature · `PATCH` = fix. API breaking changes also bump `/api/vN`.

## 5. Release checklist

- [ ] All CI green on the tag; nightly evals within tolerance
- [ ] CHANGELOG moved from *Unreleased* to the version
- [ ] Migrations tested up **and** down on a staging snapshot
- [ ] Upgrade notes: new env vars, manual steps
- [ ] Security checklist ([10](10-authentication-and-security.md) §8) re-checked
- [ ] Demo script ([16](16-project-implementation.md) §6) rehearsed on `demo`

## 6. Deploy steps (Compose / single server)

First install: §9. Upgrade to a new release:

```bash
make backup                                   # pg_dump into ./backups (keeps 14)
sed -i 's/^SAQ_VERSION=.*/SAQ_VERSION=X.Y.Z/' .env.production
docker compose -f deploy/compose.prod.yml --env-file .env.production pull
make prod-up                                  # `migrate` runs first; api waits for it
make smoke URL=https://qa.example.com
```

## 7. Rollback

1. Set `SAQ_VERSION` back to the previous release and `make prod-up`.
2. If the release ran a migration: roll back with `docker compose ... run --rm migrate alembic downgrade <rev>` only when the release notes mark it reversible; otherwise restore the pre-deploy dump (`deploy/scripts/backup.sh` header shows the `pg_restore` command).
3. Record the incident in [24-operations-runbook.md](24-operations-runbook.md).

## 8. Feature flags

Risky features ship dark behind flags (`settings.features`) and are turned on per environment after smoke tests.

## 9. Production setup (first install)

Single host with Docker; DNS `qa.example.com` → host; ports 80/443 open (and 8443 for runners).

1. `git clone … && cd Smart-QA && cp .env.production.example .env.production` and fill it:
   - passwords: `openssl rand -base64 32` for `POSTGRES_PASSWORD`, `SAQ_APP_DB_PASSWORD`, `SAQ_WORKER_DB_PASSWORD`, `REDIS_PASSWORD`;
   - `JWT_PRIVATE_KEY`: `openssl genpkey -algorithm ed25519` (paste on one line with `\n` escapes);
   - your S3 bucket (`S3_*`, enable versioning), `PUBLIC_URL=https://…`, model settings and `MODEL_PRICE_*`.
2. Runner CA for mTLS (§10) at `deploy/runner-ca.pem` (or set `RUNNER_CA_FILE`).
3. `make prod-config` → `make prod-up` → `make smoke URL=https://qa.example.com`.
4. Open the site, register the first user (owner), create a project.

Every process starts with `SAQ_ENV=prod` and **refuses to start** when something required is missing or unsafe (`apps/api/settings.py::production_problems`: dev passwords, migrator role as runtime role, memory rate limits, missing signing key / S3 / model, non-https `PUBLIC_URL`).

Hardening built in: containers read-only with `/tmp` tmpfs, all capabilities dropped, `no-new-privileges`, no database/Redis ports published, Redis password + AOF, Postgres roles with passwords from env (`deploy/postgres/init-prod/01-roles.sh`, RLS-bound `saq_app`/`saq_worker`, no `BYPASSRLS`), HSTS/CSP/frame-deny at the proxy, Secure cookies, rotated JSON logs.

## 10. Runners (mTLS, T-103)

```bash
# once: a CA for runner certificates (keep runner-ca.key offline)
openssl req -x509 -newkey ed25519 -nodes -days 825 -subj "/CN=smart-qa-runner-ca" \
  -keyout runner-ca.key -out deploy/runner-ca.pem
# per runner
openssl req -newkey ed25519 -nodes -subj "/CN=runner-1" -keyout runner.key -out runner.csr
openssl x509 -req -in runner.csr -CA deploy/runner-ca.pem -CAkey runner-ca.key -days 365 -out runner.crt
openssl x509 -in runner.crt -outform der | sha256sum     # → cert_sha256
```

Register it (QA Lead): `POST /projects/{id}/runners {"name": "runner-1", "cert_sha256": "<hex>"}` → token (shown once). On the runner host (inside the team network that can reach the app under test):

```bash
docker run -d --name saq-runner --shm-size=1g \
  -e SAQ_API_URL=https://qa.example.com:8443/api/v1 -e SAQ_RUNNER_TOKEN=saq_run_… \
  -e SAQ_CLIENT_CERT=/certs/runner.crt -e SAQ_CLIENT_KEY=/certs/runner.key \
  -e SAQ_VAULT_FILE=/vault/vault.json -e SAQ_VAULT_KEY=… \
  -v $PWD/certs:/certs:ro -v saq-vault:/vault ghcr.io/<owner>/smart-qa-runner:X.Y.Z
docker exec -it saq-runner python -m apps.cli.main vault set admin_password   # test logins stay here
```

The proxy verifies the client certificate against the CA and sets `X-Client-Cert-Sha256`; the public listener strips that header, so it cannot be forged from outside.

## 11. Environment reference

See `.env.production.example` (every variable with a comment) and `apps/api/settings.py`. Runner variables: `apps/runner/main.py` docstring.
