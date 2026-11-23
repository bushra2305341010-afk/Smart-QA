"""Planner worker (stage 3, `job.plan`): approved graph → draft coverage plan (sector 03).

Counts, risk and priority come from `packages.planning` (deterministic code; no model call),
each segment keeps its technique rows with reasons, and the plan carries a design-cost
estimate. Older draft plans are superseded. The pipeline then waits at Gate 2.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from apps.api import learning
from apps.api.db.models import Edge, GraphVersion, Node, Plan, Segment
from apps.api.db.session import project_session
from apps.api.pricing import cost_estimate
from apps.api.settings import Settings
from apps.orchestrator import engine
from apps.orchestrator.machine import TransitionError
from packages.graph.model import norm_label
from packages.planning.counts import suggest_segment
from packages.planning.from_graph import EdgeView, NodeView, journeys_from_graph

log = logging.getLogger(__name__)
WORKER = engine.Actor("system", "worker:planner")


class PlannerError(Exception):
    pass


def plan_from_graph(
    factory: sessionmaker[Session], settings: Settings, pid: uuid.UUID
) -> tuple[uuid.UUID, int, int]:
    """Create the draft plan. Returns (plan id, segments, suggested cases)."""
    with project_session(factory, pid) as s:
        gv = s.scalar(select(GraphVersion).where(GraphVersion.status == "approved"))
        if gv is None:
            raise PlannerError("No approved graph version")
        nodes = s.scalars(
            select(Node).where(Node.graph_version_id == gv.id, Node.review_status != "rejected")
        ).all()
        ids = {n.id for n in nodes}
        edges = s.scalars(select(Edge).where(Edge.from_node_id.in_(ids))).all()
        views = [NodeView(str(n.id), n.type, n.label, dict(n.attrs)) for n in nodes]
        edge_views = [
            EdgeView(str(e.from_node_id), str(e.to_node_id), e.kind)
            for e in edges
            if e.to_node_id in ids
        ]
        journeys = journeys_from_graph(views, edge_views)
        if not journeys:
            raise PlannerError("The approved graph has no journeys to plan")
        for old in s.scalars(select(Plan).where(Plan.status == "draft")):
            old.status = "superseded"
        plan = Plan(project_id=pid, graph_version_id=gv.id, status="draft")
        s.add(plan)
        s.flush()
        hints = learning.count_hints(s)
        total = 0
        for spec, risk in journeys:
            seg = suggest_segment(spec, risk)
            total += seg.suggested_count
            s.add(
                Segment(
                    project_id=pid,
                    plan_id=plan.id,
                    journey_node_id=uuid.UUID(spec.journey_id),
                    techniques={
                        "journey": spec.name,
                        "rows": [r.model_dump() for r in seg.rows],
                        "base_count": seg.base_count,
                        "multiplier": seg.multiplier,
                        "risk_inputs": risk.model_dump(),
                        # Shown to reviewers only; counts still come from code (docs/21 A5).
                        "previous_decision": hints.get(norm_label(spec.name)),
                    },
                    suggested_count=seg.suggested_count,
                    risk_score=seg.risk_score,
                    priority=seg.priority,
                )
            )
        plan.cost_estimate = cost_estimate(settings, total)
        return plan.id, len(journeys), total


def handle_plan_job(
    factory: sessionmaker[Session], settings: Settings, message: dict[str, Any]
) -> None:
    pid = uuid.UUID(message["project_id"])

    def send(event: str, **payload: Any) -> None:
        try:
            with project_session(factory, pid) as s:
                engine.transition(s, pid, event, WORKER, payload=payload or None)
        except TransitionError as exc:
            log.info("pipeline moved on; %s", exc)

    send("job_started")
    try:
        _, segments, cases = plan_from_graph(factory, settings, pid)
    except PlannerError as exc:
        send("job_failed", reason=str(exc))
        return
    send("plan_ready", segments=segments, suggested_cases=cases)
