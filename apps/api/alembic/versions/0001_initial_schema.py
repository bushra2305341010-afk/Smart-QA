"""Initial schema: all tables from docs/07-database.md §2 (security objects are in 0002).

Revision ID: 0001
Revises:
Create Date: 2026-11-20 00:11:36.883598
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.create_table(
        "app_user",
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("totp_secret_enc", sa.LargeBinary(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "disabled",
                name="user_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="active",
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_user")),
        sa.UniqueConstraint("email", name=op.f("uq_app_user_email")),
    )
    op.create_table(
        "audit_event",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("seq", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity", sa.Text(), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("prev_hash", sa.Text(), server_default="", nullable=False),
        sa.Column("hash", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_event")),
        sa.UniqueConstraint("project_id", "seq", name=op.f("uq_audit_event_project_id_seq")),
    )
    op.create_table(
        "project",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column(
            "model_policy",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "settings", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("retention_days", sa.Integer(), server_default="90", nullable=False),
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
        sa.ForeignKeyConstraint(["owner_id"], ["app_user.id"], name=op.f("fk_project_owner_id")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project")),
    )
    op.create_table(
        "environment",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "local",
                "staging",
                "public",
                "production",
                name="environment_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column(
            "allowed_hosts", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "safe_actions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("runner_id", sa.Text(), nullable=True),
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
            name=op.f("fk_environment_project_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_environment")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_environment_id_project_id")),
    )
    op.create_index(op.f("ix_environment_project_id"), "environment", ["project_id"], unique=False)
    op.create_table(
        "feedback",
        sa.Column("entity", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column(
            "decision",
            sa.Enum(
                "confirm",
                "reject",
                "edit",
                "heal_approve",
                name="feedback_decision",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("actor_id", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["actor_id"], ["app_user.id"], name=op.f("fk_feedback_actor_id")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_feedback_project_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feedback")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_feedback_id_project_id")),
    )
    op.create_index(op.f("ix_feedback_project_id"), "feedback", ["project_id"], unique=False)
    op.create_table(
        "graph_version",
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "approved",
                "superseded",
                name="graph_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
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
            ["approved_by"], ["app_user.id"], name=op.f("fk_graph_version_approved_by")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            name=op.f("fk_graph_version_project_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_graph_version")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_graph_version_id_project_id")),
        sa.UniqueConstraint(
            "project_id", "number", name=op.f("uq_graph_version_project_id_number")
        ),
    )
    op.create_index(
        op.f("ix_graph_version_project_id"), "graph_version", ["project_id"], unique=False
    )
    op.create_table(
        "membership",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "owner",
                "qa_lead",
                "tester",
                "developer",
                "viewer",
                name="membership_role",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
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
            name=op.f("fk_membership_project_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], name=op.f("fk_membership_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_membership")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_membership_id_project_id")),
        sa.UniqueConstraint("user_id", "project_id", name=op.f("uq_membership_user_id_project_id")),
    )
    op.create_index(op.f("ix_membership_project_id"), "membership", ["project_id"], unique=False)
    op.create_table(
        "outbox",
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
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
            ["project_id"], ["project.id"], name=op.f("fk_outbox_project_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_outbox_id_project_id")),
    )
    op.create_index(op.f("ix_outbox_project_id"), "outbox", ["project_id"], unique=False)
    op.create_index(
        "ix_outbox_unpublished",
        "outbox",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("published_at IS NULL"),
    )
    op.create_table(
        "replay_cache",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("approved", sa.Boolean(), server_default="false", nullable=False),
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
            name=op.f("fk_replay_cache_project_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_replay_cache")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_replay_cache_id_project_id")),
        sa.UniqueConstraint("project_id", "key", name=op.f("uq_replay_cache_project_id_key")),
    )
    op.create_index(
        op.f("ix_replay_cache_project_id"), "replay_cache", ["project_id"], unique=False
    )
    op.create_table(
        "source",
        sa.Column(
            "kind",
            sa.Enum(
                "pdf",
                "docx",
                "md",
                "openapi",
                "repo",
                "har",
                name="source_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "parsing",
                "ready",
                "failed",
                name="source_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="pending",
            nullable=False,
        ),
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
            ["project_id"], ["project.id"], name=op.f("fk_source_project_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_source_id_project_id")),
    )
    op.create_index(op.f("ix_source_project_id"), "source", ["project_id"], unique=False)
    op.create_table(
        "trained_model",
        sa.Column(
            "component",
            sa.Enum(
                "flake",
                "risk",
                "calibration",
                "locator",
                "dedup",
                name="trained_component",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("data_snapshot_hash", sa.Text(), nullable=False),
        sa.Column(
            "metrics", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "status",
            sa.Enum(
                "candidate",
                "active",
                "retired",
                name="trained_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="candidate",
            nullable=False,
        ),
        sa.Column("artifact_key", sa.Text(), nullable=False),
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
            name=op.f("fk_trained_model_project_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trained_model")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_trained_model_id_project_id")),
        sa.UniqueConstraint(
            "project_id",
            "component",
            "version",
            name=op.f("uq_trained_model_project_id_component_version"),
        ),
    )
    op.create_index(
        op.f("ix_trained_model_project_id"), "trained_model", ["project_id"], unique=False
    )
    op.create_table(
        "chunk",
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("line", sa.Integer(), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=True),
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
            ["project_id"], ["project.id"], name=op.f("fk_chunk_project_id"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_id", "project_id"],
            ["source.id", "source.project_id"],
            name=op.f("fk_chunk_source_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chunk")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_chunk_id_project_id")),
    )
    op.create_index(op.f("ix_chunk_project_id"), "chunk", ["project_id"], unique=False)
    op.create_index(
        "ix_chunk_source_id_start_offset", "chunk", ["source_id", "start_offset"], unique=False
    )
    op.create_table(
        "identity",
        sa.Column("env_id", sa.UUID(), nullable=False),
        sa.Column("role_name", sa.Text(), nullable=False),
        sa.Column("secret_ref", sa.Text(), nullable=False),
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
            ["env_id", "project_id"],
            ["environment.id", "environment.project_id"],
            name=op.f("fk_identity_env_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_identity_project_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_identity")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_identity_id_project_id")),
    )
    op.create_index(op.f("ix_identity_project_id"), "identity", ["project_id"], unique=False)
    op.create_table(
        "node",
        sa.Column("graph_version_id", sa.UUID(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "Role",
                "Journey",
                "Step",
                "Screen",
                "Field",
                "Rule",
                "Endpoint",
                "Requirement",
                "Conflict",
                "Question",
                name="node_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column(
            "attrs", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "review_status",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                "edited",
                name="node_review_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="pending",
            nullable=False,
        ),
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
            ["graph_version_id", "project_id"],
            ["graph_version.id", "graph_version.project_id"],
            name=op.f("fk_node_graph_version_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_node_project_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_node")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_node_id_project_id")),
    )
    op.create_index(
        "ix_node_graph_version_id_type", "node", ["graph_version_id", "type"], unique=False
    )
    op.create_index(op.f("ix_node_project_id"), "node", ["project_id"], unique=False)
    op.create_table(
        "plan",
        sa.Column("graph_version_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "approved",
                "superseded",
                name="plan_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "cost_estimate",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("approved_by", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["approved_by"], ["app_user.id"], name=op.f("fk_plan_approved_by")),
        sa.ForeignKeyConstraint(
            ["graph_version_id", "project_id"],
            ["graph_version.id", "graph_version.project_id"],
            name=op.f("fk_plan_graph_version_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_plan_project_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_plan_id_project_id")),
    )
    op.create_index(op.f("ix_plan_project_id"), "plan", ["project_id"], unique=False)
    op.create_table(
        "project_rule",
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("condition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("action", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_feedback_id", sa.UUID(), nullable=True),
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
            name=op.f("fk_project_rule_project_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_feedback_id", "project_id"],
            ["feedback.id", "feedback.project_id"],
            name=op.f("fk_project_rule_source_feedback_id_project_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_rule")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_project_rule_id_project_id")),
    )
    op.create_index(
        op.f("ix_project_rule_project_id"), "project_rule", ["project_id"], unique=False
    )
    op.create_table(
        "edge",
        sa.Column("from_node_id", sa.UUID(), nullable=False),
        sa.Column("to_node_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
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
            ["from_node_id", "project_id"],
            ["node.id", "node.project_id"],
            name=op.f("fk_edge_from_node_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_edge_project_id"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["to_node_id", "project_id"],
            ["node.id", "node.project_id"],
            name=op.f("fk_edge_to_node_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_edge")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_edge_id_project_id")),
    )
    op.create_index(op.f("ix_edge_project_id"), "edge", ["project_id"], unique=False)
    op.create_table(
        "lesson",
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("applies_to_node_id", sa.UUID(), nullable=True),
        sa.Column("source_feedback_id", sa.UUID(), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
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
            ["applies_to_node_id", "project_id"],
            ["node.id", "node.project_id"],
            name=op.f("fk_lesson_applies_to_node_id_project_id"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_lesson_project_id"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_feedback_id", "project_id"],
            ["feedback.id", "feedback.project_id"],
            name=op.f("fk_lesson_source_feedback_id_project_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lesson")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_lesson_id_project_id")),
    )
    op.create_index(op.f("ix_lesson_project_id"), "lesson", ["project_id"], unique=False)
    op.create_table(
        "node_citation",
        sa.Column("node_id", sa.UUID(), nullable=False),
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "unchecked",
                "verified",
                "corrected",
                "failed",
                name="citation_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="unchecked",
            nullable=False,
        ),
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
            ["chunk_id", "project_id"],
            ["chunk.id", "chunk.project_id"],
            name=op.f("fk_node_citation_chunk_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["node_id", "project_id"],
            ["node.id", "node.project_id"],
            name=op.f("fk_node_citation_node_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            name=op.f("fk_node_citation_project_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_node_citation")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_node_citation_id_project_id")),
    )
    op.create_index(
        op.f("ix_node_citation_project_id"), "node_citation", ["project_id"], unique=False
    )
    op.create_table(
        "regression_memory",
        sa.Column("journey_node_id", sa.UUID(), nullable=False),
        sa.Column("last_pass_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("flake_rate", sa.Float(), server_default="0", nullable=False),
        sa.Column("bugs_found", sa.Integer(), server_default="0", nullable=False),
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
            ["journey_node_id", "project_id"],
            ["node.id", "node.project_id"],
            name=op.f("fk_regression_memory_journey_node_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            name=op.f("fk_regression_memory_project_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_regression_memory")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_regression_memory_id_project_id")),
    )
    op.create_index(
        op.f("ix_regression_memory_project_id"), "regression_memory", ["project_id"], unique=False
    )
    op.create_table(
        "segment",
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("journey_node_id", sa.UUID(), nullable=False),
        sa.Column(
            "techniques",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("suggested_count", sa.Integer(), nullable=False),
        sa.Column("approved_count", sa.Integer(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column(
            "priority",
            sa.Enum(
                "Must",
                "Should",
                "Could",
                name="segment_priority",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
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
            ["journey_node_id", "project_id"],
            ["node.id", "node.project_id"],
            name=op.f("fk_segment_journey_node_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id", "project_id"],
            ["plan.id", "plan.project_id"],
            name=op.f("fk_segment_plan_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_segment_project_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_segment")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_segment_id_project_id")),
    )
    op.create_index(op.f("ix_segment_project_id"), "segment", ["project_id"], unique=False)
    op.create_table(
        "test_case",
        sa.Column("segment_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("technique", sa.Text(), nullable=False),
        sa.Column(
            "priority",
            sa.Enum(
                "Must",
                "Should",
                "Could",
                name="test_case_priority",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "preconditions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "data", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("expected_text", sa.Text(), nullable=False),
        sa.Column("citation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("requirement_id", sa.Text(), nullable=True),
        sa.Column(
            "review_status",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                "edited",
                name="test_case_review_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("compiled_path", sa.Text(), nullable=True),
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
            ["project_id"], ["project.id"], name=op.f("fk_test_case_project_id"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["segment_id", "project_id"],
            ["segment.id", "segment.project_id"],
            name=op.f("fk_test_case_segment_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_test_case")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_test_case_id_project_id")),
        sa.UniqueConstraint("project_id", "code", name=op.f("uq_test_case_project_id_code")),
    )
    op.create_index(op.f("ix_test_case_project_id"), "test_case", ["project_id"], unique=False)
    op.create_index(
        "ix_test_case_segment_id_review_status",
        "test_case",
        ["segment_id", "review_status"],
        unique=False,
    )
    op.create_table(
        "run",
        sa.Column("env_id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "paused",
                "completed",
                "failed",
                "cancelled",
                name="run_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_completed_case_id", sa.UUID(), nullable=True),
        sa.Column(
            "totals", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
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
            ["env_id", "project_id"],
            ["environment.id", "environment.project_id"],
            name=op.f("fk_run_env_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["last_completed_case_id", "project_id"],
            ["test_case.id", "test_case.project_id"],
            name=op.f("fk_run_last_completed_case_id_project_id"),
        ),
        sa.ForeignKeyConstraint(
            ["plan_id", "project_id"],
            ["plan.id", "plan.project_id"],
            name=op.f("fk_run_plan_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_run_project_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_run")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_run_id_project_id")),
    )
    op.create_index(op.f("ix_run_project_id"), "run", ["project_id"], unique=False)
    op.create_table(
        "step",
        sa.Column("test_case_id", sa.UUID(), nullable=False),
        sa.Column("n", sa.Integer(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("node_id", sa.UUID(), nullable=True),
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
            ["node_id", "project_id"],
            ["node.id", "node.project_id"],
            name=op.f("fk_step_node_id_project_id"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_step_project_id"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["test_case_id", "project_id"],
            ["test_case.id", "test_case.project_id"],
            name=op.f("fk_step_test_case_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_step")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_step_id_project_id")),
        sa.UniqueConstraint("test_case_id", "n", name=op.f("uq_step_test_case_id_n")),
    )
    op.create_index(op.f("ix_step_project_id"), "step", ["project_id"], unique=False)
    op.create_table(
        "model_call",
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cache_read_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "cost_usd", sa.Numeric(precision=12, scale=6), server_default="0", nullable=False
        ),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("run_id", sa.UUID(), nullable=True),
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
            name=op.f("fk_model_call_project_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "project_id"],
            ["run.id", "run.project_id"],
            name=op.f("fk_model_call_run_id_project_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_call")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_model_call_id_project_id")),
    )
    op.create_index(op.f("ix_model_call_project_id"), "model_call", ["project_id"], unique=False)
    op.create_index(
        "ix_model_call_project_id_created_at",
        "model_call",
        ["project_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "pipeline_state",
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "entered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("payload_ref", sa.Text(), nullable=True),
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
            name=op.f("fk_pipeline_state_project_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "project_id"],
            ["run.id", "run.project_id"],
            name=op.f("fk_pipeline_state_run_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pipeline_state")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_pipeline_state_id_project_id")),
    )
    op.create_index(
        op.f("ix_pipeline_state_project_id"), "pipeline_state", ["project_id"], unique=False
    )
    op.create_table(
        "result",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("test_case_id", sa.UUID(), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "passed",
                "failed",
                "error",
                "skipped",
                "timed_out",
                name="result_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("browser", sa.Text(), nullable=True),
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
            ["project_id"], ["project.id"], name=op.f("fk_result_project_id"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "project_id"],
            ["run.id", "run.project_id"],
            name=op.f("fk_result_run_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["test_case_id", "project_id"],
            ["test_case.id", "test_case.project_id"],
            name=op.f("fk_result_test_case_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_result")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_result_id_project_id")),
        sa.UniqueConstraint(
            "run_id", "test_case_id", "attempt", name=op.f("uq_result_run_id_test_case_id_attempt")
        ),
    )
    op.create_index(op.f("ix_result_project_id"), "result", ["project_id"], unique=False)
    op.create_table(
        "evidence",
        sa.Column("result_id", sa.UUID(), nullable=False),
        sa.Column("step_n", sa.Integer(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "screenshot",
                "trace",
                "video",
                "har",
                "console",
                "request",
                name="evidence_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
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
            ["project_id"], ["project.id"], name=op.f("fk_evidence_project_id"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["result_id", "project_id"],
            ["result.id", "result.project_id"],
            name=op.f("fk_evidence_result_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_evidence_id_project_id")),
    )
    op.create_index(op.f("ix_evidence_project_id"), "evidence", ["project_id"], unique=False)
    op.create_index("ix_evidence_sha256", "evidence", ["sha256"], unique=False)
    op.create_table(
        "verdict",
        sa.Column("result_id", sa.UUID(), nullable=False),
        sa.Column(
            "verdict",
            sa.Enum(
                "pass",
                "fail",
                "flaky",
                "blocked",
                "test_error",
                "unable_to_verify",
                name="verdict_value",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("rule", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name=op.f("ck_verdict_confidence_range")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_verdict_project_id"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["result_id", "project_id"],
            ["result.id", "result.project_id"],
            name=op.f("fk_verdict_result_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_verdict")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_verdict_id_project_id")),
        sa.UniqueConstraint("result_id", name=op.f("uq_verdict_result_id")),
    )
    op.create_index(op.f("ix_verdict_project_id"), "verdict", ["project_id"], unique=False)
    op.create_table(
        "bug",
        sa.Column("verdict_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "severity",
            sa.Enum(
                "critical",
                "high",
                "medium",
                "low",
                name="bug_severity",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "confirmed",
                "dismissed",
                "filed",
                name="bug_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("tracker", sa.Text(), nullable=True),
        sa.Column("tracker_ref", sa.Text(), nullable=True),
        sa.Column("dedup_of", sa.UUID(), nullable=True),
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
            ["dedup_of", "project_id"],
            ["bug.id", "bug.project_id"],
            name=op.f("fk_bug_dedup_of_project_id"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["project.id"], name=op.f("fk_bug_project_id"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["verdict_id", "project_id"],
            ["verdict.id", "verdict.project_id"],
            name=op.f("fk_bug_verdict_id_project_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bug")),
        sa.UniqueConstraint("id", "project_id", name=op.f("uq_bug_id_project_id")),
        sa.UniqueConstraint("verdict_id", name=op.f("uq_bug_verdict_id")),
    )
    op.create_index(op.f("ix_bug_project_id"), "bug", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_bug_project_id"), table_name="bug")
    op.drop_table("bug")
    op.drop_index(op.f("ix_verdict_project_id"), table_name="verdict")
    op.drop_table("verdict")
    op.drop_index("ix_evidence_sha256", table_name="evidence")
    op.drop_index(op.f("ix_evidence_project_id"), table_name="evidence")
    op.drop_table("evidence")
    op.drop_index(op.f("ix_result_project_id"), table_name="result")
    op.drop_table("result")
    op.drop_index(op.f("ix_pipeline_state_project_id"), table_name="pipeline_state")
    op.drop_table("pipeline_state")
    op.drop_index("ix_model_call_project_id_created_at", table_name="model_call")
    op.drop_index(op.f("ix_model_call_project_id"), table_name="model_call")
    op.drop_table("model_call")
    op.drop_index(op.f("ix_step_project_id"), table_name="step")
    op.drop_table("step")
    op.drop_index(op.f("ix_run_project_id"), table_name="run")
    op.drop_table("run")
    op.drop_index("ix_test_case_segment_id_review_status", table_name="test_case")
    op.drop_index(op.f("ix_test_case_project_id"), table_name="test_case")
    op.drop_table("test_case")
    op.drop_index(op.f("ix_segment_project_id"), table_name="segment")
    op.drop_table("segment")
    op.drop_index(op.f("ix_regression_memory_project_id"), table_name="regression_memory")
    op.drop_table("regression_memory")
    op.drop_index(op.f("ix_node_citation_project_id"), table_name="node_citation")
    op.drop_table("node_citation")
    op.drop_index(op.f("ix_lesson_project_id"), table_name="lesson")
    op.drop_table("lesson")
    op.drop_index(op.f("ix_edge_project_id"), table_name="edge")
    op.drop_table("edge")
    op.drop_index(op.f("ix_project_rule_project_id"), table_name="project_rule")
    op.drop_table("project_rule")
    op.drop_index(op.f("ix_plan_project_id"), table_name="plan")
    op.drop_table("plan")
    op.drop_index(op.f("ix_node_project_id"), table_name="node")
    op.drop_index("ix_node_graph_version_id_type", table_name="node")
    op.drop_table("node")
    op.drop_index(op.f("ix_identity_project_id"), table_name="identity")
    op.drop_table("identity")
    op.drop_index("ix_chunk_source_id_start_offset", table_name="chunk")
    op.drop_index(op.f("ix_chunk_project_id"), table_name="chunk")
    op.drop_table("chunk")
    op.drop_index(op.f("ix_trained_model_project_id"), table_name="trained_model")
    op.drop_table("trained_model")
    op.drop_index(op.f("ix_source_project_id"), table_name="source")
    op.drop_table("source")
    op.drop_index(op.f("ix_replay_cache_project_id"), table_name="replay_cache")
    op.drop_table("replay_cache")
    op.drop_index(
        "ix_outbox_unpublished",
        table_name="outbox",
        postgresql_where=sa.text("published_at IS NULL"),
    )
    op.drop_index(op.f("ix_outbox_project_id"), table_name="outbox")
    op.drop_table("outbox")
    op.drop_index(op.f("ix_membership_project_id"), table_name="membership")
    op.drop_table("membership")
    op.drop_index(op.f("ix_graph_version_project_id"), table_name="graph_version")
    op.drop_table("graph_version")
    op.drop_index(op.f("ix_feedback_project_id"), table_name="feedback")
    op.drop_table("feedback")
    op.drop_index(op.f("ix_environment_project_id"), table_name="environment")
    op.drop_table("environment")
    op.drop_table("project")
    op.drop_table("audit_event")
    op.drop_table("app_user")
