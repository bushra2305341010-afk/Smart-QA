"""Role → permission matrix (docs/10-authentication-and-security.md §4).

Implemented in M08b because every endpoint needs it; the safe-action policy stays in
`packages/policy` (M03). Change this table only together with docs/10 §4 and its tests.
"""

from __future__ import annotations

from typing import Literal

Role = Literal["owner", "qa_lead", "tester", "developer", "viewer"]
Permission = Literal[
    "project.view",
    "members.manage",
    "model_policy.manage",
    "budget.manage",
    "sources.manage",
    "environments.manage",
    "identities.manage",
    "graph.approve",
    "plan.approve",
    "cases.approve",
    "run.start",
    "bug.confirm",
    "heal.approve",
    "env.mark_production",
    "pipeline.manage",
]

_LEAD: frozenset[Permission] = frozenset(
    {
        "project.view",
        "sources.manage",
        "environments.manage",
        "identities.manage",
        "graph.approve",
        "plan.approve",
        "cases.approve",
        "run.start",
        "bug.confirm",
        "heal.approve",
        "pipeline.manage",
    }
)

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    "owner": _LEAD
    | {"members.manage", "model_policy.manage", "budget.manage", "env.mark_production"},
    "qa_lead": _LEAD,
    "tester": frozenset({"project.view", "cases.approve", "run.start"}),
    "developer": frozenset({"project.view", "run.start"}),
    "viewer": frozenset({"project.view"}),
}


def allowed(role: str, permission: Permission) -> bool:
    """Unknown roles get nothing (deny by default)."""
    return permission in ROLE_PERMISSIONS.get(role, frozenset())  # type: ignore[call-overload]
