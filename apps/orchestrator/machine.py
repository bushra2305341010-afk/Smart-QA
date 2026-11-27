"""Pipeline state machine (docs/03-system-workflow.md §2, ADR-002). Pure: no I/O.

A pipeline is at one `Stage` with one `Status`. Work stages dispatch a job and wait for the
worker's completion event; gate stages wait for a human. `TRANSITIONS` is the whole contract:
any (stage, event) pair not listed is rejected, so a gate cannot be skipped by calling a later
event, and human gate events can never be sent by a worker (or the reverse).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from apps.api.auth.permissions import Permission

ActorKind = Literal["user", "system"]


class Stage(StrEnum):
    INGEST = "ingest"
    UNDERSTAND = "understand"
    GRAPH_REVIEW = "graph_review"
    PLAN = "plan"
    PLAN_APPROVAL = "plan_approval"
    DESIGN = "design"
    CASE_REVIEW = "case_review"
    COMPILE = "compile"
    EXECUTE = "execute"
    JUDGE = "judge"
    BUG_REVIEW = "bug_review"
    REPORT = "report"
    DONE = "done"


class Status(StrEnum):
    QUEUED = "queued"  # job dispatched via outbox, not yet picked up
    RUNNING = "running"  # a worker reported it started
    AWAITING_APPROVAL = "awaiting_approval"  # gate stage, waiting for a human
    FAILED = "failed"  # job failed; `retry` re-dispatches the same stage
    CANCELLED = "cancelled"
    DONE = "done"


WORK_STAGES = frozenset(
    {
        Stage.INGEST,
        Stage.UNDERSTAND,
        Stage.PLAN,
        Stage.DESIGN,
        Stage.COMPILE,
        Stage.EXECUTE,
        Stage.JUDGE,
        Stage.REPORT,
    }
)
GATE_STAGES = frozenset(
    {Stage.GRAPH_REVIEW, Stage.PLAN_APPROVAL, Stage.CASE_REVIEW, Stage.BUG_REVIEW}
)
# Stages whose jobs call a model, so the budget is checked before dispatch (docs/12 §2).
MODEL_STAGES = frozenset({Stage.UNDERSTAND, Stage.PLAN, Stage.DESIGN, Stage.JUDGE})
ACTIVE = frozenset({Status.QUEUED, Status.RUNNING, Status.AWAITING_APPROVAL, Status.FAILED})


@dataclass(frozen=True)
class Rule:
    target: Stage
    actor: ActorKind
    permission: Permission | None = None
    gate: int | None = None


TRANSITIONS: dict[tuple[Stage, str], Rule] = {
    (Stage.INGEST, "sources_parsed"): Rule(Stage.UNDERSTAND, "system"),
    (Stage.UNDERSTAND, "graph_ready"): Rule(Stage.GRAPH_REVIEW, "system"),
    (Stage.GRAPH_REVIEW, "graph_rejected"): Rule(Stage.UNDERSTAND, "user", "graph.approve"),
    (Stage.GRAPH_REVIEW, "graph_approved"): Rule(Stage.PLAN, "user", "graph.approve", gate=1),
    (Stage.PLAN, "plan_ready"): Rule(Stage.PLAN_APPROVAL, "system"),
    (Stage.PLAN_APPROVAL, "plan_edited"): Rule(Stage.PLAN, "user", "plan.approve"),
    (Stage.PLAN_APPROVAL, "plan_approved"): Rule(Stage.DESIGN, "user", "plan.approve", gate=2),
    (Stage.DESIGN, "cases_ready"): Rule(Stage.CASE_REVIEW, "system"),
    (Stage.CASE_REVIEW, "cases_approved"): Rule(Stage.COMPILE, "user", "cases.approve", gate=3),
    # Gate 3 is the only optional gate: skipped only when the project enables `gate3_auto`.
    (Stage.CASE_REVIEW, "cases_auto_approved"): Rule(Stage.COMPILE, "system", gate=3),
    (Stage.COMPILE, "compiled"): Rule(Stage.EXECUTE, "system"),
    (Stage.EXECUTE, "results_ready"): Rule(Stage.JUDGE, "system"),
    (Stage.JUDGE, "rerun_needed"): Rule(Stage.EXECUTE, "system"),
    (Stage.JUDGE, "verdicts_ready"): Rule(Stage.BUG_REVIEW, "system"),
    (Stage.BUG_REVIEW, "bugs_confirmed"): Rule(Stage.REPORT, "user", "bug.confirm", gate=4),
    (Stage.REPORT, "reported"): Rule(Stage.DONE, "system"),
    # Regression run of the already-approved cases (no new model calls for unchanged cases);
    # Gate 3's precondition is re-checked, Gates 1, 2 and 4 stay in force.
    (Stage.DONE, "run_requested"): Rule(Stage.COMPILE, "user", "run.start", gate=3),
}

# Events that act on the current stage instead of moving along the pipeline.
CONTROL_EVENTS: dict[str, tuple[ActorKind, Permission | None]] = {
    "start": ("user", "pipeline.manage"),
    "retry": ("user", "pipeline.manage"),
    "cancel": ("user", "pipeline.manage"),
    "job_started": ("system", None),
    "job_failed": ("system", None),
}

USER_EVENTS = frozenset(
    {e for (_, e), r in TRANSITIONS.items() if r.actor == "user"}
    | {e for e, (kind, _) in CONTROL_EVENTS.items() if kind == "user"}
)


def status_on_entry(stage: Stage) -> Status:
    if stage in WORK_STAGES:
        return Status.QUEUED
    if stage in GATE_STAGES:
        return Status.AWAITING_APPROVAL
    return Status.DONE


class TransitionError(Exception):
    def __init__(self, stage: Stage | None, status: Status | None, event: str) -> None:
        where = f"{stage}/{status}" if stage else "no pipeline"
        super().__init__(f"Event '{event}' is not allowed at {where}")
        self.stage, self.status, self.event = stage, status, event


def plan_control(stage: Stage | None, status: Status | None, event: str) -> tuple[Stage, Status]:
    """Next (stage, status) for a control event, or raise TransitionError."""
    if event == "start":
        if stage is None or status in {Status.DONE, Status.CANCELLED}:
            return Stage.INGEST, Status.QUEUED
    elif stage is None:
        pass
    elif event == "job_started" and status == Status.QUEUED:
        return stage, Status.RUNNING
    elif event == "job_failed" and status in {Status.QUEUED, Status.RUNNING}:
        return stage, Status.FAILED
    elif event == "retry" and status == Status.FAILED:
        return stage, Status.QUEUED
    elif event == "cancel" and status in ACTIVE:
        return stage, Status.CANCELLED
    raise TransitionError(stage, status, event)


def plan_step(stage: Stage | None, status: Status | None, event: str) -> Rule:
    """The rule for a pipeline event, or raise TransitionError.

    Work stages accept their completion event only while the job is queued/running; gate stages
    accept decisions only while awaiting approval.
    """
    rule = TRANSITIONS.get((stage, event)) if stage else None
    if stage in GATE_STAGES:
        expected = {Status.AWAITING_APPROVAL}
    elif stage == Stage.DONE:
        expected = {Status.DONE}
    else:
        expected = {Status.QUEUED, Status.RUNNING}
    if rule is None or status not in expected:
        raise TransitionError(stage, status, event)
    return rule
