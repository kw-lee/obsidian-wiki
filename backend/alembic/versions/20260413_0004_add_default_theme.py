"""add default theme

Revision ID: 20260413_0004
Revises: 20260413_0003
Create Date: 2026-04-13 01:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260413_0004"
down_revision: str | None = "20260413_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("default_theme", sa.Text(), nullable=False, server_default="system"),
    )
    op.create_check_constraint(
        "ck_app_settings_default_theme",
        "app_settings",
        "default_theme IN ('light', 'dark', 'system')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_app_settings_default_theme", "app_settings", type_="check")
    op.drop_column("app_settings", "default_theme")
