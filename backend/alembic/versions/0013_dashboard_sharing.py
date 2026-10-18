"""Dashboard sharing: share links, email settings, sends, deliveries, subscriptions (feature 018).

Revision ID: 0013_dashboard_sharing
Revises: 0012_assistant_busy
Create Date: 2026-10-05
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0013_dashboard_sharing"
down_revision = "0012_assistant_busy"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"  # see 0003/0011
KINDS_012 = (
    "login_ok", "login_failed", "login_locked", "logout",
    "user_created", "user_updated", "user_deactivated", "user_reactivated", "role_changed",
    "password_changed", "password_reset", "dashboard_granted", "dashboard_revoked",
    "superuser_created", "superuser_promoted", "superuser_recovered",
    "source_created", "source_updated", "source_deleted", "source_tested", "source_enabled",
    "source_disabled", "source_imported", "mfa_enabled", "mfa_disabled", "mfa_reset",
    "recovery_code_used", "recovery_codes_regenerated", "reauth_ok", "reauth_failed",
    "login_rate_limited", "admin_address_refused", "secret_key_rotated",
    "workspace_validated", "workspace_applied", "workspace_rolled_back",
    "integration_run_requested", "token_created", "token_revoked", "source_described",
    "telegram_settings_updated", "telegram_checked", "telegram_enabled", "telegram_disabled",
    "telegram_linked", "telegram_unlinked",
    "integration_paused", "integration_resumed", "integration_schedule_changed",
    "integration_run_stopped",
    "assistant_draft_applied", "assistant_session_archived",
    "assistant_budget_extended",
)
KINDS_013 = (
    *KINDS_012,
    "share_link_created", "share_link_revoked", "sharing_toggled",
    "email_settings_updated", "email_test_sent", "email_sent",
    "email_subscription_created", "email_subscription_updated",
    "email_subscription_deleted",
)
NEW_KINDS = KINDS_013[len(KINDS_012):]


def _kinds(kinds) -> str:
    return "kind IN (" + ", ".join(f"'{k}'" for k in kinds) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", _kinds(KINDS_013))

    op.create_table(
        "share_link",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("dashboard_id", sa.SmallInteger(), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("revoked_at", TS, nullable=True),
        sa.Column("revoked_by", sa.BigInteger(), nullable=True),
        sa.Column("visits", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_visit_at", TS, nullable=True),
        sa.CheckConstraint("note IS NULL OR char_length(note) <= 200", name="note_len"),
        sa.CheckConstraint("expires_at > created_at", name="expiry"),
        sa.CheckConstraint("visits >= 0", name="visits"),
        sa.PrimaryKeyConstraint("id", name="pk_share_link"),
        sa.ForeignKeyConstraint(["dashboard_id"], ["dashboard.id"], ondelete="CASCADE",
                                name="fk_share_link_dashboard_id"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"],
                                name="fk_share_link_created_by"),
        sa.ForeignKeyConstraint(["revoked_by"], ["app_user.id"],
                                name="fk_share_link_revoked_by"),
        sa.UniqueConstraint("token_hash", name="uq_share_link_token_hash"),
    )
    op.create_index("ix_share_link_dashboard_id", "share_link", ["dashboard_id"])
    op.create_index(
        "ix_share_link_active",
        "share_link",
        ["dashboard_id", "expires_at"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

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

    op.create_table(
        "email_subscription",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("dashboard_id", sa.SmallInteger(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("recipients", pg.JSONB(astext_type=sa.Text()),
                  server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("frequency", sa.Text(), nullable=False),
        sa.Column("hour", sa.SmallInteger(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=True),
        sa.Column("monthday", sa.SmallInteger(), nullable=True),
        sa.Column("period", sa.Text(), nullable=False),
        sa.Column("attach_pdf", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("link_days", sa.Integer(), nullable=True),
        sa.Column("paused", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_due_at", TS, nullable=True),
        sa.Column("next_due_at", TS, nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("frequency IN ('daily', 'weekly', 'monthly')", name="frequency"),
        sa.CheckConstraint("hour BETWEEN 0 AND 23", name="hour"),
        sa.CheckConstraint(
            "(frequency = 'weekly') = (weekday IS NOT NULL) AND "
            "(weekday IS NULL OR weekday BETWEEN 0 AND 6)",
            name="weekday"),
        sa.CheckConstraint(
            "(frequency = 'monthly') = (monthday IS NOT NULL) AND "
            "(monthday IS NULL OR monthday BETWEEN 1 AND 28)",
            name="monthday"),
        sa.CheckConstraint("char_length(period) BETWEEN 1 AND 40", name="period_len"),
        sa.CheckConstraint("link_days IS NULL OR link_days BETWEEN 1 AND 90",
                           name="link_days"),
        sa.PrimaryKeyConstraint("id", name="pk_email_subscription"),
        sa.ForeignKeyConstraint(["dashboard_id"], ["dashboard.id"], ondelete="CASCADE",
                                name="fk_email_subscription_dashboard_id"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"],
                                name="fk_email_subscription_created_by"),
    )
    op.create_index("ix_email_subscription_dashboard_id", "email_subscription",
                    ["dashboard_id"])
    op.create_index(
        "ix_email_subscription_due",
        "email_subscription",
        ["next_due_at"],
        postgresql_where=sa.text("NOT paused"),
    )

    op.create_table(
        "email_send",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("dashboard_id", sa.SmallInteger(), nullable=False),
        sa.Column("requested_by", sa.BigInteger(), nullable=True),
        sa.Column("subscription_id", sa.BigInteger(), nullable=True),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("selection", pg.JSONB(astext_type=sa.Text()),
                  server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("attach_pdf", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("link_days", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", TS, nullable=True),
        sa.CheckConstraint("char_length(btrim(subject)) BETWEEN 1 AND 200",
                           name="subject_len"),
        sa.CheckConstraint("message IS NULL OR char_length(message) <= 2000",
                           name="message_len"),
        sa.CheckConstraint("link_days IS NULL OR link_days BETWEEN 1 AND 90",
                           name="link_days"),
        sa.CheckConstraint("status IN ('queued', 'sending', 'sent', 'partial', 'failed')",
                           name="status"),
        sa.PrimaryKeyConstraint("id", name="pk_email_send"),
        sa.ForeignKeyConstraint(["dashboard_id"], ["dashboard.id"], ondelete="CASCADE",
                                name="fk_email_send_dashboard_id"),
        sa.ForeignKeyConstraint(["requested_by"], ["app_user.id"],
                                name="fk_email_send_requested_by"),
        sa.ForeignKeyConstraint(["subscription_id"], ["email_subscription.id"],
                                ondelete="SET NULL", name="fk_email_send_subscription_id"),
    )
    op.create_index("ix_email_send_dashboard_id", "email_send", ["dashboard_id"])
    op.create_index("ix_email_send_requested_by_created", "email_send",
                    ["requested_by", "created_at"])

    op.create_table(
        "email_delivery",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("send_id", sa.BigInteger(), nullable=False),
        sa.Column("recipient", sa.Text(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("next_attempt_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", TS, nullable=True),
        sa.CheckConstraint("char_length(recipient) BETWEEN 3 AND 254", name="recipient_len"),
        sa.CheckConstraint("status IN ('queued', 'sent', 'failed', 'skipped')",
                           name="status"),
        sa.CheckConstraint("attempts >= 0", name="attempts"),
        sa.CheckConstraint("error IS NULL OR char_length(error) <= 500", name="error_len"),
        sa.PrimaryKeyConstraint("id", name="pk_email_delivery"),
        sa.ForeignKeyConstraint(["send_id"], ["email_send.id"], ondelete="CASCADE",
                                name="fk_email_delivery_send_id"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="SET NULL",
                                name="fk_email_delivery_user_id"),
    )
    op.create_index("ix_email_delivery_send_id", "email_delivery", ["send_id"])
    op.create_index(
        "ix_email_delivery_due",
        "email_delivery",
        ["next_attempt_at"],
        postgresql_where=sa.text("status = 'queued'"),
    )


def downgrade() -> None:
    new_kinds_sql = ", ".join(f"'{k}'" for k in NEW_KINDS)
    count = op.get_bind().execute(
        sa.text(f"SELECT count(*) FROM audit_event WHERE kind IN ({new_kinds_sql})")
    ).scalar()
    if count:
        raise RuntimeError(
            f"{count} evento(s) de auditoría de enlaces o correo existen: "
            "elimínalos antes de bajar de 0013")

    op.drop_index("ix_email_delivery_due", table_name="email_delivery")
    op.drop_index("ix_email_delivery_send_id", table_name="email_delivery")
    op.drop_table("email_delivery")

    op.drop_index("ix_email_send_requested_by_created", table_name="email_send")
    op.drop_index("ix_email_send_dashboard_id", table_name="email_send")
    op.drop_table("email_send")

    op.drop_index("ix_email_subscription_due", table_name="email_subscription")
    op.drop_index("ix_email_subscription_dashboard_id", table_name="email_subscription")
    op.drop_table("email_subscription")

    op.drop_table("email_settings")

    op.drop_index("ix_share_link_active", table_name="share_link")
    op.drop_index("ix_share_link_dashboard_id", table_name="share_link")
    op.drop_table("share_link")

    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", _kinds(KINDS_012))
