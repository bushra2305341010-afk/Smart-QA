"""Hash-chained audit ledger (ADR-008) and transactional outbox (docs/12) on real Postgres."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db import audit, outbox
from apps.api.db.models import AuditEvent, Outbox, Source
from apps.api.db.session import project_session

pytestmark = pytest.mark.integration


def _write_three(app: sessionmaker[Session], project_id) -> list[AuditEvent]:  # type: ignore[no-untyped-def]
    with project_session(app, project_id) as s:
        return [
            audit.record(
                s,
                project_id=project_id,
                actor="user:1",
                action=f"gate{i}.approve",
                entity=f"plan:{i}",
                payload={"n": i, "note": "naïve ✓"},
            )
            for i in (1, 2, 3)
        ]


def test_chain_is_built_by_the_trigger(app: sessionmaker[Session], make_tenant) -> None:
    t = make_tenant()
    events = _write_three(app, t.project_id)
    assert [e.seq for e in events] == [1, 2, 3]
    assert events[0].prev_hash == audit.GENESIS_HASH
    assert events[1].prev_hash == events[0].hash
    assert events[2].prev_hash == events[1].hash
    with project_session(app, t.project_id) as s:
        assert audit.verify_chain(s, t.project_id) == audit.ChainCheck(True, 3)


def test_client_supplied_chain_fields_are_ignored(app: sessionmaker[Session], make_tenant) -> None:
    t = make_tenant()
    with project_session(app, t.project_id) as s:
        e = AuditEvent(
            project_id=t.project_id, actor="a", action="x", entity="y", seq=99, hash="forged"
        )
        s.add(e)
        s.flush()
        s.refresh(e)
        assert e.seq == 1
        assert e.hash != "forged"


def test_each_project_has_its_own_chain(app: sessionmaker[Session], make_tenant) -> None:
    a, b = make_tenant(), make_tenant()
    _write_three(app, a.project_id)
    with project_session(app, b.project_id) as s:
        e = audit.record(s, project_id=b.project_id, actor="a", action="x", entity="y")
        assert e.seq == 1


def test_runtime_role_cannot_update_or_delete(app: sessionmaker[Session], make_tenant) -> None:
    t = make_tenant()
    _write_three(app, t.project_id)
    for sql in ("UPDATE audit_event SET actor = 'evil'", "DELETE FROM audit_event"):
        with (
            pytest.raises(ProgrammingError, match="permission denied"),
            project_session(app, t.project_id) as s,
        ):
            s.execute(text(sql))


def test_even_the_owner_hits_the_append_only_trigger(
    owner: sessionmaker[Session], app: sessionmaker[Session], make_tenant
) -> None:
    t = make_tenant()
    _write_three(app, t.project_id)
    for sql in (
        "UPDATE audit_event SET actor = 'evil'",
        "DELETE FROM audit_event",
        "TRUNCATE audit_event",
    ):
        with pytest.raises(DBAPIError, match="append-only"), owner.begin() as s:
            s.execute(text(sql))


def _tamper(owner: sessionmaker[Session], sql: str, project_id) -> None:  # type: ignore[no-untyped-def]
    """Simulate a DBA bypassing triggers (session_replication_role=replica skips them)."""
    with owner.begin() as s:
        s.execute(text("SET LOCAL session_replication_role = replica"))
        s.execute(text(sql), {"p": project_id})


@pytest.mark.parametrize(
    ("sql", "seq", "reason"),
    [
        (
            "UPDATE audit_event SET payload = '{\"n\": 7}' WHERE project_id = :p AND seq = 2",
            2,
            "hash does not match",
        ),
        (
            "UPDATE audit_event SET prev_hash = repeat('f', 64) WHERE project_id = :p AND seq = 3",
            3,
            "prev_hash does not match",
        ),
        ("DELETE FROM audit_event WHERE project_id = :p AND seq = 2", 3, "gap"),
    ],
)
def test_verify_detects_tampering(
    owner: sessionmaker[Session],
    app: sessionmaker[Session],
    make_tenant,
    sql: str,
    seq: int,
    reason: str,
) -> None:
    t = make_tenant()
    _write_three(app, t.project_id)
    _tamper(owner, sql, t.project_id)
    with project_session(app, t.project_id) as s:
        check = audit.verify_chain(s, t.project_id)
    assert not check.ok
    assert check.broken_at_seq == seq
    assert reason in check.reason


def test_outbox_event_rolls_back_with_the_domain_change(
    app: sessionmaker[Session], make_tenant
) -> None:
    t = make_tenant()
    with pytest.raises(RuntimeError), project_session(app, t.project_id) as s:
        s.add(Source(project_id=t.project_id, kind="md", uri="x", sha256="0"))
        outbox.enqueue(s, project_id=t.project_id, topic="source.added", payload={})
        raise RuntimeError("crash before commit")
    with project_session(app, t.project_id) as s:
        assert s.scalars(select(Source)).all() == []
        assert s.scalars(select(Outbox)).all() == []


def test_outbox_claim_and_mark_published(app: sessionmaker[Session], make_tenant) -> None:
    t = make_tenant()
    with project_session(app, t.project_id) as s:
        first = outbox.enqueue(s, project_id=t.project_id, topic="run.started", payload={"n": 1})
        outbox.enqueue(s, project_id=t.project_id, topic="run.finished", payload={"n": 2})
    with project_session(app, t.project_id) as s:
        claimed = outbox.claim_unpublished(s, limit=1)
        assert [e.id for e in claimed] == [first.id]
        outbox.mark_published(s, [e.id for e in claimed])
        outbox.mark_published(s, [])
    with project_session(app, t.project_id) as s:
        assert [e.topic for e in outbox.claim_unpublished(s)] == ["run.finished"]
