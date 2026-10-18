"""Telegram poller health: last successful poll, so sign-in can say when Telegram is down
(feature 007, FR-013).

Revision ID: 0007_telegram_poll_health
Revises: 0006_telegram
Create Date: 2026-10-01
"""
import sqlalchemy as sa

from alembic import op

revision = "0007_telegram_poll_health"
down_revision = "0006_telegram"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("telegram_settings",
                  sa.Column("last_poll_ok_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("telegram_settings", "last_poll_ok_at")
