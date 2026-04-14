"""add folder note system setting

Revision ID: 20260414_0007
Revises: 20260413_0006
Create Date: 2026-04-14 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260414_0007"
down_revision: str | None = "20260413_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("folder_note_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "folder_note_enabled")
