"""MCP preview: read-only tools over the real API (P5)."""

from __future__ import annotations

import asyncio

import httpx
import pytest
import typer
from fastapi.testclient import TestClient

from apps.cli import main as cli
from apps.mcp.server import ApiError, build_server, get_brief, plan_tests, understand_change
from tests.workers.test_analyst_int import env  # noqa: F401
from tests.workers.test_designer_int import _through_gate2

pytestmark = pytest.mark.integration


def _api(client: TestClient) -> TestClient:
    token = client.post("/api/v1/tokens", json={"name": "mcp", "scopes": ["read"]}).json()["token"]
    return TestClient(
        client.app,
        base_url="http://testserver/api/v1",
        headers={"Authorization": f"Bearer {token}"},
    )


def test_tools_before_and_after_approval(env, app) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    client, store, pid, puid = env
    api = _api(client)
    for call in (
        lambda: get_brief(api, pid),
        lambda: plan_tests(api, pid),
        lambda: understand_change(api, pid, "x"),
    ):
        with pytest.raises(ApiError, match="NOT_FOUND"):
            call()

    _through_gate2(client, store, app, pid, puid)
    brief = get_brief(api, pid)
    assert brief.startswith("<untrusted_data") and "Password must be 8 to 64 characters." in brief
    plan = plan_tests(api, pid)
    assert plan["status"] == "approved" and plan["segments"][0]["journey"] == "Sign up"
    assert {t["technique"] for t in plan["segments"][0]["techniques"]} >= {
        "happy_path",
        "boundary_value",
    }
    assert (
        plan_tests(api, pid, ["sign UP"])["segments"]
        and plan_tests(api, pid, ["Nope"])["segments"] == []
    )

    diff = "--- a/auth.py\n+++ b/auth.py\n+    if len(pw) > 64:  # password length rule\n"
    impact = understand_change(api, pid, diff)
    [hit] = impact["affected_journeys"]
    assert hit["journey"] == "Sign up" and "Rule 'Password length'" in hit["reasons"][0]
    assert understand_change(api, pid, "+ unrelated css change")["affected_journeys"] == []


def test_server_lists_read_only_tools_and_calls_them(env, app) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    client, store, pid, puid = env
    _through_gate2(client, store, app, pid, puid)
    api = _api(client)
    server = build_server(
        lambda: TestClient(api.app, base_url=str(api.base_url), headers=dict(api.headers)), pid
    )

    async def run() -> tuple[list, object, object, object]:
        tools = await server.list_tools()
        planned = await server.call_tool("plan_tests", {"journeys": ["Sign up"]})
        brief = await server.call_tool("get_brief", {})
        change = await server.call_tool("understand_change", {"diff": "+ password length"})
        return tools, planned, brief, change

    tools, planned, brief, change = asyncio.run(run())
    assert {t.name for t in tools} == {
        "get_brief", "plan_tests", "understand_change", "get_verdicts", "run_journeys"
    }  # fmt: skip
    assert all(t.annotations.read_only_hint for t in tools if t.name != "run_journeys")
    assert not next(t for t in tools if t.name == "run_journeys").annotations.read_only_hint
    assert "Sign up" in str(planned) and "untrusted_data" in str(brief) and "Sign up" in str(change)


def test_non_json_error_and_cli_wiring(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    down = httpx.Client(
        base_url="http://x/api/v1",
        transport=httpx.MockTransport(lambda r: httpx.Response(500, text="boom")),
    )
    with pytest.raises(ApiError, match="500: boom"):
        get_brief(down, "prj_x")
    monkeypatch.setenv("SAQ_CONFIG", str(tmp_path / "none.json"))
    monkeypatch.delenv("SAQ_TOKEN", raising=False)
    monkeypatch.delenv("SAQ_URL", raising=False)
    with pytest.raises(typer.Exit):
        cli.mcp_server("prj_x")
    monkeypatch.setenv("SAQ_URL", "http://localhost:1")
    monkeypatch.setenv("SAQ_TOKEN", "saq_pat_x")
    assert cli.mcp_server("prj_x").name == "smart-qa"
