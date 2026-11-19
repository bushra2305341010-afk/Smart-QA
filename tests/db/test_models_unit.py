"""Schema invariants that need no database (docs/07-database.md §2, §4)."""

import uuid
from datetime import datetime, timedelta, timezone

from apps.api.db import models
from apps.api.db.audit import GENESIS_HASH, canonical, chain_hash
from apps.api.db.base import Base

GLOBAL_TABLES = {"app_user"}


def test_all_docs_tables_are_modelled():
    assert len(models.__all__) == len(Base.metadata.tables) == 30


def test_every_table_except_user_is_project_scoped():
    for name, table in Base.metadata.tables.items():
        if name in GLOBAL_TABLES:
            assert "project_id" not in table.c
        elif name == "project":
            assert table.c.id.primary_key
        else:
            assert "project_id" in table.c, name
            assert not table.c.project_id.nullable, name


def test_references_between_scoped_tables_are_composite():
    """A single-column FK to a project-scoped table would bypass isolation (FKs ignore RLS)."""
    for name, table in Base.metadata.tables.items():
        for fk in table.foreign_key_constraints:
            target = fk.referred_table.name
            if target in {"project", "app_user"}:
                assert len(fk.columns) == 1, (name, target)
            else:
                assert {c.name for c in fk.columns} >= {"project_id"}, (name, target)


def test_audit_event_has_no_fk_to_project():
    """The ledger must outlive a deleted project (docs/07 §7)."""
    assert not Base.metadata.tables["audit_event"].foreign_keys


def test_canonical_format_matches_trigger():
    pid = uuid.UUID("00000000-0000-0000-0000-000000000001")
    dhaka = timezone(timedelta(hours=6))
    text = canonical(
        prev_hash=GENESIS_HASH,
        project_id=pid,
        seq=1,
        actor="u1",
        action="gate1.approve",
        entity="graph_version:1",
        payload_text='{"a": 1}',
        created_at=datetime(2026, 11, 20, 15, 0, 0, 1234, tzinfo=dhaka),
    )
    assert text == (
        f"{GENESIS_HASH}|{pid}|1|u1|gate1.approve|graph_version:1|"
        '{"a": 1}|2026-11-20T09:00:00.001234Z'
    )
    assert len(chain_hash(text)) == 64
    assert chain_hash(text) != chain_hash(text + " ")
