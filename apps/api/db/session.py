"""Engines and project-scoped sessions (docs/07-database.md §4).

Row-level security reads `app.project_id` (and `app.user_id` for "my projects" lookups). They are
set with `set_config(..., is_local => true)`, so they last exactly one transaction and can never
leak to the next request that reuses a pooled connection.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


def make_engine(url: str) -> Engine:
    """Create a pooled engine. `pool_pre_ping` drops dead connections after a DB restart."""
    return create_engine(url, pool_pre_ping=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def set_scope(session: Session, project_id: uuid.UUID, user_id: uuid.UUID | None = None) -> None:
    """Bind the current transaction to one project (and optionally one user) for RLS."""
    session.execute(
        text("SELECT set_config('app.project_id', :p, true), set_config('app.user_id', :u, true)"),
        {"p": str(project_id), "u": str(user_id) if user_id else ""},
    )


def set_user_scope(session: Session, user_id: uuid.UUID) -> None:
    """No project: only the caller's own memberships and projects are visible."""
    session.execute(
        text("SELECT set_config('app.project_id', '', true), set_config('app.user_id', :u, true)"),
        {"u": str(user_id)},
    )


@contextmanager
def project_session(
    factory: sessionmaker[Session], project_id: uuid.UUID, user_id: uuid.UUID | None = None
) -> Iterator[Session]:
    """One transaction scoped to `project_id`: commits on success, rolls back on error."""
    with factory.begin() as session:
        set_scope(session, project_id, user_id)
        yield session
