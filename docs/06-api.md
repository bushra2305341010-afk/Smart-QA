# 06 · API

Graph routes are nested under `/projects/{id}` (so row-level security is scoped before any lookup); plan, run and bug routes will follow the same pattern.

Base URL: `/api/v1` · JSON · OpenAPI at `/api/v1/openapi.json` · Auth: session cookie (web) or bearer token (CLI/MCP/CI).

## 1. Conventions

| Topic | Rule |
|---|---|
| IDs | Prefixed strings `<prefix>_<32 hex>`: `usr_`, `prj_`, `src_`, `chk_`, `env_`, `idn_`, `tok_`, `gv_`, `nod_`, `pln_`, `seg_`, `tc_`, `run_`, `res_`, `ver_`, `bug_` (`apps/api/ids.py`). Malformed or wrong-prefix IDs → 404 |
| Timestamps | ISO 8601 UTC |
| Pagination | `?limit=50&cursor=…` → `{ items, next_cursor }` (limit 1–200; cursor is opaque) |
| Long jobs | Return `202 Accepted` + `{ job_id }`; progress over SSE |
| Idempotency | `Idempotency-Key` header on all POSTs that start jobs |
| Versioning | Breaking change → `/api/v2`; additive changes allowed in v1 |
| Rate limits | 600 req/min per user, 30 job starts/min per project; `429` with `Retry-After` |

## 2. Error format

```json
{ "error": { "code": "GATE_NOT_APPROVED", "message": "Plan pln_12 is not approved",
  "details": {"gate": 2}, "trace_id": "4bf92f35..." } }
```

| HTTP | Code | Meaning |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Body or params invalid |
| 401 | `UNAUTHENTICATED` | No / expired / revoked session or token |
| 403 | `CSRF_FAILED` | Cookie request changing state without matching `X-CSRF-Token` |
| 409 | `EMAIL_TAKEN` | Register with an existing email |
| 503 | `UNAVAILABLE` | Database not configured / reachable |
| 403 | `FORBIDDEN` | Role lacks permission |
| 404 | `NOT_FOUND` | Resource missing or not in your project |
| 409 | `GATE_NOT_APPROVED` | Earlier gate not signed |
| 409 | `STATE_CONFLICT` | Wrong pipeline state for this action |
| 402 | `BUDGET_EXCEEDED` | Budget cap reached |
| 422 | `CITATION_UNVERIFIED` | Quote does not match source |
| 423 | `POLICY_BLOCKED` | Safe-action policy refused |
| 429 | `RATE_LIMITED` | Slow down |
| 502 | `UPSTREAM_ERROR` | Model or tracker failed |

## 3. Endpoints

### Auth & users
| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/auth/register` | public | Create account |
| POST | `/auth/login` | public | Password (+ TOTP) → session |
| POST | `/auth/logout` | any | End session |
| POST | `/auth/refresh` | any | Rotate refresh token |
| GET | `/me` | any | Profile, roles, feature flags |
| POST | `/tokens` | any | Create personal API token (CLI/CI); `{name, scopes:[read,write], expires_in_days}`; token shown once |

### Projects & sources
| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/projects` | Owner | Create project |
| GET | `/projects` | any | My projects with my role |
| GET | `/projects/{id}` | Viewer+ | Project detail + pipeline state |
| POST | `/projects/{id}/members` | Owner | Add member with role (`{email, role}`) |
| GET | `/projects/{id}/members` | Viewer+ | Members and roles |
| POST | `/projects/{id}/sources` | QA Lead+ | Register a source `{kind, uri, sha256}` (JSON, M08b); upload/multipart with M09 |
| POST | `/projects/{id}/sources/upload` | QA Lead+ | Multipart `file` (PDF, DOCX, Markdown, OpenAPI JSON/YAML; ≤ 50 MB; type from magic bytes). 201 new, 200 if the same bytes exist; 413 `PAYLOAD_TOO_LARGE`, 415 `UNSUPPORTED_TYPE`, 503 if storage is not configured |
| GET | `/projects/{id}/sources` | Viewer+ | Sources (paginated; `status`, `filename`, `size`, `error`) |
| GET | `/projects/{id}/sources/{sid}/chunks` | Viewer+ | Chunks with offsets |
| POST | `/projects/{id}/environments` | QA Lead+ | Add env (url, kind, safe flags); `kind=production` needs Owner; base URL host is added to `allowed_hosts` |
| GET | `/projects/{id}/environments` | Viewer+ | Environments |
| POST | `/projects/{id}/identities` | QA Lead+ | Add test identity (stored in vault, write-only) |
| GET | `/projects/{id}/data-sharing` | Viewer+ | What leaves the machine under current model policy |

