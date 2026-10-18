"""Assistant session busy claim for agentic assistant (feature 017).

Revision ID: 0012_assistant_busy
Revises: 0011_agentic_assistant
Create Date: 2026-10-05
"""
import sqlalchemy as sa

from alembic import op

revision = "0012_assistant_busy"
down_revision = "0011_agentic_assistant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assistant_session",
        sa.Column("busy_since", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("assistant_session", "busy_since")
