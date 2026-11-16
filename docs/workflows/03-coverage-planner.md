# Sector 03 · Coverage Planner

**Features:** F08 counts with reasons, N12 risk score, F07 coverage map, F09 plan approval (Gate 2), N13 cost/time estimate, N14 Must/Should/Could.
**Owner:** Nadia · Support: Stuti

## Flow

```
approved graph ─▶ for each journey: techniques table (pure function)
              ─▶ risk score (pure function) ─▶ multiplier 0.7–1.5 ─▶ suggested count
              ─▶ Planner LLM writes human reasons + segment names (no numbers!)
              ─▶ cost estimate (count_tokens) ─▶ plan (draft) ─▶ user edits ─▶ Gate 2
```

Numbers come from code; the model only writes the explanation. This keeps counts deterministic and testable.

## Code map

| Concern | Path |
|---|---|
| Techniques | `packages/planning/techniques.py` |
| Risk | `packages/planning/risk.py` |
| Cost estimate | `packages/planning/cost.py` → `model_gateway.count_tokens` |
| Worker | `apps/workers/planner/` |
| Gate 2 | `apps/api/routers/plans.py::approve` |
| UI | `apps/web/src/features/plan/` |

## Bug locator

| Symptom | Go to | What to fix |
|---|---|---|
| Count differs from table sum | `techniques.py` / multiplier rounding | Round once at the end |
| Boundary cases missing | `techniques.py` limit detection | Read min/max from Field/Rule attrs |
| Risk all equal | `risk.py` weights / missing inputs | Defaults for missing change frequency |
| Cost estimate 10× off | `cost.py` | Include cached context and output estimate |
| Edited count not saved as rule | `plans.py` PATCH → `project_rule` | v1 learning hook |
| Gate 2 passes with zero segments | `approve` | Validation |

## Change safety

- [ ] `make test-planner` (property tests on counts)
- [ ] Segment schema change → `make test-designer test-reporter` (Coverage sheet) + web regen
- [ ] Update §5 in `04-design.md` if formula changes
