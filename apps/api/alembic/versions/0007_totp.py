"""app_user: totp_enabled, totp_last_step (T-105a). Secrets stay encrypted in totp_secret_enc.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-20 02:25:14.281428
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_user", sa.Column("totp_enabled", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column("app_user", sa.Column("totp_last_step", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("app_user", "totp_last_step")
    op.drop_column("app_user", "totp_enabled")
