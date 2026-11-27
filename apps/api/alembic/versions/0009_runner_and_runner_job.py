"""Runners and their job leases (M10, T-103); `result.details` for the Judge.

Both tables are project-scoped with the standard RLS isolation policy.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-25 15:32:51.693407
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = ("runner", "runner_job")


def upgrade() -> None:
    op.create_table(
        "runner",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("cert_sha256", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "registered",
                "online",
                "offline",
                "revoked",
                name="runner_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="registered",
            nullable=False,
        ),
        sa.Column("version", sa.Text(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("project_id", sa.UUID(), nullable=False),
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
            ["project_id"], ["project.id"], name=op.f("fk_runner_project_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runner")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_runner_id_project_id")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_runner_token_hash")),
    )
    op.create_index(op.f("ix_runner_project_id"), "runner", ["project_id"], unique=False)
    op.create_table(
        "runner_job",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("test_case_id", sa.UUID(), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "leased",
                "done",
                "lost",
                name="runner_job_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("runner_id", sa.UUID(), nullable=True),
        sa.Column("leased_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("leases", sa.Integer(), server_default="0", nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
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
            ["project_id"],
            ["project.id"],
            name=op.f("fk_runner_job_project_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "project_id"],
            ["run.id", "run.project_id"],
            name=op.f("fk_runner_job_run_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["runner_id", "project_id"],
            ["runner.id", "runner.project_id"],
            name=op.f("fk_runner_job_runner_id_project_id"),
        ),
        sa.ForeignKeyConstraint(
            ["test_case_id", "project_id"],
            ["test_case.id", "test_case.project_id"],
            name=op.f("fk_runner_job_test_case_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runner_job")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_runner_job_id_project_id")),
        sa.UniqueConstraint(
            "run_id",
            "test_case_id",
            "attempt",
            name=op.f("uq_runner_job_run_id_test_case_id_attempt"),
        ),
    )
    op.create_index(op.f("ix_runner_job_project_id"), "runner_job", ["project_id"], unique=False)
    op.create_index("ix_runner_job_run_id_status", "runner_job", ["run_id", "status"], unique=False)
    op.add_column(
        "result",
        sa.Column(
            "details", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
    )
    for table in NEW_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO saq_app")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY project_isolation ON {table}
            USING (project_id = app_current_project())
            WITH CHECK (project_id = app_current_project())
        """)


def downgrade() -> None:
    for table in NEW_TABLES:
        op.execute(f"DROP POLICY IF EXISTS project_isolation ON {table}")
    op.drop_column("result", "details")
    op.drop_index("ix_runner_job_run_id_status", table_name="runner_job")
    op.drop_index(op.f("ix_runner_job_project_id"), table_name="runner_job")
    op.drop_table("runner_job")
    op.drop_index(op.f("ix_runner_project_id"), table_name="runner")
    op.drop_table("runner")
