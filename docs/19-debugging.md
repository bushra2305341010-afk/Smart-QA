# 19 · Debugging

## 1. First five minutes

1. **Get the `trace_id`** from the UI error toast, API error body, or log line.
2. **Find the sector**: [workflows/00-bug-triage-map.md](workflows/00-bug-triage-map.md) maps symptom → sector → folder.
3. **Open the trace** (Jaeger/Tempo or `saq debug trace <trace_id>`) to see which service failed.
4. **Read the logs** for that trace: `docker compose logs api worker orchestrator runner | grep <trace_id>`.
5. **Reproduce** with the smallest input (one case, one journey) — `saq run --case TC-CHK-007 --env local --debug`.

## 2. Tools

| Tool | Use |
|---|---|
| `saq debug trace <id>` | Prints the span tree with timings and errors |
| `saq debug run <run_id>` | Pipeline state, last completed case, stuck jobs |
| `saq debug job <job_id>` | Celery job args, attempts, last error |
| `saq debug model-call <id>` | Prompt version, redacted inputs, raw output, validation errors, tokens, cost |
| `saq debug replay <model_call_id>` | Re-run the same model call (stub or live) |
| `saq audit verify --project prj_1` | Check hash chain |
| Playwright trace viewer | `npx playwright show-trace evidence/<sha>.zip` |
| MinIO console | http://localhost:9001 — evidence objects |
| Flower | http://localhost:5555 — Celery queues |
| `psql` | `docker compose exec db psql -U saq_app saq` |
| React Query Devtools | Bottom-left in dev web app |
| `LOG_LEVEL=debug` | Verbose logs (still redacted) |

## 3. Common problems

| Symptom | Likely cause | Where to look | Fix |
|---|---|---|---|
| Run stuck at "Execute" | Runner offline / no runner bound to env | `saq debug run`, runner logs | Start/re-register runner, check env binding |
| All cases **Blocked** | SUT down, wrong base URL, allow-list missing host | Runner logs, env settings | Fix URL / allowed_hosts |
| Cases **Unable to Verify** spike | Source text changed, offsets stale, parser bug | `citations` logs, `node_citation.status` | Re-ingest source; check parser version |
| Many **Flaky** | SUT slow, timeouts too tight, shared test data | Evidence timings, HAR | Raise per-env timeout, isolate data |
| **Test Error** on many cases | UI changed, locator strategy weak | Compiler output, heal proposals | Approve heals; prefer role/label locators |
| Model output invalid JSON | Prompt/schema drift | `saq debug model-call` | Fix schema/prompt, bump version, run evals |
| Graph missing screens | Explorer step budget hit, policy blocked nav | Explorer log "budget_exhausted"/"policy_blocked" | Raise budget, add start URLs, adjust allow-list |
| `BUDGET_EXCEEDED` | Cap too low / cache misses | `model_call` table, cache hit metric | Raise cap; check volatile data before cache breakpoint |
| Cache hit rate ~0 | Timestamp/run ID inside cached prefix | Prompt assembly | Move volatile parts after last breakpoint |
| 403 on approve | Role lacks permission / wrong project | API logs, membership | Assign role |
| SSE not updating UI | Proxy buffering | NGINX config | `proxy_buffering off;` for `/events` |
| Excel opens with errors | Invalid chars / formula injection | Exporter logs | Sanitise cells starting with `= + - @` |
| GitHub filing fails | Token scope / repo not allowed | Tracker adapter logs | Fix token scopes |
| Duplicate results after crash | Missing idempotency key | `result` unique index errors | Ensure job key + ON CONFLICT |

## 4. Debugging AI behaviour

1. Pull the call: `saq debug model-call <id>` — check prompt version, input size, cache usage, `stop_reason`.
2. Is the problem **input** (wrong chunks retrieved) or **reasoning** (right chunks, wrong output)?
   - Input → check retrieval query, chunking, graph approval state.
   - Reasoning → add a failing eval case first, then change the prompt, bump version, run evals.
3. Never "fix" by loosening a guardrail (quote check, policy). Fix the cause.

## 5. Debugging the runner

```bash
saq run --case TC-CHK-007 --env local --headed --slowmo 300   # watch the browser (dev only)
PWDEBUG=1 uv run pytest generated/tests/test_checkout.py -k 007 # Playwright inspector
```
Check container limits (`docker stats`), DNS from inside the container, and that egress allow-list includes the SUT host.

## 6. After the fix

- Failing test added and now green.
- Sector doc's bug-locator table updated if this was a new kind of bug.
- Dev-log entry: symptom, root cause, fix, prevention.
