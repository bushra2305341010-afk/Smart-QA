"""Planner worker → draft plan → edit counts → Gate 2 (US-04)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from apps.api import ids
from apps.api.auth.tokens import JwtSigner
from apps.api.db.models import (
    Edge,
    GraphVersion,
    ModelCall,
    Node,
    PipelineState,
    Project,
)
from apps.api.db.session import project_session
from apps.api.main import create_app
from apps.api.settings import Settings
from apps.workers.planner import handle_plan_job
from tests.api.conftest import PASSWORD

pytestmark = pytest.mark.integration
V1 = "/api/v1"
PRICED = Settings(
    saq_model_policy="external-redacted",
    model_price_input_per_mtok=5,
    model_price_output_per_mtok=25,
    model_price_cache_read_per_mtok=0.5,
)


@pytest.fixture
def env(app, monkeypatch):  # type: ignore[no-untyped-def]
    from apps.api import pricing  # noqa: F401
    from apps.api.routers import plans as plans_router

    monkeypatch.setattr(plans_router, "get_settings", lambda: PRICED)
    client = TestClient(create_app(session_factory=app, jwt_signer=JwtSigner.ephemeral()))
    client.post(f"{V1}/auth/register", json={"email": "lead@example.com", "password": PASSWORD})
    login = client.post(
        f"{V1}/auth/login", json={"email": "lead@example.com", "password": PASSWORD}
    )
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    pid = client.post(f"{V1}/projects", json={"name": "Shop"}).json()["id"]
    return client, pid, ids.decode("prj", pid)


def _graph(app, puid, *, journeys: bool = True, status: str = "approved"):  # type: ignore[no-untyped-def]
    with project_session(app, puid) as s:
        gv = GraphVersion(project_id=puid, number=1, status=status)
        s.add(gv)
        s.flush()

        def node(type_: str, label: str, review: str = "approved", **attrs: str) -> Node:
            n = Node(project_id=puid, graph_version_id=gv.id, type=type_, label=label,
                     attrs=attrs, review_status=review)  # fmt: skip
            s.add(n)
            s.flush()
            return n

        def edge(a: Node, b: Node, kind: str) -> None:
            s.add(Edge(project_id=puid, from_node_id=a.id, to_node_id=b.id, kind=kind))

        if journeys:
            j = node("Journey", "Sign up", criticality="5")
            browse = node("Journey", "Browse", criticality="1", change_frequency="0")
            for role in ("Customer", "Admin"):
                edge(node("Role", role), j, "performs")
            edge(node("Role", "Rejected role", review="rejected"), j, "performs")
            step, screen, field = (
                node("Step", "Fill form"),
                node("Screen", "Form"),
                node("Field", "Password"),
            )
            edge(j, step, "has_step")
            edge(step, screen, "on_screen")
            edge(screen, field, "has_field")
            edge(node("Rule", "Length", subject="password length", value="8-64"), field, "governs")
            edge(node("Role", "Visitor"), browse, "performs")
        else:
            node("Rule", "Lonely rule")
        s.add(
            PipelineState(
                project_id=puid, stage="plan", status="queued", entered_at=datetime.now(UTC)
            )
        )
        return gv.id


def _state(client, pid):  # type: ignore[no-untyped-def]
    current = client.get(f"{V1}/projects/{pid}/pipeline").json()["current"]
    return current["stage"], current["status"]


def test_plan_counts_edit_and_gate2(env, app) -> None:  # type: ignore[no-untyped-def]
    client, pid, puid = env
    _graph(app, puid)
    handle_plan_job(app, PRICED, {"project_id": str(puid)})
    assert _state(client, pid) == ("plan_approval", "awaiting_approval")
    [plan] = client.get(f"{V1}/projects/{pid}/plans").json()
    assert plan["status"] == "draft" and plan["cost_estimate"]["available"]
    by_name = {seg["journey"]: seg for seg in plan["segments"]}
    signup = by_name["Sign up"]
    rows = {r["technique"]: r["count"] for r in signup["rows"]}
    # 2 roles (the rejected one is dropped), 1 limit, 1 screen
    assert rows == {"happy_path": 2, "boundary_value": 2, "accessibility": 1}
    assert "Admin, Customer" in signup["rows"][0]["reason"]
    assert signup["priority"] in {"Must", "Should"} and by_name["Browse"]["priority"] == "Could"
    assert plan["segments"][0]["journey"] == "Sign up"  # riskiest first

    url = f"{V1}/projects/{pid}/plans/{plan['id']}"
    edited = client.patch(f"{url}/segments/{signup['id']}", json={"approved_count": 6})
    assert edited.json()["approved_count"] == 6
    assert (
        client.patch(f"{url}/segments/seg_{'0' * 32}", json={"approved_count": 1}).status_code
        == 404
    )
    approved = client.post(f"{url}/approve").json()
    assert approved["status"] == "approved"
    assert approved["approved_total"] == 6 + by_name["Browse"]["suggested_count"]
    assert _state(client, pid) == ("design", "queued")
    assert client.post(f"{url}/approve").status_code == 409
    assert (
        client.patch(f"{url}/segments/{signup['id']}", json={"approved_count": 1}).status_code
        == 409
    )
    assert client.get(f"{V1}/projects/{pid}/plans/pln_{'0' * 32}").status_code == 404
    actions = [
        e["action"] for e in client.get(f"{V1}/projects/{pid}/audit?limit=100").json()["items"]
    ]
    assert {"plan.segment.edited", "gate2.approved", "pipeline.plan_approved"} <= set(actions)


def test_gate2_refusals(env, app) -> None:  # type: ignore[no-untyped-def]
    client, pid, puid = env
    gv_id = _graph(app, puid)
    handle_plan_job(app, PRICED, {"project_id": str(puid)})
    plan = client.get(f"{V1}/projects/{pid}/plans").json()[0]
    url = f"{V1}/projects/{pid}/plans/{plan['id']}"
    for seg in plan["segments"]:
        client.patch(f"{url}/segments/{seg['id']}", json={"approved_count": 0})
    zero = client.post(f"{url}/approve")
    assert zero.status_code == 409 and zero.json()["error"]["details"] == {"gate": 2}
    client.patch(f"{url}/segments/{plan['segments'][0]['id']}", json={"approved_count": 3})

    with project_session(app, puid) as s:
        s.add(
            ModelCall(
                project_id=puid, stage="x", model="m", prompt_version="v", cost_usd=Decimal("19.99")
            )
        )
    broke = client.post(f"{url}/approve")
    assert broke.status_code == 402 and broke.json()["error"]["code"] == "BUDGET_EXCEEDED"
    with project_session(app, puid) as s:
        s.get_one(Project, puid).settings = {"budget_monthly_usd": 1000}
        s.add(
            PipelineState(
                project_id=puid, stage="plan", status="queued", entered_at=datetime.now(UTC)
            )
        )
    wrong_stage = client.post(f"{url}/approve")
    assert (
        wrong_stage.status_code == 409 and wrong_stage.json()["error"]["code"] == "STATE_CONFLICT"
    )
    assert client.get(url).json()["status"] == "draft"  # rolled back with the transition
    with project_session(app, puid) as s:
        s.get_one(GraphVersion, gv_id).status = "superseded"
    stale = client.post(f"{url}/approve")
    assert stale.status_code == 409 and stale.json()["error"]["details"] == {"gate": 1}


def test_planner_failures_and_no_prices(env, app) -> None:  # type: ignore[no-untyped-def]
    client, pid, puid = env
    with project_session(app, puid) as s:
        s.add(
            PipelineState(
                project_id=puid, stage="plan", status="queued", entered_at=datetime.now(UTC)
            )
        )
    handle_plan_job(app, PRICED, {"project_id": str(puid)})
    audit = client.get(f"{V1}/projects/{pid}/audit?limit=100").json()["items"]
    assert audit[-1]["payload"]["reason"] == "No approved graph version"

    _graph(app, puid, journeys=False)
    handle_plan_job(app, PRICED, {"project_id": str(puid)})
    audit = client.get(f"{V1}/projects/{pid}/audit?limit=100").json()["items"]
    assert audit[-1]["payload"]["reason"] == "The approved graph has no journeys to plan"


def test_cost_unavailable_without_prices_and_redraft(env, app) -> None:  # type: ignore[no-untyped-def]
    client, pid, puid = env
    _graph(app, puid)
    handle_plan_job(app, Settings(saq_model_policy="external-redacted"), {"project_id": str(puid)})
    with project_session(app, puid) as s:
        s.add(
            PipelineState(
                project_id=puid, stage="plan", status="queued", entered_at=datetime.now(UTC)
            )
        )
    handle_plan_job(app, PRICED, {"project_id": str(puid)})  # plan_edited → re-plan
    plans = client.get(f"{V1}/projects/{pid}/plans").json()
    assert [p["status"] for p in plans] == ["draft", "superseded"]
    assert plans[1]["cost_estimate"]["available"] is False
    assert "MODEL_PRICE" in plans[1]["cost_estimate"]["reason"]


def test_reapproval_supersedes_and_job_after_cancel(env, app, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from apps.api.routers import plans as plans_router

    client, pid, puid = env
    _graph(app, puid)
    handle_plan_job(app, PRICED, {"project_id": str(puid)})
    monkeypatch.setattr(
        plans_router, "get_settings", lambda: Settings(saq_model_policy="external-redacted")
    )
    first = client.get(f"{V1}/projects/{pid}/plans").json()[0]
    assert client.post(f"{V1}/projects/{pid}/plans/{first['id']}/approve").status_code == 200

    with project_session(app, puid) as s:
        s.add(
            PipelineState(
                project_id=puid, stage="plan", status="queued", entered_at=datetime.now(UTC)
            )
        )
    handle_plan_job(app, PRICED, {"project_id": str(puid)})
    second = client.get(f"{V1}/projects/{pid}/plans").json()[0]
    assert client.post(f"{V1}/projects/{pid}/plans/{second['id']}/approve").status_code == 200
    statuses = {p["id"]: p["status"] for p in client.get(f"{V1}/projects/{pid}/plans").json()}
    assert statuses == {first["id"]: "superseded", second["id"]: "approved"}

    client.post(f"{V1}/projects/{pid}/pipeline/events", json={"event": "cancel"})
    handle_plan_job(app, PRICED, {"project_id": str(puid)})  # pipeline moved on: no crash
    assert _state(client, pid) == ("design", "cancelled")
