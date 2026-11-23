"""Coverage plans: view, edit approved counts, approve (Gate 2) — US-04, sector 03.

Suggested counts come from code with a reason per technique; the human sets the approved
count. Gate 2 refuses an empty plan, a plan on a graph that is no longer approved, and a plan
whose estimated design cost exceeds what is left of the monthly budget (N13).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api import ids, learning
from apps.api.auth.deps import ProjectContext, require
from apps.api.db import audit
from apps.api.db.model_store import budget_cap, month_spend
from apps.api.db.models import Feedback, GraphVersion, Plan, Project, Segment
from apps.api.errors import ApiError, conflict, not_found
from apps.api.pricing import cost_estimate
from apps.api.settings import get_settings
from apps.orchestrator import engine
from apps.orchestrator.machine import TransitionError

router = APIRouter(tags=["plans"])


class SegmentOut(BaseModel):
    id: str
    journey_id: str
    journey: str
    rows: list[dict[str, Any]]
    base_count: int
    multiplier: float
    risk_score: float
    priority: str
    suggested_count: int
    approved_count: int | None
    previous_decision: dict[str, int] | None = None  # last human edit for this journey (hint)


class PlanOut(BaseModel):
    id: str
    status: str
    graph_version_id: str
    cost_estimate: dict[str, Any]
    suggested_total: int
    approved_total: int
    segments: list[SegmentOut]


class SegmentIn(BaseModel):
    approved_count: int = Field(ge=0, le=500)


def _plan(s: Session, plan_id: str) -> Plan:
    plan = s.get(Plan, ids.decode("pln", plan_id, "Plan"))
    if plan is None:
        raise not_found("Plan")
    return plan


def _segments(s: Session, plan: Plan) -> list[Segment]:
    return list(
        s.scalars(
            select(Segment)
            .where(Segment.plan_id == plan.id)
            .order_by(Segment.risk_score.desc(), Segment.id)
        )
    )


def _segment_out(seg: Segment) -> SegmentOut:
    t = seg.techniques
    return SegmentOut(
        id=ids.encode("seg", seg.id),
        journey_id=ids.encode("nod", seg.journey_node_id),
        journey=str(t.get("journey", "")),
        rows=list(t.get("rows", [])),
        base_count=int(t.get("base_count", 0)),
        multiplier=float(t.get("multiplier", 1.0)),
        risk_score=seg.risk_score,
        priority=seg.priority,
        suggested_count=seg.suggested_count,
        approved_count=seg.approved_count,
        previous_decision=t.get("previous_decision"),
    )


def _plan_out(s: Session, plan: Plan) -> PlanOut:
    segments = _segments(s, plan)
    return PlanOut(
        id=ids.encode("pln", plan.id),
        status=plan.status,
        graph_version_id=ids.encode("gv", plan.graph_version_id),
        cost_estimate=plan.cost_estimate,
        suggested_total=sum(x.suggested_count for x in segments),
        approved_total=sum(
            x.suggested_count if x.approved_count is None else x.approved_count for x in segments
        ),
        segments=[_segment_out(x) for x in segments],
    )


@router.get("/projects/{project_id}/plans")
def list_plans(ctx: ProjectContext = Depends(require("project.view"))) -> list[PlanOut]:
    with ctx.session() as s:
        plans = s.scalars(select(Plan).order_by(Plan.created_at.desc())).all()
        return [_plan_out(s, p) for p in plans]


@router.get("/projects/{project_id}/plans/{plan_id}")
def get_plan(plan_id: str, ctx: ProjectContext = Depends(require("project.view"))) -> PlanOut:
    with ctx.session() as s:
        return _plan_out(s, _plan(s, plan_id))


@router.patch("/projects/{project_id}/plans/{plan_id}/segments/{segment_id}")
def edit_segment(
    plan_id: str,
    segment_id: str,
    body: SegmentIn,
    ctx: ProjectContext = Depends(require("plan.approve")),
) -> SegmentOut:
    """Set the approved count for one journey (a human decision kept as a learning label)."""
    with ctx.session() as s:
        plan = _plan(s, plan_id)
        if plan.status != "draft":
            raise conflict("Only a draft plan can be edited")
        seg = s.get(Segment, ids.decode("seg", segment_id, "Segment"))
        if seg is None or seg.plan_id != plan.id:
            raise not_found("Segment")
        before = {"approved_count": seg.approved_count, "suggested_count": seg.suggested_count}
        seg.approved_count = body.approved_count
        feedback = Feedback(
            project_id=ctx.project_id,
            entity="segment",
            entity_id=seg.id,
            decision="edit",
            before=before,
            after={"approved_count": body.approved_count},
            actor_id=ctx.principal.user_id,
        )
        s.add(feedback)
        s.flush()
        learning.learn_count_edit(
            s,
            ctx.project_id,
            journey=str(seg.techniques.get("journey", "")),
            suggested=seg.suggested_count,
            approved=body.approved_count,
            feedback_id=feedback.id,
        )
        audit.record(
            s,
            project_id=ctx.project_id,
            actor=ids.encode("usr", ctx.principal.user_id),
            action="plan.segment.edited",
            entity=ids.encode("seg", seg.id),
            payload={"before": before["approved_count"], "after": body.approved_count},
        )
        return _segment_out(seg)


@router.post("/projects/{project_id}/plans/{plan_id}/approve")
def approve_plan(plan_id: str, ctx: ProjectContext = Depends(require("plan.approve"))) -> PlanOut:
    """Gate 2. Unedited segments are approved at their suggested count."""
    actor = engine.Actor("user", ids.encode("usr", ctx.principal.user_id), ctx.role)
    settings = get_settings()
    try:
        with ctx.session() as s:
            plan = _plan(s, plan_id)
            if plan.status != "draft":
                raise conflict("Only a draft plan can be approved")
            graph = s.get_one(GraphVersion, plan.graph_version_id)
            if graph.status != "approved":
                raise ApiError(
                    409, "GATE_NOT_APPROVED", "The plan's graph is no longer approved", {"gate": 1}
                )
            segments = _segments(s, plan)
            for seg in segments:
                if seg.approved_count is None:
                    seg.approved_count = seg.suggested_count
            total = sum(seg.approved_count or 0 for seg in segments)
            if total < 1:
                raise ApiError(
                    409, "GATE_NOT_APPROVED", "Approve at least one test case", {"gate": 2}
                )
            plan.cost_estimate = cost_estimate(settings, total)
            if plan.cost_estimate.get("available"):
                cap = budget_cap(
                    s.scalar(select(Project.settings).where(Project.id == ctx.project_id)),
                    settings.saq_budget_monthly_usd,
                )
                remaining = cap - month_spend(s)
                needed = Decimal(str(plan.cost_estimate["usd"]))
                if needed > remaining:
                    raise ApiError(
                        402,
                        "BUDGET_EXCEEDED",
                        "Estimated design cost is above the remaining monthly budget",
                        {"estimate_usd": str(needed), "remaining_usd": str(remaining)},
                    )
            for old in s.scalars(select(Plan).where(Plan.status == "approved")):
                old.status = "superseded"
            plan.status = "approved"
            plan.approved_by = ctx.principal.user_id
            s.flush()
            audit.record(
                s,
                project_id=ctx.project_id,
                actor=actor.id,
                action="gate2.approved",
                entity=ids.encode("pln", plan.id),
                payload={"approved_cases": total, "segments": len(segments)},
            )
            engine.transition(
                s, ctx.project_id, "plan_approved", actor, payload={"approved_cases": total}
            )
            return _plan_out(s, plan)
    except TransitionError as exc:
        raise ApiError(
            409, "STATE_CONFLICT", str(exc), {"stage": exc.stage, "status": exc.status}
        ) from None
