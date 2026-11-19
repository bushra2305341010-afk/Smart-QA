# Sector 07 · Reporter and Hand-off

**Features:** F28 bug drafts, N21 bug confirmation (Gate 4) + GitHub/Jira push, N22 Excel run workbook, N23 evidence pack, N24 release readiness (v1), N25 Bangla reports (v1).
**Owner:** Nadia · Support: Stuti

## Flow

```
Fail verdicts ─▶ Reporter drafts (template, cites requirement, evidence links)
   ─▶ tracker.find_duplicates ─▶ bug (draft) ─▶ Bug review UI ─▶ Gate 4 confirm
   ─▶ tracker.file ─▶ tracker_ref ─▶ audit_event
Run finished ─▶ exporters/excel.py (6 sheets) · exporters/evidence_pack (HTML, hashes)
```

## Code map

| Concern | Path |
|---|---|
| Worker (`draft_bugs`, `job.report`) | `apps/workers/reporter.py` |
| Bug template (redacted markdown) | `packages/exporters/bug.py` (`draft_bug`) |
| Excel (6 sheets, formula-safe, redacted, verdict colours) | `packages/exporters/excel.py`, data from `apps/api/reports.py` |
| Evidence pack (self-contained HTML, no script, redacted + escaped, SHA-256 index) | `packages/exporters/evidence_pack.py`; stored at `reports/<run>-evidence.html` by the report stage |
| Trackers | `packages/exporters/trackers/github.py` (Jira later); project setting `{"tracker": {"kind": "github", "repo": "owner/name"}}`, token `GITHUB_TOKEN` env only (`apps/api/trackers.py`) |
| Bug review, duplicates, Gate 4, export | `apps/api/routers/bugs.py` |
| UI | `apps/web/src/features/bugs/`, `features/reports/` |

**Implementation (M11).** `draft_bugs(run)` drafts one bug per **Fail** verdict (never Flaky, Blocked, Test Error or Unable to Verify) with steps, test data, expected result + its source quote, actual result, environment and evidence SHA-256s; everything is redacted. The Judge stage calls it before `verdicts_ready`. A QA Lead edits, confirms or dismisses each draft (each decision is a `feedback` label); `GET …/bugs/{id}/duplicates` shows similar open tracker issues and other bugs of the same case before confirming. Gate 4 refuses while drafts remain. The report stage stores the run workbook at `reports/<run>.xlsx` and files confirmed bugs (labels `smart-qa`, `severity:<x>`), setting `filed` + `tracker_ref`; a filing error fails the stage so `retry` can file the rest.

## Bug locator

| Symptom | Go to | What to fix |
|---|---|---|
| Bug filed without confirmation | **Critical** → `bugs.py::confirm` + RBAC | Server-side gate |
| Duplicate issues in GitHub | `github.py::find_duplicates` | Similarity + endpoint + req label |
| Excel cell starts with `=` executes | `excel.py` | Escape formula injection |
| Excel colours wrong | `excel.py` style map | Use verdict tokens |
| Evidence links expired | Presign TTL | 30-day for tickets, regenerate on open |
| Secrets/PII in bug body | Redaction before render | Run redactor on all fields |

## Change safety

- [ ] `make test-reporter test-exporters`
- [ ] Excel layout change → update golden `.xlsx` snapshot + `14-integration.md` §4
- [ ] Tracker change → contract tests with recorded fixtures
