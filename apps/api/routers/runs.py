"""Runs, results, verdicts, evidence and live events (sector 05/06/11, M12).

- `GET /runs`, `GET /runs/{run}`: progress and one row per case (latest attempt, verdict, rule).
- `GET /evidence/{sha256}`: evidence bytes, only if a row of this project references the hash
  (content addresses are global; RLS on `evidence` decides who may read them).
- `GET /cases/{tc}/compiled.py`: the generated Playwright test (pillar P6).
- `GET /events`: Server-Sent Events. Sends `pipeline` and `run` snapshots when they change
  (polled from Postgres every `poll_s`), plus `ping` keep-alives; the UI patches its cache.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api import ids
from apps.api.auth.deps import ProjectContext, get_store, require
from apps.api.db.models import Environment, Evidence, Project, Result, Run, TestCase, Verdict
from apps.api.errors import ApiError, forbidden, not_found
from apps.api.ratelimit import enforce
from apps.api.routers.projects import Limit, Page, _paged
from apps.api.settings import get_settings
from apps.api.storage import ObjectStore
from apps.orchestrator import engine
from apps.orchestrator.guards import GuardError
from apps.orchestrator.machine import TransitionError

router = APIRouter(tags=["runs"])
CONTENT_TYPES = {
    "screenshot": "image/png", "trace": "application/zip", "video": "video/webm",
    "har": "application/json", "console": "text/plain; charset=utf-8",
    "request": "application/json",
}  # fmt: skip


class RunOut(BaseModel):
    id: str
    status: str
    env_id: str
    env_name: str
    started_at: datetime | None
    finished_at: datetime | None
    totals: dict[str, Any]
    created_at: datetime


class EvidenceOut(BaseModel):
    kind: str
    step_n: int | None
    sha256: str
    size: int


class CaseRow(BaseModel):
    case_id: str
    code: str
    title: str
    attempts: int
    status: str | None
    verdict: str | None
    confidence: float | None
    level: str | None
    rule: str | None
    reason: str | None
    failure: dict[str, Any] | None
    blocked: str | None
    result_id: str | None
    evidence: list[EvidenceOut]


class RunDetail(RunOut):
    cases: list[CaseRow]


def _run_out(s: Session, run: Run) -> RunOut:
    env = s.get_one(Environment, run.env_id)
    return RunOut(
        id=ids.encode("run", run.id), status=run.status, env_id=ids.encode("env", env.id),
        env_name=env.name, started_at=run.started_at, finished_at=run.finished_at,
        totals=run.totals, created_at=run.created_at,
    )  # fmt: skip


def _level(confidence: float | None) -> str | None:
    if confidence is None:
        return None
    return "high" if confidence >= 0.8 else "medium" if confidence >= 0.5 else "low"


class RunIn(BaseModel):
    env_id: str | None = Field(default=None, description="env_...; default: project default")
    journeys: list[str] = Field(default_factory=list, max_length=50)
    source: str = Field(default="api", pattern="^(api|cli|mcp|ui)$")


class RunStarted(BaseModel):
    stage: str
    status: str


@router.post("/projects/{project_id}/runs", status_code=202)
def start_run(
    body: RunIn, request: Request, ctx: ProjectContext = Depends(require("run.start"))
) -> RunStarted:
    """Regression run of the approved cases after the pipeline is done (compile → run → judge).
    The new run appears in `GET /runs` once compiled; Gate 4 still needs a human."""
    enforce(request.app.state.rate_limiter, f"jobs:{ctx.project_id}",
            get_settings().rate_job_starts_per_project_per_min)  # fmt: skip
    payload: dict[str, Any] = {"journeys": body.journeys, "source": body.source}
    with ctx.session() as s:
        if body.source == "mcp":
            settings = s.scalar(select(Project.settings).where(Project.id == ctx.project_id)) or {}
            if (settings.get("mcp") or {}).get("allow_runs") is not True:
                raise forbidden("mcp.allow_runs")
        if body.env_id:
            env_id = ids.decode("env", body.env_id, "Environment")
            if s.get(Environment, env_id) is None:
                raise not_found("Environment")
            payload["env_id"] = str(env_id)
        actor = engine.Actor("user", ids.encode("usr", ctx.principal.user_id), ctx.role)
        try:
            state = engine.transition(s, ctx.project_id, "run_requested", actor, payload=payload)
        except TransitionError as exc:
            raise ApiError(409, "STATE_CONFLICT", str(exc),
                           {"stage": exc.stage, "status": exc.status}) from None  # fmt: skip
        except GuardError as exc:
            raise ApiError(exc.status, exc.code, exc.message, exc.details) from None
        return RunStarted(stage=state.stage, status=state.status)


@router.get("/projects/{project_id}/runs")
def list_runs(
    ctx: ProjectContext = Depends(require("project.view")),
    limit: Limit = 50,
    cursor: str | None = None,
) -> Page[RunOut]:
    with ctx.session() as s:
        stmt = select(Run).order_by(Run.created_at.desc(), Run.id)
        items, nxt = _paged(s, stmt, limit, cursor)
        return Page(items=[_run_out(s, r) for r in items], next_cursor=nxt)


@router.get("/projects/{project_id}/runs/{run_id}")
def get_run(run_id: str, ctx: ProjectContext = Depends(require("project.view"))) -> RunDetail:
    rid = ids.decode("run", run_id, "Run")
    with ctx.session() as s:
        run = s.get(Run, rid)
        if run is None:
            raise not_found("Run")
        results = s.scalars(
            select(Result).where(Result.run_id == rid).order_by(Result.attempt)
        ).all()
        latest: dict[Any, Result] = {}
        counts: dict[Any, int] = {}
        for r in results:
            latest[r.test_case_id] = r
            counts[r.test_case_id] = counts.get(r.test_case_id, 0) + 1
        verdicts = {
            v.result_id: v
            for v in s.scalars(
                select(Verdict).where(Verdict.result_id.in_([r.id for r in results]))
            )
        }
        evidence: dict[Any, list[EvidenceOut]] = {}
        for e in s.scalars(
            select(Evidence)
            .where(Evidence.result_id.in_([r.id for r in latest.values()]))
            .order_by(Evidence.step_n.nulls_last(), Evidence.kind)
        ):
            evidence.setdefault(e.result_id, []).append(
                EvidenceOut(kind=e.kind, step_n=e.step_n, sha256=e.sha256, size=e.size)
            )
        cases = s.scalars(
            select(TestCase).where(TestCase.id.in_(list(latest))).order_by(TestCase.code)
        ).all()
        rows = []
        for case in cases:
            res = latest[case.id]
            v = verdicts.get(res.id)
            details = res.details or {}
            rows.append(
                CaseRow(
                    case_id=ids.encode("tc", case.id),
                    code=case.code,
                    title=str((case.preconditions or {}).get("title", case.code)),
                    attempts=counts[case.id],
                    status=res.status,
                    verdict=v.verdict if v else None,
                    confidence=v.confidence if v else None,
                    level=_level(v.confidence if v else None),
                    rule=v.rule if v else None,
                    reason=v.reason if v else None,
                    failure=details.get("failure"),
                    blocked=details.get("blocked"),
                    result_id=ids.encode("res", res.id),
                    evidence=evidence.get(res.id, []),
                )
            )
        return RunDetail(**_run_out(s, run).model_dump(), cases=rows)


@router.get("/projects/{project_id}/evidence/{sha256}")
def get_evidence(
    sha256: str,
    ctx: ProjectContext = Depends(require("project.view")),
    store: ObjectStore = Depends(get_store),
) -> Response:
    with ctx.session() as s:
        row = s.scalars(select(Evidence).where(Evidence.sha256 == sha256).limit(1)).first()
        if row is None:
            raise not_found("Evidence")
        key, kind = row.object_key, row.kind
    data = store.get(key)
    headers = {"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"}
    if kind in ("trace", "har", "video"):
        headers["Content-Disposition"] = f'attachment; filename="{sha256[:12]}-{kind}"'
    return Response(data, media_type=CONTENT_TYPES[kind], headers=headers)


@router.get("/projects/{project_id}/cases/{case_id}/compiled.py")
def get_compiled(
    case_id: str,
    ctx: ProjectContext = Depends(require("project.view")),
    store: ObjectStore = Depends(get_store),
) -> Response:
    cid = ids.decode("tc", case_id, "Test case")
    with ctx.session() as s:
        case = s.get(TestCase, cid)
        if case is None or case.compiled_path is None:
            raise not_found("Compiled test")
        path, code = case.compiled_path, case.code
    filename = f"test_{code.lower().replace('-', '_')}.py"
    return Response(
        store.get(path), media_type="text/x-python; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )  # fmt: skip


def _snapshot(ctx: ProjectContext) -> dict[str, Any]:
    with ctx.session() as s:
        state = engine.current(s)
        run = s.scalar(select(Run).order_by(Run.created_at.desc()).limit(1))
        return {
            "pipeline": {"stage": state.stage, "status": state.status} if state else None,
            "run": _run_out(s, run).model_dump(mode="json") if run else None,
        }


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.get("/projects/{project_id}/events")
async def events(
    request: Request,
    ctx: ProjectContext = Depends(require("project.view")),
    poll_s: float = Query(2.0, ge=0.05, le=30),
    max_s: float = Query(300, ge=0.1, le=3600, description="Close after this; clients reconnect"),
) -> StreamingResponse:
    async def stream() -> AsyncIterator[str]:
        last: dict[str, Any] = {}
        waited = 0.0
        yield "retry: 3000\n\n"
        while waited < max_s:
            snap = await asyncio.to_thread(_snapshot, ctx)
            for name in ("pipeline", "run"):
                if snap[name] != last.get(name, ...):
                    yield _sse(name, snap[name])
            last = snap
            if await request.is_disconnected():  # pragma: no cover - needs a real socket
                return
            await asyncio.sleep(poll_s)
            waited += poll_s
            yield ": ping\n\n"

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(stream(), media_type="text/event-stream", headers=headers)
