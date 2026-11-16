# Sector 10 · Governance, Auth and Admin

**Features:** F32 self-host, F33 bring your own model, N31 roles, N32 audit ledger, N33 redaction, F34 cost meter & budgets.
**Owner:** Shared · Details: [../10-authentication-and-security.md](../10-authentication-and-security.md), [../09-security.md](../09-security.md)

## Flow

```
request ─▶ auth (cookie/JWT/token) ─▶ require(permission) ─▶ set app.project_id (RLS)
model call ─▶ redaction ─▶ budget pre-check ─▶ provider ─▶ cost record
gate / filing / MCP call ─▶ audit_event (hash chain)
```

## Code map

| Concern | Path |
|---|---|
| Auth | `apps/api/auth/` |
| Permissions | `packages/policy/permissions.py` |
| Audit | `apps/api/audit/` + DB trigger |
| Redaction | `packages/model_gateway/redact.py` |
| Budget/cost | `packages/model_gateway/cost.py`, `apps/api/routers/costs.py` |

## Bug locator

| Symptom | Go to | What to fix |
|---|---|---|
| 403 for correct role | `permissions.py` matrix | Permission name mismatch |
| Data from another project visible | **Critical** → RLS policy / `require()` | Missing `project_id` filter |
| Audit verify fails | Trigger / canonical JSON | Key ordering, timestamp precision |
| PII reached model | **Critical** → `redact.py` | Add pattern + test |
| Budget exceeded silently | `cost.py` pre-check | Check before call, not after |

## Change safety

- [ ] `make test-auth test-policy` (100% branches)
- [ ] ZAP baseline + ASVS items for the area
- [ ] Any new table → RLS policy + test
