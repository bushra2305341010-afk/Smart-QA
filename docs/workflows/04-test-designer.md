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
| Quote verify | `packages/citations/verify.py` (**100% branch coverage**) — `verify_quote()`, `verify_citation()`, `MIN_QUOTE_CHARS = 12` |
| Normalisation | `packages/citations/normalize.py` — same function for source text and quotes |
| Chunking | `packages/citations/chunker.py` — `chunk_pages()` returns full normalised text + chunks with offsets, page, line |
| Contracts | `packages/contracts/citation.py` — `Citation`, `Chunk`, `Location` (frozen) |
| Dedup | `packages/cases/dedup.py` |
| Test data | `packages/cases/data.py` |
| Gate 3 | `apps/api/routers/cases.py::approve` |
| UI | `apps/web/src/features/cases/` |

## Bug locator

| Symptom | Go to | What to fix |
|---|---|---|
| Many UV cases | `verify.py` normalisation vs ingest | Same NFC/whitespace normalisation both sides |
| Short quotes rejected ("quote too short to be evidence") | `verify.py::MIN_QUOTE_CHARS` | Expected; ask the Designer to quote the full sentence |
| Offsets point at wrong text but case is verified | `verify_quote` relocation | By design: offsets are corrected to the nearest exact occurrence; check `reason == "offsets corrected"` |
| ruff RUF001 on curly quotes / special spaces | Source file contains literal non-ASCII | Write them as `\uXXXX` escapes |
| Expected result not supported by quote | Designer prompt | Add eval case; rule "quote must state the expected behaviour" |
| Duplicate cases | `dedup.py` threshold | Tune; include steps + node links |
| Personal data in test data | `data.py` | Faker only; block real-looking emails |
| Case count ≠ approved count | Designer batching | Enforce count per segment, re-request missing |

## Change safety

- [ ] `uv run pytest tests/citations tests/contracts --cov=packages/citations --cov=packages/contracts` → 100% branches
- [ ] Case schema change → `make test-compiler test-judge test-reporter` + Excel golden file diff
- [ ] Prompt change → `evals-small` (citation accuracy)
