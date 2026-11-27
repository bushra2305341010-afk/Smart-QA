# 24 · Operations Runbook

Step-by-step actions for when something goes wrong in a running deployment. For code-level bugs, use [19-debugging.md](19-debugging.md).

## 1. Severity and response

| Sev | Example | Response time | Who |
|---|---|---|---|
| SEV1 | Destructive action reached an app under test, secret leak, data visible across projects | Immediately; stop runs | Both team members + mentor informed |
| SEV2 | Runs cannot complete, login broken, gate bypass | Same day | On-duty developer |
| SEV3 | Single feature broken, workaround exists | Next working day | Owner of the sector |

## 2. Playbooks

### Stop everything (SEV1 kill switch)
```bash
docker compose -f deploy/compose.prod.yml --env-file .env.production stop worker orchestrator         # no new stage work is dispatched
curl -X DELETE …/api/v1/projects/<prj>/runners/<rnr>   # revoke a runner (repeat per runner)
docker stop saq-runner                                  # on each runner host
```
Cancel a project's pipeline: `saq event -p <prj> cancel`. (Planned: `saq admin pause-all-runs`.)

### Runs stuck
1. `saq status -p <prj>` and `saq verdicts -p <prj>`: stage, status and which cases have no verdict.
2. Runners online? `GET /projects/<prj>/runners` (`status`, `last_seen_at`). A killed runner's lease expires after 10 min and another runner takes the job; after 3 losses the case becomes Test Error.
3. Jobs not consumed? `docker compose -f deploy/compose.prod.yml --env-file .env.production logs worker orchestrator`; scale workers: set `WORKER_REPLICAS=3` and `make prod-up`.
4. Failed stage: `saq event -p <prj> retry`.

### Model provider failing / costs spike
1. Check `model_call` errors and the cost dashboard.
2. Circuit breaker open? Wait 60 s or switch the project to the local model.
3. Cost spike → check cache hit rate; lower budget cap; pause non-urgent understand/design jobs.

### Database issues
1. `/readyz` failing → `docker compose -f deploy/compose.prod.yml --env-file .env.production logs db`.
2. Disk full → extend the volume; prune old dumps in `./backups`. (Planned: retention job.)
3. Corruption / bad migration → restore the latest dump (`pg_restore`, see `deploy/scripts/backup.sh`), then `saq audit verify -p <prj>`.

### Suspected secret leak
1. Rotate the secret (model key, tracker token, JWT key) immediately.
2. Revoke sessions: rotating `JWT_PRIVATE_KEY` and restarting `api` invalidates every access token; refresh sessions are revoked per user via `/auth/logout`. (Planned: `saq admin revoke-sessions`.)
3. Search logs and exports for the leaked value; purge.
4. Post-mortem within 48 h.

### Audit chain verification fails
1. Freeze writes: `saq admin read-only on`.
2. `saq audit verify --project <id> --from <seq>` to locate the first broken link.
3. Compare with backup; escalate as SEV1 if tampering is suspected.

## 3. Routine operations

| Task | Frequency | Command |
|---|---|---|
| Database backup | Daily (cron) | `make backup` → `./backups/saq-<UTC>.dump`, keeps 14 (copy off-host) |
| Restore drill | Monthly | restore the latest dump into a scratch Postgres, `alembic current`, `saq audit verify` |
| Evidence / reports | Continuous | your S3 bucket with versioning + lifecycle rules |
| Smoke test | After every deploy | `make smoke URL=https://…` |
| Dependency audit | Weekly | CI + `uv lock --upgrade` / `pnpm outdated` in a PR |
| Rotate JWT key | 90 days | new `JWT_PRIVATE_KEY`, `make prod-up` (users sign in again) |
| Rotate DB / Redis passwords | 180 days | `ALTER ROLE … PASSWORD`, update `.env.production`, `make prod-up` |
| Runner certificates | Before expiry (365 d) | issue a new cert, register a new runner with its `cert_sha256`, revoke the old one |
| Audit chain | Weekly | `saq audit verify -p <prj>` |
| Flake eval | Before each release | `python -m evals.run_flake_eval` (≥ 85%, 0 false bugs) |

## 4. Post-mortem template

```markdown
### Incident <date> — <title>   (SEV?)
**Impact:** who/what was affected, for how long
**Timeline:** detection → mitigation → resolution (with times)
**Root cause:** the real cause, not the symptom
**What went well / badly:**
**Action items:** [owner, issue link, due date]
**Prevention:** test, alert or guardrail added
```
Store in `docs/security/incidents/YYYY-MM-DD-title.md` and link it from the dev log.
