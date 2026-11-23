"""Learning from human decisions (US-10, docs/21 A4/A5)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from apps.api.db.models import PipelineState, Result, Verdict
from apps.api.db.session import project_session
from apps.workers.analyst import handle_understand_job
from apps.workers.designer import handle_design_job
from apps.workers.gateway import gateway_factory
from apps.workers.planner import handle_plan_job
from apps.workers.reporter import draft_bugs
from tests.model_gateway.fakes import FakeProvider, ok
from tests.workers.test_analyst_int import SETTINGS, env  # noqa: F401
from tests.workers.test_designer_int import GRAPH, A, _through_gate2
from tests.workers.test_reporter_int import env as reporter_env  # noqa: F401

pytestmark = pytest.mark.integration
V1 = "/api/v1"


def _fail(app, puid, data, reason: str, attempt: int):  # type: ignore[no-untyped-def]
    with project_session(app, puid) as s:
        r = Result(project_id=puid, run_id=data.run.id, test_case_id=data.case.id,
                   attempt=attempt, status="failed")  # fmt: skip
        s.add(r)
        s.flush()
        s.add(
            Verdict(project_id=puid, result_id=r.id, verdict="fail", confidence=0.9, reason=reason)
        )


def test_dismissed_bug_is_not_drafted_again(reporter_env, app) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    client, pid, puid, data, _ = reporter_env
    draft_bugs(app, puid, data.run.id)
    bugs = client.get(f"{V1}/projects/{pid}/bugs").json()
    target = next(b for b in bugs if "Order total wrong" in b["title"])
    client.post(
        f"{V1}/projects/{pid}/bugs/{target['id']}/dismiss", json={"reason": "Admins see net totals"}
    )

    knowledge = client.get(f"{V1}/projects/{pid}/lessons").json()
    [lesson] = knowledge["lessons"]
    assert lesson["kind"] == "expected_behaviour" and "Admins see net totals" in lesson["text"]
    assert [r["kind"] for r in knowledge["rules"]] == ["suppress_bug"]

    _fail(app, puid, data, "Order total wrong for admin@shop.example", attempt=5)  # same failure
    _fail(app, puid, data, "Checkout button missing", attempt=6)  # a different failure
    assert draft_bugs(app, puid, data.run.id) == 1
    audit = client.get(f"{V1}/projects/{pid}/audit?limit=200").json()["items"]
    suppressed = [e for e in audit if e["action"] == "bug.suppressed"]
    assert len(suppressed) == 1 and "Admins see net totals" in suppressed[0]["payload"]["lesson"]

    off = client.post(f"{V1}/projects/{pid}/lessons/{lesson['id']}/deactivate")
    assert off.json()["active"] is False
    assert not client.get(f"{V1}/projects/{pid}/lessons").json()["rules"][0]["active"]
    assert (
        draft_bugs(app, puid, data.run.id) == 1
    )  # rule off: the expected failure is drafted again


def test_counts_lessons_and_rejections_reach_the_next_stages(env, app) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    client, store, pid, puid = env
    _through_gate2(client, store, app, pid, puid, count=7)  # differs from the suggestion
    knowledge = client.get(f"{V1}/projects/{pid}/lessons").json()
    hint = next(r for r in knowledge["rules"] if r["kind"] == "count_hint")
    assert hint["condition"] == {"journey": "sign up"} and hint["action"]["approved"] == 7

    # Re-plan: the previous human decision is shown, the suggested count is unchanged.
    with project_session(app, puid) as s:
        s.add(
            PipelineState(
                project_id=puid, stage="plan", status="queued", entered_at=datetime.now(UTC)
            )
        )
    handle_plan_job(app, SETTINGS, {"project_id": str(puid)})
    newest = client.get(f"{V1}/projects/{pid}/plans").json()[0]
    assert newest["segments"][0]["suggested_count"] == hint["action"]["suggested"]
    assert newest["segments"][0]["previous_decision"] == hint["action"]

    # A rule-off is respected, and an unknown id is 404.
    rule_off = client.post(f"{V1}/projects/{pid}/rules/{hint['id']}/deactivate")
    assert rule_off.json()["active"] is False
    assert client.post(f"{V1}/projects/{pid}/rules/rul_{'0' * 32}/deactivate").status_code == 404
    assert client.post(f"{V1}/projects/{pid}/lessons/les_{'0' * 32}/deactivate").status_code == 404


def test_rejected_node_is_told_to_the_analyst_and_lessons_to_the_designer(env, app) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    client, store, pid, puid = env
    _through_gate2(client, store, app, pid, puid)
    gv = client.get(f"{V1}/projects/{pid}/graph").json()[0]
    # Rejections on an approved version are refused, so reject on a fresh draft.
    with project_session(app, puid) as s:
        s.add(
            PipelineState(
                project_id=puid, stage="understand", status="queued", entered_at=datetime.now(UTC)
            )
        )
    analyst = gateway_factory(app, SETTINGS, provider=FakeProvider([ok(GRAPH)]))
    handle_understand_job(app, store, analyst, {"project_id": str(puid)})
    draft = client.get(f"{V1}/projects/{pid}/graph").json()[0]
    assert draft["id"] != gv["id"]
    role = next(
        n
        for n in client.get(f"{V1}/projects/{pid}/graph/{draft['id']}").json()["nodes"]
        if n["type"] == "Role"
    )
    client.patch(
        f"{V1}/projects/{pid}/graph/{draft['id']}/nodes/{role['id']}",
        json={"review_status": "rejected"},
    )
    with project_session(app, puid) as s:
        s.add(
            PipelineState(
                project_id=puid, stage="understand", status="queued", entered_at=datetime.now(UTC)
            )
        )
    fake = FakeProvider([ok(GRAPH)])
    handle_understand_job(
        app, store, gateway_factory(app, SETTINGS, provider=fake), {"project_id": str(puid)}
    )
    assert "Reviewers rejected this Role: Customer" in fake.calls[0].user

    # An expected-behaviour lesson on this journey reaches the designer prompt.
    from apps.api import learning
    from apps.api.db.models import Feedback, Node

    with project_session(app, puid) as s:
        journey = next(n for n in s.query(Node).filter(Node.type == "Journey"))
        fb = Feedback(project_id=puid, entity="bug", entity_id=journey.id, decision="reject")
        s.add(fb)
        s.flush()
        learning.learn_bug_dismissal(s, puid, case_code="TC-SIG-001", case_title="t", failure="f",
                                     reason="Welcome email is optional", journey_node_id=journey.id,
                                     feedback_id=fb.id)  # fmt: skip
        s.add(
            PipelineState(
                project_id=puid, stage="design", status="queued", entered_at=datetime.now(UTC)
            )
        )
    designer = FakeProvider([ok(json.dumps({"cases": [A]})), ok(json.dumps({"cases": [A]}))])
    handle_design_job(
        app, store, gateway_factory(app, SETTINGS, provider=designer), {"project_id": str(puid)}
    )
    assert "Welcome email is optional" in designer.calls[0].user
