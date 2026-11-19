"""`saq` CLI against the real API (FR-17)."""

from __future__ import annotations

import json
import stat

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from typer.testing import CliRunner

from apps.api import ids
from apps.api.db.session import project_session
from apps.cli import main as cli
from tests.orchestrator.seed import seed

pytestmark = pytest.mark.integration
runner = CliRunner()


@pytest.fixture
def saq(project, tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    owner, pid = project
    token = owner.post("/api/v1/tokens", json={"name": "cli"}).json()["token"]
    api = owner.client.app

    def factory(url: str, tok: str) -> httpx.Client:
        return TestClient(
            api, base_url="http://testserver/api/v1", headers={"Authorization": f"Bearer {tok}"}
        )

    monkeypatch.setattr(cli, "CLIENT_FACTORY", factory)
    monkeypatch.setenv("SAQ_CONFIG", str(tmp_path / "saq.json"))
    monkeypatch.delenv("SAQ_TOKEN", raising=False)
    monkeypatch.delenv("SAQ_URL", raising=False)

    def run(*args: str):  # type: ignore[no-untyped-def]
        return runner.invoke(cli.app, list(args))

    return run, pid, token, tmp_path


def test_cli_flow(saq, app) -> None:  # type: ignore[no-untyped-def]
    run, pid, token, tmp = saq
    assert "NOT_LOGGED_IN" in run("status", "-p", pid).output
    assert run("login", "--url", "http://x", "--token", "saq_pat_wrong").exit_code == 1
    ok = run("login", "--url", "http://x", "--token", token)
    assert ok.exit_code == 0 and "Logged in as" in ok.output
    assert stat.S_IMODE((tmp / "saq.json").stat().st_mode) == 0o600

    assert "pipeline: not started" in run("status", "-p", pid).output
    doc = tmp / "notes.md"
    doc.write_text("# Rules\n\nCoupons expire after 30 days.\n")
    up = run("upload", "-p", pid, str(doc), "--json")
    assert json.loads(up.output)[0]["kind"] == "md"
    assert "pipeline: ingest / queued" in run("event", "-p", pid, "start").output
    status = json.loads(run("status", "-p", pid, "--json").output)
    assert status["pipeline"]["stage"] == "ingest"
    bad = run("event", "-p", pid, "graph_approved")
    assert bad.exit_code == 1 and "STATE_CONFLICT" in bad.output

    none = run("plan", "-p", pid)
    assert none.exit_code == 1 and "No plan yet" in none.output
    puid = ids.decode("prj", pid)
    with project_session(app, puid) as s:
        data = seed(s, puid)
        run_id = ids.encode("run", data.run.id)
    assert "TC-CHK-001" not in run("cases", "-p", pid).output  # seeded plan is not approved
    shown = run("plan", "-p", pid).output
    assert "1 approved of 1 suggested" in shown and "risk 1.00" in shown
    assert json.loads(run("plan", "-p", pid, "--json").output)["status"] == "draft"
    assert "Checkout 500" in run("bugs", "-p", pid).output
    assert json.loads(run("cases", "-p", pid, "--json").output) == []

    assert "Give --xlsx" in run("report", "-p", pid, "--run", run_id).output
    out = run(
        "report",
        "-p",
        pid,
        "--run",
        run_id,
        "--xlsx",
        str(tmp / "r.xlsx"),
        "--pack",
        str(tmp / "r.html"),
    )
    assert out.exit_code == 0 and (tmp / "r.xlsx").read_bytes()[:2] == b"PK"
    assert "<html" in (tmp / "r.html").read_text()
    only_pack = run("report", "-p", pid, "--run", run_id, "--pack", str(tmp / "p.html"))
    assert only_pack.exit_code == 0 and (tmp / "p.html").exists()
    missing = run("report", "-p", pid, "--run", f"run_{'0' * 32}", "--xlsx", str(tmp / "x.xlsx"))
    assert missing.exit_code == 1 and "NOT_FOUND" in missing.output

    assert "audit chain OK" in run("audit", "verify", "-p", pid).output
    assert json.loads(run("audit", "verify", "-p", pid, "--json").output)["verified"] is True


def test_cli_cases_and_broken_audit(saq, app, owner) -> None:  # type: ignore[no-untyped-def]
    run, pid, token, _ = saq
    run("login", "--url", "http://x", "--token", token)
    puid = ids.decode("prj", pid)
    with project_session(app, puid) as s:
        data = seed(s, puid)
        data.plan.status = "approved"
        data.case.citation = {"status": "verified"}
    listed = run("cases", "-p", pid).output
    assert "TC-CHK-001" in listed and "verified" in listed
    with owner.begin() as s:
        s.execute(text("SET LOCAL session_replication_role = replica"))
        s.execute(text("UPDATE audit_event SET actor = 'evil' WHERE project_id = :p"), {"p": puid})
    broken = run("audit", "verify", "-p", pid)
    assert broken.exit_code == 1 and "BROKEN at seq 1" in broken.output


def test_env_token_and_non_json_errors(saq, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    run, pid, token, _ = saq
    monkeypatch.setenv("SAQ_URL", "http://x")
    monkeypatch.setenv("SAQ_TOKEN", token)
    assert "Shop" in run("status", "-p", pid).output
    gateway_down = httpx.MockTransport(lambda r: httpx.Response(502, text="bad gateway"))
    monkeypatch.setattr(
        cli,
        "CLIENT_FACTORY",
        lambda url, tok: httpx.Client(base_url="http://x/api/v1", transport=gateway_down),
    )
    res = run("status", "-p", pid)
    assert res.exit_code == 1 and "error 502: bad gateway" in res.output


def test_default_client() -> None:
    c = cli.default_client("http://localhost:8000/", "t")
    assert (
        str(c.base_url) == "http://localhost:8000/api/v1/"
        and c.headers["Authorization"] == "Bearer t"
    )
