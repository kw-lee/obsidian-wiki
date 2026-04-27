"""fix attachment updated_at default

Revision ID: 20260426_0017
Revises: 20260415_0016
Create Date: 2026-04-26 22:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260426_0017"
down_revision = "20260415_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "attachments",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )


def downgrade() -> None:
    op.alter_column(
        "attachments",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=None,
    )
