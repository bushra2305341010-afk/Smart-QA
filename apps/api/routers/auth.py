"""Auth & users endpoints (docs/06-api.md §3 "Auth & users", docs/10 §2-3)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from apps.api import ids
from apps.api.auth import service
from apps.api.auth.deps import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    REFRESH_COOKIE,
    Principal,
    check_csrf,
    current_principal,
    get_factory,
    get_signer,
)
from apps.api.auth.tokens import ACCESS_TTL, REFRESH_TTL, AccessClaims, JwtSigner, new_secret
from apps.api.db.models import AppUser, AuthSession, Membership, Project
from apps.api.db.session import set_user_scope
from apps.api.errors import unauthenticated
from apps.api.ratelimit import enforce
from apps.api.settings import get_settings

router = APIRouter(tags=["auth"])
REFRESH_PATH = "/api/v1/auth"


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=4096)


class UserOut(BaseModel):
    id: str
    email: str


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str


class MembershipOut(BaseModel):
    project_id: str
    name: str
    role: str


class MeOut(UserOut):
    memberships: list[MembershipOut]


class TokenIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    scopes: list[Literal["read", "write"]] = Field(default=["read", "write"], min_length=1)
    expires_in_days: int | None = Field(default=90, ge=1, le=365)


class TokenOut(BaseModel):
    id: str
    name: str
    scopes: list[str]
    expires_at: datetime | None
    token: str = Field(description="Shown once. Store it now; only its hash is kept.")


def _user_out(user: AppUser) -> UserOut:
    return UserOut(id=ids.encode("usr", user.id), email=user.email)


def _set_cookies(response: Response, signer: JwtSigner, issued: service.IssuedSession) -> str:
    secure = get_settings().saq_env == "prod"
    access = signer.issue(AccessClaims(issued.user_id, issued.session_id))
    csrf = new_secret()
    common = {"secure": secure, "samesite": "lax"}
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=int(ACCESS_TTL.total_seconds()),
        httponly=True,
        path="/api",
        **common,  # type: ignore[arg-type]
    )
    response.set_cookie(
        REFRESH_COOKIE,
        issued.refresh_token,
        max_age=int(REFRESH_TTL.total_seconds()),
        httponly=True,
        path=REFRESH_PATH,
        **common,  # type: ignore[arg-type]
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=int(REFRESH_TTL.total_seconds()),
        httponly=False,
        path="/",
        **common,  # type: ignore[arg-type]
    )
    return csrf


def _clear_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/api")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
    response.delete_cookie(CSRF_COOKIE, path="/")


@router.post("/auth/register", status_code=201)
def register(body: Credentials, factory: sessionmaker[Session] = Depends(get_factory)) -> UserOut:
    return _user_out(service.register(factory, body.email, body.password))


@router.post("/auth/login")
def login(
    body: Credentials,
    request: Request,
    response: Response,
    factory: sessionmaker[Session] = Depends(get_factory),
    signer: JwtSigner = Depends(get_signer),
) -> SessionOut:
    ip = request.client.host if request.client else "unknown"
    enforce(request.app.state.rate_limiter, f"login:{ip}", get_settings().rate_login_per_ip_per_min)
    user = service.authenticate(factory, body.email, body.password)
    with factory.begin() as s:
        issued = service.start_session(
            s,
            user.id,
            user_agent=request.headers.get("user-agent"),
            ip=request.client.host if request.client else None,
        )
    csrf = _set_cookies(response, signer, issued)
    return SessionOut(user=_user_out(user), csrf_token=csrf)


@router.post("/auth/refresh")
def refresh(
    request: Request,
    response: Response,
    factory: sessionmaker[Session] = Depends(get_factory),
    signer: JwtSigner = Depends(get_signer),
) -> SessionOut:
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise unauthenticated()
    check_csrf(request)
    issued = service.rotate(factory, token)
    with factory() as s:
        user = s.get_one(AppUser, issued.user_id)
    csrf = _set_cookies(response, signer, issued)
    return SessionOut(user=_user_out(user), csrf_token=csrf)


@router.post("/auth/logout", status_code=204)
def logout(
    response: Response,
    principal: Principal = Depends(current_principal),
    factory: sessionmaker[Session] = Depends(get_factory),
) -> None:
    if principal.session_id is not None:
        with factory.begin() as s:
            row = s.get_one(AuthSession, principal.session_id)
            service.revoke_family(s, row.family_id)
    _clear_cookies(response)


@router.get("/me")
def me(
    principal: Principal = Depends(current_principal),
    factory: sessionmaker[Session] = Depends(get_factory),
) -> MeOut:
    with factory.begin() as s:
        set_user_scope(s, principal.user_id)
        user = s.get_one(AppUser, principal.user_id)
        rows = s.execute(
            select(Membership.project_id, Project.name, Membership.role)
            .join(Project, Project.id == Membership.project_id)
            .where(Membership.user_id == principal.user_id)
            .order_by(Project.name)
        ).all()
    return MeOut(
        **_user_out(user).model_dump(),
        memberships=[
            MembershipOut(project_id=ids.encode("prj", pid), name=name, role=role)
            for pid, name, role in rows
        ],
    )


@router.post("/tokens", status_code=201)
def create_token(
    body: TokenIn,
    principal: Principal = Depends(current_principal),
    factory: sessionmaker[Session] = Depends(get_factory),
) -> TokenOut:
    days = body.expires_in_days
    with factory.begin() as s:
        row, token = service.create_api_token(
            s,
            principal.user_id,
            body.name,
            list(body.scopes),
            timedelta(days=days) if days else None,
        )
    return TokenOut(
        id=ids.encode("tok", row.id),
        name=row.name,
        scopes=row.scopes,
        expires_at=row.expires_at,
        token=token,
    )
