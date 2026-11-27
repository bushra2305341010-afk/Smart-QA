# Runner

Executes compiled test cases in a real browser inside the team network (sector 05, M10).
Outbound only: it calls the control plane; nothing calls it.

| | |
|---|---|
| Design doc | docs/workflows/05-executor-and-runner.md, docs/06-api.md §5 |
| Module | M10 (T-103 registration) |

## Run

```bash
# 1. Register (Owner / QA Lead): returns the token once
curl -X POST $API/projects/$PID/runners -d '{"name":"laptop"}' ...
# 2. Start
SAQ_API_URL=http://127.0.0.1:8000/api/v1 SAQ_RUNNER_TOKEN=saq_run_... \
SAQ_BROWSER_CHANNEL=chrome SAQ_SECRET_PASSWORD=... uv run python -m apps.runner
```

## Files

- `main.py`: protocol client (`RunnerClient`), `run_job` (fresh browser context + trace per job), loop.
- `executor.py`: `CaseRunner` runs one `CompiledCase` (plan lock); screenshot per step in `finally`.
- `policy_hook.py`: `packages.policy.check` before every action (on the live element) and every request (route guard).
- `detectors.py`: CAPTCHA / MFA / bot wall / login wall / environment down → Blocked.
- `secrets.py`: `{{secret:name}}` resolved on the runner only (`SAQ_SECRET_<NAME>`), masked in uploads.
- `vault.py`: encrypted vault for `{{secret:name}}` (T-203); `saq vault set NAME` on the runner machine.
- `evidence.py`: SHA-256 content addresses; uploaded before the result references them.
