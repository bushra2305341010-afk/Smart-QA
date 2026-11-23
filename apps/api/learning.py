"""L2 project knowledge from human decisions (docs/21 A4/A5, US-10).

Only human-confirmed decisions create lessons, written in the same transaction as the decision:

- Bug dismissed → lesson `expected_behaviour` + code-enforced rule `suppress_bug` (the same
  failure of the same case gets no new draft; the audit event cites the rule).
- Plan count edited → rule `count_hint`, shown to the planner, never applied automatically.
- Graph node rejected → lesson `not_a_fact`, given to the analyst next time.

Lessons never relax quote checks, the safe-action policy or the gates (A5), and every lesson can
be switched off (its rules go with it).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.db.models import Lesson, Node, ProjectRule
from packages.graph.model import norm_label

MAX_TEXT = 1000


def _clip(text: str) -> str:
    return text[:MAX_TEXT]


def fingerprint(text: str) -> str:
    """Normalised failure text, so the same failure matches across runs."""
    return norm_label(text)[:300]


def learn_bug_dismissal(
    s: Session,
    project_id: uuid.UUID,
    *,
    case_code: str,
    case_title: str,
    failure: str,
    reason: str,
    journey_node_id: uuid.UUID,
    feedback_id: uuid.UUID,
) -> Lesson:
    lesson = Lesson(
        project_id=project_id,
        kind="expected_behaviour",
        text=_clip(f"{case_code} ({case_title}): '{failure}' is expected. Reviewer: {reason}"),
        applies_to_node_id=journey_node_id,
        source_feedback_id=feedback_id,
    )
    s.add(lesson)
    s.add(
        ProjectRule(
            project_id=project_id,
            kind="suppress_bug",
            condition={"case_code": case_code, "failure": fingerprint(failure)},
            action={"skip_draft": True, "lesson": lesson.text},
            source_feedback_id=feedback_id,
        )
    )
    return lesson


def learn_count_edit(
    s: Session,
    project_id: uuid.UUID,
    *,
    journey: str,
    suggested: int,
    approved: int,
    feedback_id: uuid.UUID,
) -> None:
    if suggested == approved:
        return
    s.add(
        ProjectRule(
            project_id=project_id,
            kind="count_hint",
            condition={"journey": norm_label(journey)},
            action={"suggested": suggested, "approved": approved},
            source_feedback_id=feedback_id,
        )
    )


def learn_node_rejection(
    s: Session, project_id: uuid.UUID, node: Node, feedback_id: uuid.UUID
) -> Lesson:
    lesson = Lesson(
        project_id=project_id,
        kind="not_a_fact",
        text=_clip(f"Reviewers rejected this {node.type}: {node.label}"),
        applies_to_node_id=node.id,
        source_feedback_id=feedback_id,
    )
    s.add(lesson)
    return lesson


def suppression_for(s: Session, case_code: str, failure: str) -> ProjectRule | None:
    """The active rule that says this exact failure of this case is expected, if any."""
    rules = s.scalars(
        select(ProjectRule).where(ProjectRule.kind == "suppress_bug", ProjectRule.active.is_(True))
    )
    want = {"case_code": case_code, "failure": fingerprint(failure)}
    return next((r for r in rules if r.condition == want), None)


def count_hints(s: Session) -> dict[str, dict[str, int]]:
    """Latest active count decision per journey (normalised name)."""
    hints: dict[str, dict[str, int]] = {}
    for rule in s.scalars(
        select(ProjectRule)
        .where(ProjectRule.kind == "count_hint", ProjectRule.active.is_(True))
        .order_by(ProjectRule.created_at)
    ):
        hints[str(rule.condition["journey"])] = {
            "suggested": int(rule.action["suggested"]),
            "approved": int(rule.action["approved"]),
        }
    return hints


@dataclass(frozen=True)
class LessonText:
    kind: str
    text: str
    applies_to: str  # normalised label of the node it applies to


def active_lessons(s: Session, kinds: tuple[str, ...], limit: int = 50) -> list[LessonText]:
    rows = s.execute(
        select(Lesson.kind, Lesson.text, Node.label)
        .join(Node, Node.id == Lesson.applies_to_node_id)
        .where(Lesson.active.is_(True), Lesson.kind.in_(kinds))
        .order_by(Lesson.created_at.desc())
        .limit(limit)
    ).all()
    return [LessonText(kind, text, norm_label(label)) for kind, text, label in rows]
