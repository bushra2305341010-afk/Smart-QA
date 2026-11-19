"""Transactional outbox (docs/12-reliability.md): enqueue with the domain change, relay later.

The relay (M08c) runs `claim_unpublished` + publish + `mark_published` in its own transaction;
`FOR UPDATE SKIP LOCKED` lets several relays run without double-publishing.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from apps.api.db.models import Outbox


def enqueue(
    session: Session, *, project_id: uuid.UUID, topic: str, payload: dict[str, Any]
) -> Outbox:
    """Add an event to the caller's transaction. It is only visible if that transaction commits.

    `created_at` is the wall clock, not the transaction start, so several events written in one
    transaction keep their order when relayed.
    """
    event = Outbox(
        project_id=project_id, topic=topic, payload=payload, created_at=datetime.now(UTC)
    )
    session.add(event)
    session.flush()
    return event


def claim_unpublished(session: Session, limit: int = 100) -> Sequence[Outbox]:
    """Oldest unpublished events, row-locked so a parallel relay skips them."""
    stmt = (
        select(Outbox)
        .where(Outbox.published_at.is_(None))
        .order_by(Outbox.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return session.scalars(stmt).all()


def mark_published(session: Session, ids: Sequence[uuid.UUID]) -> None:
    if ids:
        session.execute(update(Outbox).where(Outbox.id.in_(ids)).values(published_at=func.now()))
