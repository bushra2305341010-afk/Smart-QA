"""FastAPI dependencies: who is calling (`current_principal`) and may they (`require`).

Credentials, in order: `Authorization: Bearer saq_pat_...` (API token), `Authorization: Bearer
<jwt>` (access token), then the `saq_access` cookie. Cookie requests that change state must send
`X-CSRF-Token` equal to the `saq_csrf` cookie (double submit, docs/10 §3).
"""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Literal

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from apps.api import ids
from apps.api.auth import service
from apps.api.auth.permissions import Permission, allowed
from apps.api.auth.tokens import PAT_PREFIX, InvalidTokenError, JwtSigner
from apps.api.db.models import Membership
from apps.api.db.session import project_session, set_scope
from apps.api.errors import ApiError, forbidden, not_found, unauthenticated

ACCESS_COOKIE = "saq_access"
REFRESH_COOKIE = "saq_refresh"
CSRF_COOKIE = "saq_csrf"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def get_factory(request: Request) -> sessionmaker[Session]:
    factory: sessionmaker[Session] | None = request.app.state.session_factory
    if factory is None:
        raise ApiError(503, "UNAVAILABLE", "Database is not configured")
    return factory


def get_signer(request: Request) -> JwtSigner:
    signer: JwtSigner = request.app.state.jwt_signer
    return signer


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    via: Literal["cookie", "bearer", "token"]
    session_id: uuid.UUID | None = None
    scopes: frozenset[str] = field(default_factory=lambda: frozenset({"read", "write"}))


def check_csrf(request: Request) -> None:
    cookie = request.cookies.get(CSRF_COOKIE, "")
    header = request.headers.get(CSRF_HEADER, "")
    if not cookie or not hmac.compare_digest(cookie, header):
        raise ApiError(403, "CSRF_FAILED", "Missing or wrong X-CSRF-Token header")


def _from_jwt(
    token: str, via: Literal["cookie", "bearer"], factory: sessionmaker[Session], signer: JwtSigner
) -> Principal:
    try:
        claims = signer.verify(token)
    except InvalidTokenError:
        raise unauthenticated("Session expired") from None
    with factory.begin() as s:
        if service.active_session(s, claims.session_id) is None:
            raise unauthenticated("Session revoked")
    return Principal(claims.user_id, via, claims.session_id)


def current_principal(
    request: Request,
    factory: sessionmaker[Session] = Depends(get_factory),
    signer: JwtSigner = Depends(get_signer),
) -> Principal:
    unsafe = request.method not in SAFE_METHODS
    header = request.headers.get("authorization")
    if header:
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise unauthenticated("Use: Authorization: Bearer <token>")
        if not token.startswith(PAT_PREFIX):
            return _from_jwt(token, "bearer", factory, signer)
        with factory.begin() as s:
            row = service.resolve_api_token(s, token)
            if row is None:
                raise unauthenticated("API token is invalid, expired or revoked")
            principal = Principal(row.user_id, "token", None, frozenset(row.scopes))
        if unsafe and "write" not in principal.scopes:
            raise forbidden("token.write")
        return principal
    cookie = request.cookies.get(ACCESS_COOKIE)
    if not cookie:
        raise unauthenticated()
    if unsafe:
        check_csrf(request)
    return _from_jwt(cookie, "cookie", factory, signer)


@dataclass(frozen=True)
class ProjectContext:
    """A caller who passed `require()` for one project."""

    principal: Principal
    project_id: uuid.UUID
    role: str
    factory: sessionmaker[Session]

    @contextmanager
    def session(self) -> Iterator[Session]:
        """One RLS-scoped transaction for this project."""
        with project_session(self.factory, self.project_id, self.principal.user_id) as s:
            yield s

    def can(self, permission: Permission) -> bool:
        return allowed(self.role, permission)


def require(permission: Permission) -> Callable[..., ProjectContext]:
    """Dependency: caller is a member of `{project_id}` and their role grants `permission`.

    Not a member (or no such project) → 404, so project IDs cannot be probed. Member without the
    permission → 403.
    """

    def dependency(
        project_id: str,
        principal: Principal = Depends(current_principal),
        factory: sessionmaker[Session] = Depends(get_factory),
    ) -> ProjectContext:
        pid = ids.decode("prj", project_id, "Project")
        with factory.begin() as s:
            set_scope(s, pid, principal.user_id)
            role = s.scalar(
                select(Membership.role).where(
                    Membership.project_id == pid, Membership.user_id == principal.user_id
                )
            )
        if role is None:
            raise not_found("Project")
        if not allowed(role, permission):
            raise forbidden(permission)
        return ProjectContext(principal, pid, role, factory)

    return dependency
