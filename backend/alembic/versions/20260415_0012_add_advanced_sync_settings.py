"""add advanced sync settings

Revision ID: 20260415_0012
Revises: 20260415_0011
Create Date: 2026-04-15 17:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260415_0012"
down_revision: str | None = "20260415_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column(
            "sync_mode",
            sa.Text(),
            nullable=False,
            server_default="bidirectional",
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "sync_run_on_startup",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "sync_startup_delay_seconds",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "sync_on_save",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "webdav_obsidian_policy",
            sa.Text(),
            nullable=False,
            server_default="remote-only",
        ),
    )
    op.create_check_constraint(
        "ck_app_settings_sync_mode",
        "app_settings",
        "sync_mode IN ('bidirectional', 'pull-only', 'push-only')",
    )
    op.create_check_constraint(
        "ck_app_settings_sync_startup_delay_seconds",
        "app_settings",
        "sync_startup_delay_seconds >= 0",
    )
    op.create_check_constraint(
        "ck_app_settings_webdav_obsidian_policy",
        "app_settings",
        "webdav_obsidian_policy IN ('remote-only', 'ignore', 'include')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_app_settings_webdav_obsidian_policy", "app_settings", type_="check")
    op.drop_constraint("ck_app_settings_sync_startup_delay_seconds", "app_settings", type_="check")
    op.drop_constraint("ck_app_settings_sync_mode", "app_settings", type_="check")
    op.drop_column("app_settings", "webdav_obsidian_policy")
    op.drop_column("app_settings", "sync_on_save")
    op.drop_column("app_settings", "sync_startup_delay_seconds")
    op.drop_column("app_settings", "sync_run_on_startup")
    op.drop_column("app_settings", "sync_mode")
