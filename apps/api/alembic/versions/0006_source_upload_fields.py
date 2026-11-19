"""source: filename, size, text_key (normalised text in object storage), error (M09a).

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-20 01:40:52.393039
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("source", sa.Column("filename", sa.Text(), nullable=True))
    op.add_column("source", sa.Column("size", sa.Integer(), nullable=True))
    op.add_column("source", sa.Column("text_key", sa.Text(), nullable=True))
    op.add_column("source", sa.Column("error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("source", "error")
    op.drop_column("source", "text_key")
    op.drop_column("source", "size")
    op.drop_column("source", "filename")
