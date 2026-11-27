"""Apply pipeline events: validate, guard, and persist in one transaction (sector 12 flow).

    event → machine rule → actor/permission check → DB guards → pipeline_state row
          + audit_event + outbox(stage.changed [+ job.<stage>])

`pipeline_state` is append-only history; the newest row per (project, run) is the current state.
A per-project advisory lock serialises transitions, so two approvals cannot race.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from apps.api.auth.permissions import allowed
from apps.api.db import audit, outbox
from apps.api.db.models import PipelineState
from apps.orchestrator import guards
from apps.orchestrator.machine import (
    CONTROL_EVENTS,
    MODEL_STAGES,
    WORK_STAGES,
    ActorKind,
    Stage,
    Status,
    plan_control,
    plan_step,
    status_on_entry,
)


@dataclass(frozen=True)
class Actor:
    kind: ActorKind
    id: str  # "usr_..." or a worker name
    role: str | None = None


# User events whose payload is handed to the dispatched job (e.g. env and journeys of a run).
PARAM_EVENTS = frozenset({"run_requested"})


def job_key(state_id: uuid.UUID) -> str:
    """One key per dispatch; re-dispatching the same state (recovery) reuses it (docs/12 §3)."""
    return hashlib.sha256(f"pipeline_state:{state_id}".encode()).hexdigest()


def current(s: Session, run_id: uuid.UUID | None = None) -> PipelineState | None:
    stmt = select(PipelineState).order_by(PipelineState.entered_at.desc()).limit(1)
    stmt = stmt.where(
        PipelineState.run_id.is_(None) if run_id is None else PipelineState.run_id == run_id
    )
    return s.scalar(stmt)


def history(s: Session, run_id: uuid.UUID | None = None) -> list[PipelineState]:
    stmt = select(PipelineState).order_by(PipelineState.entered_at)
    stmt = stmt.where(
        PipelineState.run_id.is_(None) if run_id is None else PipelineState.run_id == run_id
    )
    return list(s.scalars(stmt))


def _check_actor(actor: Actor, kind: ActorKind, permission: Any) -> None:
    if actor.kind != kind:
        raise guards.GuardError(
            403, "FORBIDDEN", f"This event must come from a {kind}", {"actor": actor.kind}
        )
    if permission and not allowed(actor.role or "", permission):
        raise guards.GuardError(
            403, "FORBIDDEN", "Your role lacks this permission", {"permission": permission}
        )


def job_payload(state: PipelineState, attempt: int = 1, **extra: Any) -> dict[str, Any]:
    return {
        "job_key": job_key(state.id),
        "project_id": str(state.project_id),
        "run_id": str(state.run_id) if state.run_id else None,
        "stage": state.stage,
        "state_id": str(state.id),
        "attempt": attempt,
        **extra,
    }


def transition(
    s: Session,
    project_id: uuid.UUID,
    event: str,
    actor: Actor,
    *,
    run_id: uuid.UUID | None = None,
    default_budget_usd: float = 20.0,
    payload: dict[str, Any] | None = None,
) -> PipelineState:
    """Apply `event` inside the caller's project-scoped transaction and return the new state.

    Raises `machine.TransitionError` (→ 409 STATE_CONFLICT) or `guards.GuardError`.
    """
    s.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
        {"k": f"pipeline:{project_id}:{run_id}"},
    )
    now_state = current(s, run_id)
    stage = Stage(now_state.stage) if now_state else None
    status = Status(now_state.status) if now_state else None
    gate: int | None = None

    if event in CONTROL_EVENTS:
        kind, permission = CONTROL_EVENTS[event]
        _check_actor(actor, kind, permission)
        new_stage, new_status = plan_control(stage, status, event)
    else:
        rule = plan_step(stage, status, event)
        _check_actor(actor, rule.actor, rule.permission)
        if rule.gate:
            guards.check_gate(s, project_id, rule.gate, event)
        new_stage, new_status, gate = rule.target, status_on_entry(rule.target), rule.gate

    dispatch = new_status == Status.QUEUED and new_stage in WORK_STAGES
    if dispatch and new_stage in MODEL_STAGES:
        guards.check_budget(s, project_id, default_budget_usd)

    state = PipelineState(
        project_id=project_id,
        run_id=run_id,
        stage=new_stage.value,
        status=new_status.value,
        entered_at=datetime.now(UTC),
    )
    s.add(state)
    s.flush()
    change = {
        "from": f"{stage}/{status}" if stage else None,
        "to": f"{new_stage}/{new_status}",
        "event": event,
        "gate": gate,
        **(payload or {}),
    }
    audit.record(
        s, project_id=project_id, actor=actor.id, action=f"pipeline.{event}",
        entity=f"pipeline:{run_id or project_id}", payload=change,
    )  # fmt: skip
    outbox.enqueue(
        s,
        project_id=project_id,
        topic="stage.changed",
        payload={
            "stage": state.stage,
            "status": state.status,
            "run_id": str(run_id) if run_id else None,
        },
    )
    if dispatch:
        attempt = 1 + _failed_attempts(s, run_id, new_stage) if event == "retry" else 1
        outbox.enqueue(
            s,
            project_id=project_id,
            topic=f"job.{state.stage}",
            payload=job_payload(
                state, attempt, **({"params": payload} if event in PARAM_EVENTS and payload else {})
            ),
        )
    return state


def _failed_attempts(s: Session, run_id: uuid.UUID | None, stage: Stage) -> int:
    stmt = select(func.count()).where(
        PipelineState.stage == stage.value, PipelineState.status == Status.FAILED.value
    )
    stmt = stmt.where(
        PipelineState.run_id.is_(None) if run_id is None else PipelineState.run_id == run_id
    )
    return int(s.scalar(stmt) or 0)
