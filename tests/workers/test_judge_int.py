"""Judge: rules per case, clean re-run round trip, verdict rows with rule ids, bug drafts (US-07)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from apps.api import runs
from apps.api.db.models import Bug, PipelineState, Result, Run, RunnerJob, TestCase, Verdict
from apps.api.db.session import project_session
from apps.api.storage import MemoryObjectStore
from apps.workers.compiler import handle_compile_job
from apps.workers.executor import handle_execute_job
from apps.workers.judge import WORKER, attempt_of, handle_judge_job
from packages.contracts.run import AttemptResult, Failure
from tests.workers.test_compiler_int import _pipeline, _seed

pytestmark = pytest.mark.integration


def _stage(app: sessionmaker[Session], pid: uuid.UUID) -> tuple[str, str]:
    with project_session(app, pid) as s:
        st = s.scalars(select(PipelineState).order_by(PipelineState.entered_at.desc())).first()
        assert st is not None
        return st.stage, st.status


def _report(app: sessionmaker[Session], pid: uuid.UUID, results: dict[str, AttemptResult]) -> None:
    """Act as the runners: write each case's attempt and close its job."""
    with project_session(app, pid) as s:
        run = s.scalars(select(Run)).one()
        for code, result in results.items():
            case_id = s.scalars(select(TestCase.id).where(TestCase.code == code)).one()
            runs.write_result(s, pid, run.id, case_id, result)
            s.execute(
                update(RunnerJob)
                .where(RunnerJob.test_case_id == case_id, RunnerJob.attempt == result.attempt)
                .values(status="done")
            )
        runs.finish_if_done(s, pid, run.id, WORKER)


def fail(n: int, msg: str = "Expected 'Total: 10.00' not met", **kw: Any) -> AttemptResult:
    failure = Failure(kind="assertion", message=msg, step_n=4, expected="Total: 10.00",
                      actual="Total: 9.00")  # fmt: skip
    return AttemptResult(attempt=n, status="failed", failure=failure, evidence_count=2,
                         duration_ms=1000, http_status=200, **kw)  # fmt: skip


def ok(n: int, **kw: Any) -> AttemptResult:
    return AttemptResult(attempt=n, status="passed", expectations_checked=1, evidence_count=2,
                         duration_ms=1000, **kw)  # fmt: skip


def test_judge_round_trip(app: sessionmaker[Session], make_tenant: Any) -> None:
    pid = make_tenant().project_id
    with project_session(app, pid) as s:
        _seed(s, pid, envs=[("dev", "local")])
        # make TC-CAR-005 cited but TC-CAR-002 uncited (no Pass possible)
        s.execute(update(TestCase).where(TestCase.code == "TC-CAR-002")
                  .values(citation={"status": "unable_to_verify"}))  # fmt: skip
        _pipeline(s, pid)
    handle_compile_job(app, MemoryObjectStore(), None, {"project_id": str(pid)})
    handle_execute_job(app, {"project_id": str(pid)})
    # 001 fails (real bug), 002 passes but uncited, 005 fails with noise (flaky)
    _report(app, pid, {"TC-CAR-001": fail(1), "TC-CAR-002": ok(1),
                       "TC-CAR-005": fail(1, network_errors=2)})  # fmt: skip
    assert _stage(app, pid) == ("judge", "queued")

    handle_judge_job(app, {"project_id": str(pid)})
    assert _stage(app, pid) == ("execute", "queued")
    with project_session(app, pid) as s:
        reruns = s.scalars(select(RunnerJob).where(RunnerJob.attempt == 2)).all()
        assert len(reruns) == 2 and s.scalars(select(Run)).one().status == "running"
        assert len(s.scalars(select(Verdict)).all()) == 2  # 002 (UV) and 003 (not compiled)
    handle_judge_job(app, {"project_id": str(pid)})  # stale redelivery: nothing changes
    handle_execute_job(app, {"project_id": str(pid)})
    assert _stage(app, pid) == ("execute", "running")  # waiting for the re-runs

    _report(app, pid, {"TC-CAR-001": fail(2), "TC-CAR-005": ok(2)})
    assert _stage(app, pid) == ("judge", "queued")
    handle_judge_job(app, {"project_id": str(pid)})
    assert _stage(app, pid) == ("bug_review", "awaiting_approval")
    with project_session(app, pid) as s:
        rows = s.execute(
            select(TestCase.code, Verdict.verdict, Verdict.rule, Verdict.confidence, Result.attempt)
            .join(Result, Result.id == Verdict.result_id)
            .join(TestCase, TestCase.id == Result.test_case_id)
            .order_by(TestCase.code)
        ).all()
        got = {code: (v, rule, attempt) for code, v, rule, _, attempt in rows}
        assert got == {
            "TC-CAR-001": ("fail", "J3.fail_same_twice", 2),
            "TC-CAR-002": ("unable_to_verify", "J6.no_verified_quote", 1),
            "TC-CAR-003": ("test_error", "J4.our_fault", 1),
            "TC-CAR-005": ("flaky", "J2.pass_on_rerun_with_noise", 2),
        }
        assert next(c for code, *_r, c, _a in rows if code == "TC-CAR-001") >= 0.8  # High
        bugs = s.scalars(select(Bug)).all()
        assert len(bugs) == 1 and bugs[0].status == "draft"  # only the Fail becomes a bug
        totals = s.scalars(select(Run)).one().totals
        assert totals["verdicts"] == {"fail": 1, "unable_to_verify": 1, "test_error": 1, "flaky": 1}


def test_judge_without_run_fails(app: sessionmaker[Session], make_tenant: Any) -> None:
    pid = make_tenant().project_id
    with project_session(app, pid) as s:
        _pipeline(s, pid)
        s.execute(update(PipelineState).values(stage="judge"))
    handle_judge_job(app, {"project_id": str(pid)})
    assert _stage(app, pid) == ("judge", "failed")


def test_attempt_of_falls_back_to_columns() -> None:
    row = Result(attempt=2, status="passed", duration_ms=None, details={"bogus": 1, "status": 3})
    assert attempt_of(row) == AttemptResult(attempt=2, status="passed")
