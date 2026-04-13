"""add app timezone setting

Revision ID: 20260413_0005
Revises: 20260413_0004
Create Date: 2026-04-13 09:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260413_0005"
down_revision: str | None = "20260413_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column(
            "timezone",
            sa.Text(),
            nullable=False,
            server_default=sa.text(
                "COALESCE(NULLIF(current_setting('app.app_timezone', true), ''), 'Asia/Seoul')"
            ),
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE app_settings
            SET timezone = COALESCE(
                NULLIF(current_setting('app.app_timezone', true), ''),
                'Asia/Seoul'
            )
            WHERE timezone IS NULL OR timezone = ''
            """
        )
    )
    op.alter_column("app_settings", "timezone", server_default="Asia/Seoul")


def downgrade() -> None:
    op.drop_column("app_settings", "timezone")
