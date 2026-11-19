"""Two-factor sign-in end to end (T-105a)."""

from datetime import UTC, datetime, timedelta

import pytest

from apps.api import ids
from apps.api.auth import mfa, totp
from apps.api.crypto import SecretBox
from tests.api.conftest import PASSWORD

pytestmark = pytest.mark.integration
V1 = "/api/v1"
BOX = SecretBox(b"0" * 32)


def _code(secret: str, offset: int = 0) -> str:
    return totp.code_at(secret, totp.current_step() + offset)


def _wrong(secret: str, at: float | None = None) -> str:
    """A 6-digit code that is valid for no step in the drift window."""
    step = totp.current_step(at)
    valid = {totp.code_at(secret, step + d) for d in range(-2, 3)}
    return next(c for c in (f"{n:06d}" for n in range(1_000_000)) if c not in valid)


def test_enrol_login_replay_lockout_disable(make_user, make_client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    u.client.app.state.secret_box = BOX
    setup = u.post(f"{V1}/auth/totp/setup").json()
    secret = setup["secret"]
    assert setup["otpauth_uri"].startswith("otpauth://totp/")
    bad = u.post(f"{V1}/auth/totp/enable", json={"code": _wrong(secret)})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "INVALID_CODE"
    assert u.post(f"{V1}/auth/totp/enable", json={"code": _code(secret)}).status_code == 204
    assert u.post(f"{V1}/auth/totp/setup").status_code == 409
    assert u.post(f"{V1}/auth/totp/enable", json={"code": _code(secret)}).status_code == 409

    c = make_client()
    c.app.state.secret_box = BOX
    first = c.post(f"{V1}/auth/login", json={"email": u.email, "password": PASSWORD}).json()
    assert first["mfa_required"] is True and "saq_access" not in c.cookies
    token = first["mfa_token"]
    replay = c.post(f"{V1}/auth/login/mfa", json={"mfa_token": token, "code": _code(secret)})
    assert replay.status_code == 400 and replay.json()["error"]["code"] == "INVALID_CODE"
    assert (
        c.post(f"{V1}/auth/login/mfa", json={"mfa_token": "x", "code": "123456"}).status_code == 401
    )
    ok = c.post(f"{V1}/auth/login/mfa", json={"mfa_token": token, "code": _code(secret, 1)})
    assert ok.status_code == 200 and c.get(f"{V1}/me").status_code == 200

    later = datetime.now(UTC) + timedelta(seconds=90)
    monkeypatch.setattr(mfa, "now_utc", lambda: later)
    later_code = totp.code_at(secret, totp.current_step(later.timestamp()))
    wrong_later = _wrong(secret, later.timestamp())
    assert u.post(f"{V1}/auth/totp/disable", json={"code": wrong_later}).status_code == 400
    assert u.post(f"{V1}/auth/totp/disable", json={"code": later_code}).status_code == 204
    assert u.post(f"{V1}/auth/totp/disable", json={"code": later_code}).status_code == 409
    plain = make_client().post(f"{V1}/auth/login", json={"email": u.email, "password": PASSWORD})
    assert "csrf_token" in plain.json()


def test_wrong_codes_lock_the_account(make_user, make_client) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    u.client.app.state.secret_box = BOX
    secret = u.post(f"{V1}/auth/totp/setup").json()["secret"]
    u.post(f"{V1}/auth/totp/enable", json={"code": _code(secret)})
    c = make_client()
    c.app.state.secret_box = BOX
    token = c.post(f"{V1}/auth/login", json={"email": u.email, "password": PASSWORD}).json()[
        "mfa_token"
    ]
    wrong = _wrong(secret)
    codes = [
        c.post(f"{V1}/auth/login/mfa", json={"mfa_token": token, "code": wrong}).status_code
        for _ in range(6)
    ]
    assert codes[:5] == [400] * 5 and codes[5] == 429
    assert u.post(f"{V1}/auth/totp/disable", json={"code": _wrong(secret)}).status_code == 400


def test_mfa_needs_key_and_enabled_user(make_user, make_client) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    u.client.app.state.secret_box = None
    assert u.post(f"{V1}/auth/totp/setup").status_code == 503
    assert u.post(f"{V1}/auth/totp/disable", json={"code": "123456"}).status_code == 503
    c = make_client()
    c.app.state.secret_box = BOX
    me = u.client.get(f"{V1}/me").json()["id"]
    token = c.app.state.jwt_signer.issue_mfa(ids.decode("usr", me))
    res = c.post(f"{V1}/auth/login/mfa", json={"mfa_token": token, "code": "123456"})
    assert res.status_code == 401  # two-factor is not on for this user
    u.client.app.state.secret_box = BOX
    assert u.post(f"{V1}/auth/totp/disable", json={"code": "123456"}).status_code == 409
    no_setup = u.post(f"{V1}/auth/totp/enable", json={"code": "123456"})  # never set up
    assert no_setup.status_code == 400
