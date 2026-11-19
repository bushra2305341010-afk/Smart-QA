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
| DB roles, RLS, composite FKs | `apps/api/alembic/versions/0002_rls_audit_chain.py`, `apps/api/db/base.py` (ADR-011) |
| Project scope per transaction | `apps/api/db/session.py` (`project_session`, `set_scope`) |
| Audit | `apps/api/db/audit.py` (`record`, `verify_chain`) + `audit_event_chain` trigger |
| Redaction | `packages/model_gateway/redact.py` |
| Budget/cost | `packages/model_gateway/cost.py`, `apps/api/routers/costs.py` |

## Bug locator

| Symptom | Go to | What to fix |
|---|---|---|
| 403 for correct role | `permissions.py` matrix | Permission name mismatch |
| Data from another project visible | **Critical** → RLS policy / `require()` | Missing `project_id` filter |
| Audit verify fails | `audit_event_chain` trigger vs `audit.py:canonical` | Field order, `payload::text`, UTC µs timestamp format must match |
| Row links to another project's row | Composite FK missing → `scoped_fk()` in model + migration | Never a single-column FK to a project table |
| RLS tests pass for nobody / app sees everything | App connected as superuser or owner | Use `saq_app` (not superuser); recreate old dev volume |
| PII reached model | **Critical** → `redact.py` | Add pattern + test |
| Budget exceeded silently | `cost.py` pre-check | Check before call, not after |

## Change safety

- [ ] `make test-auth test-policy` (100% branches)
- [ ] ZAP baseline + ASVS items for the area
- [ ] Any new table → `project_id`, RLS policy in a migration, composite FKs; `tests/db` invariant tests pass
- [ ] `make test-int` (RLS, audit chain, outbox) and `uv run alembic check`
