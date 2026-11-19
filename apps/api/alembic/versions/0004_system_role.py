"""System role for cross-project background work: outbox relay and crash recovery (ADR-012).

`saq_system` inherits `saq_app` (same table rights) plus narrow per-role policies: it may claim
and mark any project's outbox rows and read pipeline_state / run to find stalled work. Every other
table still needs a project scope. No BYPASSRLS, so no superuser is needed to create it.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-20
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

POLICIES = (
    ("outbox", "ALL"),
    ("pipeline_state", "SELECT"),
    ("run", "SELECT"),
)


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'saq_system') THEN
                CREATE ROLE saq_system NOLOGIN;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'saq_worker') THEN
                GRANT saq_system TO saq_worker;
            END IF;
        END $$;
    """)
    op.execute("GRANT saq_app TO saq_system")
    for table, command in POLICIES:
        check = " WITH CHECK (true)" if command == "ALL" else ""
        op.execute(
            f"CREATE POLICY system_access ON {table} FOR {command} TO saq_system USING (true){check}"
        )


def downgrade() -> None:
    for table, _ in POLICIES:
        op.execute(f"DROP POLICY IF EXISTS system_access ON {table}")
    op.execute("REVOKE saq_app FROM saq_system")
