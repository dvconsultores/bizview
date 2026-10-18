"""User locale and localization message fields (feature 022).

Revision ID: 0017_user_locale
Revises: 0016_run_transform
Create Date: 2026-10-01
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0017_user_locale"
down_revision = "0016_run_transform"
branch_labels = None
depends_on = None

LOCALE_CHECK = "ck_app_user_locale"


def upgrade() -> None:
    op.add_column("app_user", sa.Column("locale", sa.Text, nullable=True))
    op.create_check_constraint(op.f(LOCALE_CHECK), "app_user",
                               "locale IS NULL OR locale IN ('es', 'en')")
    op.add_column("integration_run", sa.Column("message_key", sa.Text, nullable=True))
    op.add_column("integration_run", sa.Column("message_params", pg.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_constraint(op.f(LOCALE_CHECK), "app_user", type_="check")
    op.drop_column("integration_run", "message_params")
    op.drop_column("integration_run", "message_key")
    op.drop_column("app_user", "locale")
