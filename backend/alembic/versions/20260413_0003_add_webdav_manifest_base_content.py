"""add webdav manifest base content

Revision ID: 20260413_0003
Revises: 20260413_0002
Create Date: 2026-04-13 01:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260413_0003"
down_revision: str | None = "20260413_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("webdav_manifest", sa.Column("base_content", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("webdav_manifest", "base_content")