### Understanding (graph)
| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/projects/{id}/understand` | QA Lead+ | Start graph build → 202 |
| GET | `/projects/{id}/graph` | Viewer+ | Graph versions with node / pending counts |
| GET | `/projects/{id}/graph/{gv}` | Viewer+ | Nodes, edges, citations (quote, file, page, line); `?type=Conflict` / `Question` / `Rule` … |
| PATCH | `/projects/{id}/graph/{gv}/nodes/{nid}` | QA Lead+ | `{review_status: approved|rejected|edited, label?}` (draft only) |
| POST | `/projects/{id}/graph/{gv}/approve` | QA Lead | **Gate 1**: 409 `GATE_NOT_APPROVED` with `pending_node_ids` while any node is pending; 409 `STATE_CONFLICT` if the pipeline is not at graph review |
| GET | `/projects/{id}/brief` | Viewer+ | Product brief (markdown) of the approved graph: roles, journeys with steps, quoted rules, endpoints, open questions, conflicts |

### Plans & cases
| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/projects/{id}/plans` | Viewer+ | Plans (the planner stage creates them; re-plan with pipeline event `plan_edited`) |
| GET | `/projects/{id}/plans/{pln}` | Viewer+ | Segments (riskiest first) with technique rows + reasons, counts, priority, cost estimate, totals |
| PATCH | `/projects/{id}/plans/{pln}/segments/{seg}` | QA Lead | `{approved_count}` (0–500, draft only) |
| POST | `/projects/{id}/plans/{pln}/approve` | QA Lead | **Gate 2**: 409 if total = 0 or graph no longer approved, 402 if estimate > remaining budget, 409 `STATE_CONFLICT` if the pipeline is not at plan approval |
| GET | `/projects/{id}/cases` | Viewer+ | Cases of the approved plan (`?review_status=`, `?segment_id=`, paginated), with steps and citation |
| GET | `/projects/{id}/cases/{tc}` | Viewer+ | One case |
| PATCH | `/projects/{id}/cases/{tc}` | Tester+ | Edit title / preconditions / steps / data of a pending case (→ `edited`); expected result is not editable |
| POST | `/projects/{id}/cases/review` | Tester+ | `{case_ids, decision: approved|rejected}`; 422 `CITATION_UNVERIFIED` if any case to approve lacks a verified quote |
| POST | `/projects/{id}/cases/approve` | Tester+ | **Gate 3**: 409 while any case is pending or none is approved |

### Runs, verdicts, bugs
| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/projects/{id}/runs` | Tester+ | Start run (`env_id`, `scope`) → 202 |
| GET | `/runs/{id}` | Viewer+ | Status, counts, verdicts |
| GET | `/runs/{id}/results` | Viewer+ | Per-case results |
| GET | `/results/{id}/evidence` | Viewer+ | Signed evidence URLs + hashes |
| POST | `/results/{id}/heal/approve` | QA Lead | Accept locator diff |
| GET | `/projects/{id}/bugs` | Viewer+ | Bugs (`?status=`, `?run_id=`) |
| PATCH | `/projects/{id}/bugs/{bug}` | Tester+ | Edit a draft's title / severity / body |
| GET | `/projects/{id}/bugs/{bug}/duplicates` | Viewer+ | Similar open tracker issues + same-case bugs (502 `UPSTREAM_ERROR` if the tracker fails) |
| POST | `/projects/{id}/bugs/{bug}/confirm` | QA Lead | Confirm a draft |
| POST | `/projects/{id}/bugs/{bug}/dismiss` | QA Lead | `{reason}`; a learning label |
| POST | `/projects/{id}/bugs/approve` | QA Lead | **Gate 4**: 409 with `bug_ids` while drafts remain; the report stage then files confirmed bugs |
| GET | `/projects/{id}/runs/{run}/export.xlsx` | Viewer+ | Six-sheet workbook |
| GET | `/projects/{id}/runs/{run}/evidence-pack` | Viewer+ | HTML evidence pack, downloaded as an attachment |

### Pipeline
| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/projects/{id}/pipeline` | Viewer+ | Current stage/status + history |
| POST | `/projects/{id}/pipeline/events` | per event | `{event}`: `start`/`retry`/`cancel` (QA Lead+), gate decisions `graph_approved`, `graph_rejected`, `plan_approved`, `plan_edited`, `cases_approved`, `bugs_confirmed` (permission per docs/10 §4). Worker events are not accepted over HTTP. Errors: 409 `STATE_CONFLICT`, 409 `GATE_NOT_APPROVED`, 402 `BUDGET_EXCEEDED`, 403 `FORBIDDEN` |

### Admin & ops
| Method | Path | Purpose |
|---|---|---|
| GET | `/projects/{id}/audit` | Audit ledger (verify chain with `?verify=true`) |
| GET | `/projects/{id}/costs` | Viewer+: this month spent/cap/remaining, per stage (calls, replay-cache hits, cost), top 50 runs, last 12 months |
| PUT | `/projects/{id}/budget` | Owner (`budget.manage`): `{monthly_usd}`; audited as `budget.changed` |
| GET | `/healthz`, `/readyz` | Liveness / readiness |
| GET | `/metrics` | Prometheus (internal network only) |

## 4. Server-Sent Events

`GET /projects/{id}/events` (text/event-stream)

| Event | Payload |
|---|---|
| `stage.changed` | `{ stage, status, run_id? }` |
| `job.progress` | `{ job_id, done, total, message }` |
| `result.created` | `{ result_id, case_id, verdict? }` |
| `verdict.created` | `{ result_id, verdict, confidence }` |
| `bug.drafted` | `{ bug_id, severity }` |
| `budget.warning` | `{ used, cap }` |

## 5. Runner protocol (internal, WSS + mTLS)

`wss://<control-plane>/runner/v1` · messages are JSON:
`register` → `heartbeat` (10 s) → `job.pull` → `job.accepted` → `log` (stream) → `evidence.upload` (presigned PUT) → `result` → `job.done`.
Missed 3 heartbeats → runner marked offline, its jobs re-queued.

## 6. Example

```bash
curl -X POST https://localhost/api/v1/projects/prj_1/runs \
  -H "Authorization: Bearer $SAQ_TOKEN" -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{"env_id":"env_staging","scope":{"journeys":["Checkout"]}}'
# → 202 {"job_id":"job_77","run_id":"run_42"}
```
