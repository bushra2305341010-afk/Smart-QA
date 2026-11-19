"""Transition table tests: every stage x every event (sector 12 change-safety list)."""

import itertools

import pytest

from apps.orchestrator.engine import job_key
from apps.orchestrator.machine import (
    CONTROL_EVENTS,
    GATE_STAGES,
    TRANSITIONS,
    USER_EVENTS,
    WORK_STAGES,
    Stage,
    Status,
    TransitionError,
    plan_control,
    plan_step,
    status_on_entry,
)
from apps.orchestrator.relay import EVENTS_STREAM, JOBS_STREAM, RedisPublisher

STEP_EVENTS = sorted({e for _, e in TRANSITIONS})


@pytest.mark.parametrize(
    ("stage", "status", "event"),
    list(itertools.product(list(Stage), list(Status), STEP_EVENTS)),
)
def test_every_stage_status_event(stage: Stage, status: Status, event: str) -> None:
    rule = TRANSITIONS.get((stage, event))
    expected_status = (
        {Status.AWAITING_APPROVAL} if stage in GATE_STAGES else {Status.QUEUED, Status.RUNNING}
    )
    if rule is not None and status in expected_status:
        assert plan_step(stage, status, event) is rule
    else:
        with pytest.raises(TransitionError):
            plan_step(stage, status, event)


def test_no_pipeline_rejects_step_events() -> None:
    with pytest.raises(TransitionError, match="no pipeline"):
        plan_step(None, None, "graph_ready")


def test_mandatory_gates_only_open_by_a_human() -> None:
    """Gates 1, 2 and 4 are always on: no system event may leave those stages forward."""
    for (stage, _event), rule in TRANSITIONS.items():
        if stage in {Stage.GRAPH_REVIEW, Stage.PLAN_APPROVAL, Stage.BUG_REVIEW}:
            assert rule.actor == "user" and rule.permission is not None
        if rule.gate in {1, 2, 4}:
            assert rule.actor == "user"
    assert {r.gate for r in TRANSITIONS.values() if r.gate} == {1, 2, 3, 4}
    system_gate = [r for r in TRANSITIONS.values() if r.actor == "system" and r.gate]
    assert [r.gate for r in system_gate] == [3]


def test_pipeline_reaches_done_in_order() -> None:
    stage, path = Stage.INGEST, [Stage.INGEST]
    forward = {s: r for (s, e), r in TRANSITIONS.items() if e not in {
        "graph_rejected", "plan_edited", "rerun_needed", "cases_auto_approved"}}  # fmt: skip
    while stage != Stage.DONE:
        stage = forward[stage].target
        path.append(stage)
    assert path == list(Stage)


@pytest.mark.parametrize(
    ("stage", "status", "event", "expected"),
    [
        (None, None, "start", (Stage.INGEST, Status.QUEUED)),
        (Stage.DONE, Status.DONE, "start", (Stage.INGEST, Status.QUEUED)),
        (Stage.PLAN, Status.CANCELLED, "start", (Stage.INGEST, Status.QUEUED)),
        (Stage.PLAN, Status.QUEUED, "job_started", (Stage.PLAN, Status.RUNNING)),
        (Stage.PLAN, Status.RUNNING, "job_failed", (Stage.PLAN, Status.FAILED)),
        (Stage.PLAN, Status.QUEUED, "job_failed", (Stage.PLAN, Status.FAILED)),
        (Stage.PLAN, Status.FAILED, "retry", (Stage.PLAN, Status.QUEUED)),
        (
            Stage.GRAPH_REVIEW,
            Status.AWAITING_APPROVAL,
            "cancel",
            (Stage.GRAPH_REVIEW, Status.CANCELLED),
        ),
        (Stage.PLAN, Status.FAILED, "cancel", (Stage.PLAN, Status.CANCELLED)),
    ],
)
def test_control_events(stage, status, event, expected) -> None:  # type: ignore[no-untyped-def]
    assert plan_control(stage, status, event) == expected


@pytest.mark.parametrize(
    ("stage", "status", "event"),
    [
        (Stage.PLAN, Status.QUEUED, "start"),
        (None, None, "retry"),
        (None, None, "cancel"),
        (Stage.PLAN, Status.RUNNING, "job_started"),
        (Stage.PLAN, Status.FAILED, "job_failed"),
        (Stage.PLAN, Status.QUEUED, "retry"),
        (Stage.DONE, Status.DONE, "cancel"),
        (Stage.PLAN, Status.CANCELLED, "cancel"),
    ],
)
def test_control_events_rejected(stage, status, event) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(TransitionError):
        plan_control(stage, status, event)


def test_status_on_entry() -> None:
    assert all(status_on_entry(s) == Status.QUEUED for s in WORK_STAGES)
    assert all(status_on_entry(s) == Status.AWAITING_APPROVAL for s in GATE_STAGES)
    assert status_on_entry(Stage.DONE) == Status.DONE


def test_user_events_exclude_system_events() -> None:
    assert "graph_approved" in USER_EVENTS and "start" in USER_EVENTS
    assert not USER_EVENTS & {"graph_ready", "job_failed", "cases_auto_approved"}
    assert set(CONTROL_EVENTS) >= {"start", "retry", "cancel", "job_started", "job_failed"}


def test_job_key_and_streams() -> None:
    import uuid

    sid = uuid.uuid4()
    assert job_key(sid) == job_key(sid) != job_key(uuid.uuid4())
    assert RedisPublisher.stream_for("job.plan") == JOBS_STREAM
    assert RedisPublisher.stream_for("stage.changed") == EVENTS_STREAM
