"""Cost meter and budget caps (F34; docs/06-api.md "Admin & ops")."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import cast

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from apps.api import ids
from apps.api.auth.deps import ProjectContext, require
from apps.api.db import audit
from apps.api.db.model_store import budget_cap, month_spend
from apps.api.db.models import ModelCall, Project
from apps.api.settings import get_settings

router = APIRouter(tags=["costs"])


class MonthOut(BaseModel):
    spent_usd: Decimal
    cap_usd: Decimal
    remaining_usd: Decimal


class StageCostOut(BaseModel):
    stage: str
    calls: int
    cache_hits: int
    cost_usd: Decimal


class RunCostOut(BaseModel):
    run_id: str
    cost_usd: Decimal


class PeriodCostOut(BaseModel):
    month: str
    cost_usd: Decimal


class CostsOut(BaseModel):
    month: MonthOut
    by_stage: list[StageCostOut]
    by_run: list[RunCostOut]
    by_month: list[PeriodCostOut]


class BudgetIn(BaseModel):
    monthly_usd: Decimal = Field(ge=0, le=1_000_000, decimal_places=2)


@router.get("/projects/{project_id}/costs")
def get_costs(ctx: ProjectContext = Depends(require("project.view"))) -> CostsOut:
    default = get_settings().saq_budget_monthly_usd
    with ctx.session() as s:
        cap = budget_cap(s.scalar(select(Project.settings)), default)
        spent = month_spend(s)
        stages = s.execute(
            select(
                ModelCall.stage,
                func.count(),
                func.count().filter(ModelCall.from_cache.is_(True)),
                func.sum(ModelCall.cost_usd),
            )
            .group_by(ModelCall.stage)
            .order_by(func.sum(ModelCall.cost_usd).desc(), ModelCall.stage)
        ).all()
        runs = s.execute(
            select(ModelCall.run_id, func.sum(ModelCall.cost_usd))
            .where(ModelCall.run_id.is_not(None))
            .group_by(ModelCall.run_id)
            .order_by(func.sum(ModelCall.cost_usd).desc())
            .limit(50)
        ).all()
        month = func.to_char(func.date_trunc("month", ModelCall.created_at), "YYYY-MM")
        months = s.execute(
            select(month, func.sum(ModelCall.cost_usd))
            .group_by(month)
            .order_by(month.desc())
            .limit(12)
        ).all()
    return CostsOut(
        month=MonthOut(spent_usd=spent, cap_usd=cap, remaining_usd=max(cap - spent, Decimal(0))),
        by_stage=[
            StageCostOut(stage=a, calls=b, cache_hits=c, cost_usd=d) for a, b, c, d in stages
        ],
        by_run=[
            RunCostOut(run_id=ids.encode("run", cast(uuid.UUID, r)), cost_usd=c) for r, c in runs
        ],
        by_month=[PeriodCostOut(month=m, cost_usd=c) for m, c in months],
    )


@router.put("/projects/{project_id}/budget")
def set_budget(body: BudgetIn, ctx: ProjectContext = Depends(require("budget.manage"))) -> MonthOut:
    with ctx.session() as s:
        project = s.get_one(Project, ctx.project_id)
        old = project.settings.get("budget_monthly_usd")
        project.settings = {**project.settings, "budget_monthly_usd": float(body.monthly_usd)}
        audit.record(
            s,
            project_id=ctx.project_id,
            actor=ids.encode("usr", ctx.principal.user_id),
            action="budget.changed",
            entity=ids.encode("prj", ctx.project_id),
            payload={"from": old, "to": float(body.monthly_usd)},
        )
        spent = month_spend(s)
    cap = body.monthly_usd
    return MonthOut(spent_usd=spent, cap_usd=cap, remaining_usd=max(cap - spent, Decimal(0)))
