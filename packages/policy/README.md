# Policy

Safe-action policy and domain allow-list (100% branch coverage). The RBAC matrix lives in
`apps/api/auth/permissions.py` (M08b).

| | |
|---|---|
| Design doc | docs/09-security.md §6 |
| Module | M03 |

- `domains.py`: `is_allowed_url(url, base_url, allowed_hosts)`; base host always allowed; entries
  may be `host`, `host:port` or `*.suffix`.
- `actions.py`: `check(Action, PolicyContext) -> Decision(allowed, category, reason)`; the
  runner calls it before every action and request (`apps/runner/policy_hook.py`).

Environment relaxations (`environment.safe_actions`): `allow: ["delete"]`, `payments: "test"`,
`mail_sink: true`, `allow_production: true`. Transfers are never allowed.
