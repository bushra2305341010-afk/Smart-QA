"""Auth: sign-in sessions, personal API tokens, login lockout columns (M08b, docs/10 §3).

Both tables are global like app_user (no project, no RLS); only token hashes are stored.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-20 01:21:39.110010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_token",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], name=op.f("fk_api_token_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_token")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_api_token_token_hash")),
    )
    op.create_index(op.f("ix_api_token_user_id"), "api_token", ["user_id"], unique=False)
    op.create_table(
        "auth_session",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("family_id", sa.UUID(), nullable=False),
        sa.Column("refresh_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], name=op.f("fk_auth_session_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_session")),
        sa.UniqueConstraint("refresh_hash", name=op.f("uq_auth_session_refresh_hash")),
    )
    op.create_index(op.f("ix_auth_session_family_id"), "auth_session", ["family_id"], unique=False)
    op.create_index(op.f("ix_auth_session_user_id"), "auth_session", ["user_id"], unique=False)
    op.add_column(
        "app_user", sa.Column("failed_logins", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("app_user", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON auth_session, api_token TO saq_app")


def downgrade() -> None:
    op.execute("REVOKE ALL ON auth_session, api_token FROM saq_app")
    op.drop_column("app_user", "locked_until")
    op.drop_column("app_user", "failed_logins")
    op.drop_index(op.f("ix_auth_session_user_id"), table_name="auth_session")
    op.drop_index(op.f("ix_auth_session_family_id"), table_name="auth_session")
    op.drop_table("auth_session")
    op.drop_index(op.f("ix_api_token_user_id"), table_name="api_token")
    op.drop_table("api_token")
