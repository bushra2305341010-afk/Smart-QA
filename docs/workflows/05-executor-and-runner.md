# Sector 05 · Executor and Runner

**Features:** F20 compile to Playwright, N17 replay cache, F21 evidence per step, F15 web execution, F16 API tests, F18 local server access, F19 heal proposals, F25 accessibility scan, N18 safe-action policy, N19 Blocked verdict.
**Owner:** Stuti · Support: Nadia

## Flow

```
approved cases ─▶ Compiler: template + locator fill ─▶ lint + import allow-list
   ─▶ generated/tests/*.py committed to user's repo branch (optional)
   ─▶ scheduler shards by journey ─▶ runner pulls job (WSS mTLS)
   ─▶ per test: fresh container + browser ─▶ policy check every action
   ─▶ evidence per step (screenshot, trace, HAR, console, video) ─▶ sha256 ─▶ presigned PUT
   ─▶ result ─▶ run.last_completed_case_id ─▶ Judge
```

## Code map

| Concern | Path |
|---|---|
| Compiler | `apps/workers/compiler/` (Jinja templates in `templates/`) |
| Scheduler | `apps/orchestrator/scheduler.py` |
| Runner main / protocol | `apps/runner/{main,protocol}.py` |
| Sandbox | `deploy/runner.Dockerfile`, `apps/runner/sandbox.py` |
| Evidence capture | `apps/runner/evidence.py` |
| Policy hook | `apps/runner/policy_hook.py` → `packages/policy` |
| Blocked detectors | `apps/runner/detectors.py` (CAPTCHA, MFA, bot wall) |
| Healer | `apps/workers/healer/` |
| A11y | `apps/runner/a11y.py` (axe-core) |

## Bug locator

| Symptom | Go to | What to fix |
|---|---|---|
| Compiled test fails import check | Compiler template | Allowed imports list |
| Locator flaky | Compiler locator strategy | Prefer `get_by_role`/`get_by_label` over CSS |
| Evidence missing for a step | `evidence.py` | Capture in `finally`; upload retry |
| Hash mismatch on read | Upload path | Hash before upload, verify after |
| Container leak | `sandbox.py` | Always remove in `finally`; soak test |
| Second run still calls model | Replay cache key | Volatile input in key |
| Off-domain navigation | `policy_hook.py` | **Critical**: add test + red-team page |
| CAPTCHA counted as Fail | `detectors.py` | Add detector signature |

## Change safety

- [ ] `make test-runner test-compiler test-policy`
- [ ] Protocol change → bump `runner/v2`, keep v1 for one release, `make test-contract`
- [ ] `make redteam` + `make golden`
- [ ] Chaos: kill runner mid-run, assert resume
