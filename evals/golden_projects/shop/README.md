# Golden project 1: Shop

A small e-commerce product used to measure Smart QA, not to ship.

| File | Purpose |
|---|---|
| `PRD.md` | Requirements with numbered rules (REQ-…), roles and journeys |
| `openapi.yaml` | API description; deliberately disagrees with the PRD on the password maximum length (64 vs 128) |
| `expected_graph.json` | Hand-made graph: required and optional nodes with aliases, the exact quote of every rule, the expected conflict and the vague term ("fast") |

Seeded bugs for run/judge evaluation are listed only in `evals/private/` (git-ignored), so no model or test can learn them from the repo.

## Measure the graph

1. Create a project, upload `PRD.md` and `openapi.yaml`, start the pipeline and let the analyst build the graph.
2. Score it:

```bash
SAQ_URL=http://localhost:8000 SAQ_TOKEN=saq_pat_... \
uv run python -m evals.run_graph_eval --project prj_... --golden evals/golden_projects/shop
```

The scorer (`evals/scoring.py`) prints precision, recall, citation accuracy, whether the conflict and the vague-term question were found, and the missing / unmatched nodes. Exit code 0 means the targets in docs/08 §6 are met (precision ≥ 0.80, recall ≥ 0.75, citation accuracy ≥ 0.90). Record results in docs/20 §4.
