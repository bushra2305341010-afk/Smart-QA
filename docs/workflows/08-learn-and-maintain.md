# Sector 08 · Learn and Maintain

**Features:** N27 regression memory (MVP basic), F10 change-impact selection (preview MVP, full v1), N26 learning from human decisions (v1), N28 model upgrade check (v1).
**Owner:** Shared

## Flow

```
run finished ─▶ update regression_memory per journey (last pass, flake rate, bugs)
human decision (dismissed bug, edited count) ─▶ project_rule (v1)
git diff / PR ─▶ map changed files → code facts → graph nodes → journeys ─▶ run affected first,
                 others "unchanged since last pass"
model switch ─▶ replay saved eval set on new model ─▶ show diff ─▶ owner approves
```

## Code map

| Concern | Path |
|---|---|
| Memory | `packages/memory/` |
| Impact | `packages/impact/{diff_map,select}.py` |
| Rules | `packages/learning/rules.py` |
| Model check | `evals/model_upgrade.py` |

## Self-learning (full design: [../21-self-learning-and-data-privacy.md](../21-self-learning-and-data-privacy.md))

```
gate decision ─▶ feedback row ─▶ lesson (pgvector)        ─▶ retrieved into prompts
                              └▶ nightly trainer (≥30 new labels) ─▶ candidate model
                                   ─▶ eval gate ─▶ active (registry) or discarded
```

| Concern | Path |
|---|---|
| Feedback + lessons | `packages/learning/{feedback,lessons}.py` |
| Trainer | `apps/workers/trainer/` (flake, risk, calibration, locator, dedup) |
| Registry + rollback | `packages/learning/registry.py` |

## Bug locator

| Symptom | Go to | What to fix |
|---|---|---|
| Flake rate > 100% or negative | `memory/update.py` | Window maths |
| Change-impact misses a journey | `diff_map.py` | File → node mapping missing (shared components) |
| Rule applied to wrong project | `rules.py` | `project_id` filter / RLS |
| Model got worse after retrain | `registry.py`, eval report | `saq learn rollback <component>`; check label quality |
| Trainer used unconfirmed verdicts | **High** → `feedback.py` query | Train only on `feedback` rows, never raw verdicts |
| Deleted project still in a model | Trainer data snapshot | Retrain excluding it; check the forget hook |

## Change safety

- [ ] `make test-learn`
- [ ] Impact change → run on golden projects with known diffs (expected journey lists in `evals/impact/`)
