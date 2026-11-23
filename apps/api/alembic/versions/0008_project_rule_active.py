"""project_rule.active: learned rules can be switched off (undo a lesson, docs/21 A5).

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-24 01:39:50.171818
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project_rule", sa.Column("active", sa.Boolean(), server_default="true", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("project_rule", "active")
