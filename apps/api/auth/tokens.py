"""Access JWTs (EdDSA, 15 min) and opaque secrets: refresh tokens, API tokens, CSRF tokens.

Opaque secrets are random 256-bit values; only their SHA-256 is stored (docs/10 §3).
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ACCESS_TTL = timedelta(minutes=15)
MFA_TTL = timedelta(minutes=5)
REFRESH_TTL = timedelta(days=7)
PAT_PREFIX = "saq_pat_"
ISSUER = "smart-qa"
_ALG = "EdDSA"


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def new_api_token() -> str:
    return PAT_PREFIX + new_secret()


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    session_id: uuid.UUID


class InvalidTokenError(Exception):
    """Expired, tampered or otherwise unusable access token."""


class JwtSigner:
    """Signs and verifies access tokens with one Ed25519 key (`kid` allows rotation later)."""

    def __init__(self, private_key: Ed25519PrivateKey, kid: str = "k1") -> None:
        self._private = private_key
        self._public = private_key.public_key()
        self.kid = kid

    @classmethod
    def from_pem(cls, pem: str) -> JwtSigner:
        key = serialization.load_pem_private_key(pem.encode(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError("JWT_PRIVATE_KEY must be an Ed25519 private key (PEM)")
        return cls(key)

    @classmethod
    def ephemeral(cls) -> JwtSigner:
        """Dev/test only: a fresh key per process (tokens die on restart)."""
        return cls(Ed25519PrivateKey.generate(), kid="ephemeral")

    def issue(self, claims: AccessClaims, now: datetime | None = None) -> str:
        issued = now or datetime.now(UTC)
        payload = {
            "iss": ISSUER,
            "sub": str(claims.user_id),
            "sid": str(claims.session_id),
            "iat": issued,
            "exp": issued + ACCESS_TTL,
        }
        return jwt.encode(payload, self._private, algorithm=_ALG, headers={"kid": self.kid})

    def verify(self, token: str) -> AccessClaims:
        try:
            data = jwt.decode(
                token,
                self._public,
                algorithms=[_ALG],
                issuer=ISSUER,
                options={"require": ["exp", "iat", "sub", "sid", "iss"]},
            )
            return AccessClaims(uuid.UUID(data["sub"]), uuid.UUID(data["sid"]))
        except (jwt.PyJWTError, ValueError) as exc:
            raise InvalidTokenError(str(exc)) from exc

    def issue_mfa(self, user_id: uuid.UUID, now: datetime | None = None) -> str:
        """Short-lived proof that the password step passed; only good for /auth/login/mfa."""
        issued = now or datetime.now(UTC)
        payload = {
            "iss": ISSUER,
            "sub": str(user_id),
            "purpose": "mfa",
            "iat": issued,
            "exp": issued + MFA_TTL,
        }
        return jwt.encode(payload, self._private, algorithm=_ALG, headers={"kid": self.kid})

    def verify_mfa(self, token: str) -> uuid.UUID:
        try:
            data = jwt.decode(
                token,
                self._public,
                algorithms=[_ALG],
                issuer=ISSUER,
                options={"require": ["exp", "sub", "purpose"]},
            )
            if data["purpose"] != "mfa":
                raise InvalidTokenError("not an MFA token")
            return uuid.UUID(data["sub"])
        except (jwt.PyJWTError, ValueError) as exc:
            raise InvalidTokenError(str(exc)) from exc
