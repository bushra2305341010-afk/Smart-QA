"""Hash-chained audit ledger: write and verify (ADR-008, docs/07-database.md §4).

The chain is computed by the `audit_event_chain` trigger in Postgres. `verify_chain` recomputes it
independently in Python, so tampering with any stored field (or deleting a row) is detected.

    hash = sha256(prev_hash | project_id | seq | actor | action | entity | payload | created_at)

`payload` is the stored `jsonb` rendered as text by Postgres (stable key order) and `created_at`
is UTC with microseconds, e.g. `2026-11-20T09:15:02.123456Z`.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.db.models import AuditEvent

GENESIS_HASH = "0" * 64


def canonical(
    *,
    prev_hash: str,
    project_id: uuid.UUID,
    seq: int,
    actor: str,
    action: str,
    entity: str,
    payload_text: str,
    created_at: datetime,
) -> str:
    """The exact string the trigger hashes. Keep in sync with the migration's SQL."""
    stamp = created_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    parts = [prev_hash, str(project_id), str(seq), actor, action, entity, payload_text, stamp]
    return "|".join(parts)


def chain_hash(canonical_text: str) -> str:
    return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()


def record(
    session: Session,
    *,
    project_id: uuid.UUID,
    actor: str,
    action: str,
    entity: str,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    """Append one event in the caller's transaction and return it with seq and hash filled in."""
    event = AuditEvent(
        project_id=project_id, actor=actor, action=action, entity=entity, payload=payload or {}
    )
    session.add(event)
    session.flush()
    session.refresh(event)
    return event


@dataclass(frozen=True)
class ChainCheck:
    ok: bool
    checked: int
    broken_at_seq: int | None = None
    reason: str = ""


_ROWS = text(
    "SELECT seq, actor, action, entity, payload::text AS payload_text, prev_hash, hash, created_at"
    " FROM audit_event WHERE project_id = :p ORDER BY seq"
)


def verify_chain(session: Session, project_id: uuid.UUID) -> ChainCheck:
    """Walk the project's ledger from seq 1 and recompute every link."""
    prev = GENESIS_HASH
    checked = 0
    for row in session.execute(_ROWS, {"p": project_id}).mappings():
        expected_seq = checked + 1
        if row["seq"] != expected_seq:
            return ChainCheck(False, checked, row["seq"], f"gap: expected seq {expected_seq}")
        if row["prev_hash"] != prev:
            return ChainCheck(False, checked, row["seq"], "prev_hash does not match")
        recomputed = chain_hash(
            canonical(
                prev_hash=prev,
                project_id=project_id,
                seq=row["seq"],
                actor=row["actor"],
                action=row["action"],
                entity=row["entity"],
                payload_text=row["payload_text"],
                created_at=row["created_at"],
            )
        )
        if recomputed != row["hash"]:
            return ChainCheck(False, checked, row["seq"], "hash does not match row content")
        prev = row["hash"]
        checked += 1
    return ChainCheck(True, checked)
