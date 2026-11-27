"""Execution, verdict and bug tables (docs/07-database.md §2, Gate 4)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.db.base import Base, JsonDict, ProjectScoped, choice, scoped_fk

# Pillar P3: the six honest verdicts. A missing verified quote means unable_to_verify, never pass.
VERDICTS = ("pass", "fail", "flaky", "blocked", "test_error", "unable_to_verify")


class Run(ProjectScoped, Base):
    """`last_completed_case_id` is the resume point after a crash (NFR-4)."""

    __tablename__ = "run"
    __extra_args__ = (
        scoped_fk("env_id", "environment"),
        scoped_fk("plan_id", "plan"),
        scoped_fk("last_completed_case_id", "test_case", ondelete=None),
    )

    env_id: Mapped[uuid.UUID]
    plan_id: Mapped[uuid.UUID]
    status: Mapped[str] = mapped_column(
        choice("run_status", "queued", "running", "paused", "completed", "failed", "cancelled"),
        default="queued",
        server_default="queued",
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_completed_case_id: Mapped[uuid.UUID | None]
    totals: Mapped[JsonDict] = mapped_column(default=dict, server_default="{}")


class Result(ProjectScoped, Base):
    """One attempt of one case. The unique key makes result writes idempotent on retry."""

    __tablename__ = "result"
    __extra_args__ = (
        scoped_fk("run_id", "run"),
        scoped_fk("test_case_id", "test_case"),
        UniqueConstraint("run_id", "test_case_id", "attempt"),
    )

    run_id: Mapped[uuid.UUID]
    test_case_id: Mapped[uuid.UUID]
    attempt: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    status: Mapped[str] = mapped_column(
        choice("result_status", "passed", "failed", "error", "skipped", "timed_out")
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    browser: Mapped[str | None] = mapped_column(Text)
    # The runner's full `AttemptResult` (failure kind/message, blocked signal, noise counters);
    # the Judge reads it. Never holds secret values (placeholders only).
    details: Mapped[JsonDict] = mapped_column(default=dict, server_default="{}")


class Evidence(ProjectScoped, Base):
    """Metadata only; the blob lives in object storage under a content address (ADR-007)."""

    __tablename__ = "evidence"
    __extra_args__ = (scoped_fk("result_id", "result"), Index("ix_evidence_sha256", "sha256"))

    result_id: Mapped[uuid.UUID]
    step_n: Mapped[int | None] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(
        choice("evidence_kind", "screenshot", "trace", "video", "har", "console", "request")
    )
    sha256: Mapped[str] = mapped_column(Text)
    object_key: Mapped[str] = mapped_column(Text)
    size: Mapped[int] = mapped_column(BigInteger)


class Verdict(ProjectScoped, Base):
    __tablename__ = "verdict"
    __extra_args__ = (
        scoped_fk("result_id", "result"),
        UniqueConstraint("result_id"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
    )

    result_id: Mapped[uuid.UUID]
    verdict: Mapped[str] = mapped_column(choice("verdict_value", *VERDICTS))
    confidence: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text)
    rule: Mapped[str] = mapped_column(Text)  # deciding rule id (J0-J7); never empty


class Bug(ProjectScoped, Base):
    """A bug draft. Only Gate 4 moves it to `confirmed`; the tracker adapter sets `filed`."""

    __tablename__ = "bug"
    __extra_args__ = (
        scoped_fk("verdict_id", "verdict"),
        scoped_fk("dedup_of", "bug", ondelete=None),
        UniqueConstraint("verdict_id"),
    )

    verdict_id: Mapped[uuid.UUID]
    title: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(
        choice("bug_severity", "critical", "high", "medium", "low")
    )
    body_md: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        choice("bug_status", "draft", "confirmed", "dismissed", "filed"),
        default="draft",
        server_default="draft",
    )
    tracker: Mapped[str | None] = mapped_column(Text)
    tracker_ref: Mapped[str | None] = mapped_column(Text)
    dedup_of: Mapped[uuid.UUID | None]


class Runner(ProjectScoped, Base):
    """A registered runner (T-103). Only the token hash is stored; `cert_sha256` pins the client
    certificate the TLS proxy reports, when mTLS is used."""

    __tablename__ = "runner"
    __extra_args__ = (UniqueConstraint("token_hash"),)

    name: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text)
    cert_sha256: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        choice("runner_status", "registered", "online", "offline", "revoked"),
        default="registered",
        server_default="registered",
    )
    version: Mapped[str | None] = mapped_column(Text)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunnerJob(ProjectScoped, Base):
    """One attempt of one case waiting for / leased by a runner. A lease that expires (runner
    killed, network lost) makes the job claimable again; the result's unique key keeps the
    retry idempotent (NFR-4)."""

    __tablename__ = "runner_job"
    __extra_args__ = (
        scoped_fk("run_id", "run"),
        scoped_fk("test_case_id", "test_case"),
        scoped_fk("runner_id", "runner", ondelete=None),
        UniqueConstraint("run_id", "test_case_id", "attempt"),
        Index("ix_runner_job_run_id_status", "run_id", "status"),
    )

    run_id: Mapped[uuid.UUID]
    test_case_id: Mapped[uuid.UUID]
    attempt: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    status: Mapped[str] = mapped_column(
        choice("runner_job_status", "queued", "leased", "done", "lost"),
        default="queued",
        server_default="queued",
    )
    runner_id: Mapped[uuid.UUID | None]
    leased_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    leases: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
