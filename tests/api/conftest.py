"""API test helpers: a TestClient wired to the RLS-enforcing runtime-role session factory."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from apps.api.auth.tokens import JwtSigner
from apps.api.main import create_app

PASSWORD = "correct horse battery staple"


@dataclass
class User:
    client: TestClient
    email: str
    csrf: str
    user_id: str

    def post(self, url: str, **kw):  # type: ignore[no-untyped-def]
        return self.client.post(url, headers={"X-CSRF-Token": self.csrf}, **kw)


@pytest.fixture
def make_client(app: sessionmaker[Session]) -> Callable[[], TestClient]:
    signer = JwtSigner.ephemeral()

    def _make() -> TestClient:
        return TestClient(create_app(session_factory=app, jwt_signer=signer))

    return _make


@pytest.fixture
def make_user(make_client: Callable[[], TestClient]) -> Callable[[], User]:
    def _make() -> User:
        client = make_client()
        email = f"{uuid.uuid4().hex[:12]}@example.com"
        res = client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
        assert res.status_code == 201, res.text
        res = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert res.status_code == 200, res.text
        body = res.json()
        return User(client, email, body["csrf_token"], body["user"]["id"])

    return _make


@pytest.fixture
def project(make_user: Callable[[], User]) -> tuple[User, str]:
    owner = make_user()
    res = owner.post("/api/v1/projects", json={"name": "Shop"})
    assert res.status_code == 201, res.text
    return owner, res.json()["id"]
