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
| Analyst worker + prompts | `apps/workers/analyst/` |
| Explorer worker | `apps/workers/explorer/` |
| Graph schema / merge / diff | `packages/graph/{schema,merge,diff}.py` |
| Conflicts / ambiguity | `packages/graph/{conflicts,ambiguity}.py` |
| Brief | `apps/workers/analyst/brief.py` |
| Gate 1 | `apps/api/routers/graph.py::approve` |
| UI | `apps/web/src/features/graph/` (React Flow) |

## Contract

Node types: Role, Journey, Step, Screen, Field, Rule, Endpoint, Requirement, Conflict, Question. Every Rule has ≥ 1 verified citation. **Only approved nodes may drive expected results.**

## Bug locator

| Symptom | Go to | What to fix |
|---|---|---|
| Duplicate nodes | `merge.py` | Matching key / label normalisation |
| Rules without citations | Analyst structuring step | Schema requires citation; reject uncited |
| Explorer misses screens | Explorer log `budget_exhausted` / `policy_blocked` | Budget, start URLs, allow-list |
| Explorer clicked a "Delete" | **Critical** → `packages/policy` | Add pattern; add red-team page |
| Conflict false positives | `conflicts.py` | Comparison threshold; require both citations |
| Approve succeeds with rejected nodes pending | `graph.py::approve` | Server-side check all nodes reviewed |
| Graph canvas slow | `features/graph` | Virtualise, collapse by journey |

## Change safety

- [ ] `make test-graph test-explorer`
- [ ] Graph schema change → `make test-planner test-designer test-learn test-mcp` + web type regen
- [ ] Prompt change → `evals-small` (precision/recall)
- [ ] Policy change → `make redteam`
