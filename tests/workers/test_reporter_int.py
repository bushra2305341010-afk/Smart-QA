"""Bug drafts, Gate 4, filing and the run workbook (US-08, US-09)."""

from __future__ import annotations

import io
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from pydantic import SecretStr

from apps.api import ids
from apps.api.auth.tokens import JwtSigner
from apps.api.db.models import (
    Evidence,
    PipelineState,
    Project,
    Result,
    Source,
    Step,
    TestCase,
    Verdict,
)
from apps.api.db.session import project_session
from apps.api.main import create_app
from apps.api.settings import Settings
from apps.api.storage import MemoryObjectStore
from apps.api.trackers import tracker_factory
from apps.workers.reporter import draft_bugs, handle_report_job, report_key
from packages.exporters.trackers.github import GitHubTracker, Issue, TrackerError
from tests.api.conftest import PASSWORD
from tests.orchestrator.seed import seed

pytestmark = pytest.mark.integration
V1 = "/api/v1"


class FakeTracker:
    def __init__(self, fail: bool = False) -> None:
        self.filed: list[tuple[str, list[str]]] = []
        self.fail = fail

    def find_duplicates(self, title: str, limit: int = 5) -> list[Issue]:
        if self.fail:
            raise TrackerError("GitHub 502")
        return [Issue(3, "Checkout 500 (old)", "https://github.com/acme/shop/issues/3")]

    def file(self, title: str, body: str, labels: list[str]) -> Issue:
        if self.fail:
            raise TrackerError("GitHub 502")
        self.filed.append((title, labels))
        return Issue(9, title, "https://github.com/acme/shop/issues/9")


@pytest.fixture
def env(app):  # type: ignore[no-untyped-def]
    tracker = FakeTracker()
    trackers = {"t": tracker}
    client = TestClient(
        create_app(
            session_factory=app,
            jwt_signer=JwtSigner.ephemeral(),
            trackers=lambda settings: trackers["t"] if settings.get("tracker") else None,
        )
    )
    client.post(f"{V1}/auth/register", json={"email": "lead@example.com", "password": PASSWORD})
    login = client.post(
        f"{V1}/auth/login", json={"email": "lead@example.com", "password": PASSWORD}
    )
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    pid = client.post(f"{V1}/projects", json={"name": "Shop"}).json()["id"]
    puid = ids.decode("prj", pid)
    with project_session(app, puid) as s:
        data = seed(s, puid)  # 1 failed result + fail verdict + bug draft
        data.plan.status = "approved"
        s.get_one(Project, puid).settings = {"tracker": {"kind": "github", "repo": "acme/shop"}}
        second = Result(
            project_id=puid,
            run_id=data.run.id,
            test_case_id=data.case.id,
            attempt=2,
            status="failed",
        )
        flaky = Result(
            project_id=puid,
            run_id=data.run.id,
            test_case_id=data.case.id,
            attempt=3,
            status="passed",
        )
        no_verdict = Result(project_id=puid, run_id=data.run.id, test_case_id=data.case.id,
                            attempt=4, status="error")  # fmt: skip
        src = Source(
            project_id=puid, kind="md", uri="upload:prd.md", sha256="c" * 64, filename="prd.md"
        )
        s.add_all([second, flaky, no_verdict, src])
        s.flush()
        data.case.citation = {
            "status": "verified",
            "source_id": str(src.id),
            "quote": "Orders are placed.",
        }
        s.add_all([Step(project_id=puid, test_case_id=data.case.id, n=i, action=a)
                   for i, a in enumerate(["Open cart", "Pay"], start=1)])  # fmt: skip
        s.add_all([
            Verdict(project_id=puid, result_id=second.id, verdict="fail", confidence=0.95,
                    reason="Order total wrong for admin@shop.example"),
            Verdict(project_id=puid, result_id=flaky.id, verdict="flaky", confidence=0.6,
                    reason="timing"),
            Evidence(project_id=puid, result_id=second.id, step_n=2, kind="screenshot",
                     sha256="ab" * 32, object_key="evidence/ab", size=10),
            PipelineState(project_id=puid, stage="bug_review", status="awaiting_approval",
                          entered_at=datetime.now(UTC)),
        ])  # fmt: skip
    return client, pid, puid, data, trackers


