"""Accounts, login with lockout, rotating refresh sessions and API tokens (docs/10 §2-3).

Functions that must persist something *and then fail* (a wrong password increments the failure
counter; a reused refresh token revokes its family) take a session factory and commit before
raising, so the side effect is not rolled back with the error.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from apps.api.auth import passwords
from apps.api.auth.breached import BreachChecker
from apps.api.auth.tokens import REFRESH_TTL, hash_secret, new_api_token, new_secret
from apps.api.db.models import ApiToken, AppUser, AuthSession
from apps.api.errors import ApiError, conflict, unauthenticated

LOCK_AFTER = 5
BASE_LOCK = timedelta(seconds=30)
MAX_LOCK = timedelta(hours=1)
BAD_LOGIN = "Email or password is wrong"


def now_utc() -> datetime:
    return datetime.now(UTC)


def lock_duration(failures: int) -> timedelta | None:
    """No lock for the first 4 failures, then 30 s doubling per failure, capped at 1 hour."""
    if failures < LOCK_AFTER:
        return None
    return min(BASE_LOCK * (1 << min(failures - LOCK_AFTER, 16)), MAX_LOCK)


def register(
    factory: sessionmaker[Session],
    email: str,
    password: str,
    breach: BreachChecker | None = None,
) -> AppUser:
    problem = passwords.check_password_rule(password)
    if problem is None and breach is not None and breach.is_breached(password):
        problem = "This password appears in a known data breach; choose another one"
    if problem:
        raise ApiError(400, "VALIDATION_ERROR", problem, {"field": "password"})
    try:
        with factory.begin() as s:
            user = AppUser(email=email, password_hash=passwords.hash_password(password))
            s.add(user)
            s.flush()
            return user
    except IntegrityError:
        raise conflict("An account with this email already exists", "EMAIL_TAKEN") from None


def authenticate(
    factory: sessionmaker[Session], email: str, password: str, now: datetime | None = None
) -> AppUser:
    now = now or now_utc()
    error: ApiError | None = None
    with factory.begin() as s:
        user = s.scalar(select(AppUser).where(AppUser.email == email).with_for_update())
        if user is None:
            passwords.verify_password(passwords.DUMMY_HASH, password)  # equal timing
            error = unauthenticated(BAD_LOGIN)
        elif user.locked_until is not None and user.locked_until > now:
            wait = int((user.locked_until - now).total_seconds()) + 1
            error = ApiError(
                429,
                "RATE_LIMITED",
                "Too many failed sign-ins; try again later",
                {"retry_after_s": wait},
                {"Retry-After": str(wait)},
            )
        elif not passwords.verify_password(user.password_hash, password):
            user.failed_logins += 1
            lock = lock_duration(user.failed_logins)
            user.locked_until = now + lock if lock else None
            error = unauthenticated(BAD_LOGIN)
        elif user.status != "active":
            error = unauthenticated(BAD_LOGIN)
        else:
            user.failed_logins = 0
            user.locked_until = None
            if passwords.needs_rehash(user.password_hash):
                user.password_hash = passwords.hash_password(password)
    if error:
        raise error
    assert user is not None
    return user


@dataclass(frozen=True)
class IssuedSession:
    session_id: uuid.UUID
    family_id: uuid.UUID
    user_id: uuid.UUID
    refresh_token: str


def start_session(
    s: Session,
    user_id: uuid.UUID,
    *,
    family_id: uuid.UUID | None = None,
    user_agent: str | None = None,
    ip: str | None = None,
    now: datetime | None = None,
) -> IssuedSession:
    token = new_secret()
    row = AuthSession(
        user_id=user_id,
        family_id=family_id or uuid.uuid4(),
        refresh_hash=hash_secret(token),
        expires_at=(now or now_utc()) + REFRESH_TTL,
        user_agent=user_agent,
        ip=ip,
    )
    s.add(row)
    s.flush()
    return IssuedSession(row.id, row.family_id, user_id, token)


def revoke_family(s: Session, family_id: uuid.UUID, now: datetime | None = None) -> None:
    s.execute(
        update(AuthSession)
        .where(AuthSession.family_id == family_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now or now_utc())
    )


def rotate(
    factory: sessionmaker[Session], refresh_token: str, now: datetime | None = None
) -> IssuedSession:
    """Exchange a refresh token for a new one. Reusing an old token revokes the whole family."""
    now = now or now_utc()
    reused = False
    issued: IssuedSession | None = None
    with factory.begin() as s:
        row = s.scalar(
            select(AuthSession)
            .where(AuthSession.refresh_hash == hash_secret(refresh_token))
            .with_for_update()
        )
        if row is None or row.revoked_at is not None or row.expires_at <= now:
            pass
        elif row.rotated_at is not None:
            reused = True
            revoke_family(s, row.family_id, now)
        else:
            row.rotated_at = now
            issued = start_session(
                s,
                row.user_id,
                family_id=row.family_id,
                user_agent=row.user_agent,
                ip=row.ip,
                now=now,
            )
    if issued is None:
        raise unauthenticated("Session revoked" if reused else "Session expired")
    return issued


def active_session(s: Session, session_id: uuid.UUID) -> AuthSession | None:
    """The session row if neither it nor its user is revoked/disabled."""
    return s.scalar(
        select(AuthSession)
        .join(AppUser, AppUser.id == AuthSession.user_id)
        .where(
            AuthSession.id == session_id,
            AuthSession.revoked_at.is_(None),
            AppUser.status == "active",
        )
    )


def create_api_token(
    s: Session,
    user_id: uuid.UUID,
    name: str,
    scopes: list[str],
    expires_in: timedelta | None,
    now: datetime | None = None,
) -> tuple[ApiToken, str]:
    token = new_api_token()
    row = ApiToken(
        user_id=user_id,
        name=name,
        token_hash=hash_secret(token),
        scopes=sorted(set(scopes)),
        expires_at=(now or now_utc()) + expires_in if expires_in else None,
    )
    s.add(row)
    s.flush()
    return row, token


def resolve_api_token(s: Session, token: str, now: datetime | None = None) -> ApiToken | None:
    now = now or now_utc()
    row = s.scalar(
        select(ApiToken)
        .join(AppUser, AppUser.id == ApiToken.user_id)
        .where(
            ApiToken.token_hash == hash_secret(token),
            ApiToken.revoked_at.is_(None),
            AppUser.status == "active",
        )
    )
    if row is None or (row.expires_at is not None and row.expires_at <= now):
        return None
    row.last_used_at = now
    return row
