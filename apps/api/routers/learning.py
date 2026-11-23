"""Lessons and learned rules (docs/21 A4/A5): see what the system learned, switch it off."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, update

from apps.api import ids
from apps.api.auth.deps import ProjectContext, require
from apps.api.db import audit
from apps.api.db.models import Lesson, ProjectRule
from apps.api.errors import not_found

router = APIRouter(tags=["learning"])


class LessonOut(BaseModel):
    id: str
    kind: str
    text: str
    active: bool
    created_at: datetime


class RuleOut(BaseModel):
    id: str
    kind: str
    condition: dict[str, Any]
    action: dict[str, Any]
    active: bool


class KnowledgeOut(BaseModel):
    lessons: list[LessonOut]
    rules: list[RuleOut]


@router.get("/projects/{project_id}/lessons")
def list_knowledge(ctx: ProjectContext = Depends(require("project.view"))) -> KnowledgeOut:
    with ctx.session() as s:
        lessons = s.scalars(select(Lesson).order_by(Lesson.created_at.desc())).all()
        rules = s.scalars(select(ProjectRule).order_by(ProjectRule.created_at.desc())).all()
        return KnowledgeOut(
            lessons=[
                LessonOut(
                    id=ids.encode("les", x.id),
                    kind=x.kind,
                    text=x.text,
                    active=x.active,
                    created_at=x.created_at,
                )
                for x in lessons
            ],
            rules=[
                RuleOut(
                    id=ids.encode("rul", r.id),
                    kind=r.kind,
                    condition=r.condition,
                    action=r.action,
                    active=r.active,
                )
                for r in rules
            ],
        )


@router.post("/projects/{project_id}/lessons/{lesson_id}/deactivate")
def deactivate_lesson(
    lesson_id: str, ctx: ProjectContext = Depends(require("pipeline.manage"))
) -> LessonOut:
    """Undo a lesson; rules learned from the same decision are switched off with it."""
    with ctx.session() as s:
        lesson = s.get(Lesson, ids.decode("les", lesson_id, "Lesson"))
        if lesson is None:
            raise not_found("Lesson")
        lesson.active = False
        s.execute(  # rules learned from the same human decision
            update(ProjectRule)
            .where(ProjectRule.source_feedback_id == lesson.source_feedback_id)
            .values(active=False)
        )
        audit.record(
            s,
            project_id=ctx.project_id,
            actor=ids.encode("usr", ctx.principal.user_id),
            action="lesson.deactivated",
            entity=lesson_id,
            payload={"kind": lesson.kind},
        )
        return LessonOut(
            id=lesson_id,
            kind=lesson.kind,
            text=lesson.text,
            active=False,
            created_at=lesson.created_at,
        )


@router.post("/projects/{project_id}/rules/{rule_id}/deactivate")
def deactivate_rule(
    rule_id: str, ctx: ProjectContext = Depends(require("pipeline.manage"))
) -> RuleOut:
    with ctx.session() as s:
        rule = s.get(ProjectRule, ids.decode("rul", rule_id, "Rule"))
        if rule is None:
            raise not_found("Rule")
        rule.active = False
        audit.record(
            s,
            project_id=ctx.project_id,
            actor=ids.encode("usr", ctx.principal.user_id),
            action="rule.deactivated",
            entity=rule_id,
            payload={"kind": rule.kind},
        )
        return RuleOut(
            id=rule_id, kind=rule.kind, condition=rule.condition, action=rule.action, active=False
        )
