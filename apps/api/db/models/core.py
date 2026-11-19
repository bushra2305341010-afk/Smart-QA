"""Accounts, projects, environments and sources (docs/07-database.md §2)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, LargeBinary, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.db.base import (
    Base,
    JsonDict,
    ProjectScoped,
    Timestamped,
    choice,
    hnsw_index,
    scoped_fk,
)

ROLES = ("owner", "qa_lead", "tester", "developer", "viewer")
EMBEDDING_DIM = 1024


class AppUser(Timestamped, Base):
    """A person who signs in. Global (no project), so no row-level security; named `app_user`
    because `user` is a reserved word in PostgreSQL."""

    __tablename__ = "app_user"

    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    totp_secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    status: Mapped[str] = mapped_column(
        choice("user_status", "active", "disabled"), default="active", server_default="active"
    )
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Project(Timestamped, Base):
    """The isolation unit: row-level security keys every other table on `project.id`."""

    __tablename__ = "project"

    name: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    model_policy: Mapped[JsonDict] = mapped_column(default=dict, server_default="{}")
    settings: Mapped[JsonDict] = mapped_column(default=dict, server_default="{}")
    retention_days: Mapped[int] = mapped_column(Integer, default=90, server_default="90")


class Membership(ProjectScoped, Base):
    __tablename__ = "membership"
    __extra_args__ = (UniqueConstraint("user_id", "project_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(choice("membership_role", *ROLES))


class Environment(ProjectScoped, Base):
    """A target app deployment. `production` is blocked by default (safe-action policy)."""

    __tablename__ = "environment"

    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(
        choice("environment_kind", "local", "staging", "public", "production")
    )
    base_url: Mapped[str] = mapped_column(Text)
    allowed_hosts: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    safe_actions: Mapped[JsonDict] = mapped_column(default=dict, server_default="{}")
    runner_id: Mapped[str | None] = mapped_column(Text)


class Identity(ProjectScoped, Base):
    """A test login. Only a vault reference is stored, never the secret value."""

    __tablename__ = "identity"
    __extra_args__ = (scoped_fk("env_id", "environment"),)

    env_id: Mapped[uuid.UUID]
    role_name: Mapped[str] = mapped_column(Text)
    secret_ref: Mapped[str] = mapped_column(Text)


class Source(ProjectScoped, Base):
    __tablename__ = "source"

    kind: Mapped[str] = mapped_column(
        choice("source_kind", "pdf", "docx", "md", "openapi", "repo", "har")
    )
    uri: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        choice("source_status", "pending", "parsing", "ready", "failed"),
        default="pending",
        server_default="pending",
    )
    filename: Mapped[str | None] = mapped_column(Text)
    size: Mapped[int | None] = mapped_column(Integer)
    text_key: Mapped[str | None] = mapped_column(Text)  # normalised text in object storage
    error: Mapped[str | None] = mapped_column(Text)


class Chunk(ProjectScoped, Base):
    """A slice of a source with exact offsets; quote verification reads `text` by offset."""

    __tablename__ = "chunk"
    __extra_args__ = (
        scoped_fk("source_id", "source"),
        Index("ix_chunk_source_id_start_offset", "source_id", "start_offset"),
        hnsw_index("chunk"),
    )

    source_id: Mapped[uuid.UUID]
    text: Mapped[str] = mapped_column(Text)
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer)
    line: Mapped[int | None] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
