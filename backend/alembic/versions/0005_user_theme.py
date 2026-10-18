"""Dark mode: each user's theme preference (feature 006).

Revision ID: 0005_user_theme
Revises: 0004_vibe_reporting
Create Date: 2026-09-30
"""
import sqlalchemy as sa

from alembic import op

revision = "0005_user_theme"
down_revision = "0004_vibe_reporting"
branch_labels = None
depends_on = None

THEME_CHECK = "ck_app_user_theme"


def upgrade() -> None:
    op.add_column("app_user", sa.Column("theme", sa.Text, nullable=False,
                                        server_default=sa.text("'system'")))
    op.create_check_constraint(op.f(THEME_CHECK), "app_user",
                               "theme IN ('system', 'light', 'dark')")


def downgrade() -> None:
    op.drop_constraint(op.f(THEME_CHECK), "app_user", type_="check")
    op.drop_column("app_user", "theme")
