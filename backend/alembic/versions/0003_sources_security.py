"""Data sources with encrypted credentials, two-step sign-in, throttling (feature 004).

Revision ID: 0003_sources_security
Revises: 0002_dashboards
Create Date: 2026-09-29
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0003_sources_security"
down_revision = "0002_dashboards"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)
# Name created by 0001: the naming convention prefixed an already-prefixed name. Kept as is so
# deployed databases match; op.f() stops the convention from prefixing it again.
AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"
KINDS_002 = (
    "login_ok", "login_failed", "login_locked", "logout",
    "user_created", "user_updated", "user_deactivated", "user_reactivated", "role_changed",
    "password_changed", "password_reset",
    "dashboard_granted", "dashboard_revoked",
    "superuser_created", "superuser_promoted", "superuser_recovered",
)
KINDS_004 = (
    *KINDS_002,
    "source_created", "source_updated", "source_deleted", "source_tested", "source_enabled",
    "source_disabled", "source_imported", "mfa_enabled", "mfa_disabled", "mfa_reset",
    "recovery_code_used", "recovery_codes_regenerated", "reauth_ok", "reauth_failed",
    "login_rate_limited", "admin_address_refused", "secret_key_rotated",
)


def _kind_check(kinds) -> str:
    return "kind IN (" + ", ".join(f"'{k}'" for k in kinds) + ")"


def upgrade() -> None:
    op.create_table(
        "data_source",
        sa.Column("id", sa.BigInteger, sa.Identity(), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("settings", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("secrets_ct", sa.LargeBinary),
        sa.Column("secrets_key_id", sa.Text),
        sa.Column("secret_fields", pg.ARRAY(sa.Text), nullable=False,
                  server_default=sa.text("'{}'")),
        sa.Column("imported", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("last_test_at", TS),
        sa.Column("last_test_ok", sa.Boolean),
        sa.Column("last_test", pg.JSONB),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger,
                  sa.ForeignKey("app_user.id", name="fk_data_source_created_by")),
        sa.Column("updated_by", sa.BigInteger,
                  sa.ForeignKey("app_user.id", name="fk_data_source_updated_by")),
        sa.PrimaryKeyConstraint("id", name="pk_data_source"),
        sa.CheckConstraint("kind IN ('postgresql', 'soap', 'rest')", name="kind"),
        sa.CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 80", name="name_len"),
        sa.CheckConstraint("char_length(description) <= 300", name="description_len"),
        sa.CheckConstraint("(secrets_ct IS NULL) = (secrets_key_id IS NULL)", name="secrets_pair"),
    )
    op.create_index("uq_data_source_name_ci", "data_source", [sa.text("lower(name)")],
                    unique=True)

    op.create_table(
        "security_state",
        sa.Column("id", sa.SmallInteger, nullable=False, autoincrement=False),
        sa.Column("key_id", sa.Text, nullable=False),
        sa.Column("key_check", sa.LargeBinary, nullable=False),
        sa.Column("key_rotated_at", TS),
        sa.Column("legacy_origin_notice", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("id", name="pk_security_state"),
        sa.CheckConstraint("id = 1", name="singleton"),
    )

    op.add_column("app_user", sa.Column("totp_secret_ct", sa.LargeBinary))
    op.add_column("app_user", sa.Column("totp_key_id", sa.Text))
    op.add_column("app_user", sa.Column("totp_enabled_at", TS))
    op.add_column("app_user", sa.Column("totp_last_step", sa.BigInteger))

    op.create_table(
        "recovery_code",
        sa.Column("id", sa.BigInteger, sa.Identity(), nullable=False),
        sa.Column("user_id", sa.BigInteger,
                  sa.ForeignKey("app_user.id", ondelete="CASCADE",
                                name="fk_recovery_code_user_id"), nullable=False),
        sa.Column("code_hash", sa.Text, nullable=False),
        sa.Column("used_at", TS),
        sa.PrimaryKeyConstraint("id", name="pk_recovery_code"),
    )
    op.create_index("ix_recovery_code_user_id", "recovery_code", ["user_id"])

    op.add_column("user_session", sa.Column("mfa_pending", sa.Boolean, nullable=False,
                                            server_default=sa.false()))
    op.add_column("user_session", sa.Column("reauth_at", TS))

    op.create_table(
        "login_throttle",
        sa.Column("ip", pg.INET, nullable=False),
        sa.Column("window_start", TS, nullable=False),
        sa.Column("failures", sa.Integer, nullable=False, server_default="0"),
        sa.Column("limited_audited", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("ip", "window_start", name="pk_login_throttle"),
    )

    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", _kind_check(KINDS_004))


def downgrade() -> None:
    op.execute("DELETE FROM audit_event WHERE " + "NOT " + _kind_check(KINDS_002))
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", _kind_check(KINDS_002))
    op.drop_table("login_throttle")
    op.drop_column("user_session", "reauth_at")
    op.drop_column("user_session", "mfa_pending")
    op.drop_table("recovery_code")
    for col in ("totp_last_step", "totp_enabled_at", "totp_key_id", "totp_secret_ct"):
        op.drop_column("app_user", col)
    op.drop_table("security_state")
    op.drop_table("data_source")
