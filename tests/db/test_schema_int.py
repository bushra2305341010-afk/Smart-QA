"""Migrations, row-level security and cross-project references against real Postgres."""

import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.models import Chunk, Membership, Project, Source
from apps.api.db.session import project_session, set_scope

pytestmark = pytest.mark.integration


def _source(project_id: uuid.UUID, uri: str = "spec.md") -> Source:
    return Source(project_id=project_id, kind="md", uri=uri, sha256="0" * 64)


def test_migrations_downgrade_and_upgrade_cleanly(alembic_cfg: Config) -> None:
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")
    command.check(alembic_cfg)  # models and migrations agree (no drift)


def test_every_table_has_rls_forced_with_a_policy(owner: sessionmaker[Session]) -> None:
    with owner() as s:
        rows = s.execute(
            text(
                "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,"
                " (SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid) AS policies"
                " FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
                " WHERE n.nspname = 'public' AND c.relkind = 'r'"
            )
        ).all()
    found = {r.relname: r for r in rows}
    for name in Base.metadata.tables:
        if name == "app_user":
            continue
        row = found[name]
        assert row.relrowsecurity and row.relforcerowsecurity and row.policies == 1, name


def test_projects_cannot_see_each_other(app: sessionmaker[Session], make_tenant) -> None:
    a, b = make_tenant("A"), make_tenant("B")
    with project_session(app, a.project_id) as s:
        s.add(_source(a.project_id, "a.md"))
    with project_session(app, b.project_id) as s:
        s.add(_source(b.project_id, "b.md"))
    with project_session(app, a.project_id) as s:
        assert [x.uri for x in s.scalars(select(Source))] == ["a.md"]
        assert s.scalars(select(Project.name)).all() == ["A"]


def test_no_scope_sees_nothing(app: sessionmaker[Session], make_tenant) -> None:
    t = make_tenant()
    with project_session(app, t.project_id) as s:
        s.add(_source(t.project_id))
    with app.begin() as s:
        assert s.scalars(select(Source)).all() == []
        assert s.scalars(select(Project)).all() == []


def test_scope_ends_with_the_transaction(app: sessionmaker[Session], make_tenant) -> None:
    t = make_tenant()
    with project_session(app, t.project_id) as s:
        s.add(_source(t.project_id))
    with app() as s:  # same pooled connection, new transaction, no scope
        assert s.scalars(select(Source)).all() == []


def test_writing_into_another_project_is_rejected(app: sessionmaker[Session], make_tenant) -> None:
    a, b = make_tenant(), make_tenant()
    with (
        pytest.raises(ProgrammingError, match="row-level security"),
        project_session(app, a.project_id) as s,
    ):
        s.add(_source(b.project_id))


def test_reference_to_another_projects_row_is_rejected(
    app: sessionmaker[Session], make_tenant
) -> None:
    """FK checks ignore RLS; the composite (id, project_id) key still blocks the link."""
    a, b = make_tenant(), make_tenant()
    with project_session(app, a.project_id) as s:
        src = _source(a.project_id)
        s.add(src)
    with (
        pytest.raises(IntegrityError, match="fk_chunk_source_id_project_id"),
        project_session(app, b.project_id) as s,
    ):
        s.add(
            Chunk(
                project_id=b.project_id,
                source_id=src.id,
                text="x",
                start_offset=0,
                end_offset=1,
            )
        )


def test_user_scope_lists_only_my_projects(app: sessionmaker[Session], make_tenant) -> None:
    mine, other = make_tenant("Mine"), make_tenant("Other")
    with app.begin() as s:
        s.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(mine.user_id)})
        assert s.scalars(select(Project.name)).all() == ["Mine"]
        assert s.scalars(select(Membership.project_id)).all() == [mine.project_id]
    assert other.project_id != mine.project_id


def test_set_scope_without_user(app: sessionmaker[Session], make_tenant) -> None:
    t = make_tenant()
    with app.begin() as s:
        set_scope(s, t.project_id)
        assert s.execute(text("SELECT app_current_user()")).scalar() is None
        assert s.execute(text("SELECT app_current_project()")).scalar() == t.project_id


def test_runtime_role_cannot_run_ddl(app: sessionmaker[Session]) -> None:
    with pytest.raises(ProgrammingError, match="permission denied"), app.begin() as s:
        s.execute(text("CREATE TABLE evil (id int)"))


def test_check_constraints_reject_unknown_values(app: sessionmaker[Session], make_tenant) -> None:
    t = make_tenant()
    with (
        pytest.raises(DBAPIError, match="ck_source_source_kind"),
        project_session(app, t.project_id) as s,
    ):
        s.add(Source(project_id=t.project_id, kind="exe", uri="x", sha256="0"))
