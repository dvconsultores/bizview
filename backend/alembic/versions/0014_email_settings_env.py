"""Email settings come from the environment (feature 018, amendment 2026-10-07):
drop email_settings.

Revision ID: 0014_email_settings_env
Revises: 0013_dashboard_sharing
Create Date: 2026-10-07
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0014_email_settings_env"
down_revision = "0013_dashboard_sharing"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.drop_table("email_settings")


def downgrade() -> None:
    op.create_table(
        "email_settings",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sharing_enabled", sa.Boolean(), server_default=sa.text("false"),
                  nullable=False),
        sa.Column("host", sa.Text(), nullable=True),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("security", sa.Text(), server_default=sa.text("'starttls'"), nullable=False),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("password_ct", sa.LargeBinary(), nullable=True),
        sa.Column("password_key_id", sa.Text(), nullable=True),
        sa.Column("sender_name", sa.Text(), nullable=True),
        sa.Column("sender_address", sa.Text(), nullable=True),
        sa.Column("allowed_domains", pg.ARRAY(sa.Text()), server_default=sa.text("'{}'"),
                  nullable=False),
        sa.Column("last_test_at", TS, nullable=True),
        sa.Column("last_test_ok", sa.Boolean(), nullable=True),
        sa.Column("last_test", pg.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.CheckConstraint("id = 1", name="singleton"),
        sa.CheckConstraint("host IS NULL OR char_length(host) BETWEEN 1 AND 253",
                           name="host_len"),
        sa.CheckConstraint("port IS NULL OR port BETWEEN 1 AND 65535", name="port"),
        sa.CheckConstraint("security IN ('starttls', 'ssl', 'none')", name="security"),
        sa.CheckConstraint("(password_ct IS NULL) = (password_key_id IS NULL)",
                           name="password_pair"),
        sa.CheckConstraint(
            "sender_address IS NULL OR (char_length(sender_address) BETWEEN 3 AND 254 "
            "AND position('@' in sender_address) > 1)",
            name="sender_address_format"),
        sa.PrimaryKeyConstraint("id", name="pk_email_settings"),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"],
                                name="fk_email_settings_updated_by"),
    )
