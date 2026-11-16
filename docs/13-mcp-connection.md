# 13 · MCP Connection

Pillar P5: **independent verifier for coding agents.** Claude Code, Codex or Cursor can ask Smart QA, through MCP, to check that a change really works for users.

Code: `apps/mcp/` (official MCP Python SDK). Transport: `stdio` (local) and streamable HTTP (team server).

## 1. Tools

| Tool | Input | Output | Default access |
|---|---|---|---|
| `understand_change` | `{ project, diff? , pr_number? }` | Affected journeys, rules, endpoints with reasons | read-only |
| `plan_tests` | `{ project, journeys[] }` | Suggested cases, counts, techniques, reasons (from approved graph) | read-only |
| `run_journeys` | `{ project, journeys[], env }` | `{ run_id }` | **disabled** unless project setting `mcp.allow_runs=true` |
| `get_verdicts` | `{ run_id }` | Verdicts, confidence, reasons, evidence links, bug drafts | read-only |
| `get_brief` | `{ project }` | Product brief (markdown) | read-only |

Not exposed: approving gates, filing bugs, changing settings. **Humans keep the gates.**

## 2. Resources

| URI | Content |
|---|---|
| `saq://projects/{id}/brief` | Product brief |
| `saq://projects/{id}/graph/approved` | Approved graph (JSON) |
| `saq://runs/{id}/report` | Run summary (markdown) |

## 3. Connect from Claude Code

Local (stdio):
```bash
claude mcp add smart-qa -- saq mcp serve --project prj_1
```
Team server (HTTP):
```bash
claude mcp add --transport http smart-qa https://qa.team.local/mcp \
  --header "Authorization: Bearer $SAQ_TOKEN"
```
Project-scoped `.mcp.json`:
```json
{ "mcpServers": { "smart-qa": {
    "command": "saq", "args": ["mcp", "serve", "--project", "prj_1"],
    "env": { "SAQ_URL": "http://localhost:8000", "SAQ_TOKEN": "${SAQ_TOKEN}" } } } }
```
Cursor / other clients: same command in their MCP config.

## 4. Typical agent loop

```
coding agent edits code
  → understand_change(diff)           "Checkout + Coupon journeys affected"
  → run_journeys(["Checkout","Coupon"], env="local")   (if allowed)
  → get_verdicts(run_id)              "1 Fail: REQ-PAY-03, evidence…"
  → agent fixes code, repeats
  → human confirms bug / merges
```

## 5. Security

- Token scopes: `mcp:read`, `mcp:run`. Default token has only `mcp:read`.
- Results returned to the agent are **data**; bug text from the SUT is wrapped as untrusted.
- Rate limit: 10 runs/hour per token; budget caps still apply.
- Every MCP call writes an `audit_event` with the token ID.

## 6. CLI (same capabilities)

```bash
saq login --url http://localhost:8000
saq plan --project prj_1 --journeys Checkout --json
saq run  --project prj_1 --env local --wait --json
saq report --run run_42 --xlsx out/run_42.xlsx
saq mcp serve --project prj_1
```
Exit codes: 0 all pass, 1 confirmed fail, 2 blocked/unverified only, 3 tool error.

## 7. Using external MCP servers inside Smart QA (v2)

The `ExecutionEngine` interface allows engines backed by MCP servers (Playwright MCP, Appium MCP, Maestro MCP). The adapter maps our fixed tool list onto the server's tools and keeps the policy engine in front of every call.

## 8. Debugging MCP

| Symptom | Check |
|---|---|
| Tool list empty | `saq mcp serve --debug`; token valid? project ID right? |
| `run_journeys` forbidden | Project setting `mcp.allow_runs`, token scope `mcp:run` |
| Hangs | Use `--wait=false` and poll `get_verdicts`; check runner online |
| Claude Code can't start server | `which saq`, PATH in the MCP config env |
