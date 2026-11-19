# Sector 02 · Product Understanding Graph

**Features:** F05 build graph, F04 UI explorer, N05 code analyzer, N06 document analyzer, N07 spec conflict finder, N08 ambiguity checker, N09 human review (Gate 1), N10 brief, N11 graph diff (v1).
**Owner:** Nadia · Support: Stuti

## Flow

```
chunks + code facts ──▶ Analyst call 1 (cited extraction) ──▶ Analyst call 2 (structure to schema)
                                                   │
Explorer tool loop (≤150 steps, policy-checked) ───┤
                                                   ▼
                        packages/graph/merge.py (dedupe by type+label+source)
                                                   ▼
             conflict finder (doc says X, code/UI says Y) · ambiguity checker
                                                   ▼
                    graph_version (draft) ─▶ UI review ─▶ Gate 1 approve
```

## Code map

| Concern | Path |
|---|---|
| Extraction contract (what the model returns) | `packages/contracts/graph.py` |
| Analyst worker + prompt (`analyst@1.0.0`) | `apps/workers/analyst.py` (`job.understand`), gateway wiring `apps/workers/gateway.py` |
| Explorer worker | `apps/workers/explorer/` (M09c) |
| Merge / quote check / build | `packages/graph/{model,merge,cite,build}.py` |
| Conflicts / ambiguity | `packages/graph/{conflicts,ambiguity}.py` (deterministic code) |
| Diff, brief | v1 |
| Graph API, node review, Gate 1 | `apps/api/routers/graph.py` (`approve_graph`) |
| UI | `apps/web/src/features/graph/` (React Flow) |

## Contract

Node types: Role, Journey, Step, Screen, Field, Rule, Endpoint, Requirement, Conflict, Question. Every Rule has ≥ 1 verified citation. **Only approved nodes may drive expected results.**

**Implementation (M09b).** One structured call per source window (≤ 40k chars, the source sent as untrusted data) returns `Extraction`: nodes with an exact `quote`, edges. Then code, not the model, decides what is true:
- `merge`: same type + normalised label → one node (stable key `<type>:<label>`).
- `cite`: every quote is checked with `verify_quote` against the stored normalised text; a Rule/Requirement with no verified quote becomes a **Question** "Could not verify …" (never a silent rule).
- `conflicts`: Rules with the same `subject` but different `value`, cited from different sources → **Conflict** citing both.
- `ambiguity`: vague words ("fast", "easy", "appropriate", …) in a Rule/Requirement → **Question**.
The result is saved as a new **draft** version; each review decision (approve / reject / edit) writes a `feedback` row (human-confirmed label) and an audit event. Gate 1 refuses while any node is pending (409 lists them), supersedes the previous approved version, and moves the pipeline in the same transaction. The docs' two-call design (cited extraction → structuring) is replaced by one schema-bound call plus the code quote check, which is the actual guarantee.

## Bug locator

| Symptom | Go to | What to fix |
|---|---|---|
| Duplicate nodes | `merge.py` | Matching key / label normalisation |
| Rules without citations | Analyst structuring step | Schema requires citation; reject uncited |
| Explorer misses screens | Explorer log `budget_exhausted` / `policy_blocked` | Budget, start URLs, allow-list |
| Explorer clicked a "Delete" | **Critical** → `packages/policy` | Add pattern; add red-team page |
| Conflict false positives | `conflicts.py` | Comparison threshold; require both citations |
| Approve succeeds with nodes pending | `routers/graph.py::approve_graph` | Server-side check all nodes reviewed |
| Every rule became "Could not verify" | `packages/graph/cite.py`, redaction | Model paraphrased instead of quoting, or redaction masked text inside the quote |
| Citation line number off | `routers/graph.py` line calc | Line = chunk line + newlines before the quote in the chunk |
| Graph canvas slow | `features/graph` | Virtualise, collapse by journey |

## Change safety

- [ ] `tests/graph/`, `tests/workers/test_analyst_int.py`
- [ ] Graph schema change → `make test-planner test-designer test-learn test-mcp` + web type regen
- [ ] Prompt change → `evals-small` (precision/recall)
- [ ] Policy change → `make redteam`
