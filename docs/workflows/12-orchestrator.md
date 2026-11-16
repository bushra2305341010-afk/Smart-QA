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
| States & transitions | `apps/orchestrator/machine.py` |
| Guards | `apps/orchestrator/guards.py` |
| Outbox relay | `apps/orchestrator/outbox.py` |
| Scheduler (runner shards) | `apps/orchestrator/scheduler.py` |
| Recovery | `apps/orchestrator/recover.py` |

## Bug locator

| Symptom | Go to | What to fix |
|---|---|---|
| Stage never advances | `outbox.py` relay / queue | Relay stopped; unacked events |
| Gate bypassed | **High** → `guards.py` | Guard missing on a transition |
| Job runs twice with two results | Idempotency key | Key scope / ON CONFLICT |
| Resume restarts from zero | `recover.py` | Read `last_completed_case_id` |
| Run never ends after all cases | Completion check | Count includes skipped/blocked |

## Change safety

- [ ] `make test-orchestrator` (transition table tests: every state × event)
- [ ] `make golden` + chaos kill tests
- [ ] New state → update diagram in `03-system-workflow.md`
