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

```
PR ─▶ lint · types · unit · contract · security scans · red-team · evals-small (if AI) · build images
merge to main ─▶ integration (compose) · e2e · ZAP baseline ─▶ push images :sha ─▶ deploy staging ─▶ smoke test
tag vX.Y.Z ─▶ SBOM · Trivy · sign images ─▶ release notes ─▶ deploy demo (manual approval)
```

Workflows live in `.github/workflows/{pr,main,release,nightly}.yml`.

## 3. Build artifacts

| Image | Contents | Tag |
|---|---|---|
| `saq/api` | FastAPI + orchestrator | `:sha`, `:vX.Y.Z` |
| `saq/worker` | Celery workers + trainer | same |
| `saq/runner` | Playwright browsers, axe, ffmpeg | same |
| `saq/web` | Static build served by nginx | same |

Images are minimal (distroless / slim), pinned by digest, scanned by Trivy, with an SBOM (CycloneDX) attached.

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

```bash
git fetch --tags && git checkout vX.Y.Z
docker compose pull
docker compose run --rm api alembic upgrade head
docker compose up -d
make smoke            # health, login, start tiny run, export
```

## 7. Rollback

1. `docker compose down` → `git checkout vPREV` → `docker compose up -d`.
2. If a migration ran: only roll back with `alembic downgrade <rev>` if the release notes mark it reversible. Otherwise restore the DB from the pre-deploy backup (taken automatically by `make deploy`).
3. Record the incident in [24-operations-runbook.md](24-operations-runbook.md).

## 8. Feature flags

Risky features ship dark behind flags (`settings.features`) and are turned on per environment after smoke tests.
