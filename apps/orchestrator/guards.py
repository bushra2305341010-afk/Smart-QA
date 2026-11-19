"""Server-side guards checked before a transition is written (sector 12 "Gate bypassed").

Gates are enforced against the database, not the caller's word: Gate 1 needs an approved graph
version, Gate 2 an approved plan on an approved graph, Gate 3 every case reviewed (or the
project's `gate3_auto` switch for the automatic event), Gate 4 no bug draft left undecided.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.db.model_store import budget_cap, month_spend
from apps.api.db.models import Bug, GraphVersion, Plan, Project, TestCase


@dataclass
class GuardError(Exception):
    status: int
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


def _gate(n: int, message: str) -> GuardError:
    return GuardError(409, "GATE_NOT_APPROVED", message, {"gate": n})


def check_gate(s: Session, project_id: uuid.UUID, gate: int, event: str) -> None:
    if gate == 1:
        approved = s.scalar(select(func.count()).where(GraphVersion.status == "approved"))
        if not approved:
            raise _gate(1, "Approve a graph version before Gate 1")
    elif gate == 2:
        ok = s.scalar(
            select(func.count())
            .select_from(Plan)
            .join(GraphVersion, GraphVersion.id == Plan.graph_version_id)
            .where(Plan.status == "approved", GraphVersion.status == "approved")
        )
        if not ok:
            raise _gate(2, "Approve the plan (on an approved graph) before Gate 2")
    elif gate == 3:
        if event == "cases_auto_approved":
            settings = s.scalar(select(Project.settings).where(Project.id == project_id)) or {}
            if settings.get("gate3_auto") is not True:
                raise _gate(3, "Gate 3 can only be skipped when the project enables gate3_auto")
            return
        pending = s.scalar(select(func.count()).where(TestCase.review_status == "pending"))
        if pending:
            raise _gate(3, f"{pending} test case(s) still need review")
    else:  # gate 4
        drafts = s.scalar(select(func.count()).where(Bug.status == "draft"))
        if drafts:
            raise _gate(4, f"{drafts} bug draft(s) still need a decision")


def check_budget(s: Session, project_id: uuid.UUID, default_usd: float) -> None:
    """Refuse to dispatch a model stage once this month's spend reaches the cap."""
    settings = s.scalar(select(Project.settings).where(Project.id == project_id))
    cap = budget_cap(settings, default_usd)
    spent = month_spend(s)
    if spent >= cap:
        raise GuardError(
            402,
            "BUDGET_EXCEEDED",
            "Monthly model budget reached; raise the budget to continue",
            {"spent_usd": str(spent), "cap_usd": str(cap)},
        )
