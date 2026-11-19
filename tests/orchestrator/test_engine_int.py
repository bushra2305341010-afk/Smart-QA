"""Orchestrator transitions, gates, budget, recovery and relay on real Postgres (+ Redis)."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db import audit
from apps.api.db.models import AuditEvent, ModelCall, Outbox, PipelineState, Project
from apps.api.db.session import project_session
from apps.orchestrator import engine, recover, relay
from apps.orchestrator.engine import Actor
from apps.orchestrator.guards import GuardError
from apps.orchestrator.machine import TransitionError
from tests.orchestrator.seed import seed

pytestmark = pytest.mark.integration

LEAD = Actor("user", "usr_lead", "qa_lead")
TESTER = Actor("user", "usr_tester", "tester")
SYSTEM = Actor("system", "worker")


def _send(app, pid, event, actor=SYSTEM, run_id=None, budget=20.0):  # type: ignore[no-untyped-def]
    with project_session(app, pid) as s:
        st = engine.transition(s, pid, event, actor, run_id=run_id, default_budget_usd=budget)
        return st.stage, st.status


def _topics(app, pid) -> list[str]:  # type: ignore[no-untyped-def]
    with project_session(app, pid) as s:
        rows = s.scalars(select(Outbox).order_by(Outbox.created_at)).all()
        return [r.topic for r in rows if r.topic.startswith("job.")]


def _gate_error(app, pid, event, actor=LEAD) -> GuardError:  # type: ignore[no-untyped-def]
    with pytest.raises(GuardError) as exc:
        _send(app, pid, event, actor)
    return exc.value


def test_full_pipeline_with_server_side_gates(app: sessionmaker[Session], make_tenant) -> None:
    pid = make_tenant().project_id
    with project_session(app, pid) as s:
        data = seed(s, pid)

    assert _send(app, pid, "start", LEAD) == ("ingest", "queued")
    assert _send(app, pid, "sources_parsed") == ("understand", "queued")
    assert _send(app, pid, "graph_ready") == ("graph_review", "awaiting_approval")
    err = _gate_error(app, pid, "graph_approved")
    assert (err.status, err.code, err.details) == (409, "GATE_NOT_APPROVED", {"gate": 1})
    with project_session(app, pid) as s:
        s.get_one(type(data.graph), data.graph.id).status = "approved"
    assert _send(app, pid, "graph_approved", LEAD) == ("plan", "queued")
    assert _send(app, pid, "plan_ready") == ("plan_approval", "awaiting_approval")
    assert _gate_error(app, pid, "plan_approved").details == {"gate": 2}
    with project_session(app, pid) as s:
        s.get_one(type(data.plan), data.plan.id).status = "approved"
    assert _send(app, pid, "plan_approved", LEAD) == ("design", "queued")
    assert _send(app, pid, "cases_ready") == ("case_review", "awaiting_approval")
    assert "1 test case" in _gate_error(app, pid, "cases_approved").message
    with project_session(app, pid) as s:
        s.get_one(type(data.case), data.case.id).review_status = "approved"
    assert _send(app, pid, "cases_approved", TESTER) == ("compile", "queued")
    assert _send(app, pid, "compiled") == ("execute", "queued")
    assert _send(app, pid, "results_ready") == ("judge", "queued")
    assert _send(app, pid, "rerun_needed") == ("execute", "queued")  # clean re-run
    assert _send(app, pid, "results_ready") == ("judge", "queued")
    assert _send(app, pid, "verdicts_ready") == ("bug_review", "awaiting_approval")
    assert _gate_error(app, pid, "bugs_confirmed").details == {"gate": 4}
    with project_session(app, pid) as s:
        s.get_one(type(data.bug), data.bug.id).status = "confirmed"
    assert _send(app, pid, "bugs_confirmed", LEAD) == ("report", "queued")
    assert _send(app, pid, "reported") == ("done", "done")

    assert _topics(app, pid) == [
        "job.ingest", "job.understand", "job.plan", "job.design", "job.compile",
        "job.execute", "job.judge", "job.execute", "job.judge", "job.report",
    ]  # fmt: skip
    with project_session(app, pid) as s:
        check = audit.verify_chain(s, pid)
        assert check.ok and check.checked == 15
        assert len(engine.history(s)) == 15


def test_actor_and_permission_checks(app: sessionmaker[Session], make_tenant) -> None:
    pid = make_tenant().project_id
    _send(app, pid, "start", LEAD)
    with pytest.raises(GuardError, match="must come from a system"):
        _send(app, pid, "sources_parsed", LEAD)
    _send(app, pid, "sources_parsed")
    _send(app, pid, "graph_ready")
    err = _gate_error(app, pid, "graph_approved", TESTER)
    assert err.status == 403 and err.details == {"permission": "graph.approve"}
    assert _gate_error(app, pid, "graph_approved", SYSTEM).details == {"actor": "system"}
    with pytest.raises(GuardError):
        _send(app, pid, "start", TESTER)
    with pytest.raises(TransitionError):
        _send(app, pid, "plan_ready")  # skipping ahead is impossible
    assert _send(app, pid, "graph_rejected", LEAD) == ("understand", "queued")


def test_job_lifecycle_retry_and_cancel(app: sessionmaker[Session], make_tenant) -> None:
    pid = make_tenant().project_id
    with pytest.raises(TransitionError):
        _send(app, pid, "job_started")
    _send(app, pid, "start", LEAD)
    assert _send(app, pid, "job_started") == ("ingest", "running")
    assert _send(app, pid, "job_failed") == ("ingest", "failed")
    assert _send(app, pid, "retry", LEAD) == ("ingest", "queued")
    with project_session(app, pid) as s:
        jobs = [o.payload for o in s.scalars(select(Outbox).where(Outbox.topic == "job.ingest"))]
    assert sorted(j["attempt"] for j in jobs) == [1, 2]
    assert _send(app, pid, "cancel", LEAD) == ("ingest", "cancelled")
    assert _send(app, pid, "start", LEAD) == ("ingest", "queued")


def test_gate3_auto_needs_project_switch(app: sessionmaker[Session], make_tenant) -> None:
    pid = make_tenant().project_id
    with project_session(app, pid) as s:
        seed(s, pid)
        s.add(PipelineState(project_id=pid, stage="case_review", status="awaiting_approval",
                            entered_at=datetime.now(UTC)))  # fmt: skip
    assert "gate3_auto" in _gate_error(app, pid, "cases_auto_approved", SYSTEM).message
    with project_session(app, pid) as s:
        s.get_one(Project, pid).settings = {"gate3_auto": True}
    assert _send(app, pid, "cases_auto_approved") == ("compile", "queued")


def test_budget_blocks_model_stages(app: sessionmaker[Session], make_tenant) -> None:
    pid = make_tenant().project_id
    _send(app, pid, "start", LEAD)
    with project_session(app, pid) as s:
        s.add(ModelCall(project_id=pid, stage="understand", model="m", prompt_version="v1",
                        cost_usd=Decimal("5.00")))  # fmt: skip
    with pytest.raises(GuardError) as exc:
        _send(app, pid, "sources_parsed", budget=5.0)
    assert exc.value.status == 402 and exc.value.details["cap_usd"] == "5.0"
    with project_session(app, pid) as s:
        s.get_one(Project, pid).settings = {"budget_monthly_usd": 50}
    assert _send(app, pid, "sources_parsed", budget=5.0) == ("understand", "queued")


def test_recovery_redispatches_with_same_key_and_resume_point(
    app: sessionmaker[Session], system: sessionmaker[Session], make_tenant
) -> None:
    pid = make_tenant().project_id
    with project_session(app, pid) as s:
        data = seed(s, pid)
        data.run.last_completed_case_id = data.case.id
        run_id = data.run.id
    _send(app, pid, "start", LEAD)  # project pipeline: ingest queued
    with project_session(app, pid) as s:
        s.add(PipelineState(project_id=pid, run_id=run_id, stage="execute", status="running",
                            entered_at=datetime.now(UTC)))  # fmt: skip
    assert recover.recover(system, older_than=timedelta(hours=1)) == 0  # too fresh
    assert recover.recover(system) >= 2
    with project_session(app, pid) as s:
        ingest = [o.payload for o in s.scalars(select(Outbox).where(Outbox.topic == "job.ingest"))]
        execute = [
            o.payload for o in s.scalars(select(Outbox).where(Outbox.topic == "job.execute"))
        ]
        recovered = s.scalar(select(func.count()).where(AuditEvent.action == "pipeline.recovered"))
    assert len(ingest) == 2 and ingest[0]["job_key"] == ingest[1]["job_key"]
    assert execute[0]["resume_after_case_id"] == str(data.case.id) and execute[0]["recovered"]
    assert recovered == 2


def test_recovery_skips_states_that_moved_on(
    app: sessionmaker[Session], system: sessionmaker[Session], make_tenant, monkeypatch
) -> None:
    pid = make_tenant().project_id
    _send(app, pid, "start", LEAD)
    with system.begin() as s:
        stale = [
            x
            for x in recover.find_stalled(s, timedelta(0), datetime.now(UTC))
            if x.project_id == pid
        ]
    _send(app, pid, "sources_parsed")
    monkeypatch.setattr(recover, "find_stalled", lambda *_: stale)
    assert recover.recover(system) == 0


def test_recovery_execute_without_resume_point(
    app: sessionmaker[Session], system: sessionmaker[Session], make_tenant, monkeypatch
) -> None:
    pid = make_tenant().project_id
    with project_session(app, pid) as s:
        run_id = seed(s, pid).run.id
        s.add(PipelineState(project_id=pid, run_id=run_id, stage="execute", status="queued",
                            entered_at=datetime.now(UTC)))  # fmt: skip
    with system.begin() as s:
        mine = [
            x
            for x in recover.find_stalled(s, timedelta(0), datetime.now(UTC))
            if x.project_id == pid
        ]
    monkeypatch.setattr(recover, "find_stalled", lambda *_: mine)
    assert recover.recover(system) == 1
    with project_session(app, pid) as s:
        job = s.scalar(select(Outbox.payload).where(Outbox.topic == "job.execute"))
    assert job["resume_after_case_id"] is None


class ListPublisher:
    def __init__(self, fail_on: int | None = None) -> None:
        self.sent: list[tuple[str, dict]] = []
        self.fail_on = fail_on

    def publish(self, topic: str, message: dict) -> None:
        if self.fail_on is not None and len(self.sent) == self.fail_on:
            raise ConnectionError("redis down")
        self.sent.append((topic, message))


def _drain(system: sessionmaker[Session]) -> None:
    while relay.relay_once(system, ListPublisher(), limit=1000):
        pass


def test_relay_publishes_in_order_and_marks(
    app: sessionmaker[Session], system: sessionmaker[Session], make_tenant
) -> None:
    _drain(system)
    pid = make_tenant().project_id
    _send(app, pid, "start", LEAD)  # stage.changed + job.ingest
    _send(app, pid, "job_started")  # stage.changed
    failing = ListPublisher(fail_on=1)
    assert relay.relay_once(system, failing) == 1  # stops at the failure, keeps the rest
    pub = ListPublisher()
    assert relay.relay_once(system, pub) == 2
    assert [t for t, _ in pub.sent] == ["job.ingest", "stage.changed"]
    assert pub.sent[0][1]["payload"]["stage"] == "ingest" and pub.sent[0][1]["event_id"]
    assert relay.relay_once(system, ListPublisher()) == 0


def test_runtime_role_cannot_relay_across_projects(
    app: sessionmaker[Session], system: sessionmaker[Session], make_tenant
) -> None:
    _drain(system)
    _send(app, make_tenant().project_id, "start", LEAD)
    assert relay.relay_once(app, ListPublisher()) == 0  # no scope → RLS shows nothing
    assert relay.relay_once(system, ListPublisher()) == 2


def test_serve_loop_stops(system: sessionmaker[Session]) -> None:
    _drain(system)
    stop = threading.Event()

    timer = threading.Timer(0.2, stop.set)
    timer.start()
    relay.serve(system, ListPublisher(), stop, interval_s=0.05)
    assert stop.is_set()


def test_serve_drains_backlog_then_stops(
    app: sessionmaker[Session], system: sessionmaker[Session], make_tenant
) -> None:
    _drain(system)
    _send(app, make_tenant().project_id, "start", LEAD)
    stop = threading.Event()

    class StopWhenDrained(ListPublisher):
        def publish(self, topic: str, message: dict) -> None:
            super().publish(topic, message)
            if len(self.sent) == 2:
                stop.set()

    pub = StopWhenDrained()
    relay.serve(system, pub, stop, interval_s=0.05)
    assert [t for t, _ in pub.sent] == ["stage.changed", "job.ingest"]


@pytest.mark.skipif(not os.environ.get("REDIS_URL"), reason="REDIS_URL not set")
def test_redis_publisher_writes_streams(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import redis

    client = redis.Redis.from_url(os.environ["REDIS_URL"])
    stream = f"test:{uuid.uuid4().hex}"
    monkeypatch.setattr(relay, "JOBS_STREAM", stream)
    relay.RedisPublisher(client).publish("job.plan", {"b": 1, "a": 2})
    ((_, fields),) = client.xrange(stream)
    assert fields[b"topic"] == b"job.plan"
    assert json.loads(fields[b"message"]) == {"a": 2, "b": 1}
    client.delete(stream)
