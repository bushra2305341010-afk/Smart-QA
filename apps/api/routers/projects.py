"""Projects, members, sources, environments, identities and audit (docs/06-api.md §3).

Every project route goes through `require(<permission>)`, which also scopes the DB transaction
to the project for row-level security. State changes append an audit event and, where workers
must react, an outbox event in the same transaction.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr, Field, HttpUrl
from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from apps.api import ids
from apps.api.auth.deps import (
    Principal,
    ProjectContext,
    current_principal,
    get_factory,
    require,
)
from apps.api.auth.permissions import Role
from apps.api.db import audit, outbox
from apps.api.db.models import (
    AppUser,
    AuditEvent,
    Chunk,
    Environment,
    Identity,
    Membership,
    PipelineState,
    Project,
    Source,
)
from apps.api.db.session import project_session, set_user_scope
from apps.api.errors import conflict, forbidden, not_found

router = APIRouter(tags=["projects"])

Limit = Annotated[int, Query(ge=1, le=200)]


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None


def _paged(
    s: Session, stmt: Select[Any], limit: int, cursor: str | None
) -> tuple[list[Any], str | None]:
    offset = int(cursor) if cursor and cursor.isdigit() else 0
    rows = list(s.scalars(stmt.offset(offset).limit(limit + 1)))
    more = len(rows) > limit
    return rows[:limit], str(offset + limit) if more else None


def _actor(principal: Principal) -> str:
    return ids.encode("usr", principal.user_id)


# ---------- projects ----------


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ProjectOut(BaseModel):
    id: str
    name: str
    role: str
    retention_days: int
    stage: str | None = None
    created_at: datetime


def _project_out(p: Project, role: str, stage: str | None = None) -> ProjectOut:
    return ProjectOut(
        id=ids.encode("prj", p.id),
        name=p.name,
        role=role,
        retention_days=p.retention_days,
        stage=stage,
        created_at=p.created_at,
    )


@router.post("/projects", status_code=201)
def create_project(
    body: ProjectIn,
    principal: Principal = Depends(current_principal),
    factory: sessionmaker[Session] = Depends(get_factory),
) -> ProjectOut:
    """Any signed-in user may create a project and becomes its Owner."""
    pid = uuid.uuid4()
    with project_session(factory, pid, principal.user_id) as s:
        project = Project(id=pid, name=body.name, owner_id=principal.user_id)
        s.add(project)
        s.flush()
        s.add(Membership(project_id=pid, user_id=principal.user_id, role="owner"))
        audit.record(
            s,
            project_id=pid,
            actor=_actor(principal),
            action="project.created",
            entity=ids.encode("prj", pid),
            payload={"name": body.name},
        )
        outbox.enqueue(s, project_id=pid, topic="project.created", payload={"project_id": str(pid)})
        s.refresh(project)
        return _project_out(project, "owner")


@router.get("/projects")
def list_projects(
    principal: Principal = Depends(current_principal),
    factory: sessionmaker[Session] = Depends(get_factory),
) -> list[ProjectOut]:
    with factory.begin() as s:
        set_user_scope(s, principal.user_id)
        rows = s.execute(
            select(Project, Membership.role)
            .join(Membership, Membership.project_id == Project.id)
            .where(Membership.user_id == principal.user_id)
            .order_by(Project.created_at)
        ).all()
        return [_project_out(p, role) for p, role in rows]


@router.get("/projects/{project_id}")
def get_project(ctx: ProjectContext = Depends(require("project.view"))) -> ProjectOut:
    with ctx.session() as s:
        project = s.get_one(Project, ctx.project_id)
        stage = s.scalar(
            select(PipelineState.stage).order_by(PipelineState.entered_at.desc()).limit(1)
        )
        return _project_out(project, ctx.role, stage)


# ---------- members ----------


class MemberIn(BaseModel):
    email: EmailStr
    role: Role


class MemberOut(BaseModel):
    user_id: str
    email: str
    role: str


@router.post("/projects/{project_id}/members", status_code=201)
def add_member(
    body: MemberIn, ctx: ProjectContext = Depends(require("members.manage"))
) -> MemberOut:
    try:
        with ctx.session() as s:
            user = s.scalar(select(AppUser).where(AppUser.email == body.email))
            if user is None:
                raise not_found("User")
            s.add(Membership(project_id=ctx.project_id, user_id=user.id, role=body.role))
            s.flush()
            audit.record(
                s,
                project_id=ctx.project_id,
                actor=_actor(ctx.principal),
                action="member.added",
                entity=ids.encode("usr", user.id),
                payload={"role": body.role},
            )
            return MemberOut(user_id=ids.encode("usr", user.id), email=user.email, role=body.role)
    except IntegrityError:
        raise conflict("User is already a member of this project") from None


@router.get("/projects/{project_id}/members")
def list_members(ctx: ProjectContext = Depends(require("project.view"))) -> list[MemberOut]:
    with ctx.session() as s:
        rows = s.execute(
            select(AppUser.id, AppUser.email, Membership.role)
            .join(Membership, Membership.user_id == AppUser.id)
            .where(Membership.project_id == ctx.project_id)
            .order_by(AppUser.email)
        ).all()
    return [MemberOut(user_id=ids.encode("usr", u), email=e, role=r) for u, e, r in rows]


# ---------- sources ----------


class SourceIn(BaseModel):
    kind: Literal["pdf", "docx", "md", "openapi", "repo", "har"]
    uri: str = Field(min_length=1, max_length=2048)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SourceOut(BaseModel):
    id: str
    kind: str
    uri: str
    sha256: str
    status: str
    created_at: datetime


def _source_out(src: Source) -> SourceOut:
    return SourceOut(
        id=ids.encode("src", src.id),
        kind=src.kind,
        uri=src.uri,
        sha256=src.sha256,
        status=src.status,
        created_at=src.created_at,
    )


@router.post("/projects/{project_id}/sources", status_code=201)
def add_source(
    body: SourceIn, ctx: ProjectContext = Depends(require("sources.manage"))
) -> SourceOut:
    """Register a source. Upload and parsing happen in the ingest worker (M09)."""
    with ctx.session() as s:
        src = Source(project_id=ctx.project_id, kind=body.kind, uri=body.uri, sha256=body.sha256)
        s.add(src)
        s.flush()
        public = ids.encode("src", src.id)
        audit.record(
            s,
            project_id=ctx.project_id,
            actor=_actor(ctx.principal),
            action="source.added",
            entity=public,
            payload={"kind": body.kind, "sha256": body.sha256},
        )
        outbox.enqueue(
            s, project_id=ctx.project_id, topic="source.added", payload={"source_id": str(src.id)}
        )
        s.refresh(src)
        return _source_out(src)


@router.get("/projects/{project_id}/sources")
def list_sources(
    ctx: ProjectContext = Depends(require("project.view")),
    limit: Limit = 50,
    cursor: str | None = None,
) -> Page[SourceOut]:
    with ctx.session() as s:
        items, nxt = _paged(s, select(Source).order_by(Source.created_at, Source.id), limit, cursor)
        return Page(items=[_source_out(x) for x in items], next_cursor=nxt)


class ChunkOut(BaseModel):
    id: str
    text: str
    start_offset: int
    end_offset: int
    page: int | None
    line: int | None


@router.get("/projects/{project_id}/sources/{source_id}/chunks")
def list_chunks(
    source_id: str,
    ctx: ProjectContext = Depends(require("project.view")),
    limit: Limit = 50,
    cursor: str | None = None,
) -> Page[ChunkOut]:
    sid = ids.decode("src", source_id, "Source")
    with ctx.session() as s:
        if s.get(Source, sid) is None:
            raise not_found("Source")
        stmt = select(Chunk).where(Chunk.source_id == sid).order_by(Chunk.start_offset, Chunk.id)
        items, nxt = _paged(s, stmt, limit, cursor)
        out = [
            ChunkOut(
                id=ids.encode("chk", c.id),
                text=c.text,
                start_offset=c.start_offset,
                end_offset=c.end_offset,
                page=c.page,
                line=c.line,
            )
            for c in items
        ]
        return Page(items=out, next_cursor=nxt)


# ---------- environments & identities ----------


class EnvironmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["local", "staging", "public", "production"]
    base_url: HttpUrl
    allowed_hosts: list[str] = Field(default_factory=list, max_length=50)
    safe_actions: dict[str, Any] = Field(default_factory=dict)


class EnvironmentOut(BaseModel):
    id: str
    name: str
    kind: str
    base_url: str
    allowed_hosts: list[str]
    safe_actions: dict[str, Any]


def _env_out(e: Environment) -> EnvironmentOut:
    return EnvironmentOut(
        id=ids.encode("env", e.id),
        name=e.name,
        kind=e.kind,
        base_url=e.base_url,
        allowed_hosts=e.allowed_hosts,
        safe_actions=e.safe_actions,
    )


@router.post("/projects/{project_id}/environments", status_code=201)
def add_environment(
    body: EnvironmentIn, ctx: ProjectContext = Depends(require("environments.manage"))
) -> EnvironmentOut:
    """Production targets need the Owner-only `env.mark_production` permission (docs/10 §4)."""
    if body.kind == "production" and not ctx.can("env.mark_production"):
        raise forbidden("env.mark_production")
    base_url = str(body.base_url)
    host = urlparse(base_url).hostname or ""
    hosts = sorted({h.lower() for h in [*body.allowed_hosts, host] if h})
    with ctx.session() as s:
        env = Environment(
            project_id=ctx.project_id,
            name=body.name,
            kind=body.kind,
            base_url=base_url,
            allowed_hosts=hosts,
            safe_actions=body.safe_actions,
        )
        s.add(env)
        s.flush()
        audit.record(
            s,
            project_id=ctx.project_id,
            actor=_actor(ctx.principal),
            action="environment.added",
            entity=ids.encode("env", env.id),
            payload={"kind": body.kind, "base_url": base_url},
        )
        return _env_out(env)


@router.get("/projects/{project_id}/environments")
def list_environments(
    ctx: ProjectContext = Depends(require("project.view")),
) -> list[EnvironmentOut]:
    with ctx.session() as s:
        return [
            _env_out(e) for e in s.scalars(select(Environment).order_by(Environment.created_at))
        ]


class IdentityIn(BaseModel):
    env_id: str
    role_name: str = Field(min_length=1, max_length=100)
    secret_ref: str = Field(min_length=1, max_length=500, description="Vault reference, write-only")


class IdentityOut(BaseModel):
    id: str
    env_id: str
    role_name: str


@router.post("/projects/{project_id}/identities", status_code=201)
def add_identity(
    body: IdentityIn, ctx: ProjectContext = Depends(require("identities.manage"))
) -> IdentityOut:
    """The secret reference is stored but never returned by any endpoint."""
    env_id = ids.decode("env", body.env_id, "Environment")
    with ctx.session() as s:
        if s.get(Environment, env_id) is None:
            raise not_found("Environment")
        idn = Identity(
            project_id=ctx.project_id,
            env_id=env_id,
            role_name=body.role_name,
            secret_ref=body.secret_ref,
        )
        s.add(idn)
        s.flush()
        audit.record(
            s,
            project_id=ctx.project_id,
            actor=_actor(ctx.principal),
            action="identity.added",
            entity=ids.encode("idn", idn.id),
            payload={"role_name": body.role_name},
        )
        return IdentityOut(
            id=ids.encode("idn", idn.id), env_id=body.env_id, role_name=body.role_name
        )


# ---------- audit ----------


class AuditEventOut(BaseModel):
    seq: int
    actor: str
    action: str
    entity: str
    payload: dict[str, Any]
    hash: str
    created_at: datetime


class AuditOut(BaseModel):
    items: list[AuditEventOut]
    next_cursor: str | None
    verified: bool | None = None
    broken_at_seq: int | None = None


@router.get("/projects/{project_id}/audit")
def list_audit(
    ctx: ProjectContext = Depends(require("project.view")),
    verify: bool = False,
    limit: Limit = 50,
    cursor: str | None = None,
) -> AuditOut:
    with ctx.session() as s:
        items, nxt = _paged(s, select(AuditEvent).order_by(AuditEvent.seq), limit, cursor)
        out = AuditOut(
            items=[
                AuditEventOut(
                    seq=e.seq,
                    actor=e.actor,
                    action=e.action,
                    entity=e.entity,
                    payload=e.payload,
                    hash=e.hash,
                    created_at=e.created_at,
                )
                for e in items
            ],
            next_cursor=nxt,
        )
        if verify:
            check = audit.verify_chain(s, ctx.project_id)
            out.verified, out.broken_at_seq = check.ok, check.broken_at_seq
        return out
