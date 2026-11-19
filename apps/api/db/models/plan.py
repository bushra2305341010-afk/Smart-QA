"""Coverage plan and test design tables (docs/07-database.md §2, Gate 2)."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.db.base import Base, JsonDict, ProjectScoped, choice, scoped_fk
from apps.api.db.models.graph import REVIEW_STATUS


class Plan(ProjectScoped, Base):
    __tablename__ = "plan"
    __extra_args__ = (scoped_fk("graph_version_id", "graph_version"),)

    graph_version_id: Mapped[uuid.UUID]
    status: Mapped[str] = mapped_column(
        choice("plan_status", "draft", "approved", "superseded"),
        default="draft",
        server_default="draft",
    )
    cost_estimate: Mapped[JsonDict] = mapped_column(default=dict, server_default="{}")
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))


class Segment(ProjectScoped, Base):
    __tablename__ = "segment"
    __extra_args__ = (scoped_fk("plan_id", "plan"), scoped_fk("journey_node_id", "node"))

    plan_id: Mapped[uuid.UUID]
    journey_node_id: Mapped[uuid.UUID]
    techniques: Mapped[JsonDict] = mapped_column(default=dict, server_default="{}")
    suggested_count: Mapped[int] = mapped_column(Integer)
    approved_count: Mapped[int | None] = mapped_column(Integer)
    risk_score: Mapped[float] = mapped_column(Float)
    priority: Mapped[str] = mapped_column(choice("segment_priority", "Must", "Should", "Could"))


class TestCase(ProjectScoped, Base):
    """A designed test. `citation` holds the quote that justifies `expected_text` (pillar P1)."""

    __tablename__ = "test_case"
    __test__ = False  # not a pytest class
    __extra_args__ = (
        scoped_fk("segment_id", "segment"),
        UniqueConstraint("project_id", "code"),
        Index("ix_test_case_segment_id_review_status", "segment_id", "review_status"),
    )

    segment_id: Mapped[uuid.UUID]
    code: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    technique: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(choice("test_case_priority", "Must", "Should", "Could"))
    preconditions: Mapped[JsonDict] = mapped_column(default=dict, server_default="{}")
    data: Mapped[JsonDict] = mapped_column(default=dict, server_default="{}")
    expected_text: Mapped[str] = mapped_column(Text)
    citation: Mapped[JsonDict | None]
    requirement_id: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(
        choice("test_case_review_status", *REVIEW_STATUS),
        default="pending",
        server_default="pending",
    )
    compiled_path: Mapped[str | None] = mapped_column(Text)


class Step(ProjectScoped, Base):
    __tablename__ = "step"
    __extra_args__ = (
        scoped_fk("test_case_id", "test_case"),
        scoped_fk("node_id", "node", ondelete=None),
        UniqueConstraint("test_case_id", "n"),
    )

    test_case_id: Mapped[uuid.UUID]
    n: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(Text)
    node_id: Mapped[uuid.UUID | None]
