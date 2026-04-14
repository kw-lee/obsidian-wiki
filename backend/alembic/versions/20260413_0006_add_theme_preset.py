"""add theme preset setting

Revision ID: 20260413_0006
Revises: 20260413_0005
Create Date: 2026-04-13 18:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260413_0006"
down_revision: str | None = "20260413_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("theme_preset", sa.Text(), nullable=False, server_default="obsidian"),
    )
    op.create_check_constraint(
        "ck_app_settings_theme_preset",
        "app_settings",
        "theme_preset IN ('obsidian', 'graphite', 'dawn', 'forest')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_app_settings_theme_preset", "app_settings", type_="check")
    op.drop_column("app_settings", "theme_preset")
