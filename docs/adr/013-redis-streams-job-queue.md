# ADR-013: Redis Streams consumer groups for job dispatch instead of Celery

**Status:** Accepted · **Date:** 2026-11-20 · Supersedes the "Celery" part of the stack table

## Context
Jobs are created by the transactional outbox (ADR-002, docs/12) with a stable `job_key`, and the orchestrator relay already publishes them to Redis. Celery would add a second message format, its own retry/ack semantics on top of ours, and a beat scheduler, while our state machine already owns retries, budgets and resume.

## Decision
The relay writes `job.<stage>` messages to the Redis stream `saq:jobs` (other events to `saq:events`). Each worker type reads with its own consumer group (`apps/workers/consumer.py`):
- acks a job only after the handler succeeds; failures stay pending and are re-claimed after an idle timeout (`XAUTOCLAIM`);
- skips a job whose `job_key` is already marked done (`saq:done:<group>:<key>`, 7 days), so redelivery and recovery are idempotent;
- acks topics it does not handle.

## Consequences
- One delivery mechanism, end to end at-least-once with idempotent handlers; no Celery dependency.
- Scheduled jobs (nightly training, retention) need a small scheduler later (cron container or `apps/workers` loop).
- Scaling = more consumers in the same group.

## Alternatives considered
Celery on Redis (the original plan): mature, but duplicates our retry/state logic and adds config surface. RQ / Dramatiq: same overlap.
