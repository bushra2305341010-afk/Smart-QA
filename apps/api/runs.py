"""Run progress shared by the execute worker, the runner API and the Judge (sector 05).

Kept in `apps/api` (not `apps/workers`) because the runner endpoints need it and `apps/api` must
not import workers. Everything here runs inside the caller's project-scoped transaction.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.db.models import Result, Run, RunnerJob
from apps.orchestrator import engine
from apps.orchestrator.machine import TransitionError
from packages.contracts.run import AttemptResult, Failure

log = logging.getLogger(__name__)
OPEN = ("queued", "leased")


def latest_run(s: Session) -> Run | None:
    return s.scalar(select(Run).order_by(Run.created_at.desc()).limit(1))


def open_jobs(s: Session, run_id: uuid.UUID) -> int:
    stmt = select(func.count()).where(RunnerJob.run_id == run_id, RunnerJob.status.in_(OPEN))
    return int(s.scalar(stmt) or 0)


def write_result(
    s: Session,
    pid: uuid.UUID,
    run_id: uuid.UUID,
    case_id: uuid.UUID,
    result: AttemptResult,
    browser: str | None = None,
) -> tuple[Result, bool]:
    """Insert the attempt's result once. Returns (row, created); a repeat is a no-op (NFR-4)."""
    existing = s.scalar(
        select(Result).where(
            Result.run_id == run_id,
            Result.test_case_id == case_id,
            Result.attempt == result.attempt,
        )
    )
    if existing is not None:
        return existing, False
    row = Result(
        project_id=pid,
        run_id=run_id,
        test_case_id=case_id,
        attempt=result.attempt,
        status=result.status,
        duration_ms=result.duration_ms,
        browser=browser,
        details=result.model_dump(mode="json"),
    )
    s.add(row)
    s.flush()
    run = s.get_one(Run, run_id)
    run.last_completed_case_id = case_id
    return row, True


def error_result(attempt: int, message: str) -> AttemptResult:
    """A result for a case that could not run because of us (→ Test Error, never Pass)."""
    return AttemptResult(
        attempt=attempt, status="error", failure=Failure(kind="script", message=message)
    )


def finish_if_done(s: Session, pid: uuid.UUID, run_id: uuid.UUID, actor: engine.Actor) -> bool:
    """When no job of the run is open, mark the run completed and move the pipeline to Judge."""
    if open_jobs(s, run_id):
        return False
    run = s.get_one(Run, run_id)
    run.status, run.finished_at = "completed", datetime.now(UTC)
    payload: dict[str, Any] = {"run_id": str(run_id)}
    try:
        engine.transition(s, pid, "results_ready", actor, payload=payload)
    except TransitionError as exc:  # pipeline already moved on (duplicate delivery)
        log.info("results already reported; %s", exc)
    return True
