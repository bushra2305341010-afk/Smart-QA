# Sector 09 · Integrations, MCP and CLI

**Features:** F31 MCP server, N29 CLI, F30 CI gate (v1), N30 REST/webhooks (v1), tracker adapters.
**Owner:** Shared · Details: [../13-mcp-connection.md](../13-mcp-connection.md), [../14-integration.md](../14-integration.md)

## Flow

```
Coding agent ─MCP─▶ apps/mcp ─▶ API client (token scopes) ─▶ same services as UI
Terminal/CI ─▶ saq CLI ─▶ API ─▶ JSON output + exit codes
Events ─▶ webhooks (HMAC) ─▶ external systems
```

MCP and CLI never call services directly — always the public API, so RBAC and audit apply.

## Code map

| Concern | Path |
|---|---|
| MCP server | `apps/mcp/server.py`, `tools/*.py` |
| CLI | `apps/cli/main.py` (Typer) |
| Webhooks | `apps/api/webhooks.py` |
| GitHub Action | `deploy/github-action/` |

## Bug locator

| Symptom | Go to | What to fix |
|---|---|---|
| Tool missing in client | `server.py` registration | Feature flag `mcp_preview` |
| `run_journeys` runs though disabled | **High** → scope check in tool | Check `mcp.allow_runs` + `mcp:run` |
| CLI wrong exit code | `cli/main.py` mapping | Align with verdict summary |
| Webhook signature mismatch | `webhooks.py` | Sign raw body bytes |

## Change safety

- [ ] `make test-mcp test-cli test-contract`
- [ ] Tool input/output change → bump tool version string, update `13-mcp-connection.md`
