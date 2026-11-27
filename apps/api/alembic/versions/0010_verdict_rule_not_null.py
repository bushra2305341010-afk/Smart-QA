"""verdict.rule NOT NULL: every verdict names its deciding rule (sector 06 bug locator).

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE verdict SET rule = 'legacy.unknown' WHERE rule IS NULL")
    op.alter_column("verdict", "rule", existing_type=sa.Text(), nullable=False)


def downgrade() -> None:
    op.alter_column("verdict", "rule", existing_type=sa.Text(), nullable=True)
