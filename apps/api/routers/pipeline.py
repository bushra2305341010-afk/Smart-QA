"""Pipeline state and human events (docs/03 §2, sector 12).

Gate decisions sent here are checked server-side by the orchestrator: the role must hold the
gate's permission and the database must show the gate's precondition (e.g. an approved plan).
Worker (system) events are not accepted over HTTP.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from apps.api import ids
from apps.api.auth.deps import ProjectContext, require
from apps.api.db.models import PipelineState
from apps.api.errors import ApiError
from apps.api.ratelimit import enforce
from apps.api.settings import get_settings
from apps.orchestrator import engine
from apps.orchestrator.guards import GuardError
from apps.orchestrator.machine import USER_EVENTS, TransitionError

router = APIRouter(tags=["pipeline"])
JOB_STARTS = frozenset({"start", "retry", "graph_rejected", "plan_edited"})


class StateOut(BaseModel):
    stage: str
    status: str
    entered_at: datetime


class PipelineOut(BaseModel):
    current: StateOut | None
    history: list[StateOut]


class EventIn(BaseModel):
    event: str = Field(description=f"One of: {', '.join(sorted(USER_EVENTS))}")


def _out(state: PipelineState) -> StateOut:
    return StateOut(stage=state.stage, status=state.status, entered_at=state.entered_at)


@router.get("/projects/{project_id}/pipeline")
def get_pipeline(ctx: ProjectContext = Depends(require("project.view"))) -> PipelineOut:
    with ctx.session() as s:
        states = engine.history(s)
    return PipelineOut(
        current=_out(states[-1]) if states else None, history=[_out(x) for x in states]
    )


@router.post("/projects/{project_id}/pipeline/events")
def send_event(
    body: EventIn, request: Request, ctx: ProjectContext = Depends(require("project.view"))
) -> StateOut:
    if body.event not in USER_EVENTS:
        raise ApiError(
            400,
            "VALIDATION_ERROR",
            "Unknown or system-only event",
            {"allowed": sorted(USER_EVENTS)},
        )
    if body.event in JOB_STARTS:
        enforce(
            request.app.state.rate_limiter,
            f"jobs:{ctx.project_id}",
            get_settings().rate_job_starts_per_project_per_min,
        )
    actor = engine.Actor("user", ids.encode("usr", ctx.principal.user_id), ctx.role)
    try:
        with ctx.session() as s:
            state = engine.transition(
                s,
                ctx.project_id,
                body.event,
                actor,
                default_budget_usd=get_settings().saq_budget_monthly_usd,
            )
            return _out(state)
    except TransitionError as exc:
        raise ApiError(
            409,
            "STATE_CONFLICT",
            str(exc),
            {"stage": exc.stage, "status": exc.status, "event": exc.event},
        ) from None
    except GuardError as exc:
        raise ApiError(exc.status, exc.code, exc.message, exc.details) from None
