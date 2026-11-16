import asyncio

import pytest
from fastapi.testclient import TestClient

from apps.api import health
from apps.api.main import create_app
from apps.api.settings import get_settings


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    get_settings.cache_clear()
    return TestClient(create_app())


def test_healthz_returns_ok(client: TestClient) -> None:
    res = client.get("/api/v1/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_readyz_ready_when_nothing_configured(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "database_url", None)
    monkeypatch.setattr(get_settings(), "redis_url", None)
    res = client.get("/api/v1/readyz")
    assert res.status_code == 200
    assert res.json()["status"] == "ready"


def test_readyz_503_when_dependency_down(client: TestClient, monkeypatch) -> None:
    # Port 1 on localhost is never a Postgres server.
    monkeypatch.setattr(get_settings(), "database_url", "postgresql://u:p@127.0.0.1:1/db")
    monkeypatch.setattr(get_settings(), "redis_url", None)
    res = client.get("/api/v1/readyz")
    assert res.status_code == 503
    body = res.json()
    assert body["status"] == "not_ready"
    assert body["dependencies"]["database"] == "down"


def test_tcp_reachable_rejects_url_without_port() -> None:
    assert asyncio.run(health.tcp_reachable("postgresql://localhost/db")) is False


def test_openapi_is_served(client: TestClient) -> None:
    res = client.get("/api/v1/openapi.json")
    assert res.status_code == 200
    assert res.json()["info"]["title"] == "Smart Autonomous QA API"


def test_tcp_reachable_true_for_listening_socket() -> None:
    async def scenario() -> bool:
        server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            return await health.tcp_reachable(f"redis://127.0.0.1:{port}/0")

    assert asyncio.run(scenario()) is True


def test_check_dependencies_reports_reachable() -> None:
    async def scenario() -> list[health.DependencyStatus]:
        server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            return await health.check_dependencies({"redis": f"redis://127.0.0.1:{port}/0"})

    [status] = asyncio.run(scenario())
    assert status.ok and status.detail == "reachable"
