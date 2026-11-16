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
| Worker | `apps/workers/reporter/` |
| Bug template | `apps/workers/reporter/templates/bug.md.j2` |
| Excel | `packages/exporters/excel.py` |
| Evidence pack | `packages/exporters/evidence_pack/` |
| Trackers | `packages/exporters/trackers/{github,jira}.py` |
| Gate 4 | `apps/api/routers/bugs.py::confirm` |
| UI | `apps/web/src/features/bugs/`, `features/reports/` |

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
