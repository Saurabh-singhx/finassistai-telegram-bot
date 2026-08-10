"""add persistent Telegram access verification

Revision ID: a61c3d8e9b20
Revises: f92b7a4859a3
"""

from alembic import op
import sqlalchemy as sa


revision = "a61c3d8e9b20"
down_revision = "f92b7a4859a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing users must verify once as well; defaulting to false is intentional.
    op.add_column(
        "users",
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "is_verified")
