"""Test cases: browse, edit, review and approve (Gate 3) — US-05, sector 04.

Expected results and their citations are not editable here: changing an expected result needs a
new verified quote, so a human rejects the case instead. A case whose citation is
`unable_to_verify` cannot be approved (422 CITATION_UNVERIFIED) — pillar P1.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api import ids
from apps.api.auth.deps import ProjectContext, require
from apps.api.db import audit
from apps.api.db.models import Feedback, Plan, Segment, Step, TestCase
from apps.api.errors import ApiError, conflict, not_found
from apps.orchestrator import engine
from apps.orchestrator.guards import GuardError
from apps.orchestrator.machine import TransitionError

router = APIRouter(tags=["cases"])


class StepOut(BaseModel):
    n: int
    action: str


class CaseOut(BaseModel):
    id: str
    code: str
    segment_id: str
    title: str
    role: str
    technique: str
    priority: str
    preconditions: list[str]
    data: dict[str, Any]
    expected_text: str
    citation: dict[str, Any] | None
    requirement_id: str | None
    review_status: str
    steps: list[StepOut]


class CasePage(BaseModel):
    items: list[CaseOut]
    next_cursor: str | None


class CaseEditIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    preconditions: list[str] | None = Field(default=None, max_length=20)
    steps: list[str] | None = Field(default=None, min_length=1, max_length=40)
    data: dict[str, str] | None = None


class ReviewIn(BaseModel):
    case_ids: list[str] = Field(min_length=1, max_length=500)
    decision: Literal["approved", "rejected"]


class ReviewOut(BaseModel):
    updated: int


def _out(case: TestCase, steps: list[Step]) -> CaseOut:
    pre = case.preconditions or {}
    return CaseOut(
        id=ids.encode("tc", case.id),
        code=case.code,
        segment_id=ids.encode("seg", case.segment_id),
        title=str(pre.get("title", case.code)),
        role=case.role,
        technique=case.technique,
        priority=case.priority,
        preconditions=list(pre.get("items", [])),
        data=case.data,
        expected_text=case.expected_text,
        citation=case.citation,
        requirement_id=case.requirement_id,
        review_status=case.review_status,
        steps=[StepOut(n=st.n, action=st.action) for st in steps],
    )


def _steps(s: Session, case_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[Step]]:
    found: dict[uuid.UUID, list[Step]] = {c: [] for c in case_ids}
    for st in s.scalars(select(Step).where(Step.test_case_id.in_(case_ids)).order_by(Step.n)):
        found[st.test_case_id].append(st)
    return found


@router.get("/projects/{project_id}/cases")
def list_cases(
    ctx: ProjectContext = Depends(require("project.view")),
    review_status: str | None = None,
    segment_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
) -> CasePage:
    """Cases of the approved plan, by code."""
    offset = int(cursor) if cursor and cursor.isdigit() else 0
    with ctx.session() as s:
        stmt = (
            select(TestCase)
            .join(Segment, Segment.id == TestCase.segment_id)
            .join(Plan, Plan.id == Segment.plan_id)
            .where(Plan.status == "approved")
            .order_by(TestCase.code)
        )
        if review_status:
            stmt = stmt.where(TestCase.review_status == review_status)
        if segment_id:
            stmt = stmt.where(TestCase.segment_id == ids.decode("seg", segment_id, "Segment"))
        rows = list(s.scalars(stmt.offset(offset).limit(limit + 1)))
        more = len(rows) > limit
        rows = rows[:limit]
        steps = _steps(s, [c.id for c in rows])
        return CasePage(
            items=[_out(c, steps[c.id]) for c in rows],
            next_cursor=str(offset + limit) if more else None,
        )


@router.get("/projects/{project_id}/cases/{case_id}")
def get_case(case_id: str, ctx: ProjectContext = Depends(require("project.view"))) -> CaseOut:
    with ctx.session() as s:
        case = s.get(TestCase, ids.decode("tc", case_id, "Test case"))
        if case is None:
            raise not_found("Test case")
        return _out(case, _steps(s, [case.id])[case.id])


@router.patch("/projects/{project_id}/cases/{case_id}")
def edit_case(
    case_id: str, body: CaseEditIn, ctx: ProjectContext = Depends(require("cases.approve"))
) -> CaseOut:
    """Edit title, preconditions, steps or data of a pending case (marks it `edited`)."""
    with ctx.session() as s:
        case = s.get(TestCase, ids.decode("tc", case_id, "Test case"))
        if case is None:
            raise not_found("Test case")
        if case.review_status != "pending":
            raise conflict("Only a case awaiting review can be edited")
        before = _out(case, _steps(s, [case.id])[case.id]).model_dump()
        pre = dict(case.preconditions or {})
        if body.title is not None:
            pre["title"] = body.title
        if body.preconditions is not None:
            pre["items"] = body.preconditions
        case.preconditions = pre
        if body.data is not None:
            case.data = dict(body.data)
        if body.steps is not None:
            for old in s.scalars(select(Step).where(Step.test_case_id == case.id)):
                s.delete(old)
            s.flush()
            s.add_all(
                Step(project_id=ctx.project_id, test_case_id=case.id, n=i, action=a)
                for i, a in enumerate(body.steps, start=1)
            )
        case.review_status = "edited"
        s.flush()
        after = _out(case, _steps(s, [case.id])[case.id])
        s.add(
            Feedback(
                project_id=ctx.project_id,
                entity="test_case",
                entity_id=case.id,
                decision="edit",
                before=before,
                after=after.model_dump(),
                actor_id=ctx.principal.user_id,
            )
        )
        return after


@router.post("/projects/{project_id}/cases/review")
def review_cases(
    body: ReviewIn, ctx: ProjectContext = Depends(require("cases.approve"))
) -> ReviewOut:
    """Approve or reject a batch of cases. Unverified expected results cannot be approved."""
    wanted = [ids.decode("tc", c, "Test case") for c in body.case_ids]
    with ctx.session() as s:
        cases = list(s.scalars(select(TestCase).where(TestCase.id.in_(wanted))))
        if len(cases) != len(set(wanted)):
            raise not_found("Test case")
        if body.decision == "approved":
            unverified = [
                ids.encode("tc", c.id)
                for c in cases
                if (c.citation or {}).get("status") != "verified"
            ]
            if unverified:
                raise ApiError(
                    422,
                    "CITATION_UNVERIFIED",
                    "These cases have no verified source for their expected result",
                    {"case_ids": unverified},
                )
        for c in cases:
            before = c.review_status
            c.review_status = body.decision
            s.add(
                Feedback(
                    project_id=ctx.project_id,
                    entity="test_case",
                    entity_id=c.id,
                    decision="confirm" if body.decision == "approved" else "reject",
                    before={"review_status": before},
                    after={"review_status": body.decision},
                    actor_id=ctx.principal.user_id,
                )
            )
        audit.record(
            s,
            project_id=ctx.project_id,
            actor=ids.encode("usr", ctx.principal.user_id),
            action=f"cases.{body.decision}",
            entity="test_case",
            payload={"case_ids": [ids.encode("tc", c.id) for c in cases]},
        )
        return ReviewOut(updated=len(cases))


@router.post("/projects/{project_id}/cases/approve")
def approve_cases(ctx: ProjectContext = Depends(require("cases.approve"))) -> dict[str, Any]:
    """Gate 3: every case of the approved plan reviewed, at least one approved."""
    actor = engine.Actor("user", ids.encode("usr", ctx.principal.user_id), ctx.role)
    try:
        with ctx.session() as s:
            state = engine.transition(s, ctx.project_id, "cases_approved", actor)
            audit.record(
                s,
                project_id=ctx.project_id,
                actor=actor.id,
                action="gate3.approved",
                entity=f"pipeline:{ctx.project_id}",
                payload={},
            )
            return {"stage": state.stage, "status": state.status}
    except TransitionError as exc:
        raise ApiError(
            409, "STATE_CONFLICT", str(exc), {"stage": exc.stage, "status": exc.status}
        ) from None
    except GuardError as exc:
        raise ApiError(exc.status, exc.code, exc.message, exc.details) from None