def test_drafts_gate4_filing_and_workbook(env, app) -> None:  # type: ignore[no-untyped-def]
    client, pid, puid, data, trackers = env
    assert draft_bugs(app, puid, data.run.id) == 1  # only the new Fail; never Flaky
    assert draft_bugs(app, puid, data.run.id) == 0
    bugs = client.get(f"{V1}/projects/{pid}/bugs").json()
    assert [b["status"] for b in bugs] == ["draft", "draft"]
    new = bugs[1]
    assert new["severity"] == "high" and "admin@shop.example" not in new["body_md"]
    assert "Order placed" in new["body_md"] and "screenshot " + "ab" * 32 in new["body_md"]
    run_filter = client.get(f"{V1}/projects/{pid}/bugs?run_id={new['run_id']}&status=draft").json()
    assert len(run_filter) == 2

    dups = client.get(f"{V1}/projects/{pid}/bugs/{new['id']}/duplicates").json()
    assert {d["source"] for d in dups} == {"project", "tracker"}
    blocked = client.post(f"{V1}/projects/{pid}/bugs/approve")
    assert blocked.status_code == 409 and len(blocked.json()["error"]["details"]["bug_ids"]) == 2

    edited = client.patch(
        f"{V1}/projects/{pid}/bugs/{new['id']}",
        json={"title": "Wrong total", "severity": "critical"},
    )
    assert edited.json()["title"] == "Wrong total" and edited.json()["body_md"] == new["body_md"]
    assert (
        client.post(f"{V1}/projects/{pid}/bugs/{new['id']}/confirm").json()["status"] == "confirmed"
    )
    dismissed = client.post(
        f"{V1}/projects/{pid}/bugs/{bugs[0]['id']}/dismiss", json={"reason": "expected behaviour"}
    )
    assert dismissed.json()["status"] == "dismissed"
    assert client.post(f"{V1}/projects/{pid}/bugs/{new['id']}/confirm").status_code == 409
    assert (
        client.patch(f"{V1}/projects/{pid}/bugs/{new['id']}", json={"title": "x"}).status_code
        == 409
    )
    assert client.get(f"{V1}/projects/{pid}/bugs/bug_{'0' * 32}/duplicates").status_code == 404

    gate = client.post(f"{V1}/projects/{pid}/bugs/approve")
    assert gate.json() == {"stage": "report", "status": "queued"}
    assert (
        client.post(f"{V1}/projects/{pid}/bugs/approve").json()["error"]["code"] == "STATE_CONFLICT"
    )

    xlsx = client.get(f"{V1}/projects/{pid}/runs/{new['run_id']}/export.xlsx")
    assert xlsx.headers["content-type"].startswith("application/vnd.openxmlformats")
    wb = load_workbook(io.BytesIO(xlsx.content))
    assert wb.sheetnames == [
        "Test Cases",
        "Run Results",
        "Bugs",
        "Traceability",
        "Coverage",
        "Evidence Index",
    ]
    assert (
        wb["Run Results"].max_row == 5
        and wb["Bugs"].max_row == 3
        and wb["Evidence Index"].max_row == 2
        and wb["Test Cases"]["K2"].value == "prd.md"
    )
    assert client.get(f"{V1}/projects/{pid}/runs/run_{'0' * 32}/export.xlsx").status_code == 404

    store = MemoryObjectStore()
    tracker = trackers["t"]
    handle_report_job(app, store, lambda s: tracker, {"project_id": str(puid)})
    assert [labels for _, labels in tracker.filed] == [["smart-qa", "severity:critical"]]
    assert report_key(data.run.id) in store.objects
    filed = client.get(f"{V1}/projects/{pid}/bugs?status=filed").json()
    assert filed[0]["tracker_ref"].endswith("/issues/9")
    current = client.get(f"{V1}/projects/{pid}/pipeline").json()["current"]
    assert (current["stage"], current["status"]) == ("done", "done")


def test_filing_failure_and_no_tracker(env, app) -> None:  # type: ignore[no-untyped-def]
    client, pid, puid, data, trackers = env
    trackers["t"] = FakeTracker(fail=True)
    [bug] = client.get(f"{V1}/projects/{pid}/bugs").json()
    assert client.get(f"{V1}/projects/{pid}/bugs/{bug['id']}/duplicates").status_code == 502
    with project_session(app, puid) as s:
        s.get_one(Project, puid).settings = {}
        case = s.get_one(TestCase, data.case.id)
        case.citation = {
            **(case.citation or {}),
            "source_id": "00000000-0000-0000-0000-000000000000",
        }
    assert client.get(f"{V1}/projects/{pid}/bugs/{bug['id']}/duplicates").json() == []
    xlsx = client.get(f"{V1}/projects/{pid}/runs/{bug['run_id']}/export.xlsx").content
    assert load_workbook(io.BytesIO(xlsx))["Test Cases"]["K2"].value is None
    with project_session(app, puid) as s:
        s.get_one(TestCase, data.case.id).citation = {"status": "unable_to_verify", "quote": "q"}
    xlsx = client.get(f"{V1}/projects/{pid}/runs/{bug['run_id']}/export.xlsx").content
    assert load_workbook(io.BytesIO(xlsx))["Test Cases"]["M2"].value == "unable_to_verify"
    client.post(f"{V1}/projects/{pid}/bugs/{bug['id']}/confirm")
    client.post(f"{V1}/projects/{pid}/bugs/approve")
    store = MemoryObjectStore()
    handle_report_job(app, store, lambda s: trackers["t"], {"project_id": str(puid)})
    current = client.get(f"{V1}/projects/{pid}/pipeline").json()["current"]
    assert current["status"] == "failed"
    client.post(f"{V1}/projects/{pid}/pipeline/events", json={"event": "retry"})
    handle_report_job(
        app, store, lambda s: None, {"project_id": str(puid)}
    )  # no tracker: nothing filed
    assert client.get(f"{V1}/projects/{pid}/pipeline").json()["current"]["status"] == "done"
    assert client.get(f"{V1}/projects/{pid}/bugs").json()[0]["status"] == "confirmed"
    handle_report_job(app, store, lambda s: None, {"project_id": str(puid)})  # done: no crash


def test_report_without_run(app, make_tenant) -> None:  # type: ignore[no-untyped-def]
    pid = make_tenant().project_id
    with project_session(app, pid) as s:
        s.add(
            PipelineState(
                project_id=pid, stage="report", status="queued", entered_at=datetime.now(UTC)
            )
        )
    store = MemoryObjectStore()
    handle_report_job(app, store, lambda s: None, {"project_id": str(pid)})
    assert store.objects == {}


def test_tracker_factory() -> None:
    make = tracker_factory(Settings(github_token=SecretStr("t")))
    assert make({}) is None and make({"tracker": {"kind": "jira"}}) is None
    assert isinstance(make({"tracker": {"kind": "github", "repo": "a/b"}}), GitHubTracker)
    assert (
        tracker_factory(Settings(github_token=None))({"tracker": {"kind": "github", "repo": "a/b"}})
        is None
    )
