"""Users, sessions and audit events.

Revision ID: 0001_app_auth
Revises:
Create Date: 2026-09-29
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0001_app_auth"
down_revision = None
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)
AUDIT_KINDS = (
    "login_ok", "login_failed", "login_locked", "logout",
    "user_created", "user_updated", "user_deactivated", "user_reactivated", "role_changed",
    "password_changed", "password_reset",
    "dashboard_granted", "dashboard_revoked",
    "superuser_created", "superuser_promoted", "superuser_recovered",
)


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("full_name", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("is_superuser", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("must_change_password", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("failed_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("locked_until", TS),
        sa.Column("last_login_at", TS),
        sa.Column("password_changed_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger,
                  sa.ForeignKey("app_user.id", name="fk_app_user_created_by")),
        sa.PrimaryKeyConstraint("id", name="pk_app_user"),
        sa.UniqueConstraint("email", name="uq_app_user_email"),
        sa.CheckConstraint("email = lower(btrim(email))", name="ck_app_user_email_normalised"),
        sa.CheckConstraint(
            "char_length(email) BETWEEN 3 AND 254 AND position('@' in email) > 1",
            name="ck_app_user_email_format"),
        sa.CheckConstraint("char_length(btrim(full_name)) BETWEEN 1 AND 120",
                           name="ck_app_user_full_name_len"),
        sa.CheckConstraint("role IN ('admin', 'user')", name="ck_app_user_role"),
        sa.CheckConstraint("NOT is_superuser OR role = 'admin'",
                           name="ck_app_user_superuser_is_admin"),
        sa.CheckConstraint("is_active OR NOT is_superuser", name="ck_app_user_superuser_active"),
    )
    op.create_index("uq_app_user_single_superuser", "app_user", [sa.text("(true)")],
                    unique=True, postgresql_where=sa.text("is_superuser"))
    op.create_index("ix_app_user_role_active", "app_user", ["role", "is_active"])

    op.create_table(
        "user_session",
        sa.Column("id_hash", sa.LargeBinary, nullable=False),
        sa.Column("user_id", sa.BigInteger,
                  sa.ForeignKey("app_user.id", ondelete="CASCADE",
                                name="fk_user_session_user_id"), nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("user_agent", sa.Text),
        sa.Column("ip", pg.INET),
        sa.PrimaryKeyConstraint("id_hash", name="pk_user_session"),
    )
    op.create_index("ix_user_session_user_id", "user_session", ["user_id"])

    kinds = ", ".join(f"'{k}'" for k in AUDIT_KINDS)
    op.create_table(
        "audit_event",
        sa.Column("id", sa.BigInteger, sa.Identity(), nullable=False),
        sa.Column("occurred_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("actor_id", sa.BigInteger,
                  sa.ForeignKey("app_user.id", name="fk_audit_event_actor_id")),
        sa.Column("target_id", sa.BigInteger,
                  sa.ForeignKey("app_user.id", name="fk_audit_event_target_id")),
        sa.Column("ip", pg.INET),
        sa.Column("detail", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id", name="pk_audit_event"),
        sa.CheckConstraint(f"kind IN ({kinds})", name="ck_audit_event_kind"),
    )
    op.create_index("ix_audit_event_occurred_at", "audit_event", [sa.text("occurred_at DESC")])
    op.create_index("ix_audit_event_target_id", "audit_event", ["target_id"])


def downgrade() -> None:
    op.drop_table("audit_event")
    op.drop_table("user_session")
    op.drop_table("app_user")
