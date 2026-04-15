"""add font settings

Revision ID: 20260415_0010
Revises: 20260415_0009
Create Date: 2026-04-15 12:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260415_0010"
down_revision: str | None = "20260415_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("ui_font", sa.Text(), nullable=False, server_default="system"),
    )
    op.add_column(
        "app_settings",
        sa.Column("editor_font", sa.Text(), nullable=False, server_default="system"),
    )
    op.create_check_constraint(
        "ck_app_settings_ui_font",
        "app_settings",
        "ui_font IN ('system', 'nanum-square', 'nanum-square-ac')",
    )
    op.create_check_constraint(
        "ck_app_settings_editor_font",
        "app_settings",
        "editor_font IN ('system', 'd2coding')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_app_settings_editor_font", "app_settings", type_="check")
    op.drop_constraint("ck_app_settings_ui_font", "app_settings", type_="check")
    op.drop_column("app_settings", "editor_font")
    op.drop_column("app_settings", "ui_font")
