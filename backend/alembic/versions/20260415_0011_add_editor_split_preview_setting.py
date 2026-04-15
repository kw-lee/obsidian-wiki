"""add editor split preview setting

Revision ID: 20260415_0011
Revises: 20260415_0010
Create Date: 2026-04-15 16:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260415_0011"
down_revision: str | None = "20260415_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column(
            "editor_split_preview_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "editor_split_preview_enabled")
