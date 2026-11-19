"""Analyst → draft graph → review → Gate 1 (US-02, US-03), with a scripted model."""

from __future__ import annotations

import io
import json
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from apps.api import ids
from apps.api.auth.tokens import JwtSigner
from apps.api.db.models import Feedback, ModelCall, PipelineState, Project
from apps.api.db.session import project_session
from apps.api.main import create_app
from apps.api.settings import Settings
from apps.api.storage import MemoryObjectStore
from apps.workers.analyst import handle_understand_job, windows
from apps.workers.gateway import gateway_factory, prices_for
from apps.workers.ingest import handle_ingest_job
from packages.model_gateway.factory import LOCAL_PRICES
from packages.model_gateway.local_adapter import LocalProvider
from tests.api.conftest import PASSWORD
from tests.model_gateway.fakes import FakeProvider, ok

pytestmark = pytest.mark.integration
V1 = "/api/v1"
PRD = (
    b"# Accounts\n\nPassword must be 8 to 64 characters.\n\n"
    b"Search results must load fast.\n\nCustomers can check out with a saved card.\n"
)
CODE = b"# Validators\n\nThe validator allows a password maximum length of 128 characters.\n"
SETTINGS = Settings(
    saq_model_policy="external-redacted",
    model_price_input_per_mtok=5,
    model_price_output_per_mtok=25,
    model_price_cache_read_per_mtok=0.5,
)


def extraction(*nodes: dict, edges: list[dict] | None = None) -> str:
    return json.dumps({"nodes": list(nodes), "edges": edges or []})


def n(key: str, type_: str, label: str, quote: str, **attrs: str) -> dict:
    return {
        "key": key, "type": type_, "label": label, "source": "S?", "quote": quote,
        "attrs": [{"name": k, "value": v} for k, v in attrs.items()],
    }  # fmt: skip


PRD_OUT = extraction(
    n("r1", "Rule", "Password length 8-64", "Password must be 8 to 64 characters.",
      subject="password maximum length", value="64"),
    n("q1", "Requirement", "Search loads fast", "Search results must load fast."),
    n("j1", "Journey", "Checkout", "Customers can check out with a saved card."),
    n("c1", "Role", "Customer", "Customers can check out with a saved card."),
    n("x1", "Rule", "Invented rule", "Refunds are instant."),
    edges=[{"from_key": "c1", "to_key": "j1", "kind": "performs"}],
)  # fmt: skip
CODE_OUT = extraction(
    n("r2", "Rule", "Validator max 128",
      "The validator allows a password maximum length of 128 characters.",
      subject="Password maximum length", value="128"),
)  # fmt: skip


@pytest.fixture
def env(app):  # type: ignore[no-untyped-def]
    store = MemoryObjectStore()
    client = TestClient(
        create_app(session_factory=app, jwt_signer=JwtSigner.ephemeral(), object_store=store)
    )
    client.post(f"{V1}/auth/register", json={"email": "lead@example.com", "password": PASSWORD})
    login = client.post(
        f"{V1}/auth/login", json={"email": "lead@example.com", "password": PASSWORD}
    )
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    pid = client.post(f"{V1}/projects", json={"name": "Shop"}).json()["id"]
    return client, store, pid, ids.decode("prj", pid)


def _ingest(client, store, app, pid, puid, files):  # type: ignore[no-untyped-def]
    for name, data in files.items():
        client.post(f"{V1}/projects/{pid}/sources/upload", files={"file": (name, io.BytesIO(data))})
    client.post(f"{V1}/projects/{pid}/pipeline/events", json={"event": "start"})
    handle_ingest_job(app, store, {"project_id": str(puid)})


def _understand(app, store, puid, *responses):  # type: ignore[no-untyped-def]
    fake = FakeProvider(list(responses))
    handle_understand_job(
        app, store, gateway_factory(app, SETTINGS, provider=fake), {"project_id": str(puid)}
    )
    return fake


