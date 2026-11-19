# 12 · Reliability

## 1. Service level objectives (MVP)

| SLO | Target |
|---|---|
| API availability (team mode) | 99.5% monthly |
| API p95 latency (non-job endpoints) | < 400 ms |
| Run completes once started (excluding SUT down) | 99% |
| Lost jobs | 0 |
| Evidence integrity (hash check passes) | 100% |
| Run resume after crash | From last completed case (NFR-4) |

## 2. Failure modes and responses

| Failure | Detection | Response |
|---|---|---|
| API replica crash | LB health check | Traffic shifts; stateless, no data loss |
| Worker crash mid-job | `acks_late` + visibility timeout | Job re-delivered; idempotency key prevents duplicate writes |
| Redis restart | Connection error | Outbox republishes unpublished events; consumers reconnect and re-claim pending jobs (ADR-013) |
| Postgres down | `/readyz` fails | API returns 503; workers pause; runner buffers results (≤ 15 min) |
| Runner disconnect | 3 missed heartbeats | Shard re-queued; partially done cases skipped via `last_completed_case_id` |
| Model provider 429/5xx | Gateway | Backoff + jitter, circuit breaker, fallback model if project allows |
| Model returns invalid JSON | Pydantic | Retry ≤ 2 with error; then `Test Error` / `Unable to Verify` (never Pass) |
| Model refuses | `stop_reason` | Recorded, item routed to human queue |
| SUT down / 5xx storm | Runner | Reduce parallelism, then **Blocked: environment down** |
| CAPTCHA / MFA wall | Runner detectors | **Blocked** verdict, not Fail |
| Budget cap hit | Gateway pre-check | Pause run, notify, resume on raise |
| Disk full (evidence) | Metrics alert at 80% | Retention job, refuse new runs at 95% |

## 3. Core techniques

**Idempotency.** Every job has `key = sha256(job_type, entity_id, attempt_scope)`. Writes use `INSERT … ON CONFLICT DO NOTHING` on natural keys (`result(run_id, test_case_id, attempt)`).

**Transactional outbox.** Domain change + event row in the same DB transaction; a relay publishes to Redis and marks `published_at`. No "saved but never queued".

**Resumable runs.** After each case finishes, `run.last_completed_case_id` is updated in the same transaction as its result. On restart the orchestrator re-queues only cases after that point.

**Retries.** Exponential backoff with full jitter: base 2 s, cap 60 s, max 5 attempts for infra errors; 2 for model-schema errors; 0 for policy blocks.

**Timeouts.** Every external call has one: model 120 s (stream), tracker 15 s, SUT navigation 30 s, test case 5 min default, run 2 h default.

**Circuit breakers.** Model provider and tracker adapters: open after 5 consecutive failures, half-open after 60 s.

**Deterministic replay.** Passing runs make no model calls → model outages don't break regression runs.

**Flake handling.** Clean-context re-run before any Fail; Flaky never files a bug; flake rate tracked per journey.

## 4. Data durability

| Data | Durability |
|---|---|
| Postgres | Nightly dump (laptop); WAL + PITR, 7-day window (team) |
| Evidence | Object store with versioning off but write-once policy; SHA-256 verified on read |
| Audit ledger | Hash chain; `saq audit verify` in nightly job |
| Exports | Regenerable from DB + evidence |

RPO ≤ 24 h laptop, ≤ 5 min team. RTO ≤ 1 h team.

## 5. Observability

- **Traces:** OpenTelemetry across web → API → orchestrator → worker → gateway → runner; `trace_id` in every log line and error response.
- **Metrics:** request rate/errors/latency, queue depth & age, run duration, verdict mix, flake rate, tokens & cost, cache hit rate, runner count, browser crashes.
- **Logs:** JSON, redacted, with `project_id`, `run_id`, `job_id`, `trace_id`.
- **Dashboards:** Grafana (team), in-app run view (laptop).
- **Alerts:** API 5xx > 2% for 5 min; queue age > 10 min; runner offline during a run; budget 80%; audit verify fail; disk 80%.

## 6. Graceful degradation

| If this is down | Still works |
|---|---|
| Model provider | Replay runs, reports, exports, review of existing data |
| Tracker | Bugs stay confirmed locally; filing retried |
| Object store | Runs pause (evidence required); UI read-only |
| Redis | API reads work; new jobs return 503 |

## 7. Reliability tests

- Chaos script `tests/chaos/`: kill worker mid-job, kill runner mid-run, restart Redis, pause Postgres 30 s → assert no lost/duplicate results and run resumes.
- Contract tests for runner protocol.
- Nightly full eval doubles as a long-running stability test.
