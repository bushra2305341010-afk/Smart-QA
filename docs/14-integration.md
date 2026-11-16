# 14 · Integration

Every external system sits behind an adapter in `packages/` so it can be replaced or mocked.

## 1. Integration map

| System | Direction | Adapter | Release |
|---|---|---|---|
| Git (GitHub, GitLab, local folder) | In: read-only clone | `analyzers/code/git_source.py` | MVP |
| Documents (PDF, DOCX, MD, OpenAPI) | In | `citations/parsers/*` | MVP |
| GitHub Issues (stories in, bugs out) | Both | `exporters/trackers/github.py` | MVP |
| Jira | Both | `exporters/trackers/jira.py` | v1 |
| Claude API | Out | `model_gateway/adapters/anthropic.py` | MVP |
| Local model server | Out | `model_gateway/adapters/local.py` | MVP |
| Runner ↔ control plane | Both (outbound from runner) | `apps/runner/protocol.py` | MVP |
| Cloudflare Tunnel / ngrok | SUT exposure (alternative to runner) | config only | MVP |
| Excel | Out | `exporters/excel.py` (openpyxl) | MVP |
| HTML evidence pack | Out | `exporters/evidence_pack/` (Jinja2) | MVP |
| GitHub Actions CI gate | Both | `saq` CLI + action | v1 |
| Webhooks / REST | Out | `apps/api/webhooks.py` | v1 |
| HAR traffic import | In | `analyzers/traffic/har.py` | v1 |
| Slack / email notifications | Out | `notifications/` | v1 |

## 2. GitHub Issues

**Auth:** fine-grained PAT or GitHub App installation token, scopes `issues:write`, `contents:read`, limited to chosen repos.

**Filing (after Gate 4):**
1. `find_duplicates`: search open issues by title similarity + endpoint + requirement ID label.
2. If duplicate ≥ 0.85 similarity → comment on existing issue instead (user chooses).
3. Create issue: title, body from Appendix B template, labels `saq`, `severity:high`, `req:REQ-PAY-03`.
4. Attach evidence as links (presigned, 30-day) — never upload secrets/PII.
5. Store `tracker_ref` and write `audit_event`.

**Import stories:** issues with label `story` → `Requirement` nodes linked back by URL.

## 3. Jira (v1)

Jira Cloud REST v3, OAuth 2.0 (3LO) or API token. Fields mapping configurable per project: summary, description (ADF), priority ← severity, labels, custom field for requirement ID.

## 4. Excel workbook

Sheets and columns follow the plan's Appendix A:

| Sheet | Columns (short) |
|---|---|
| Test Cases | Case ID, Journey, Segment, Role, Technique, Priority, Preconditions, Steps, Test data, Expected, Source, Source quote, Citation status, Requirement ID, Approved by/date |
| Run Results | Run ID, Case ID, Verdict, Confidence, Reason, Duration, Browser, Evidence links, Re-run result, Judge rule |
| Bugs | Bug ID, Title, Severity, Steps, Expected (quote), Actual, Evidence, Environment, Build, Tracker link, Status |
| Traceability | Requirement ID, Text, Cases, Last verdict, Bugs, Coverage status |
| Coverage | Segment, Suggested, Approved, Executed, Passed, Failed, Blocked, Unable to Verify |
| Evidence Index | Evidence ID, Type, SHA-256, Link, Captured at |

Rules: frozen header row, autofilter, verdict cell colours from the design tokens, hyperlinks to evidence, no secrets.

## 5. Connecting to the app under test

| Option | When | How |
|---|---|---|
| Runner in team network (**default**) | Local or private staging | `docker run saq/runner --token …` on a machine that can reach the app |
| Sandbox | Uploaded ZIP / repo | Orchestrator builds container with start command + health check |
| Tunnel | Quick demo from a laptop | `cloudflared tunnel --url http://localhost:3000` → public URL as env |
| Public URL | Already deployed staging | Add as environment |

## 6. CI gate (GitHub Actions, v1)

```yaml
- name: Smart QA
  uses: smart-qa/action@v1
  with:
    url: ${{ secrets.SAQ_URL }}
    token: ${{ secrets.SAQ_TOKEN }}
    project: prj_1
    env: preview-${{ github.event.number }}
    mode: change-impact
# fails only on confirmed bugs (exit 1), not on flakes
```

## 7. Webhooks (v1)

Events: `run.finished`, `bug.confirmed`, `graph.approved`. Signed with HMAC-SHA256 header `X-SAQ-Signature`; retries with backoff for 24 h.

## 8. Adding a new integration

1. Implement the adapter Protocol (`TrackerAdapter`, `ModelProvider`, `ExecutionEngine`, `EvidenceStore`).
2. Add contract tests with recorded fixtures (`tests/contracts/<name>/`).
3. Add settings schema + UI form.
4. List the new external data flow on the data-sharing page.
5. Document here and in [workflows/09-integrations-and-mcp.md](workflows/09-integrations-and-mcp.md).
