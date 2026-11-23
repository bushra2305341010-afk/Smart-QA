"""Designer + Gate 3, driven end to end from upload with a scripted model (US-05)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from apps.api.db.models import PipelineState, Project
from apps.api.db.session import project_session
from apps.workers.analyst import handle_understand_job
from apps.workers.designer import handle_design_job
from apps.workers.gateway import gateway_factory
from apps.workers.planner import handle_plan_job
from tests.model_gateway.fakes import FakeProvider, ok
from tests.workers.test_analyst_int import SETTINGS, _ingest, env, extraction, n  # noqa: F401

pytestmark = pytest.mark.integration
V1 = "/api/v1"
PRD = (
    b"# Sign up\n\nCustomers can create an account.\n\n"
    b"Password must be 8 to 64 characters.\n\nA welcome email is sent after sign up.\n"
)
GRAPH = extraction(
    n("j", "Journey", "Sign up", "Customers can create an account."),
    n("c", "Role", "Customer", "Customers can create an account."),
    n("r", "Rule", "Password length", "Password must be 8 to 64 characters.",
      subject="password length", value="8-64"),
    edges=[
        {"from_key": "c", "to_key": "j", "kind": "performs"},
        {"from_key": "r", "to_key": "j", "kind": "governs"},
    ],
)  # fmt: skip


def case(title: str, expected: str, quote: str, steps: list[str], source: str = "S1") -> dict:
    return {
        "title": title, "role": "Customer", "technique": "boundary_value",
        "preconditions": ["On the sign-up page"], "steps": [{"action": a} for a in steps],
        "data": [{"name": "password", "value": "x" * 64}], "expected_text": expected,
        "source": source, "quote": quote, "requirement_id": None,
    }  # fmt: skip


A = case(
    "64 chars ok", "Account is created", "Password must be 8 to 64 characters.", ["Type", "Submit"]
)
B = case("Welcome", "Welcome email arrives", "An email welcomes every new user.", ["Sign up"])
C = case(
    "Email",
    "Welcome email is sent",
    "A welcome email is sent after sign up.",
    ["Sign up", "Open inbox"],
)
A2 = {**A, "title": "duplicate of A"}


def _through_gate2(client, store, app, pid, puid, count: int = 3) -> None:  # type: ignore[no-untyped-def]
    _ingest(client, store, app, pid, puid, {"prd.md": PRD})
    fake = FakeProvider([ok(GRAPH)])
    handle_understand_job(
        app, store, gateway_factory(app, SETTINGS, provider=fake), {"project_id": str(puid)}
    )
    gv = client.get(f"{V1}/projects/{pid}/graph").json()[0]["id"]
    for node in client.get(f"{V1}/projects/{pid}/graph/{gv}").json()["nodes"]:
        client.patch(
            f"{V1}/projects/{pid}/graph/{gv}/nodes/{node['id']}", json={"review_status": "approved"}
        )
    assert client.post(f"{V1}/projects/{pid}/graph/{gv}/approve").status_code == 200
    handle_plan_job(app, SETTINGS, {"project_id": str(puid)})
    plan = client.get(f"{V1}/projects/{pid}/plans").json()[0]
    seg = plan["segments"][0]
    client.patch(
        f"{V1}/projects/{pid}/plans/{plan['id']}/segments/{seg['id']}",
        json={"approved_count": count},
    )
    with project_session(app, puid) as s:
        s.get_one(Project, puid).settings = {"budget_monthly_usd": 1000}
    assert client.post(f"{V1}/projects/{pid}/plans/{plan['id']}/approve").status_code == 200


def _design(app, store, puid, *responses):  # type: ignore[no-untyped-def]
    fake = FakeProvider(list(responses))
    handle_design_job(
        app, store, gateway_factory(app, SETTINGS, provider=fake), {"project_id": str(puid)}
    )
    return fake


def _state(client, pid):  # type: ignore[no-untyped-def]
    cur = client.get(f"{V1}/projects/{pid}/pipeline").json()["current"]
    return cur["stage"], cur["status"]


def test_design_verify_review_and_gate3(env, app) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    client, store, pid, puid = env
    _through_gate2(client, store, app, pid, puid)
    assert _state(client, pid) == ("design", "queued")
    fake = _design(
        app, store, puid, ok(json.dumps({"cases": [A, B]})), ok(json.dumps({"cases": [A2, C]}))
    )
    assert len(fake.calls) == 2 and "Design exactly 1 test case" in fake.calls[1].user
    assert "Password length" in fake.calls[0].user and "<untrusted_data" in fake.calls[0].user
    assert _state(client, pid) == ("case_review", "awaiting_approval")

    page = client.get(f"{V1}/projects/{pid}/cases").json()
    cases = {c["title"]: c for c in page["items"]}
    assert [c["code"] for c in page["items"]] == ["TC-SIG-001", "TC-SIG-002", "TC-SIG-003"]
    assert set(cases) == {"64 chars ok", "Welcome", "Email"}
    assert cases["64 chars ok"]["citation"]["status"] == "verified"
    assert cases["Welcome"]["citation"]["status"] == "unable_to_verify"
    assert [s["action"] for s in cases["Email"]["steps"]] == ["Sign up", "Open inbox"]
    audit = client.get(f"{V1}/projects/{pid}/audit?limit=200").json()["items"]
    ready = next(e for e in audit if e["action"] == "pipeline.cases_ready")["payload"]
    assert (ready["cases"], ready["unable_to_verify"], ready["duplicates"], ready["shortfall"]) == (
        3,
        1,
        1,
        0,
    )

    early = client.post(f"{V1}/projects/{pid}/cases/approve")
    assert early.status_code == 409 and early.json()["error"]["details"] == {"gate": 3}
    ids_all = [c["id"] for c in page["items"]]
    uv = client.post(
        f"{V1}/projects/{pid}/cases/review", json={"case_ids": ids_all, "decision": "approved"}
    )
    assert uv.status_code == 422 and uv.json()["error"]["details"]["case_ids"] == [
        cases["Welcome"]["id"]
    ]

    edit_body = {
        "title": "Email arrives",
        "steps": ["Sign up", "Wait", "Open inbox"],
        "data": {"email": "a@example.com"},
    }
    edited = client.patch(f"{V1}/projects/{pid}/cases/{cases['Email']['id']}", json=edit_body)
    assert edited.json()["review_status"] == "edited" and len(edited.json()["steps"]) == 3
    again = client.patch(f"{V1}/projects/{pid}/cases/{cases['Email']['id']}", json={"title": "x"})
    assert again.status_code == 409
    partial = client.patch(
        f"{V1}/projects/{pid}/cases/{cases['64 chars ok']['id']}",
        json={"preconditions": ["Fresh browser"]},
    ).json()
    assert partial["title"] == "64 chars ok" and partial["preconditions"] == ["Fresh browser"]
    every = [c["id"] for c in page["items"]]
    client.post(
        f"{V1}/projects/{pid}/cases/review", json={"case_ids": every, "decision": "rejected"}
    )
    none_ok = client.post(f"{V1}/projects/{pid}/cases/approve")
    assert none_ok.status_code == 409 and "at least one" in none_ok.json()["error"]["message"]
    client.post(
        f"{V1}/projects/{pid}/cases/review",
        json={"case_ids": [cases["Welcome"]["id"]], "decision": "rejected"},
    )
    ok_ids = [cases["64 chars ok"]["id"], cases["Email"]["id"]]
    assert client.post(
        f"{V1}/projects/{pid}/cases/review", json={"case_ids": ok_ids, "decision": "approved"}
    ).json() == {"updated": 2}
    approved = client.post(f"{V1}/projects/{pid}/cases/approve")
    assert approved.status_code == 200 and approved.json() == {
        "stage": "compile",
        "status": "queued",
    }
    assert (
        client.post(f"{V1}/projects/{pid}/cases/approve").json()["error"]["code"]
        == "STATE_CONFLICT"
    )

    filtered = client.get(f"{V1}/projects/{pid}/cases?review_status=rejected&limit=1").json()
    assert [c["title"] for c in filtered["items"]] == ["Welcome"] and filtered[
        "next_cursor"
    ] is None
    seg = page["items"][0]["segment_id"]
    assert (
        len(client.get(f"{V1}/projects/{pid}/cases?segment_id={seg}&limit=2").json()["items"]) == 2
    )
    assert client.get(f"{V1}/projects/{pid}/cases?limit=1").json()["next_cursor"] == "1"
    one = client.get(f"{V1}/projects/{pid}/cases/{cases['Email']['id']}").json()
    assert one["title"] == "Email arrives"
    assert client.get(f"{V1}/projects/{pid}/cases/tc_{'0' * 32}").status_code == 404
    assert (
        client.patch(f"{V1}/projects/{pid}/cases/tc_{'0' * 32}", json={"title": "x"}).status_code
        == 404
    )
    missing = client.post(
        f"{V1}/projects/{pid}/cases/review",
        json={"case_ids": [f"tc_{'0' * 32}"], "decision": "rejected"},
    )
    assert missing.status_code == 404


def test_designer_failures(env, app, owner) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    client, store, pid, puid = env
    with project_session(app, puid) as s:
        s.add(
            PipelineState(
                project_id=puid, stage="design", status="queued", entered_at=datetime.now(UTC)
            )
        )
    _design(app, store, puid)
    audit = client.get(f"{V1}/projects/{pid}/audit?limit=200").json()["items"]
    assert audit[-1]["payload"]["reason"] == "No approved plan"
    client.post(f"{V1}/projects/{pid}/pipeline/events", json={"event": "cancel"})

    _through_gate2(client, store, app, pid, puid, count=1)
    unknown = case("x", "y", "Password must be 8 to 64 characters.", ["s"], source="S9")
    _design(app, store, puid, ok(json.dumps({"cases": [unknown]})))
    [only] = client.get(f"{V1}/projects/{pid}/cases").json()["items"]
    assert only["citation"] == {
        **only["citation"],
        "status": "unable_to_verify",
        "reason": "unknown source",
    }

    with project_session(app, puid) as s:
        s.add(
            PipelineState(
                project_id=puid, stage="design", status="queued", entered_at=datetime.now(UTC)
            )
        )
    with owner.begin() as s:  # the same request would be served from the replay cache
        s.execute(text("DELETE FROM replay_cache"))
    garbage = [ok("garbage")] * 3  # first call invalid 3 times, then an empty batch
    _design(app, store, puid, *garbage, ok(json.dumps({"cases": []})))
    audit = client.get(f"{V1}/projects/{pid}/audit?limit=200").json()["items"]
    assert audit[-1]["payload"]["reason"] == "The model returned no usable test cases"

    with project_session(app, puid) as s:
        s.add(
            PipelineState(
                project_id=puid, stage="design", status="queued", entered_at=datetime.now(UTC)
            )
        )
        s.get_one(Project, puid).settings = {"budget_monthly_usd": 0}
    with owner.begin() as s:  # cached answers cost nothing, so clear them to hit the budget
        s.execute(text("DELETE FROM replay_cache"))
    _design(app, store, puid)
    audit = client.get(f"{V1}/projects/{pid}/audit?limit=200").json()["items"]
    assert audit[-1]["payload"]["reason"] == "Monthly model budget reached"
    client.post(f"{V1}/projects/{pid}/pipeline/events", json={"event": "cancel"})
    _design(app, store, puid)  # pipeline cancelled: nothing breaks


def test_context_is_scoped_to_the_journey() -> None:
    import uuid

    from apps.workers.designer import Context
    from packages.planning.from_graph import EdgeView, NodeView

    j1, j2, r1, r2 = (str(uuid.uuid4()) for _ in range(4))
    ctx = Context(
        texts={}, sources={},
        lines={j1: "[Journey] Sign up", j2: "[Journey] Checkout",
               r1: "[Rule] Password", r2: "[Rule] Coupon"},
        views=[NodeView(j1, "Journey", "Sign up"), NodeView(j2, "Journey", "Checkout"),
               NodeView(r1, "Rule", "Password"), NodeView(r2, "Rule", "Coupon")],
        edges=[EdgeView(r1, j1, "governs"), EdgeView(r2, j2, "governs")],
    )  # fmt: skip
    facts = ctx.facts_for(uuid.UUID(j1))
    assert "Password" in facts and "Coupon" not in facts and "Checkout" not in facts
