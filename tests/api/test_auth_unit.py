"""Auth building blocks that need no database."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import sessionmaker

from apps.api import ids, main
from apps.api.auth import passwords
from apps.api.auth.permissions import ROLE_PERMISSIONS, allowed
from apps.api.auth.service import lock_duration
from apps.api.auth.tokens import (
    AccessClaims,
    InvalidTokenError,
    JwtSigner,
    hash_secret,
    new_api_token,
)
from apps.api.errors import ApiError
from apps.api.settings import Settings


def _pem(key) -> str:  # type: ignore[no-untyped-def]
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


# ---------- passwords ----------


def test_password_rule() -> None:
    assert passwords.check_password_rule("short") is not None
    assert passwords.check_password_rule("x" * 1025) is not None
    assert passwords.check_password_rule("twelve chars") is None


def test_hash_and_verify() -> None:
    h = passwords.hash_password("correct horse battery")
    assert h.startswith("$argon2id$")
    assert passwords.verify_password(h, "correct horse battery")
    assert not passwords.verify_password(h, "wrong")
    assert not passwords.verify_password("not-a-hash", "x")
    assert not passwords.needs_rehash(h)


# ---------- tokens ----------


def test_jwt_roundtrip_and_tamper() -> None:
    signer = JwtSigner.ephemeral()
    claims = AccessClaims(uuid.uuid4(), uuid.uuid4())
    token = signer.issue(claims)
    assert signer.verify(token) == claims
    with pytest.raises(InvalidTokenError):
        signer.verify(token[:-2] + "xx")
    with pytest.raises(InvalidTokenError):
        JwtSigner.ephemeral().verify(token)  # other key


def test_jwt_expires_after_15_minutes() -> None:
    signer = JwtSigner.ephemeral()
    old = signer.issue(
        AccessClaims(uuid.uuid4(), uuid.uuid4()), datetime.now(UTC) - timedelta(minutes=16)
    )
    with pytest.raises(InvalidTokenError):
        signer.verify(old)


def test_signer_from_pem() -> None:
    signer = JwtSigner.from_pem(_pem(Ed25519PrivateKey.generate()))
    claims = AccessClaims(uuid.uuid4(), uuid.uuid4())
    assert signer.verify(signer.issue(claims)) == claims
    with pytest.raises(ValueError, match="Ed25519"):
        JwtSigner.from_pem(_pem(generate_private_key(SECP256R1())))


def test_opaque_tokens() -> None:
    token = new_api_token()
    assert token.startswith("saq_pat_") and len(token) > 40
    assert hash_secret(token) != token and len(hash_secret(token)) == 64


# ---------- permissions (docs/10 §4) ----------


@pytest.mark.parametrize(
    ("role", "permission", "expected"),
    [
        ("owner", "members.manage", True),
        ("qa_lead", "members.manage", False),
        ("qa_lead", "plan.approve", True),
        ("tester", "plan.approve", False),
        ("tester", "cases.approve", True),
        ("developer", "run.start", True),
        ("developer", "cases.approve", False),
        ("viewer", "run.start", False),
        ("viewer", "project.view", True),
        ("owner", "env.mark_production", True),
        ("qa_lead", "env.mark_production", False),
        ("stranger", "project.view", False),
    ],
)
def test_matrix(role: str, permission, expected: bool) -> None:  # type: ignore[no-untyped-def]
    assert allowed(role, permission) is expected


def test_every_role_can_view_and_owner_has_everything() -> None:
    assert all("project.view" in perms for perms in ROLE_PERMISSIONS.values())
    assert set().union(*ROLE_PERMISSIONS.values()) == ROLE_PERMISSIONS["owner"]


# ---------- lockout ----------


def test_lock_duration() -> None:
    assert lock_duration(4) is None
    assert lock_duration(5) == timedelta(seconds=30)
    assert lock_duration(6) == timedelta(seconds=60)
    assert lock_duration(100) == timedelta(hours=1)


# ---------- ids ----------


def test_ids_roundtrip_and_rejects() -> None:
    value = uuid.uuid4()
    assert ids.decode("prj", ids.encode("prj", value)) == value
    for bad in ("src_" + value.hex, "prj_short", "prj_" + "z" * 32, "nonsense"):
        with pytest.raises(ApiError) as exc:
            ids.decode("prj", bad, "Project")
        assert exc.value.status == 404


# ---------- app wiring ----------


def test_prod_requires_jwt_key() -> None:
    with pytest.raises(RuntimeError, match="JWT_PRIVATE_KEY"):
        main._signer(Settings(saq_env="prod", jwt_private_key=None))
    key = SecretStr(_pem(Ed25519PrivateKey.generate()))
    assert main._signer(Settings(saq_env="prod", jwt_private_key=key)).kid == "k1"


def test_no_database_gives_503_envelope_and_security_headers(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(main, "get_settings", lambda: Settings(database_url=None))
    client = TestClient(main.create_app())
    res = client.post("/api/v1/auth/register", json={"email": "a@b.co", "password": "x" * 12})
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "UNAVAILABLE"
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in res.headers["Content-Security-Policy"]


def test_validation_and_unknown_route_use_the_envelope(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(main, "get_settings", lambda: Settings(database_url=None))
    client = TestClient(main.create_app(session_factory=sessionmaker()))
    res = client.post("/api/v1/auth/register", json={"email": "not-an-email"})
    assert res.status_code == 400
    body = res.json()["error"]
    assert body["code"] == "VALIDATION_ERROR" and body["details"]["fields"] and body["trace_id"]
    assert client.get("/api/v1/nope").json()["error"]["code"] == "NOT_FOUND"


def test_object_store_only_when_s3_is_configured() -> None:
    from apps.api.storage import S3ObjectStore

    assert main._store(Settings(s3_endpoint=None)) is None
    configured = Settings(
        s3_endpoint="http://localhost:1", s3_access_key="k", s3_secret_key=SecretStr("s")
    )
    assert isinstance(main._store(configured), S3ObjectStore)
