"""Bug drafts, Gate 4 and the run workbook (US-08, US-09, sector 07).

Nothing reaches a tracker without a human: a QA Lead confirms or dismisses each draft, then
closes Gate 4; filing happens in the report stage. Before confirming, the duplicate check shows
similar open tracker issues and other drafts of the same test case.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api import ids, learning
from apps.api.auth.deps import ProjectContext, require
from apps.api.db import audit
from apps.api.db.models import Bug, Feedback, Project, Result, Run, Segment, TestCase, Verdict
from apps.api.errors import ApiError, conflict, not_found
from apps.api.reports import collect_run_export
from apps.api.trackers import TrackerFactory
from apps.orchestrator import engine
from apps.orchestrator.machine import TransitionError
from packages.exporters.evidence_pack import build_evidence_pack
from packages.exporters.excel import build_workbook
from packages.exporters.trackers.github import TrackerError

router = APIRouter(tags=["bugs"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class BugOut(BaseModel):
    id: str
    run_id: str
    case_id: str
    title: str
    severity: str
    body_md: str
    status: str
    tracker_ref: str | None


class BugEditIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    severity: Literal["critical", "high", "medium", "low"] | None = None
    body_md: str | None = Field(default=None, min_length=1, max_length=20_000)


class DismissIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class DuplicateOut(BaseModel):
    source: Literal["tracker", "project"]
    title: str
    ref: str


def _bug_query() -> Any:
    return (
        select(Bug, Result.run_id, Result.test_case_id)
        .join(Verdict, Verdict.id == Bug.verdict_id)
        .join(Result, Result.id == Verdict.result_id)
    )


def _out(bug: Bug, run_id: Any, case_id: Any) -> BugOut:
    return BugOut(
        id=ids.encode("bug", bug.id),
        run_id=ids.encode("run", run_id),
        case_id=ids.encode("tc", case_id),
        title=bug.title,
        severity=bug.severity,
        body_md=bug.body_md,
        status=bug.status,
        tracker_ref=bug.tracker_ref,
    )


def _get(s: Session, bug_id: str) -> tuple[Bug, Any, Any]:
    row = s.execute(_bug_query().where(Bug.id == ids.decode("bug", bug_id, "Bug"))).first()
    if row is None:
        raise not_found("Bug")
    return row[0], row[1], row[2]


def _decide(ctx: ProjectContext, bug_id: str, status: str, reason: str | None) -> BugOut:
    with ctx.session() as s:
        bug, run_id, case_id = _get(s, bug_id)
        if bug.status != "draft":
            raise conflict("Only a draft can be confirmed or dismissed")
        bug.status = status
        feedback = Feedback(
            project_id=ctx.project_id,
            entity="bug",
            entity_id=bug.id,
            decision="confirm" if status == "confirmed" else "reject",
            before={"status": "draft"},
            after={"status": status, "reason": reason},
            actor_id=ctx.principal.user_id,
        )
        s.add(feedback)
        s.flush()
        if status == "dismissed" and reason:
            verdict = s.get_one(Verdict, bug.verdict_id)
            case = s.get_one(TestCase, case_id)
            segment = s.get_one(Segment, case.segment_id)
            learning.learn_bug_dismissal(
                s,
                ctx.project_id,
                case_code=case.code,
                case_title=str((case.preconditions or {}).get("title", case.code)),
                failure=verdict.reason,
                reason=reason,
                journey_node_id=segment.journey_node_id,
                feedback_id=feedback.id,
            )
        audit.record(
            s,
            project_id=ctx.project_id,
            actor=ids.encode("usr", ctx.principal.user_id),
            action=f"bug.{status}",
            entity=ids.encode("bug", bug.id),
            payload={"reason": reason} if reason else {},
        )
        return _out(bug, run_id, case_id)


@router.get("/projects/{project_id}/bugs")
def list_bugs(
    ctx: ProjectContext = Depends(require("project.view")),
    status: str | None = None,
    run_id: str | None = None,
) -> list[BugOut]:
    with ctx.session() as s:
        stmt = _bug_query().order_by(Bug.created_at)
        if status:
            stmt = stmt.where(Bug.status == status)
        if run_id:
            stmt = stmt.where(Result.run_id == ids.decode("run", run_id, "Run"))
        return [_out(b, r, c) for b, r, c in s.execute(stmt).all()]


@router.patch("/projects/{project_id}/bugs/{bug_id}")
def edit_bug(
    bug_id: str, body: BugEditIn, ctx: ProjectContext = Depends(require("cases.approve"))
) -> BugOut:
    with ctx.session() as s:
        bug, run_id, case_id = _get(s, bug_id)
        if bug.status != "draft":
            raise conflict("Only a draft can be edited")
        for name in ("title", "severity", "body_md"):
            value = getattr(body, name)
            if value is not None:
                setattr(bug, name, value)
        return _out(bug, run_id, case_id)


@router.get("/projects/{project_id}/bugs/{bug_id}/duplicates")
def find_duplicates(
    bug_id: str, request: Request, ctx: ProjectContext = Depends(require("project.view"))
) -> list[DuplicateOut]:
    """Similar open tracker issues + other open bugs of the same test case (US-08)."""
    make: TrackerFactory = request.app.state.tracker_factory
    with ctx.session() as s:
        bug, _, case_id = _get(s, bug_id)
        siblings = s.execute(
            _bug_query().where(
                Result.test_case_id == case_id,
                Bug.id != bug.id,
                Bug.status.in_(("draft", "confirmed", "filed")),
            )
        ).all()
        found = [
            DuplicateOut(source="project", title=b.title, ref=ids.encode("bug", b.id))
            for b, _, _ in siblings
        ]
        settings = s.scalar(select(Project.settings).where(Project.id == ctx.project_id)) or {}
        title = bug.title
    tracker = make(settings)
    if tracker is not None:
        try:
            found += [
                DuplicateOut(source="tracker", title=i.title, ref=i.url)
                for i in tracker.find_duplicates(title)
            ]
        except TrackerError as exc:
            raise ApiError(502, "UPSTREAM_ERROR", str(exc)) from None
    return found


@router.post("/projects/{project_id}/bugs/{bug_id}/confirm")
def confirm_bug(bug_id: str, ctx: ProjectContext = Depends(require("bug.confirm"))) -> BugOut:
    return _decide(ctx, bug_id, "confirmed", None)


@router.post("/projects/{project_id}/bugs/{bug_id}/dismiss")
def dismiss_bug(
    bug_id: str, body: DismissIn, ctx: ProjectContext = Depends(require("bug.confirm"))
) -> BugOut:
    """Dismissal reasons are learning labels (e.g. "expected behaviour", US-10)."""
    return _decide(ctx, bug_id, "dismissed", body.reason)


@router.post("/projects/{project_id}/bugs/approve")
def close_gate4(ctx: ProjectContext = Depends(require("bug.confirm"))) -> dict[str, str]:
    """Gate 4: every draft decided. The report stage then files confirmed bugs."""
    actor = engine.Actor("user", ids.encode("usr", ctx.principal.user_id), ctx.role)
    try:
        with ctx.session() as s:
            drafts = s.scalars(select(Bug.id).where(Bug.status == "draft").order_by(Bug.id)).all()
            if drafts:
                raise ApiError(
                    409,
                    "GATE_NOT_APPROVED",
                    f"{len(drafts)} bug draft(s) still need a decision",
                    {"gate": 4, "bug_ids": [ids.encode("bug", b) for b in drafts]},
                )
            state = engine.transition(s, ctx.project_id, "bugs_confirmed", actor)
            audit.record(
                s,
                project_id=ctx.project_id,
                actor=actor.id,
                action="gate4.approved",
                entity=f"pipeline:{ctx.project_id}",
                payload={},
            )
            return {"stage": state.stage, "status": state.status}
    except TransitionError as exc:
        raise ApiError(
            409, "STATE_CONFLICT", str(exc), {"stage": exc.stage, "status": exc.status}
        ) from None


@router.get("/projects/{project_id}/runs/{run_id}/export.xlsx")
def export_run(run_id: str, ctx: ProjectContext = Depends(require("project.view"))) -> Response:
    """The six-sheet run workbook (US-09): redacted, formula-safe, verdict colours."""
    with ctx.session() as s:
        run = s.get(Run, ids.decode("run", run_id, "Run"))
        if run is None:
            raise not_found("Run")
        data = build_workbook(collect_run_export(s, run))
    return Response(
        data,
        media_type=XLSX,
        headers={"Content-Disposition": f'attachment; filename="smart-qa-{run_id}.xlsx"'},
    )


@router.get("/projects/{project_id}/runs/{run_id}/evidence-pack")
def evidence_pack(run_id: str, ctx: ProjectContext = Depends(require("project.view"))) -> Response:
    """Self-contained HTML (no script), downloaded as a file so it never renders in the app."""
    with ctx.session() as s:
        run = s.get(Run, ids.decode("run", run_id, "Run"))
        if run is None:
            raise not_found("Run")
        html = build_evidence_pack(collect_run_export(s, run))
    return Response(
        html,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="evidence-{run_id}.html"'},
    )
