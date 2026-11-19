"""Seed rows that gate guards look at (graph, plan, cases, run, bugs)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from apps.api.db.models import (
    Bug,
    Environment,
    GraphVersion,
    Node,
    Plan,
    Result,
    Run,
    Segment,
    TestCase,
    Verdict,
)


@dataclass
class Seed:
    graph: GraphVersion
    plan: Plan
    case: TestCase
    run: Run
    bug: Bug


def seed(s: Session, pid: uuid.UUID) -> Seed:
    graph = GraphVersion(project_id=pid, number=1, status="draft")
    s.add(graph)
    s.flush()
    journey = Node(project_id=pid, graph_version_id=graph.id, type="Journey", label="Checkout")
    plan = Plan(project_id=pid, graph_version_id=graph.id, status="draft")
    s.add_all([journey, plan])
    s.flush()
    seg = Segment(project_id=pid, plan_id=plan.id, journey_node_id=journey.id,
                  suggested_count=1, risk_score=1.0, priority="Must")  # fmt: skip
    env = Environment(project_id=pid, name="local", kind="local", base_url="http://localhost")
    s.add_all([seg, env])
    s.flush()
    case = TestCase(
        project_id=pid, segment_id=seg.id, code="TC-CHK-001", role="buyer",
        technique="happy_path", priority="Must", expected_text="Order placed",
    )  # fmt: skip
    s.add(case)
    s.flush()
    run = Run(project_id=pid, env_id=env.id, plan_id=plan.id)
    s.add(run)
    s.flush()
    result = Result(project_id=pid, run_id=run.id, test_case_id=case.id, status="failed")
    s.add(result)
    s.flush()
    verdict = Verdict(project_id=pid, result_id=result.id, verdict="fail", confidence=0.9,
                      reason="500 on submit")  # fmt: skip
    s.add(verdict)
    s.flush()
    bug = Bug(project_id=pid, verdict_id=verdict.id, title="Checkout 500", severity="high",
              body_md="...")  # fmt: skip
    s.add(bug)
    s.flush()
    return Seed(graph, plan, case, run, bug)
