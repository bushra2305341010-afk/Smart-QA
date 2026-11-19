# Sector 12 · Orchestrator (pipeline engine)

**Responsibility:** state machine, gate enforcement, job dispatch, retries, budgets, resume, outbox relay.
**Owner:** Shared · Flow: [../03-system-workflow.md](../03-system-workflow.md)

## Flow

```
API action ─▶ orchestrator.transition(run, event) ─▶ guard (gate signed? budget ok? role ok?)
   ─▶ write pipeline_state + audit_event + outbox (one transaction)
   ─▶ relay publishes job to queue ─▶ worker ─▶ result event ─▶ next transition
crash/restart ─▶ scan non-terminal states ─▶ re-dispatch idempotent jobs ─▶ resume
```

## Code map

| Concern | Path |
|---|---|
| States & transitions | `apps/orchestrator/machine.py` (pure table) |
| Apply an event (lock, guard, write state + audit + outbox) | `apps/orchestrator/engine.py:transition` |
| Guards (gates, budget) | `apps/orchestrator/guards.py` |
| Outbox relay → Redis streams `saq:jobs` / `saq:events` | `apps/orchestrator/relay.py` |
| Recovery | `apps/orchestrator/recover.py` |
| Process (`python -m apps.orchestrator`, Compose `orchestrator`) | `apps/orchestrator/__main__.py` |
| HTTP | `apps/api/routers/pipeline.py` (`GET /projects/{id}/pipeline`, `POST …/pipeline/events`) |
| Scheduler (runner shards) | `apps/orchestrator/scheduler.py` (M10) |

## Bug locator

| Symptom | Go to | What to fix |
|---|---|---|
| Stage never advances | `relay.py` / Redis | Relay stopped (check `orchestrator` logs); `WORKER_DATABASE_URL` not `saq_worker` → RLS hides the outbox |
| Events arrive out of order | `db/outbox.py:enqueue` | `created_at` must be wall clock, not `now()` |
| 409 STATE_CONFLICT on a gate | `machine.py` table | Event not valid at current stage/status |
| Gate bypassed | **High** → `guards.py` | Guard missing on a transition |
| Job runs twice with two results | Idempotency key | Key scope / ON CONFLICT |
| Resume restarts from zero | `recover.py` | Read `last_completed_case_id` |
| Run never ends after all cases | Completion check | Count includes skipped/blocked |

## Change safety

- [ ] `tests/orchestrator/test_machine.py` (every stage × status × event) and `test_engine_int.py`
- [ ] `make golden` + chaos kill tests
- [ ] New state → update diagram in `03-system-workflow.md`
