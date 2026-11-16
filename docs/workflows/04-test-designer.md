# Sector 04 · Test Designer

**Features:** F11 cases, F12 negative/boundary/permission, F13 cited expected results with quote verification, N15 duplicate detection, F14 synthetic data, N16 case review (Gate 3), F29 Excel export of cases.
**Owner:** Nadia · Support: Stuti

## Flow

```
approved plan + graph ─▶ Designer (batched per segment, cached graph prefix)
   ─▶ JSON cases ─▶ schema validate ─▶ citations.verify(quote, source[start:end])
        ├─ verified ─▶ case.review_status = pending
        └─ failed   ─▶ retry once with error ─▶ still failed ─▶ Unable to Verify
   ─▶ dedup (embedding similarity + shared graph links) ─▶ merge suggestions
   ─▶ Case review UI ─▶ Gate 3 (or auto for low-risk if enabled)
```

## Code map

| Concern | Path |
|---|---|
| Worker + prompts | `apps/workers/designer/` |
| Quote verify | `packages/citations/verify.py` (**100% branch coverage**) |
| Dedup | `packages/cases/dedup.py` |
| Test data | `packages/cases/data.py` |
| Gate 3 | `apps/api/routers/cases.py::approve` |
| UI | `apps/web/src/features/cases/` |

## Bug locator

| Symptom | Go to | What to fix |
|---|---|---|
| Many UV cases | `verify.py` normalisation vs ingest | Same NFC/whitespace normalisation both sides |
| Expected result not supported by quote | Designer prompt | Add eval case; rule "quote must state the expected behaviour" |
| Duplicate cases | `dedup.py` threshold | Tune; include steps + node links |
| Personal data in test data | `data.py` | Faker only; block real-looking emails |
| Case count ≠ approved count | Designer batching | Enforce count per segment, re-request missing |

## Change safety

- [ ] `make test-designer test-citations`
- [ ] Case schema change → `make test-compiler test-judge test-reporter` + Excel golden file diff
- [ ] Prompt change → `evals-small` (citation accuracy)
