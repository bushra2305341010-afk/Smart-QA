# 11 · Load Balancing and Scaling

Smart QA has four very different loads. Each scales separately.

| Load | Shape | Bottleneck | Scales by |
|---|---|---|---|
| Web/API requests | Many short requests, SSE streams | CPU, DB connections | API replicas behind a load balancer |
| AI stage jobs | Few long jobs (seconds–minutes) | Model rate limits, tokens | Worker count per queue + gateway concurrency |
| Test execution | Many browser sessions | CPU/RAM per browser | Runner count × browsers per runner |
| Evidence I/O | Large blobs | Bandwidth, storage | Direct presigned upload to object store |

## 1. Topology (team / hosted mode)

```
                ┌──────────── Load balancer (Traefik / NGINX, TLS 1.3) ────────────┐
Users ─HTTPS──▶ │  /           → web (static, CDN-cacheable)                        │
                │  /api/*      → api-1 … api-N   (least_conn)                       │
                │  /api/*/events → api (SSE, sticky not required)                   │
                │  /runner/v1  → api (WSS, long-lived, least_conn)                  │
                └──────────────────────────────────────────────────────────────────┘
api-N ─▶ PgBouncer ─▶ Postgres primary (+ read replica for reports)
api-N ─▶ Redis (queues, rate limits, SSE fan-out via pub/sub)
workers: q.understand │ q.plan │ q.design │ q.judge │ q.report │ q.export
runners (team network) ─outbound WSS─▶ LB
```

Laptop mode: the same containers, one replica each; NGINX in `deploy/nginx/` does the routing.

## 2. API tier

- **Stateless** replicas: sessions in signed cookies/JWT + DB; no in-memory state.
- Algorithm: `least_conn` (SSE and WSS hold connections for a long time, so round-robin would skew).
- SSE fan-out: each replica subscribes to Redis channel `project:{id}`; any replica can serve any client → no sticky sessions.
- Health: `/healthz` (process alive) for liveness, `/readyz` (DB + Redis reachable) for the LB.
- Autoscale (k8s HPA, v1): CPU > 65% or p95 latency > 400 ms → +1 replica, min 2, max 10.
- Rate limiting at two layers: LB (per IP) and API (per user/project, Redis token bucket).

## 3. Worker tier (queues)

| Queue | Concurrency per worker | Why separate |
|---|---|---|
| `q.understand` | 2 | Heavy, long, high effort |
| `q.plan` | 4 | Short |
| `q.design` | 4 (batch API for > 100 cases) | Bursty |
| `q.judge` | 8 | Latency matters during a run |
| `q.report` / `q.export` | 4 | CPU (openpyxl, HTML) |

- Celery `prefetch_multiplier=1`, `acks_late=True` → fair dispatch, no lost jobs.
- **Priority:** judge > design > plan > understand > export during an active run.
- **Per-project fairness:** max in-flight jobs per project (default 4) so one big project cannot starve others.
- Scale signal: queue depth / age (KEDA in v1). Laptop: fixed.

## 4. Model Gateway load control

- Token-bucket limiter per provider + per model matching the account's rate limits (requests/min, input tokens/min, output tokens/min).
- Concurrency semaphore (default 8 in-flight calls).
- On `429`/`529`: exponential backoff with jitter, honour `retry-after`; circuit breaker opens after 5 consecutive failures for 60 s.
- Load shedding: when saturated, low-priority stages (understand, export) wait; judge continues.
- Cost savers that are also load savers: prompt caching, replay cache, Message Batches for bulk design.

## 5. Runner pool

- Each runner advertises `{env_ids, max_browsers, labels}` at registration.
- Scheduler assigns jobs with **least-loaded first** among runners bound to the run's environment.
- One test = one isolated container + browser; a runner runs N in parallel (default 4).
- Sharding: run is split into shards by journey (keeps related cases together for cache warmth), each shard is a job.
- Missed heartbeats (3 × 10 s) → runner offline, its shards re-queued to another runner.
- Back-pressure: if the SUT returns many 5xx/timeouts, the scheduler reduces parallelism for that env (protects the user's server).

## 6. Database

- PgBouncer (transaction pooling), API pool size 10 per replica.
- Read replica for reports, exports, cost dashboards.
- Heavy writes (evidence metadata) batched per step group.
- Partition `audit_event`, `model_call`, `evidence` by month when > 10M rows.

## 7. Evidence

- Runner uploads directly to MinIO/S3 with presigned PUT URLs → no blob traffic through the API.
- Downloads via short-lived presigned GET; static web assets via CDN in hosted mode.

## 8. Capacity rule of thumb (MVP laptop)

| Resource | Supports |
|---|---|
| 8 vCPU / 16 GB laptop | 1 API, 2 workers, 1 runner × 4 browsers |
| 50 replayed tests | < 10 min |
| Concurrent UI users | ~10 |

## 9. Load tests for our own platform

- k6 script `tests/load/api.js`: 50 VUs, 10 min, mixed reads + run starts; p95 < 400 ms, error rate < 1%.
- Runner soak: 500 cases on 2 runners; no leaked containers, memory flat.
