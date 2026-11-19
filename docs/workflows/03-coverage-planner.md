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

**Implementation (planner stage).** The worker makes no model call: technique reasons come from `technique_rows`, so the plan is free and fully reproducible (an LLM paraphrase of the reasons can be added later). Rejected graph nodes are ignored. Each segment stores its rows, base count, multiplier and risk inputs in `segment.techniques`. Gate 2 approves unedited segments at their suggested count, refuses an empty plan, a plan whose graph is no longer approved, and an estimate above the remaining monthly budget (402), then supersedes the previous approved plan and moves the pipeline in the same transaction. Segment edits write `feedback` rows (learning labels).

## Code map

| Concern | Path |
|---|---|
| Contracts | `packages/contracts/plan.py` — `JourneySpec`, `InputField`, `Limit`, `RiskInputs`, `RiskWeights`, `TechniqueRow`, `SegmentPlan`, `PriceTable`, `CostAssumptions`, `CostEstimate` |
| Techniques | `packages/planning/techniques.py` — `technique_rows()` |
| Risk + priority | `packages/planning/risk.py` — `risk_score()`, `priority_for()` (Must ≥ 0.66, Should ≥ 0.33, else Could) |
| Counts | `packages/planning/counts.py` — `suggest_segment()`, `multiplier_for()` (0.7 → 1.5), half-up rounding once, never below one per role |
| Cost estimate | `packages/planning/cost.py` — `estimate_design_cost()`; prices come from a `PriceTable` passed in (load from settings, verify against the provider's price page). Later: exact counts via `model_gateway.count_tokens` |
| Graph → planner inputs | `packages/planning/from_graph.py` — `journeys_from_graph()` (roles via `performs`, steps/screens/fields via edges, limits from Rule attrs `min`/`max`/`value`, `forbidden_roles`, `transition`; Journey attrs `criticality`, `change_frequency`) |
| Worker (`job.plan`, no model call) | `apps/workers/planner.py` |
| Plan API, segment edits, Gate 2 | `apps/api/routers/plans.py` (`approve_plan`) |
| Prices / cost estimate | `apps/api/pricing.py` (`prices_for`, `cost_estimate`) |
| UI | `apps/web/src/features/plan/` |

## Bug locator

| Symptom | Go to | What to fix |
|---|---|---|
| Count differs from table sum | `techniques.py` / multiplier rounding | Round once at the end |
| Boundary cases missing | `techniques.py` limit detection | Read min/max from Field/Rule attrs |
| Risk all equal | `risk.py` weights / missing inputs | Defaults for missing change frequency |
| Cost estimate 10× off | `cost.py` | Include cached context and output estimate |
| Edited count not saved as rule | `plans.py` PATCH → `project_rule` | v1 learning hook |
| Gate 2 passes with zero segments | `approve_plan` | Refuses total < 1 (409 gate 2) |
| Range "8-64" read as -64 | `from_graph.py` `_NUMBER` | A "-" after a digit is a range dash |
| Gate 2 402 although budget is fine | `plans.py` budget check | Estimate vs *remaining* month budget; settings must be read for this project id |
| Low-risk journey lost its happy paths | `counts.py::suggest_segment` floor | Count must be ≥ happy-path rows |
| 12.5 rounded to 12 | `counts.py::_round_half_up` | Half-up after `round(x, 6)`, never Python's banker's `round()` |

## Change safety

- [ ] `uv run pytest tests/planning --cov=packages/planning --cov=packages/contracts` → 100% branches; the Login example must stay at base 10
- [ ] Segment schema change → `make test-designer test-reporter` (Coverage sheet) + web regen
- [ ] Update §5 in `04-design.md` if formula changes
