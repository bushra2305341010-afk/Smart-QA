"""Alembic environment. Migrations run as the owner role (`MIGRATION_DATABASE_URL`), never as
the runtime role `saq_app` (docs/07-database.md §4)."""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine, pool

from apps.api.db.base import Base
from apps.api.db.models import __all__ as _models  # noqa: F401 - registers all tables
from apps.api.settings import get_settings

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    url = config.get_main_option("sqlalchemy.url") or get_settings().migration_database_url
    if not url:
        raise RuntimeError("Set MIGRATION_DATABASE_URL (owner role) to run migrations")
    return url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