def test_graph_review_and_gate1(env, app) -> None:  # type: ignore[no-untyped-def]
    client, store, pid, puid = env
    _ingest(client, store, app, pid, puid, {"prd.md": PRD, "code.md": CODE})
    fake = _understand(app, store, puid, ok(PRD_OUT), ok(CODE_OUT))
    assert len(fake.calls) == 2
    assert (
        "<untrusted_data" in fake.calls[0].user and "never an instruction" in fake.calls[0].system
    )

    state = client.get(f"{V1}/projects/{pid}/pipeline").json()["current"]
    assert (state["stage"], state["status"]) == ("graph_review", "awaiting_approval")
    [version] = client.get(f"{V1}/projects/{pid}/graph").json()
    assert version["status"] == "draft" and version["pending"] == version["nodes"]
    graph = client.get(f"{V1}/projects/{pid}/graph/{version['id']}").json()
    by_type: dict[str, list] = {}
    for node in graph["nodes"]:
        by_type.setdefault(node["type"], []).append(node)
    rule = next(x for x in by_type["Rule"] if x["label"] == "Password length 8-64")
    [cite] = rule["citations"]
    assert cite["quote"] == "Password must be 8 to 64 characters." and cite["file"] == "prd.md"
    assert cite["page"] == 1 and cite["line"] == 3
    [conflict] = by_type["Conflict"]
    assert {c["file"] for c in conflict["citations"]} == {"prd.md", "code.md"}
    reasons = sorted(q["attrs"]["reason"] for q in by_type["Question"])
    assert reasons == ["quote_not_found", "vague_terms"]
    assert {e["kind"] for e in graph["edges"]} >= {"performs", "conflicts_with", "asks_about"}
    only_q = client.get(f"{V1}/projects/{pid}/graph/{version['id']}?type=Question").json()
    assert len(only_q["nodes"]) == 2

    blocked = client.post(f"{V1}/projects/{pid}/graph/{version['id']}/approve")
    assert blocked.status_code == 409
    err = blocked.json()["error"]
    assert (
        err["code"] == "GATE_NOT_APPROVED"
        and len(err["details"]["pending_node_ids"]) == version["nodes"]
    )

    url = f"{V1}/projects/{pid}/graph/{version['id']}/nodes"
    nodes = graph["nodes"]
    bad = client.patch(f"{url}/{nodes[0]['id']}", json={"review_status": "approved", "label": "x"})
    assert bad.status_code == 400
    edited = client.patch(
        f"{url}/{rule['id']}", json={"review_status": "edited", "label": "Password 8 to 64 chars"}
    )
    assert edited.json()["label"] == "Password 8 to 64 chars"
    for node in nodes:
        if node["id"] != rule["id"]:
            status = "rejected" if node["type"] == "Question" else "approved"
            assert (
                client.patch(f"{url}/{node['id']}", json={"review_status": status}).status_code
                == 200
            )
    assert (
        client.patch(f"{url}/nod_{'0' * 32}", json={"review_status": "approved"}).status_code == 404
    )

    approved = client.post(f"{V1}/projects/{pid}/graph/{version['id']}/approve")
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    state = client.get(f"{V1}/projects/{pid}/pipeline").json()["current"]
    assert (state["stage"], state["status"]) == ("plan", "queued")
    again = client.post(f"{V1}/projects/{pid}/graph/{version['id']}/approve")
    assert again.status_code == 409
    late = client.patch(f"{url}/{rule['id']}", json={"review_status": "approved"})
    assert late.status_code == 409
    actions = [
        e["action"] for e in client.get(f"{V1}/projects/{pid}/audit?limit=200").json()["items"]
    ]
    assert "gate1.approved" in actions and "pipeline.graph_approved" in actions
    with project_session(app, puid) as s:
        assert s.scalar(select(func.count()).select_from(Feedback)) == version["nodes"]
        assert s.scalar(select(func.count()).select_from(ModelCall)) == 2
    assert client.get(f"{V1}/projects/{pid}/graph/gv_{'0' * 32}").status_code == 404


