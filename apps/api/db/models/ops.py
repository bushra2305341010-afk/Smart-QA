"""Audit, cost, pipeline state, learning and outbox tables (docs/07-database.md §2, docs/21)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.db.base import Base, JsonDict, ProjectScoped, choice, hnsw_index, scoped_fk
from apps.api.db.models.core import EMBEDDING_DIM


class AuditEvent(Base):
    """Append-only, hash-chained ledger (ADR-008).

    `seq`, `prev_hash`, `hash` and `created_at` are set by the `audit_event_chain` trigger; values
    sent by the client are ignored. `project_id` has no FK so the ledger outlives a deleted project
    (docs/07 §7). UPDATE, DELETE and TRUNCATE are revoked and also rejected by a trigger.
    """

    __tablename__ = "audit_event"
    __table_args__ = (UniqueConstraint("project_id", "seq"),)

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID]
    seq: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    actor: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    entity: Mapped[str] = mapped_column(Text)
    payload: Mapped[JsonDict] = mapped_column(default=dict, server_default="{}")
    prev_hash: Mapped[str] = mapped_column(Text, default="", server_default="")
    hash: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelCall(ProjectScoped, Base):
    __tablename__ = "model_call"
    __extra_args__ = (
        scoped_fk("run_id", "run", ondelete=None),
        Index("ix_model_call_project_id_created_at", "project_id", "created_at"),
    )

    stage: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[str] = mapped_column(Text, default="ok", server_default="ok")
    attempts: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    from_cache: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    redactions: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0, server_default="0")
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    run_id: Mapped[uuid.UUID | None]


class ReplayCache(ProjectScoped, Base):
    __tablename__ = "replay_cache"
    __extra_args__ = (UniqueConstraint("project_id", "key"),)

    key: Mapped[str] = mapped_column(Text)
    output: Mapped[JsonDict]
    approved: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class PipelineState(ProjectScoped, Base):
    """Current stage of the explicit workflow state machine (ADR-002, docs/03 §2)."""

    __tablename__ = "pipeline_state"
    __extra_args__ = (scoped_fk("run_id", "run"),)

    run_id: Mapped[uuid.UUID | None]
    stage: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    payload_ref: Mapped[str | None] = mapped_column(Text)


class RegressionMemory(ProjectScoped, Base):
    __tablename__ = "regression_memory"
    __extra_args__ = (scoped_fk("journey_node_id", "node"),)

    journey_node_id: Mapped[uuid.UUID]
    last_pass_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    flake_rate: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    bugs_found: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Feedback(ProjectScoped, Base):
    """A human decision. Human-confirmed labels are the only training data (docs/21)."""

    __tablename__ = "feedback"

    entity: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[uuid.UUID]
    decision: Mapped[str] = mapped_column(
        choice("feedback_decision", "confirm", "reject", "edit", "heal_approve")
    )
    before: Mapped[JsonDict | None]
    after: Mapped[JsonDict | None]
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))


class ProjectRule(ProjectScoped, Base):
    __tablename__ = "project_rule"
    __extra_args__ = (scoped_fk("source_feedback_id", "feedback", ondelete=None),)

    kind: Mapped[str] = mapped_column(Text)
    condition: Mapped[JsonDict]
    action: Mapped[JsonDict]
    source_feedback_id: Mapped[uuid.UUID | None]
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Lesson(ProjectScoped, Base):
    __tablename__ = "lesson"
    __extra_args__ = (
        scoped_fk("applies_to_node_id", "node", ondelete=None),
        scoped_fk("source_feedback_id", "feedback", ondelete=None),
        hnsw_index("lesson"),
    )

    kind: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    applies_to_node_id: Mapped[uuid.UUID | None]
    source_feedback_id: Mapped[uuid.UUID | None]
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class TrainedModel(ProjectScoped, Base):
    __tablename__ = "trained_model"
    __extra_args__ = (UniqueConstraint("project_id", "component", "version"),)

    component: Mapped[str] = mapped_column(
        choice("trained_component", "flake", "risk", "calibration", "locator", "dedup")
    )
    version: Mapped[int] = mapped_column(Integer)
    data_snapshot_hash: Mapped[str] = mapped_column(Text)
    metrics: Mapped[JsonDict] = mapped_column(default=dict, server_default="{}")
    status: Mapped[str] = mapped_column(
        choice("trained_status", "candidate", "active", "retired"),
        default="candidate",
        server_default="candidate",
    )
    artifact_key: Mapped[str] = mapped_column(Text)


class Outbox(ProjectScoped, Base):
    """Transactional outbox: written in the same transaction as the domain change (docs/12)."""

    __tablename__ = "outbox"
    __extra_args__ = (
        Index(
            "ix_outbox_unpublished",
            "created_at",
            postgresql_where=text("published_at IS NULL"),
        ),
    )

    topic: Mapped[str] = mapped_column(Text)
    payload: Mapped[JsonDict]
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
