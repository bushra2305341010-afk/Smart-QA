"""Declarative base, shared columns and helpers for every table (docs/07-database.md §2).

Isolation rule: every table except `app_user` carries `project_id`, and every reference to another
project-scoped row is a *composite* foreign key `(ref_id, project_id) -> (id, project_id)`. Postgres
checks foreign keys without row-level security, so a plain `ref_id` FK would let a row in project B
point at a row in project A. The composite key makes that impossible in the schema itself.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    MetaData,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s",
    "pk": "pk_%(table_name)s",
}

JsonDict = dict[str, Any]


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    metadata = MetaData(naming_convention=NAMING)
    type_annotation_map: ClassVar[dict[Any, Any]] = {JsonDict: JSONB, uuid.UUID: UUID(as_uuid=True)}


def choice(name: str, *values: str) -> Enum:
    """A text column limited to `values` by a CHECK constraint (easy to expand, unlike PG enums)."""
    return Enum(*values, name=name, native_enum=False, create_constraint=True, length=32)


def scoped_fk(
    column: str, target: str, *, ondelete: str | None = "CASCADE"
) -> ForeignKeyConstraint:
    """Composite FK `(column, project_id) -> target(id, project_id)`: same-project refs only."""
    return ForeignKeyConstraint(
        [column, "project_id"],
        [f"{target}.id", f"{target}.project_id"],
        ondelete=ondelete,
    )


def hnsw_index(table: str) -> Index:
    """Approximate nearest-neighbour index on `embedding` (cosine) for retrieval."""
    return Index(
        f"ix_{table}_embedding_hnsw",
        "embedding",
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


class Timestamped:
    """`id`, `created_at`, `updated_at` for every table."""

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProjectScoped(Timestamped):
    """Adds `project_id` (row-level security key) and the `(id, project_id)` target for FKs."""

    @declared_attr
    def project_id(cls) -> Mapped[uuid.UUID]:  # noqa: N805 - SQLAlchemy declared_attr signature
        return mapped_column(ForeignKey("project.id", ondelete="CASCADE"), index=True)

    @declared_attr.directive
    def __table_args__(cls) -> tuple[Any, ...]:  # noqa: N805
        return (UniqueConstraint("id", "project_id"), *getattr(cls, "__extra_args__", ()))
