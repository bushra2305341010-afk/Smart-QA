"""Product Understanding Graph tables (docs/07-database.md §2, Gate 1)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.db.base import Base, JsonDict, ProjectScoped, choice, scoped_fk

NODE_TYPES = (
    "Role",
    "Journey",
    "Step",
    "Screen",
    "Field",
    "Rule",
    "Endpoint",
    "Requirement",
    "Conflict",
    "Question",
)
REVIEW_STATUS = ("pending", "approved", "rejected", "edited")


class GraphVersion(ProjectScoped, Base):
    __tablename__ = "graph_version"
    __extra_args__ = (UniqueConstraint("project_id", "number"),)

    number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        choice("graph_status", "draft", "approved", "superseded"),
        default="draft",
        server_default="draft",
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Node(ProjectScoped, Base):
    __tablename__ = "node"
    __extra_args__ = (
        scoped_fk("graph_version_id", "graph_version"),
        Index("ix_node_graph_version_id_type", "graph_version_id", "type"),
    )

    graph_version_id: Mapped[uuid.UUID]
    type: Mapped[str] = mapped_column(choice("node_type", *NODE_TYPES))
    label: Mapped[str] = mapped_column(Text)
    attrs: Mapped[JsonDict] = mapped_column(default=dict, server_default="{}")
    review_status: Mapped[str] = mapped_column(
        choice("node_review_status", *REVIEW_STATUS), default="pending", server_default="pending"
    )


class Edge(ProjectScoped, Base):
    __tablename__ = "edge"
    __extra_args__ = (scoped_fk("from_node_id", "node"), scoped_fk("to_node_id", "node"))

    from_node_id: Mapped[uuid.UUID]
    to_node_id: Mapped[uuid.UUID]
    kind: Mapped[str] = mapped_column(Text)


class NodeCitation(ProjectScoped, Base):
    """Links a graph node to the exact source quote that supports it (pillar P1)."""

    __tablename__ = "node_citation"
    __extra_args__ = (scoped_fk("node_id", "node"), scoped_fk("chunk_id", "chunk"))

    node_id: Mapped[uuid.UUID]
    chunk_id: Mapped[uuid.UUID]
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)
    quote: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        choice("citation_status", "unchecked", "verified", "corrected", "failed"),
        default="unchecked",
        server_default="unchecked",
    )
