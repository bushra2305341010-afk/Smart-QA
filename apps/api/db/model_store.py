"""Postgres-backed parts of the model gateway (T-603): replay cache, call recorder, budget.

`packages/model_gateway` defines the interfaces (`ReplayCache`, `Recorder`, `Budget`) and stays
free of database code; these classes implement them per project, under row-level security.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.models import ModelCall, Project, ReplayCache
from apps.api.db.session import project_session
from packages.model_gateway.cost import Budget
from packages.model_gateway.types import ModelCallRecord


class PostgresReplayCache:
    """`replay_cache` rows for one project.

    The first stored output for a key wins (`ON CONFLICT DO NOTHING`), so replays are
    deterministic. With `approved_only=True` only outputs a human approved are served: regression
    runs then make zero model calls for approved work and fresh calls for anything new.
    """

    def __init__(
        self, factory: sessionmaker[Session], project_id: uuid.UUID, *, approved_only: bool = False
    ) -> None:
        self._factory = factory
        self._project_id = project_id
        self._approved_only = approved_only

    def get(self, key: str) -> dict[str, Any] | None:
        stmt = select(ReplayCache.output).where(ReplayCache.key == key)
        if self._approved_only:
            stmt = stmt.where(ReplayCache.approved.is_(True))
        with project_session(self._factory, self._project_id) as s:
            return s.scalar(stmt)

    def put(self, key: str, value: dict[str, Any]) -> None:
        stmt = (
            insert(ReplayCache)
            .values(project_id=self._project_id, key=key, output=value)
            .on_conflict_do_nothing(index_elements=["project_id", "key"])
        )
        with project_session(self._factory, self._project_id) as s:
            s.execute(stmt)

    def approve(self, keys: list[str]) -> int:
        """Mark outputs as human-approved (called when the artifact they produced is approved)."""
        if not keys:
            return 0
        with project_session(self._factory, self._project_id) as s:
            result = s.execute(
                update(ReplayCache).where(ReplayCache.key.in_(keys)).values(approved=True)
            )
            return int(result.rowcount)  # type: ignore[attr-defined]


class PostgresRecorder:
    """A gateway `Recorder` that writes one `model_call` row per call (cost reports, budgets)."""

    def __init__(
        self,
        factory: sessionmaker[Session],
        project_id: uuid.UUID,
        run_id: uuid.UUID | None = None,
    ) -> None:
        self._factory = factory
        self._project_id = project_id
        self._run_id = run_id

    def __call__(self, record: ModelCallRecord) -> None:
        row = ModelCall(
            project_id=self._project_id,
            run_id=self._run_id,
            stage=record.stage,
            model=record.model,
            prompt_version=record.prompt_version,
            status=record.status,
            attempts=record.attempts,
            input_tokens=record.usage.input_tokens,
            output_tokens=record.usage.output_tokens,
            cache_read_tokens=record.usage.cache_read_input_tokens,
            cache_write_tokens=record.usage.cache_creation_input_tokens,
            cost_usd=Decimal(str(round(record.cost_usd, 6))),
            latency_ms=record.latency_ms,
            from_cache=record.from_cache,
            redactions=record.redactions,
        )
        with project_session(self._factory, self._project_id) as s:
            s.add(row)


def month_spend(s: Session) -> Decimal:
    """Model spend of the scoped project in the current calendar month (UTC, DB clock)."""
    spent = s.scalar(
        select(func.coalesce(func.sum(ModelCall.cost_usd), 0)).where(
            ModelCall.created_at >= func.date_trunc("month", func.now())
        )
    )
    return Decimal(spent or 0)


def budget_cap(settings: dict[str, Any] | None, default_usd: float) -> Decimal:
    value = (settings or {}).get("budget_monthly_usd", default_usd)
    return Decimal(str(value))


def project_budget(
    factory: sessionmaker[Session], project_id: uuid.UUID, default_usd: float
) -> Budget:
    """A gateway `Budget` preloaded with this month's spend, so the cap holds across processes."""
    with project_session(factory, project_id) as s:
        settings = s.scalar(select(Project.settings).where(Project.id == project_id))
        spent = month_spend(s)
    return Budget(cap_usd=float(budget_cap(settings, default_usd)), spent_usd=float(spent))
