"""model_call: status, attempts, replay-cache hit, cache-write tokens, redactions (T-603).

All new columns have defaults, so this is a plain expand step.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-20 01:37:18.979764
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "model_call",
        sa.Column("cache_write_tokens", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("model_call", sa.Column("status", sa.Text(), server_default="ok", nullable=False))
    op.add_column(
        "model_call", sa.Column("attempts", sa.Integer(), server_default="1", nullable=False)
    )
    op.add_column(
        "model_call", sa.Column("from_cache", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column(
        "model_call", sa.Column("redactions", sa.Integer(), server_default="0", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("model_call", "redactions")
    op.drop_column("model_call", "from_cache")
    op.drop_column("model_call", "attempts")
    op.drop_column("model_call", "status")
    op.drop_column("model_call", "cache_write_tokens")