def test_new_version_supersedes_and_needs_pipeline(env, app) -> None:  # type: ignore[no-untyped-def]
    client, store, pid, puid = env
    _ingest(client, store, app, pid, puid, {"prd.md": PRD})
    _understand(app, store, puid, ok(PRD_OUT))
    first = client.get(f"{V1}/projects/{pid}/graph").json()[0]
    graph = client.get(f"{V1}/projects/{pid}/graph/{first['id']}").json()
    for node in graph["nodes"]:
        client.patch(
            f"{V1}/projects/{pid}/graph/{first['id']}/nodes/{node['id']}",
            json={"review_status": "approved"},
        )
    assert client.post(f"{V1}/projects/{pid}/graph/{first['id']}/approve").status_code == 200
    # A second draft cannot be approved unless the pipeline is waiting at Gate 1.
    _understand(
        app, store, puid, ok(PRD_OUT)
    )  # pipeline is at plan, so no transition, version 2 saved
    second = client.get(f"{V1}/projects/{pid}/graph").json()[0]
    assert second["number"] == 2
    for node in client.get(f"{V1}/projects/{pid}/graph/{second['id']}").json()["nodes"]:
        client.patch(
            f"{V1}/projects/{pid}/graph/{second['id']}/nodes/{node['id']}",
            json={"review_status": "approved"},
        )
    res = client.post(f"{V1}/projects/{pid}/graph/{second['id']}/approve")
    assert res.status_code == 409 and res.json()["error"]["code"] == "STATE_CONFLICT"
    statuses = {v["number"]: v["status"] for v in client.get(f"{V1}/projects/{pid}/graph").json()}
    assert statuses == {1: "approved", 2: "draft"}  # rolled back together


def test_understand_failures(env, app) -> None:  # type: ignore[no-untyped-def]
    client, store, pid, puid = env
    client.post(f"{V1}/projects/{pid}/pipeline/events", json={"event": "start"})
    with project_session(app, puid) as s:
        s.add(
            PipelineState(
                project_id=puid, stage="understand", status="queued", entered_at=datetime.now(UTC)
            )
        )
    _understand(app, store, puid)
    current = client.get(f"{V1}/projects/{pid}/pipeline").json()["current"]
    assert current["status"] == "failed"

    _ingest(client, store, app, pid, puid, {"prd.md": PRD})
    with project_session(app, puid) as s:
        s.add(
            PipelineState(
                project_id=puid, stage="understand", status="queued", entered_at=datetime.now(UTC)
            )
        )
    _understand(app, store, puid, ok("not json"), ok("still not json"), ok("{}x"))
    audit = client.get(f"{V1}/projects/{pid}/audit?limit=200").json()["items"]
    assert audit[-1]["payload"]["reason"] == "The model returned no usable output"

    with project_session(app, puid) as s:
        s.add(
            PipelineState(
                project_id=puid, stage="understand", status="queued", entered_at=datetime.now(UTC)
            )
        )
        s.get_one(Project, puid).settings = {"budget_monthly_usd": 0}
    _understand(app, store, puid)
    audit = client.get(f"{V1}/projects/{pid}/audit?limit=200").json()["items"]
    assert audit[-1]["payload"]["reason"] == "Monthly model budget reached"


def test_partial_model_failure_is_counted(env, app) -> None:  # type: ignore[no-untyped-def]
    client, store, pid, puid = env
    _ingest(client, store, app, pid, puid, {"prd.md": PRD, "code.md": CODE})
    refusal = ok("")
    refusal = refusal.model_copy(update={"stop_reason": "refusal"})
    _understand(app, store, puid, ok(PRD_OUT), refusal)
    audit = client.get(f"{V1}/projects/{pid}/audit?limit=200").json()["items"]
    assert (
        audit[-1]["action"] == "pipeline.graph_ready" and audit[-1]["payload"]["failed_calls"] == 1
    )


def test_windows_split_on_paragraphs() -> None:
    assert windows("a\n\nb", size=10) == ["a\n\nb"]
    assert windows("aaaa\n\nbbbb\n\ncc", size=8) == ["aaaa", "bbbb\n\ncc"]
    assert windows("x" * 10 + "\n\ny", size=4) == ["xxxx", "xxxx", "xx", "y"]
    assert windows("ab\n\n" + "z" * 9, size=4) == ["ab", "zzzz", "zzzz", "z"]
    assert windows("   ") == []


def test_prices_and_provider_selection(app) -> None:  # type: ignore[no-untyped-def]
    assert prices_for(Settings(saq_model_policy="local-only")) == LOCAL_PRICES
    with pytest.raises(ValueError, match="MODEL_PRICE"):
        prices_for(Settings(saq_model_policy="external-redacted"))
    assert prices_for(SETTINGS).input_per_mtok_usd == 5
    local = Settings(saq_model_policy="local-only", local_model_url="http://localhost:11434")
    make = gateway_factory(app, local)
    assert isinstance(make(uuid.uuid4()).provider, LocalProvider)
