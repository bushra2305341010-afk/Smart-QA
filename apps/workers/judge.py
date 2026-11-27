"""Judge worker (`job.judge`, sector 06, M10b): attempts → honest verdicts (P3).

For every case of the latest run:
- the M05 rules (`packages.verdicts.rules.decide`) decide from attempt 1 and, if present, the
  clean re-run (attempt 2); the quote must be verified or there is no Pass;
- a first failure without a re-run queues attempt 2 (fresh browser context) and the pipeline
  goes back to Execute (`rerun_needed`); the runners' results bring it back here;
- otherwise one `verdict` row on the deciding attempt, with the rule id, reason and confidence.
When every case has a verdict, Fail verdicts become bug drafts (`reporter.draft_bugs`, which
also applies learned suppressions) and the pipeline moves to Gate 4 (`verdicts_ready`).
Idempotent: cases that already have a verdict or a queued re-run are skipped.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from apps.api import runs
from apps.api.db.models import Result, RunnerJob, TestCase, Verdict
from apps.api.db.session import project_session
from apps.orchestrator import engine
from apps.orchestrator.machine import TransitionError
from apps.workers.reporter import draft_bugs
from packages.contracts.run import AttemptResult
from packages.verdicts.rules import Rerun, decide

log = logging.getLogger(__name__)
WORKER = engine.Actor("system", "worker:judge")


class JudgeError(Exception):
    pass


@dataclass(frozen=True)
class JudgeOutcome:
    run_id: uuid.UUID
    reruns: int
    verdicts: dict[str, int]


def attempt_of(row: Result) -> AttemptResult:
    """The runner's full result; rows without details (older data) fall back to the columns."""
    try:
        return AttemptResult.model_validate({**row.details, "attempt": row.attempt})
    except ValidationError:
        return AttemptResult(
            attempt=row.attempt,
            status=row.status,
            duration_ms=row.duration_ms or 0,
        )


def judge_run(s: Session, pid: uuid.UUID) -> JudgeOutcome:
    run = runs.latest_run(s)
    if run is None:
        raise JudgeError("No run to judge")
    rows = s.scalars(
        select(Result).where(Result.run_id == run.id).order_by(Result.test_case_id, Result.attempt)
    ).all()
    by_case: dict[uuid.UUID, list[Result]] = {}
    for row in rows:
        by_case.setdefault(row.test_case_id, []).append(row)
    judged = set(
        s.scalars(
            select(Result.test_case_id)
            .join(Verdict, Verdict.result_id == Result.id)
            .where(Result.run_id == run.id)
        )
    )
    queued = set(
        s.scalars(
            select(RunnerJob.test_case_id).where(RunnerJob.run_id == run.id, RunnerJob.attempt == 2)
        )
    )
    reruns = 0
    for case_id, attempts in by_case.items():
        if case_id in judged:
            continue
        case = s.get_one(TestCase, case_id)
        cited = (case.citation or {}).get("status") == "verified"
        first = attempts[0]
        second = attempts[1] if len(attempts) > 1 else None
        decision = decide(
            attempt_of(first), attempt_of(second) if second else None, citation_verified=cited
        )
        if isinstance(decision, Rerun):
            if case_id not in queued:
                s.add(RunnerJob(project_id=pid, run_id=run.id, test_case_id=case_id, attempt=2))
                reruns += 1
            continue
        s.add(
            Verdict(
                project_id=pid,
                result_id=(second or first).id,
                verdict=decision.verdict,
                confidence=decision.confidence,
                reason=decision.reason,
                rule=decision.rule,
            )
        )
    s.flush()
    counts = Counter(
        s.scalars(
            select(Verdict.verdict)
            .join(Result, Result.id == Verdict.result_id)
            .where(Result.run_id == run.id)
        )
    )
    if reruns:
        run.status = "running"
    run.totals = {**run.totals, "verdicts": dict(counts)}
    return JudgeOutcome(run.id, reruns, dict(counts))


def handle_judge_job(factory: sessionmaker[Session], message: dict[str, Any]) -> None:
    pid = uuid.UUID(message["project_id"])

    def send(s: Session, event: str, **payload: Any) -> None:
        try:
            engine.transition(s, pid, event, WORKER, payload=payload or None)
        except TransitionError as exc:
            log.info("pipeline moved on; %s", exc)

    with project_session(factory, pid) as s:
        send(s, "job_started")
    try:
        with project_session(factory, pid) as s:
            outcome = judge_run(s, pid)
            if outcome.reruns:
                send(s, "rerun_needed", run_id=str(outcome.run_id), reruns=outcome.reruns)
                return
    except JudgeError as exc:
        with project_session(factory, pid) as s:
            send(s, "job_failed", reason=str(exc))
        return
    drafts = draft_bugs(factory, pid, outcome.run_id)
    with project_session(factory, pid) as s:
        send(s, "verdicts_ready", run_id=str(outcome.run_id), bug_drafts=drafts,
             **outcome.verdicts)  # fmt: skip
