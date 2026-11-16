# 04 · Software Design

How the code is shaped so that each part can change without breaking the others.

## 1. Module boundaries (domain-driven)

| Domain module | Owns tables | Public service (only entry point) | Depends on |
|---|---|---|---|
| `projects` | project, environment, member | `ProjectService` | auth |
| `sources` | source, chunk | `SourceService` | citations, storage |
| `graph` | graph_version, node, edge, node_citation | `GraphService` | sources |
| `plans` | plan, segment | `PlanService` | graph |
| `cases` | test_case, step | `CaseService` | plans, citations |
| `runs` | run, result, evidence | `RunService` | cases, runner protocol |
| `verdicts` | verdict | `VerdictService` | runs |
| `bugs` | bug | `BugService` | verdicts, integrations |
| `audit` | audit_event | `AuditService` (append only) | — |
| `billing` | model_call, budget | `CostService` | — |

Rules:
1. Another module never queries your tables directly; it calls your service.
2. Services return Pydantic DTOs, never ORM objects.
3. Cross-module side effects go through **domain events** (`GraphApproved`, `PlanApproved`, `RunFinished`, `BugConfirmed`) published by the orchestrator.

## 2. Key interfaces (plug-in boundaries)

```python
class ModelProvider(Protocol):
    def generate(self, task: TaskSpec, inputs: Inputs) -> ModelResult: ...
    def count_tokens(self, task: TaskSpec, inputs: Inputs) -> int: ...

class ExecutionEngine(Protocol):          # Playwright today; Appium/Maestro MCP later
    def run(self, job: RunJob, emit: EvidenceSink) -> RunResult: ...
    def explore(self, start: ExploreSpec, policy: ActionPolicy) -> CrawlResult: ...

class TrackerAdapter(Protocol):           # GitHub, Jira
    def find_duplicates(self, bug: BugDraft) -> list[TicketRef]: ...
    def file(self, bug: ConfirmedBug) -> TicketRef: ...

class EvidenceStore(Protocol):            # MinIO, S3, local disk
    def put(self, data: bytes, kind: str) -> EvidenceRef: ...   # returns sha256 key
    def get(self, ref: EvidenceRef) -> bytes: ...
```

Adding a new provider / engine / tracker = one new adapter class + its contract tests. No change to stage workers.

## 3. Patterns used

| Pattern | Where | Why |
|---|---|---|
| State machine | Orchestrator | Gates, resume after crash, audit |
| Strategy / adapter | Model, engine, tracker, storage | Swap without touching callers |
| Pipeline of pure functions | Citations, coverage formula, verdict rules | Deterministic, 100% testable |
| Outbox | Domain events → queue | No lost jobs if Redis restarts |
| Idempotent job keys | All Celery tasks | Safe retries |
| Content addressing | Evidence | Tamper evidence, dedup |
| Hash chain | Audit ledger | Non-repudiation |
| CQRS-lite | Run dashboard reads from materialised `run_summary` | Fast UI under load |

## 4. Core data contracts

**Citation** (shared by graph rules, expected results, bugs)
```json
{ "source_id": "src_8f2", "start_offset": 10342, "end_offset": 10398,
  "quote": "Cards expiring in the current month must be accepted.",
  "location": { "file": "PRD-v3.pdf", "page": 12, "line": 4 },
  "status": "verified" }
```
`status` is set only by `citations.verify(quote, source_text[start:end])` — a plain string comparison.

**Test case**
```json
{ "id": "TC-CHK-007", "journey": "Checkout", "segment": "Payment validation",
  "role": "Registered customer", "technique": "boundary", "priority": "Must",
  "preconditions": ["Cart has 1 item", "User logged in"],
  "steps": [{"n":1,"action":"Open checkout","node_id":"scr_checkout"}],
  "data": {"card":"test-visa","expiry":"12/2026"},
  "expected": {"text":"Payment form accepts the card","citation":{...}},
  "requirement_id": "REQ-PAY-03" }
```

**Verdict**
```json
{ "result_id": "res_91", "verdict": "fail", "confidence": "high",
  "reason": "Failed twice; POST /api/payments 422 both times",
  "rule": "J3-same-failure-twice", "evidence": ["sha256:ab12…"] }
```

## 5. Coverage count design

Suggested count per segment = Σ technique rows, × risk multiplier (0.7 – 1.5).

| Technique | Rule |
|---|---|
| Happy path | 1 per role that can use the journey |
| Equivalence classes | 1 per valid/invalid class of each input |
| Boundary values | 2 per numeric/length limit |
| Negative & permission | 1 per forbidden role or state |
| State transition | 1 per important transition |
| Accessibility | 1 scan per screen |

Risk score = weighted sum of business criticality, rule count, input count, change frequency, past defects. Formula in `packages/planning/risk.py`, weights in project settings.

## 6. Error design

- Domain errors are typed (`GateNotApproved`, `CitationUnverified`, `BudgetExceeded`, `PolicyBlocked`) and map to stable API error codes (see [06-api.md](06-api.md)).
- Workers never swallow errors: they mark the job `failed` with `error_code` and `trace_id`.
- Model failures (`stop_reason` refusal, invalid JSON) are retried twice with the validation error appended, then surfaced as `Test Error` / `Unable to Verify`, never as Pass.

## 7. Configuration

Precedence: defaults in code → `settings.yaml` → env vars → per-project settings in DB. All settings typed with Pydantic `BaseSettings`.
