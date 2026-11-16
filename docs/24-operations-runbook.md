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
saq admin pause-all-runs --reason "SEV1 <short>"     # runners stop pulling jobs
saq runner revoke --all                              # if a runner may be compromised
```

### Runs stuck
1. `saq debug run <run_id>` → check stage + last completed case.
2. Runner online? `saq runner list`. If offline → restart runner container.
3. Queue backed up? Flower (`:5555`) → scale workers `docker compose up -d --scale worker=3`.
4. Resume: `saq run resume <run_id>`.

### Model provider failing / costs spike
1. Check `model_call` errors and the cost dashboard.
2. Circuit breaker open? Wait 60 s or switch the project to the local model.
3. Cost spike → check cache hit rate; lower budget cap; pause non-urgent understand/design jobs.

### Database issues
1. `/readyz` failing → `docker compose logs db`.
2. Disk full → run retention job `saq admin retention --now`; extend volume.
3. Corruption / bad migration → restore latest backup ([07](07-database.md) §7), then `saq audit verify`.

### Suspected secret leak
1. Rotate the secret (model key, tracker token, JWT key) immediately.
2. Revoke sessions: `saq admin revoke-sessions --all`.
3. Search logs and exports for the leaked value; purge.
4. Post-mortem within 48 h.

### Audit chain verification fails
1. Freeze writes: `saq admin read-only on`.
2. `saq audit verify --project <id> --from <seq>` to locate the first broken link.
3. Compare with backup; escalate as SEV1 if tampering is suspected.

## 3. Routine operations

| Task | Frequency | Command |
|---|---|---|
| Backup check | Daily | `make backup-verify` |
| Restore drill | Monthly | `make restore-drill` |
| Dependency audit | Weekly (CI nightly) | — |
| Rotate JWT key | 90 days | `saq admin rotate-jwt` |
| Runner cert renewal | Automatic at day 20 | check `saq runner list` |
| Learning report review | Weekly | `saq learn report` |

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
