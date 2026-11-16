# Sector 06 · Judge (the oracle)

**Features:** N20 verdict taxonomy, F22 flake classifier, F23 confidence + Unable to Verify, F24 AI-feature oracle (preview), F26 injection checks on product AI (v1).
**Owner:** Stuti · Support: Nadia

## Flow

```
result ─▶ passed? ── yes ─▶ citation verified? ─ yes ─▶ PASS
   │                               └─ no ─▶ UNABLE TO VERIFY
   └─ no ─▶ detectors say blocked? ─▶ BLOCKED
          ─▶ script/locator fault? ─▶ TEST ERROR ─▶ Healer proposal
          ─▶ re-run in clean context
                ├─ passes + noise ─▶ FLAKY
                └─ fails same way + verified citation ─▶ FAIL ─▶ bug draft
                                    └─ evidence weak ─▶ UNABLE TO VERIFY
confidence = f(same failure twice, HTTP status, DOM match, judge score)  · rule id stored
```

Rules are **code** (`packages/verdicts/rules.py`); the LLM only scores semantic match and writes the reason.

## Code map

| Concern | Path |
|---|---|
| Rules | `packages/verdicts/rules.py` |
| Flake features | `packages/verdicts/flake.py` |
| Confidence | `packages/verdicts/confidence.py` |
| Worker | `apps/workers/judge/` |
| AI-feature oracle | `apps/workers/judge/semantic_oracle.py` |
| UV queue UI | `apps/web/src/features/runs/UvQueue.tsx` |

## Bug locator

| Symptom | Go to | What to fix |
|---|---|---|
| Pass shown without verified citation | **Critical** → `rules.py` | Guard order |
| Real bug labelled Flaky | `flake.py` | Require noise evidence, not just pass-on-retry |
| No re-run happened | Orchestrator `Judge→Execute` transition | Job dispatch |
| Confidence always High | `confidence.py` | Signal weights |
| Verdict without rule id | Worker save | Make `rule` NOT NULL |

## Change safety

- [ ] `make test-judge` (table-driven tests per rule)
- [ ] Verdict enum change → `make test-reporter test-learn test-web` + Excel colours
- [ ] `evals-small` (flake accuracy, false-bug rate)
