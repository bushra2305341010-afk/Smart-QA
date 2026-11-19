"""Crash recovery: re-dispatch jobs whose pipeline is still queued/running (docs/12 §2-3).

Uses the same `job_key` as the original dispatch, so a worker that already finished the job
ignores the duplicate. Execute jobs carry `resume_after_case_id` (= run.last_completed_case_id)
so a run continues from the last finished case instead of starting over (NFR-4).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session, aliased, sessionmaker

from apps.api.db import audit, outbox
from apps.api.db.models import PipelineState, Run
from apps.api.db.session import project_session
from apps.orchestrator.engine import current, job_payload
from apps.orchestrator.machine import Stage, Status

STALLED = (Status.QUEUED.value, Status.RUNNING.value)


def find_stalled(s: Session, older_than: timedelta, now: datetime) -> list[PipelineState]:
    """Newest state per (project, run) that is queued/running and older than `older_than`."""
    latest = (
        select(PipelineState)
        .ext(distinct_on(PipelineState.project_id, PipelineState.run_id))
        .order_by(PipelineState.project_id, PipelineState.run_id, PipelineState.entered_at.desc())
        .subquery()
    )
    row = aliased(PipelineState, latest)
    stmt = select(row).where(row.status.in_(STALLED), row.entered_at <= now - older_than)
    return list(s.scalars(stmt))


def recover(
    factory: sessionmaker[Session],
    older_than: timedelta = timedelta(0),
    now: datetime | None = None,
) -> int:
    """Re-dispatch every stalled job. Returns how many were re-queued."""
    now = now or datetime.now(UTC)
    with factory.begin() as s:
        stalled = [(st.id, st.project_id, st.run_id) for st in find_stalled(s, older_than, now)]
    count = 0
    for state_id, project_id, run_id in stalled:
        with project_session(factory, project_id) as s:
            state = current(s, run_id)
            if state is None or state.id != state_id:  # moved on since the scan
                continue
            extra: dict[str, Any] = {"recovered": True}
            if state.stage == Stage.EXECUTE.value and run_id is not None:
                run = s.get(Run, run_id)
                last = run.last_completed_case_id if run else None
                extra["resume_after_case_id"] = str(last) if last else None
            outbox.enqueue(
                s, project_id=project_id, topic=f"job.{state.stage}",
                payload=job_payload(state, **extra),
            )  # fmt: skip
            audit.record(
                s, project_id=project_id, actor="system:recovery", action="pipeline.recovered",
                entity=f"pipeline:{run_id or project_id}", payload={"stage": state.stage},
            )  # fmt: skip
            count += 1
    return count
