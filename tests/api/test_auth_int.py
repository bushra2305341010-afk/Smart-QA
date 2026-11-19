"""Register, login, lockout, CSRF, refresh rotation, logout and API tokens on real Postgres."""

from datetime import UTC, datetime, timedelta

import pytest
from argon2 import PasswordHasher
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from apps.api.auth import service
from apps.api.auth.tokens import AccessClaims, JwtSigner
from apps.api.db.models import ApiToken, AppUser
from tests.api.conftest import PASSWORD

pytestmark = pytest.mark.integration
V1 = "/api/v1"


def test_register_rules(make_client) -> None:  # type: ignore[no-untyped-def]
    c = make_client()
    ok = c.post(f"{V1}/auth/register", json={"email": "Ana@Example.com", "password": PASSWORD})
    assert ok.status_code == 201 and ok.json()["id"].startswith("usr_")
    dup = c.post(f"{V1}/auth/register", json={"email": "ana@example.com", "password": PASSWORD})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "EMAIL_TAKEN"  # citext
    short = c.post(f"{V1}/auth/register", json={"email": "b@example.com", "password": "short"})
    assert short.status_code == 400 and short.json()["error"]["details"] == {"field": "password"}


def test_login_and_me(make_user, project) -> None:  # type: ignore[no-untyped-def]
    owner, pid = project
    me = owner.client.get(f"{V1}/me").json()
    assert me["email"] == owner.email
    assert me["memberships"] == [{"project_id": pid, "name": "Shop", "role": "owner"}]
    assert {"saq_access", "saq_refresh", "saq_csrf"} <= set(owner.client.cookies.keys())


def test_wrong_password_and_unknown_email_look_the_same(make_user, make_client) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    c = make_client()
    a = c.post(f"{V1}/auth/login", json={"email": u.email, "password": "wrong password!"})
    b = c.post(f"{V1}/auth/login", json={"email": "nobody@example.com", "password": "x"})
    assert a.status_code == b.status_code == 401
    assert a.json()["error"]["message"] == b.json()["error"]["message"]


def test_lockout_after_five_failures(make_user, make_client, owner: sessionmaker[Session]) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    c = make_client()
    for _ in range(5):
        c.post(f"{V1}/auth/login", json={"email": u.email, "password": "wrong password!"})
    locked = c.post(f"{V1}/auth/login", json={"email": u.email, "password": PASSWORD})
    assert locked.status_code == 429 and int(locked.headers["Retry-After"]) > 0
    with owner.begin() as s:
        s.execute(
            update(AppUser)
            .where(AppUser.email == u.email)
            .values(locked_until=datetime.now(UTC) - timedelta(seconds=1))
        )
    assert (
        c.post(f"{V1}/auth/login", json={"email": u.email, "password": PASSWORD}).status_code == 200
    )
    with owner() as s:
        assert s.scalar(select(AppUser.failed_logins).where(AppUser.email == u.email)) == 0


def test_disabled_user_cannot_sign_in(make_user, make_client, owner) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    with owner.begin() as s:
        s.execute(update(AppUser).where(AppUser.email == u.email).values(status="disabled"))
    c = make_client()
    assert (
        c.post(f"{V1}/auth/login", json={"email": u.email, "password": PASSWORD}).status_code == 401
    )
    assert u.client.get(f"{V1}/me").status_code == 401  # existing session stops working


def test_cookie_writes_need_csrf(make_user) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    res = u.client.post(f"{V1}/projects", json={"name": "x"})
    assert res.status_code == 403 and res.json()["error"]["code"] == "CSRF_FAILED"
    bad = u.client.post(f"{V1}/projects", json={"name": "x"}, headers={"X-CSRF-Token": "nope"})
    assert bad.status_code == 403
    assert u.post(f"{V1}/projects", json={"name": "x"}).status_code == 201


def test_no_credentials(make_client) -> None:  # type: ignore[no-untyped-def]
    c = make_client()
    assert c.get(f"{V1}/me").json()["error"]["code"] == "UNAUTHENTICATED"
    assert c.get(f"{V1}/me", headers={"Authorization": "Basic abc"}).status_code == 401
    assert c.get(f"{V1}/me", headers={"Authorization": "Bearer not.a.jwt"}).status_code == 401
    assert c.post(f"{V1}/auth/refresh").status_code == 401


