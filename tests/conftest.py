"""Integration fixtures: a throwaway `saq_test` database migrated to head.

Needs MIGRATION_DATABASE_URL (owner role), e.g. `docker compose up -d db`. The dev database
itself is never touched. Runtime-role sessions use `SET ROLE saq_app`, so row-level security
applies exactly as in production.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.models import AppUser, Membership, Project
from apps.api.db.session import make_engine, make_session_factory
from apps.api.settings import get_settings

TEST_DB = "saq_test"


def _admin_url() -> str:
    url = os.environ.get("MIGRATION_DATABASE_URL") or get_settings().migration_database_url
    if not url:
        pytest.skip("MIGRATION_DATABASE_URL not set (start Postgres: docker compose up -d db)")
    return url


@pytest.fixture(scope="session")
def test_url() -> str:
    admin = make_url(_admin_url())
    engine = create_engine(admin, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {TEST_DB}"))
    engine.dispose()
    return admin.set(database=TEST_DB).render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def alembic_cfg(test_url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", test_url.replace("%", "%%"))
    command.upgrade(cfg, "head")
    return cfg


@pytest.fixture(scope="session")
def owner_engine(alembic_cfg: Config, test_url: str) -> Iterator[Engine]:
    engine = make_engine(test_url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def app_engine(alembic_cfg: Config, test_url: str) -> Iterator[Engine]:
    """Connections that act as the runtime role (no DDL, RLS enforced)."""
    engine = create_engine(test_url)

    @event.listens_for(engine, "connect")
    def _as_app(dbapi_conn, _record):  # type: ignore[no-untyped-def]
        with dbapi_conn.cursor() as cur:
            cur.execute("SET ROLE saq_app")
        dbapi_conn.commit()

    yield engine
    engine.dispose()


@pytest.fixture
def owner(owner_engine: Engine) -> sessionmaker[Session]:
    return make_session_factory(owner_engine)


@pytest.fixture
def app(app_engine: Engine) -> sessionmaker[Session]:
    return make_session_factory(app_engine)


@dataclass(frozen=True)
class Tenant:
    user_id: uuid.UUID
    project_id: uuid.UUID


@pytest.fixture
def make_tenant(owner: sessionmaker[Session]):  # type: ignore[no-untyped-def]
    """Create a user + project + owner membership, bypassing RLS like an admin bootstrap."""

    def _make(name: str = "Shop") -> Tenant:
        with owner.begin() as s:
            user = AppUser(email=f"{uuid.uuid4().hex}@example.com", password_hash="x")
            s.add(user)
            s.flush()
            project = Project(name=name, owner_id=user.id)
            s.add(project)
            s.flush()
            s.add(Membership(project_id=project.id, user_id=user.id, role="owner"))
            return Tenant(user.id, project.id)

    return _make
