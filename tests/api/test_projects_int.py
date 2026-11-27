"""Projects, RBAC, sources, environments, identities and audit endpoints on real Postgres."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from apps.api import ids
from apps.api.db.models import Chunk, Outbox
from apps.api.db.session import project_session

pytestmark = pytest.mark.integration
V1 = "/api/v1"
SHA = "a" * 64


def _member(owner, pid: str, make_user, role: str):  # type: ignore[no-untyped-def]
    user = make_user()
    res = owner.post(f"{V1}/projects/{pid}/members", json={"email": user.email, "role": role})
    assert res.status_code == 201, res.text
    return user


def test_create_list_get_project(project, make_user) -> None:  # type: ignore[no-untyped-def]
    owner, pid = project
    assert pid.startswith("prj_")
    assert [p["id"] for p in owner.client.get(f"{V1}/projects").json()] == [pid]
    got = owner.client.get(f"{V1}/projects/{pid}").json()
    assert got["role"] == "owner" and got["stage"] is None and got["retention_days"] == 90


def test_outsiders_get_404_not_403(project, make_user) -> None:  # type: ignore[no-untyped-def]
    _, pid = project
    stranger = make_user()
    assert stranger.client.get(f"{V1}/projects/{pid}").status_code == 404
    assert stranger.client.get(f"{V1}/projects").json() == []
    assert stranger.client.get(f"{V1}/projects/prj_bad").status_code == 404


def test_members_and_roles(project, make_user) -> None:  # type: ignore[no-untyped-def]
    owner, pid = project
    viewer = _member(owner, pid, make_user, "viewer")
    tester = _member(owner, pid, make_user, "tester")
    assert viewer.client.get(f"{V1}/projects/{pid}").json()["role"] == "viewer"
    src = viewer.post(
        f"{V1}/projects/{pid}/sources", json={"kind": "md", "uri": "a", "sha256": SHA}
    )
    assert src.status_code == 403
    assert src.json()["error"]["details"] == {"permission": "sources.manage"}
    nope = tester.post(
        f"{V1}/projects/{pid}/members", json={"email": viewer.email, "role": "owner"}
    )
    assert nope.status_code == 403
    dup = owner.post(f"{V1}/projects/{pid}/members", json={"email": viewer.email, "role": "tester"})
    assert dup.status_code == 409
    ghost = owner.post(
        f"{V1}/projects/{pid}/members", json={"email": "ghost@example.com", "role": "viewer"}
    )
    assert ghost.status_code == 404
    roles = {m["email"]: m["role"] for m in owner.client.get(f"{V1}/projects/{pid}/members").json()}
    assert roles == {owner.email: "owner", viewer.email: "viewer", tester.email: "tester"}


def test_sources_and_pagination(project, app: sessionmaker[Session]) -> None:  # type: ignore[no-untyped-def]
    owner, pid = project
    for name in ("a.md", "b.md", "c.md"):
        res = owner.post(
            f"{V1}/projects/{pid}/sources", json={"kind": "md", "uri": name, "sha256": SHA}
        )
        assert res.status_code == 201 and res.json()["status"] == "pending"
    page1 = owner.client.get(f"{V1}/projects/{pid}/sources?limit=2").json()
    assert [s["uri"] for s in page1["items"]] == ["a.md", "b.md"] and page1["next_cursor"] == "2"
    page2 = owner.client.get(f"{V1}/projects/{pid}/sources?limit=2&cursor=2").json()
    assert [s["uri"] for s in page2["items"]] == ["c.md"] and page2["next_cursor"] is None
    bad_sha = owner.post(
        f"{V1}/projects/{pid}/sources", json={"kind": "md", "uri": "x", "sha256": "zz"}
    )
    assert bad_sha.status_code == 400

    pid_uuid = ids.decode("prj", pid)
    sid = page1["items"][0]["id"]
    with project_session(app, pid_uuid) as s:
        for i in range(3):
            s.add(
                Chunk(
                    project_id=pid_uuid,
                    source_id=ids.decode("src", sid),
                    text=f"t{i}",
                    start_offset=i * 10,
                    end_offset=i * 10 + 2,
                    page=1,
                    line=i + 1,
                )
            )
        topics = s.scalars(select(Outbox.topic)).all()
    assert topics.count("source.added") == 3 and "project.created" in topics
    chunks = owner.client.get(f"{V1}/projects/{pid}/sources/{sid}/chunks?limit=2").json()
    assert [c["start_offset"] for c in chunks["items"]] == [0, 10] and chunks["next_cursor"] == "2"
    missing = owner.client.get(f"{V1}/projects/{pid}/sources/src_{'0' * 32}/chunks")
    assert missing.status_code == 404


def test_environments_and_production_rule(project, make_user) -> None:  # type: ignore[no-untyped-def]
    owner, pid = project
    lead = _member(owner, pid, make_user, "qa_lead")
    body = {
        "name": "staging",
        "kind": "staging",
        "base_url": "https://Staging.Shop.test/app",
        "allowed_hosts": ["api.shop.test"],
    }
    env = lead.post(f"{V1}/projects/{pid}/environments", json=body)
    assert env.status_code == 201
    assert env.json()["allowed_hosts"] == ["api.shop.test", "staging.shop.test"]
    prod = {**body, "name": "prod", "kind": "production"}
    denied = lead.post(f"{V1}/projects/{pid}/environments", json=prod)
    assert denied.status_code == 403
    assert denied.json()["error"]["details"] == {"permission": "env.mark_production"}
    assert owner.post(f"{V1}/projects/{pid}/environments", json=prod).status_code == 201
    names = [e["name"] for e in lead.client.get(f"{V1}/projects/{pid}/environments").json()]
    assert names == ["staging", "prod"]


def test_identities_are_write_only(project) -> None:  # type: ignore[no-untyped-def]
    owner, pid = project
    env = owner.post(
        f"{V1}/projects/{pid}/environments",
        json={"name": "local", "kind": "local", "base_url": "http://localhost:3000"},
    ).json()
    res = owner.post(
        f"{V1}/projects/{pid}/identities",
        json={"env_id": env["id"], "role_name": "admin", "secret_ref": "vault:shop_admin"},
    )
    assert res.status_code == 201
    assert "secret_ref" not in res.json() and "vault" not in res.text
    missing = owner.post(
        f"{V1}/projects/{pid}/identities",
        json={"env_id": f"env_{'0' * 32}", "role_name": "x", "secret_ref": "env:x"},
    )
    assert missing.status_code == 404
    raw = owner.post(  # a pasted password is refused: only references are stored
        f"{V1}/projects/{pid}/identities",
        json={"env_id": env["id"], "role_name": "x", "secret_ref": "hunter2!"},
    )
    assert raw.status_code == 400 and "hunter2" not in raw.text


def test_audit_endpoint_verifies_chain(project) -> None:  # type: ignore[no-untyped-def]
    owner, pid = project
    owner.post(f"{V1}/projects/{pid}/sources", json={"kind": "md", "uri": "a", "sha256": SHA})
    res = owner.client.get(f"{V1}/projects/{pid}/audit?verify=true").json()
    assert [e["action"] for e in res["items"]] == ["project.created", "source.added"]
    assert res["verified"] is True and res["broken_at_seq"] is None
    plain = owner.client.get(f"{V1}/projects/{pid}/audit").json()
    assert plain["verified"] is None