def test_refresh_rotates_and_reuse_revokes_family(make_user, make_client) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    old_refresh = u.client.cookies.get("saq_refresh")
    res = u.post(f"{V1}/auth/refresh")
    assert res.status_code == 200
    u.csrf = res.json()["csrf_token"]
    assert u.client.cookies.get("saq_refresh") != old_refresh
    assert u.client.get(f"{V1}/me").status_code == 200
    # An attacker replays the old refresh token: the whole family is revoked.
    attacker = make_client()
    replay = attacker.post(
        f"{V1}/auth/refresh",
        headers={"Cookie": f"saq_refresh={old_refresh}; saq_csrf=c", "X-CSRF-Token": "c"},
    )
    assert replay.status_code == 401 and replay.json()["error"]["message"] == "Session revoked"
    assert u.client.get(f"{V1}/me").status_code == 401
    assert u.post(f"{V1}/auth/refresh").status_code == 401


def test_refresh_needs_csrf(make_user) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    assert u.client.post(f"{V1}/auth/refresh").status_code == 403


def test_expired_refresh_token(app: sessionmaker[Session], make_user) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    token = u.client.cookies.get("saq_refresh")
    later = datetime.now(UTC) + timedelta(days=8)
    with pytest.raises(Exception, match="Session expired"):
        service.rotate(app, token, now=later)


def test_logout_revokes_session(make_user) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    access = u.client.cookies.get("saq_access")
    assert u.post(f"{V1}/auth/logout").status_code == 204
    u.client.cookies.set("saq_access", access, path="/api")
    assert u.client.get(f"{V1}/me").status_code == 401


def test_bearer_access_token(make_user, make_client, app) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    c = make_client()
    signer: JwtSigner = c.app.state.jwt_signer  # type: ignore[attr-defined]
    with app.begin() as s:
        uid = s.scalar(select(AppUser.id).where(AppUser.email == u.email))
        issued = service.start_session(s, uid)
    token = signer.issue(AccessClaims(uid, issued.session_id))
    res = c.post(
        f"{V1}/projects", json={"name": "cli"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 201  # no CSRF needed without cookies


def test_api_tokens(make_user, make_client, owner) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    rw = u.post(f"{V1}/tokens", json={"name": "ci"}).json()
    ro = u.post(
        f"{V1}/tokens", json={"name": "mcp", "scopes": ["read"], "expires_in_days": None}
    ).json()
    assert rw["token"].startswith("saq_pat_") and ro["expires_at"] is None
    c = make_client()
    auth_rw = {"Authorization": f"Bearer {rw['token']}"}
    auth_ro = {"Authorization": f"Bearer {ro['token']}"}
    assert c.get(f"{V1}/me", headers=auth_rw).json()["email"] == u.email
    assert c.post(f"{V1}/projects", json={"name": "t"}, headers=auth_rw).status_code == 201
    denied = c.post(f"{V1}/projects", json={"name": "t"}, headers=auth_ro)
    assert denied.status_code == 403 and denied.json()["error"]["details"] == {
        "permission": "token.write"
    }
    with owner.begin() as s:
        s.execute(
            update(ApiToken).where(ApiToken.name == "ci").values(expires_at=datetime.now(UTC))
        )
        s.execute(
            update(ApiToken).where(ApiToken.name == "mcp").values(revoked_at=datetime.now(UTC))
        )
    assert c.get(f"{V1}/me", headers=auth_rw).status_code == 401
    assert c.get(f"{V1}/me", headers=auth_ro).status_code == 401
    with owner() as s:
        stored = s.scalars(select(ApiToken.token_hash)).all()
    assert rw["token"] not in stored


def test_weak_hash_is_upgraded_on_login(make_user, make_client, owner) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    weak = PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1).hash(PASSWORD)
    with owner.begin() as s:
        s.execute(update(AppUser).where(AppUser.email == u.email).values(password_hash=weak))
    assert (
        make_client()
        .post(f"{V1}/auth/login", json={"email": u.email, "password": PASSWORD})
        .status_code
        == 200
    )
    with owner() as s:
        assert s.scalar(select(AppUser.password_hash).where(AppUser.email == u.email)) != weak


def test_token_logout_only_clears_cookies(make_user, make_client) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    token = u.post(f"{V1}/tokens", json={"name": "ci"}).json()["token"]
    c = make_client()
    auth = {"Authorization": f"Bearer {token}"}
    assert c.post(f"{V1}/auth/logout", headers=auth).status_code == 204
    assert c.get(f"{V1}/me", headers=auth).status_code == 200
