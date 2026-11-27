"""Execute stage scheduler (`job.execute`, sector 05): queue one runner job per compiled case.

Idempotent: a case that already has a job (or a result) is not queued again, so a redelivered
job or a resume after a crash never duplicates work (NFR-4). Cases that did not compile get an
error result straight away (→ Test Error). Re-runs (attempt 2) are queued by the Judge before it
sends `rerun_needed`; this handler then only marks the run running and waits.
The runners report results over the runner API, which moves the pipeline on when the last
open job finishes.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from apps.api import runs
from apps.api.db.models import Result, RunnerJob, Segment, TestCase
from apps.api.db.session import project_session
from apps.orchestrator import engine
from apps.orchestrator.machine import TransitionError

log = logging.getLogger(__name__)
WORKER = engine.Actor("system", "worker:executor")
APPROVED = ("approved", "edited")


def schedule(s: Session, pid: uuid.UUID) -> tuple[uuid.UUID, int, int] | None:
    """Returns (run_id, queued, errors) or None when there is no run."""
    run = runs.latest_run(s)
    if run is None:
        return None
    if run.status in ("queued", "completed"):
        run.status = "running"
        run.started_at = run.started_at or datetime.now(UTC)
    cases = s.execute(
        select(TestCase.id, TestCase.compiled_path)
        .join(Segment, Segment.id == TestCase.segment_id)
        .where(Segment.plan_id == run.plan_id, TestCase.review_status.in_(APPROVED))
        .order_by(TestCase.code)
    ).all()
    has_job = set(s.scalars(select(RunnerJob.test_case_id).where(RunnerJob.run_id == run.id)))
    has_result = set(s.scalars(select(Result.test_case_id).where(Result.run_id == run.id)))
    queued = errors = 0
    for case_id, path in cases:
        if case_id in has_job or case_id in has_result:
            continue
        if path is None:
            runs.write_result(s, pid, run.id, case_id, runs.error_result(1, "Not compiled"))
            errors += 1
            continue
        s.add(RunnerJob(project_id=pid, run_id=run.id, test_case_id=case_id, attempt=1))
        queued += 1
    s.flush()
    return run.id, queued, errors


def handle_execute_job(factory: sessionmaker[Session], message: dict[str, Any]) -> None:
    pid = uuid.UUID(message["project_id"])

    def send(s: Session, event: str, **payload: Any) -> None:
        try:
            engine.transition(s, pid, event, WORKER, payload=payload or None)
        except TransitionError as exc:
            log.info("pipeline moved on; %s", exc)

    with project_session(factory, pid) as s:
        scheduled = schedule(s, pid)
        if scheduled is None:
            send(s, "job_failed", reason="No run to execute; compile first")
            return
        run_id, queued, errors = scheduled
        send(s, "job_started", run_id=str(run_id), queued=queued, errors=errors)
        runs.finish_if_done(s, pid, run_id, WORKER)
