"""Dashboard catalogue and per-user access grants.

Revision ID: 0002_dashboards
Revises: 0001_app_auth
Create Date: 2026-09-29
"""
import sqlalchemy as sa

from alembic import op

revision = "0002_dashboards"
down_revision = "0001_app_auth"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    dashboard = op.create_table(
        "dashboard",
        sa.Column("id", sa.SmallInteger, sa.Identity(), nullable=False),
        sa.Column("code", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("icon", sa.Text, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="100"),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_dashboard"),
        sa.UniqueConstraint("code", name="uq_dashboard_code"),
        sa.CheckConstraint("code ~ '^[a-z][a-z0-9-]{1,39}$'", name="ck_dashboard_code_format"),
        sa.CheckConstraint("char_length(description) <= 200",
                           name="ck_dashboard_description_len"),
        sa.CheckConstraint("status IN ('available', 'coming_soon', 'hidden')",
                           name="ck_dashboard_status"),
    )
    op.create_table(
        "dashboard_access",
        sa.Column("user_id", sa.BigInteger,
                  sa.ForeignKey("app_user.id", ondelete="CASCADE",
                                name="fk_dashboard_access_user_id"), nullable=False),
        sa.Column("dashboard_id", sa.SmallInteger,
                  sa.ForeignKey("dashboard.id", ondelete="CASCADE",
                                name="fk_dashboard_access_dashboard_id"), nullable=False),
        sa.Column("granted_by", sa.BigInteger,
                  sa.ForeignKey("app_user.id", name="fk_dashboard_access_granted_by")),
        sa.Column("granted_at", TS, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("user_id", "dashboard_id", name="pk_dashboard_access"),
    )
    op.bulk_insert(dashboard, [{
        "code": "ventas",
        "name": "Ventas",
        "description": "Resumen, tendencias y productos de tus ventas.",
        "icon": "chart-line",
        "sort_order": 10,
        "status": "coming_soon",
    }])


def downgrade() -> None:
    op.drop_table("dashboard_access")
    op.drop_table("dashboard")
