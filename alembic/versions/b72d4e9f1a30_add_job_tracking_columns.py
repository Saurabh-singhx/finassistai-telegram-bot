"""add job tracking columns to notification_preferences and custom_alerts

Revision ID: b72d4e9f1a30
Revises: a61c3d8e9b20
"""

from alembic import op
import sqlalchemy as sa


revision = "b72d4e9f1a30"
down_revision = "a61c3d8e9b20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_preferences",
        sa.Column("last_briefing_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_preferences",
        sa.Column("last_briefing_date", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "custom_alerts",
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("custom_alerts", "last_triggered_at")
    op.drop_column("notification_preferences", "last_briefing_date")
    op.drop_column("notification_preferences", "last_briefing_sent_at")
