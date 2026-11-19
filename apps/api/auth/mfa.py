"""TOTP enrolment and the second login step (docs/10 §2, T-105a).

The TOTP secret is stored only encrypted (AES-256-GCM, context bound to the user id). A code is
accepted once: `totp_last_step` refuses replays inside the drift window. Wrong codes count
towards the same lockout as wrong passwords.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.auth import totp
from apps.api.auth.service import lock_duration, now_utc
from apps.api.crypto import SecretBox
from apps.api.db.models import AppUser
from apps.api.errors import ApiError, conflict, unauthenticated


def _context(user_id: uuid.UUID) -> bytes:
    return b"totp:" + user_id.bytes


def invalid_code() -> ApiError:
    return ApiError(400, "INVALID_CODE", "The code is wrong or was already used")


@dataclass(frozen=True)
class Enrolment:
    secret: str
    otpauth_uri: str


def setup(s: Session, box: SecretBox, user_id: uuid.UUID) -> Enrolment:
    user = s.get_one(AppUser, user_id)
    if user.totp_enabled:
        raise conflict("Two-factor sign-in is already on; disable it first")
    secret = totp.new_secret()
    user.totp_secret_enc = box.seal(secret, _context(user.id))
    return Enrolment(secret, totp.provisioning_uri(secret, user.email))


def _check(user: AppUser, box: SecretBox, code: str, now: datetime) -> int | None:
    if user.totp_secret_enc is None:
        return None
    secret = box.open(user.totp_secret_enc, _context(user.id))
    return totp.verify(secret, code, now.timestamp(), after_step=user.totp_last_step)


def enable(s: Session, box: SecretBox, user_id: uuid.UUID, code: str) -> None:
    user = s.get_one(AppUser, user_id)
    if user.totp_enabled:
        raise conflict("Two-factor sign-in is already on")
    step = _check(user, box, code, now_utc())
    if step is None:
        raise invalid_code()
    user.totp_enabled, user.totp_last_step = True, step


def disable(s: Session, box: SecretBox, user_id: uuid.UUID, code: str) -> None:
    user = s.get_one(AppUser, user_id)
    if not user.totp_enabled:
        raise conflict("Two-factor sign-in is not on")
    if _check(user, box, code, now_utc()) is None:
        raise invalid_code()
    user.totp_enabled, user.totp_secret_enc, user.totp_last_step = False, None, None


def complete_login(
    factory: sessionmaker[Session],
    box: SecretBox,
    user_id: uuid.UUID,
    code: str,
    now: datetime | None = None,
) -> AppUser:
    """Second step. Commits the failure counter before raising, like the password step."""
    now = now or now_utc()
    error: ApiError | None = None
    with factory.begin() as s:
        user = s.scalar(select(AppUser).where(AppUser.id == user_id).with_for_update())
        if user is None or user.status != "active" or not user.totp_enabled:
            error = unauthenticated("Sign in again")
        elif user.locked_until is not None and user.locked_until > now:
            error = ApiError(429, "RATE_LIMITED", "Too many failed sign-ins; try again later")
        else:
            step = _check(user, box, code, now)
            if step is None:
                user.failed_logins += 1
                lock = lock_duration(user.failed_logins)
                user.locked_until = now + lock if lock else None
                error = invalid_code()
            else:
                user.totp_last_step, user.failed_logins, user.locked_until = step, 0, None
    if error:
        raise error
    assert user is not None
    return user
