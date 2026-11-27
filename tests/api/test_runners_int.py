"""Runner registration + protocol: compile → execute → pull → evidence → result → Judge (M10)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from apps.api import ids
from apps.api.auth.tokens import JwtSigner
from apps.api.db.models import (
    Environment,
    Evidence,
    PipelineState,
    Result,
    Run,
    RunnerJob,
    TestCase,
)
from apps.api.db.session import project_session
from apps.api.main import create_app
from apps.api.routers import runners as runners_router
from apps.api.storage import MemoryObjectStore
from apps.runner.main import Browser, RunnerClient, process_one
from apps.runner.secrets import EnvSecrets
from apps.workers.compiler import handle_compile_job
from apps.workers.executor import handle_execute_job, schedule
from packages.contracts.run import AttemptResult, Failure
from tests.api.conftest import PASSWORD
from tests.workers.test_compiler_int import _pipeline, _seed

pytestmark = pytest.mark.integration
V1 = "/api/v1"


@pytest.fixture
def setup(app: sessionmaker[Session]) -> dict[str, Any]:
    store = MemoryObjectStore()
    api = create_app(session_factory=app, jwt_signer=JwtSigner.ephemeral(), object_store=store)
    user = TestClient(api)
    email = f"{uuid.uuid4().hex[:10]}@example.com"
    user.post(f"{V1}/auth/register", json={"email": email, "password": PASSWORD})
    login = user.post(f"{V1}/auth/login", json={"email": email, "password": PASSWORD})
    user.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    pid = user.post(f"{V1}/projects", json={"name": "Shop"}).json()["id"]
    puid = ids.decode("prj", pid)
    with project_session(app, puid) as s:
        _seed(s, puid, envs=[("dev", "local")])
        _pipeline(s, puid)
    handle_compile_job(app, store, None, {"project_id": str(puid)})
    return {"api": api, "user": user, "pid": pid, "puid": puid, "store": store}


def runner(st: dict[str, Any], name: str = "r1", **body: Any) -> tuple[TestClient, str]:
    res = st["user"].post(f"{V1}/projects/{st['pid']}/runners", json={"name": name, **body})
    assert res.status_code == 201, res.text
    token = res.json()["token"]
    client = TestClient(st["api"], base_url=f"http://testserver{V1}")
    client.headers["Authorization"] = f"Bearer {token}"
    return client, res.json()["id"]


def stage(app: sessionmaker[Session], puid: uuid.UUID) -> tuple[str, str]:
    with project_session(app, puid) as s:
        st = s.scalars(select(PipelineState).order_by(PipelineState.entered_at.desc())).first()
        assert st is not None
        return st.stage, st.status


def passed(attempt: int = 1, **kw: Any) -> AttemptResult:
    return AttemptResult(attempt=attempt, status="passed", expectations_checked=1, **kw)


def test_full_protocol(setup: dict[str, Any], app: sessionmaker[Session]) -> None:
    st, puid = setup, setup["puid"]
    handle_execute_job(app, {"project_id": str(puid)})
    assert stage(app, puid) == ("execute", "running")
    with project_session(app, puid) as s:
        jobs = s.scalars(select(RunnerJob)).all()
        errors = s.scalars(select(Result).where(Result.status == "error")).all()
        assert len(jobs) == 3 and len(errors) == 1  # TC-CAR-003 did not compile
        assert errors[0].details["failure"]["message"] == "Not compiled"
    # redelivery of the execute job schedules nothing new
    with project_session(app, puid) as s:
        assert schedule(s, puid)[1:] == (0, 0)  # type: ignore[index]

    http, _ = runner(st)
    client = RunnerClient(http)
    assert client.heartbeat() == {"ok": True, "renewed": 0}
    other_http, _ = runner(st, "r2")
    other = RunnerClient(other_http)

    job = client.pull()
    assert job is not None and job["attempt"] == 1 and job["env"]["kind"] == "local"
    assert job["case"]["actions"][0]["kind"] == "goto" and job["identities"] == []
    assert client.heartbeat()["renewed"] == 1

    shot = b"\x89PNG fake"
    sha = hashlib.sha256(shot).hexdigest()
    assert http.put("/runner/evidence/NOTHEX", params={"kind": "screenshot"},
                    content=shot).status_code == 400  # fmt: skip
    assert http.put(f"/runner/evidence/{'0' * 64}", params={"kind": "screenshot"},
                    content=shot).status_code == 422  # fmt: skip
    ref = {"kind": "screenshot", "sha256": sha, "size": len(shot), "step_n": 1}
    missing = http.post(
        f"/runner/jobs/{job['job_id']}/result",
        json={"result": passed().model_dump(mode="json"), "evidence": [ref]},
    )
    assert missing.status_code == 422 and missing.json()["error"]["code"] == "EVIDENCE_MISSING"
    client.upload("screenshot", sha, shot)
    wrong = http.post(f"/runner/jobs/{job['job_id']}/result",
                      json={"result": passed(2).model_dump(mode="json")})  # fmt: skip
    assert wrong.status_code == 422
    stolen = other_http.post(f"/runner/jobs/{job['job_id']}/result",
                             json={"result": passed().model_dump(mode="json")})  # fmt: skip
    assert stolen.status_code == 409
    assert (
        http.post(
            f"/runner/jobs/job_{'0' * 32}/result", json={"result": passed().model_dump(mode="json")}
        ).status_code
        == 404
    )

    out = client.report(job["job_id"], passed(evidence_count=1), [ref], "chromium")
    assert out["created"] and not out["run_finished"]
    again = client.report(job["job_id"], passed(evidence_count=1), [ref], "chromium")
    assert not again["created"]

    second = other.pull()
    third = client.pull()
    assert second and third and client.pull() is None
    failure = AttemptResult(attempt=1, status="failed",
                            failure=Failure(kind="assertion", message="x"))  # fmt: skip
    other.report(second["job_id"], failure, [], "chromium")
    final = client.report(third["job_id"], passed(), [], "chromium")
    assert final["run_finished"]
    assert stage(app, puid) == ("judge", "queued")
    with project_session(app, puid) as s:
        run = s.scalars(select(Run)).one()
        assert run.status == "completed" and run.last_completed_case_id is not None
        ev = s.scalars(select(Evidence)).one()
        assert ev.object_key.endswith(sha) and ev.step_n == 1
        assert s.scalar(select(Result.browser).where(Result.status == "failed")) == "chromium"


def test_lease_expiry_and_loss(setup: dict[str, Any], app: sessionmaker[Session]) -> None:
    st, puid = setup, setup["puid"]
    handle_execute_job(app, {"project_id": str(puid)})
    a = RunnerClient(runner(st, "a")[0])
    b = RunnerClient(runner(st, "b")[0])
    job = a.pull()
    assert job is not None
    jid = ids.decode("job", job["job_id"])
    past = datetime.now(UTC) - timedelta(seconds=1)
    with project_session(app, puid) as s:  # runner a was killed: its lease ran out
        s.execute(update(RunnerJob).where(RunnerJob.id == jid).values(leased_until=past))
    taken = [j["job_id"] for j in iter(b.pull, None)]
    assert job["job_id"] in taken and len(taken) == 3  # the expired lease is claimable again
    with project_session(app, puid) as s:
        s.execute(update(RunnerJob).values(leased_until=past, status="leased",
                                           leases=runners_router.MAX_LEASES))  # fmt: skip
    assert b.pull() is None  # every job lost too often → error results, run done
    with project_session(app, puid) as s:
        assert {r.status for r in s.scalars(select(Result))} == {"error"}
        assert s.scalar(select(RunnerJob.status).limit(1)) == "lost"
    assert stage(app, puid) == ("judge", "queued")


def test_registration_and_auth(setup: dict[str, Any], app: sessionmaker[Session]) -> None:
    st = setup
    http, rid = runner(st, "pinned", cert_sha256="a" * 64)
    assert http.post("/runner/heartbeat", json={}).status_code == 401
    http.headers["X-Client-Cert-Sha256"] = "A" * 64
    assert http.post("/runner/heartbeat", json={}).status_code == 200
    listed = st["user"].get(f"{V1}/projects/{st['pid']}/runners").json()
    assert listed[0]["mtls"] and listed[0]["status"] == "online" and "token" not in listed[0]
    anon = TestClient(st["api"], base_url=f"http://testserver{V1}")
    assert anon.post("/runner/heartbeat", json={}).status_code == 401
    anon.headers["Authorization"] = f"Bearer saq_run_{st['puid'].hex}_{'x' * 40}"
    assert anon.post("/runner/heartbeat", json={}).status_code == 401
    assert st["user"].delete(f"{V1}/projects/{st['pid']}/runners/{rid}").status_code == 204
    assert http.post("/runner/heartbeat", json={}).status_code == 401
    gone = st["user"].delete(f"{V1}/projects/{st['pid']}/runners/rnr_{'0' * 32}")
    assert gone.status_code == 404
    audit = st["user"].get(f"{V1}/projects/{st['pid']}/audit?limit=200").json()["items"]
    assert {"runner.registered", "runner.revoked"} <= {e["action"] for e in audit}


def test_evidence_size_limit(setup: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    http, _ = runner(setup)
    monkeypatch.setattr(runners_router, "MAX_EVIDENCE_BYTES", 3)
    big = b"four"
    sha = hashlib.sha256(big).hexdigest()
    assert http.put(f"/runner/evidence/{sha}", params={"kind": "console"},
                    content=big).status_code == 413  # fmt: skip


def test_execute_without_run_fails(app: sessionmaker[Session], make_tenant: Any) -> None:
    pid = make_tenant().project_id
    with project_session(app, pid) as s:
        _pipeline(s, pid)
        s.execute(update(PipelineState).values(stage="execute"))
    handle_execute_job(app, {"project_id": str(pid)})
    assert stage(app, pid) == ("execute", "failed")
    handle_execute_job(app, {"project_id": str(pid)})  # stale job: no crash


def test_execute_with_nothing_compiled_goes_to_judge(
    setup: dict[str, Any], app: sessionmaker[Session]
) -> None:
    puid = setup["puid"]
    with project_session(app, puid) as s:
        s.execute(update(TestCase).values(compiled_path=None))
        env = s.scalars(select(Environment)).one()
        assert env.kind == "local"
    handle_execute_job(app, {"project_id": str(puid)})
    assert stage(app, puid) == ("judge", "queued")


@pytest.mark.browser
def test_end_to_end_with_real_browser(
    setup: dict[str, Any], app: sessionmaker[Session], chromium: Any, site: Any
) -> None:
    puid = setup["puid"]
    host, port = site.server_address[:2]
    with project_session(app, puid) as s:
        s.execute(update(Environment).values(base_url=f"http://{host}:{port}"))
    handle_execute_job(app, {"project_id": str(puid)})
    client = RunnerClient(runner(setup)[0])
    browser = Browser(chromium.new_context, "chromium-test")
    done = 0
    while process_one(client, browser, [EnvSecrets({})]):
        done += 1
    assert done == 3
    assert stage(app, puid) == ("judge", "queued")
    with project_session(app, puid) as s:
        results = s.scalars(select(Result)).all()
        assert len(results) == 4 and {r.browser for r in results if r.browser} == {"chromium-test"}
        kinds = {e.kind for e in s.scalars(select(Evidence))}
        assert {"screenshot", "trace"} <= kinds
        for e in s.scalars(select(Evidence)):
            data = setup["store"].get(e.object_key)
            assert hashlib.sha256(data).hexdigest() == e.sha256 == e.object_key.rsplit("/", 1)[1]


@pytest.mark.browser
def test_explorer_observations_become_pending_nodes(
    setup: dict[str, Any], app: sessionmaker[Session], chromium: Any, site: Any
) -> None:
    from apps.api.db.models import Edge, GraphVersion, Node
    from apps.runner.explorer import explore, submit
    from apps.runner.policy_hook import policy_context

    http, _ = runner(setup)
    client = RunnerClient(http)
    host, port = site.server_address[:2]
    envs = http.get("/runner/environments").json()
    assert envs[0]["kind"] == "local" and envs[0]["id"].startswith("env_")
    env = {**envs[0], "base_url": f"http://{host}:{port}"}
    page = chromium.new_context().new_page()
    result = explore(page, policy_context(env))
    page.context.close()
    with pytest.raises(Exception, match="409"):
        submit(client, env["id"], result)  # the seeded graph is approved: no draft to add to
    puid = setup["puid"]
    with project_session(app, puid) as s:
        s.add(GraphVersion(project_id=puid, number=2, status="draft"))
    out = submit(client, env["id"], result)
    assert out == {"graph_version": 2, "screens_added": 3, "fields_added": 6, "skipped_existing": 0}
    again = submit(client, env["id"], result)
    assert again["screens_added"] == 0 and again["skipped_existing"] == 9
    missing = http.post(
        "/runner/explorations",
        json={"env_id": f"env_{'0' * 32}", "exploration": result.model_dump(mode="json")},
    )
    assert missing.status_code == 404
    with project_session(app, puid) as s:
        nodes = s.scalars(select(Node).where(Node.attrs["origin"].astext == "explorer")).all()
        assert {n.review_status for n in nodes} == {"pending"}
        age = next(n for n in nodes if n.label == "Age")
        assert age.attrs["required"] == "true" and age.attrs["max"] == "18"
        assert next(n for n in nodes if n.label == "Country").attrs["options"] == "BD, IN"
        assert len(s.scalars(select(Edge).where(Edge.kind == "has_field")).all()) == 6
    audit = setup["user"].get(f"{V1}/projects/{setup['pid']}/audit?limit=200").json()["items"]
    assert any(e["action"] == "graph.explored" for e in audit)
