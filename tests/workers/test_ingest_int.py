"""Upload → ingest worker → chunks with verifiable offsets → pipeline advances (US-01)."""

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from apps.api import ids
from apps.api.auth.tokens import JwtSigner
from apps.api.db.models import Chunk, PipelineState, Source
from apps.api.db.session import project_session
from apps.api.main import create_app
from apps.api.routers import projects as projects_router
from apps.api.storage import MemoryObjectStore
from apps.workers.ingest import handle_ingest_job, ingest_source
from packages.citations.verify import verify_quote
from tests.api.conftest import PASSWORD
from tests.citations.fixtures import OPENAPI_YAML, make_docx, make_pdf

pytestmark = pytest.mark.integration
V1 = "/api/v1"


@pytest.fixture
def setup(app):  # type: ignore[no-untyped-def]
    store = MemoryObjectStore()
    client = TestClient(
        create_app(session_factory=app, jwt_signer=JwtSigner.ephemeral(), object_store=store)
    )
    email = "lead@example.com"
    client.post(f"{V1}/auth/register", json={"email": email, "password": PASSWORD})
    csrf = client.post(f"{V1}/auth/login", json={"email": email, "password": PASSWORD}).json()[
        "csrf_token"
    ]
    client.headers["X-CSRF-Token"] = csrf
    pid = client.post(f"{V1}/projects", json={"name": "Shop"}).json()["id"]
    return client, store, pid, ids.decode("prj", pid)


def _upload(client, pid, name, data):  # type: ignore[no-untyped-def]
    return client.post(
        f"{V1}/projects/{pid}/sources/upload", files={"file": (name, io.BytesIO(data))}
    )


def test_upload_ingest_and_advance(setup, app) -> None:  # type: ignore[no-untyped-def]
    client, store, pid, puid = setup
    files = {
        "prd.pdf": make_pdf(["Password must be 8 to 64 characters.", "Lock after 5 failures."]),
        "rules.docx": make_docx(
            ["Totals include VAT."], [["Field", "Rule"], ["Email", "Required"]]
        ),
        "notes.md": b"# Coupons\n\nCoupons expire after 30 days.\n",
        "api.yaml": OPENAPI_YAML,
        "scan.pdf": make_pdf([""]),
    }
    kinds = {name: _upload(client, pid, name, data).json() for name, data in files.items()}
    assert {n: k["kind"] for n, k in kinds.items()} == {
        "prd.pdf": "pdf",
        "rules.docx": "docx",
        "notes.md": "md",
        "api.yaml": "openapi",
        "scan.pdf": "pdf",
    }
    again = _upload(client, pid, "copy.md", files["notes.md"])
    assert again.status_code == 200 and again.json()["id"] == kinds["notes.md"]["id"]

    client.post(f"{V1}/projects/{pid}/pipeline/events", json={"event": "start"})
    handle_ingest_job(app, store, {"project_id": str(puid)})

    sources = {s["filename"]: s for s in client.get(f"{V1}/projects/{pid}/sources").json()["items"]}
    assert (
        sources["scan.pdf"]["status"] == "failed"
        and "No text found" in sources["scan.pdf"]["error"]
    )
    assert all(
        sources[n]["status"] == "ready" for n in ("prd.pdf", "rules.docx", "notes.md", "api.yaml")
    )
    chunks = client.get(f"{V1}/projects/{pid}/sources/{sources['prd.pdf']['id']}/chunks").json()[
        "items"
    ]
    assert [c["page"] for c in chunks] == [1, 2]
    with project_session(app, puid) as s:
        src = s.get_one(Source, ids.decode("src", sources["prd.pdf"]["id"]))
        text = store.get(src.text_key or "").decode()
        for c in s.scalars(select(Chunk).where(Chunk.source_id == src.id)):
            assert verify_quote(text, c.text, c.start_offset, c.end_offset).verified
        state = s.scalars(select(PipelineState).order_by(PipelineState.entered_at.desc())).first()
    assert (state.stage, state.status) == ("understand", "queued")
    audit = client.get(f"{V1}/projects/{pid}/audit").json()["items"]
    assert audit[-1]["payload"]["ready"] == 4 and audit[-1]["payload"]["failed"] == 1


def test_reingest_replaces_chunks(setup, app) -> None:  # type: ignore[no-untyped-def]
    client, store, pid, puid = setup
    sid = ids.decode("src", _upload(client, pid, "a.md", b"One.\n\nTwo.\n").json()["id"])
    assert ingest_source(app, store, puid, sid) == "ready"
    assert ingest_source(app, store, puid, sid) == "ready"
    with project_session(app, puid) as s:
        assert len(s.scalars(select(Chunk).where(Chunk.source_id == sid)).all()) == 1


def test_no_parsable_source_fails_the_stage(setup, app) -> None:  # type: ignore[no-untyped-def]
    client, store, pid, puid = setup
    client.post(
        f"{V1}/projects/{pid}/sources",
        json={"kind": "repo", "uri": "git@x:y.git", "sha256": "a" * 64},
    )
    client.post(f"{V1}/projects/{pid}/pipeline/events", json={"event": "start"})
    handle_ingest_job(app, store, {"project_id": str(puid)})
    state = client.get(f"{V1}/projects/{pid}/pipeline").json()["current"]
    assert (state["stage"], state["status"]) == ("ingest", "failed")
    [src] = client.get(f"{V1}/projects/{pid}/sources").json()["items"]
    assert src["error"] == "Original file was never uploaded"


def test_job_for_cancelled_pipeline_does_not_crash(setup, app) -> None:  # type: ignore[no-untyped-def]
    client, store, pid, puid = setup
    _upload(client, pid, "a.md", b"Rule.\n")
    client.post(f"{V1}/projects/{pid}/pipeline/events", json={"event": "start"})
    client.post(f"{V1}/projects/{pid}/pipeline/events", json={"event": "cancel"})
    handle_ingest_job(app, store, {"project_id": str(puid)})
    assert client.get(f"{V1}/projects/{pid}/pipeline").json()["current"]["status"] == "cancelled"


def test_upload_errors(setup, monkeypatch, app) -> None:  # type: ignore[no-untyped-def]
    client, _, pid, _ = setup
    bad = _upload(client, pid, "x.exe", b"\xff\xfe\x00\x01")
    assert bad.status_code == 415 and bad.json()["error"]["code"] == "UNSUPPORTED_TYPE"
    monkeypatch.setattr(projects_router, "MAX_BYTES", 4)
    big = _upload(client, pid, "big.md", b"12345")
    assert big.status_code == 413
    nostore = TestClient(create_app(session_factory=app, jwt_signer=JwtSigner.ephemeral()))
    nostore.app.state.object_store = None  # type: ignore[attr-defined]
    nostore.post(f"{V1}/auth/login", json={"email": "lead@example.com", "password": PASSWORD})
    res = nostore.post(f"{V1}/projects/{pid}/sources/upload", files={"file": ("a.md", b"x")},
                       headers={"X-CSRF-Token": nostore.cookies.get("saq_csrf") or ""})  # fmt: skip
    assert res.status_code == 503
