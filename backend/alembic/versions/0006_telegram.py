"""Telegram sign-in: bot settings, account links, approval requests (feature 007).

Revision ID: 0006_telegram
Revises: 0005_user_theme
Create Date: 2026-09-30
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0006_telegram"
down_revision = "0005_user_theme"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"   # see 0003
KINDS_005 = (
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
)
KINDS_006 = (*KINDS_005, "telegram_settings_updated", "telegram_checked", "telegram_enabled",
             "telegram_disabled", "telegram_linked", "telegram_unlinked")


def _kinds(kinds) -> str:
    return "kind IN (" + ", ".join(f"'{k}'" for k in kinds) + ")"


def upgrade() -> None:
    op.create_table(
        "telegram_settings",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("bot_username", sa.Text(), nullable=True),
        sa.Column("token_ct", sa.LargeBinary(), nullable=True),
        sa.Column("token_key_id", sa.Text(), nullable=True),
        sa.Column("token_changed_at", TS, nullable=True),
        sa.Column("last_check_at", TS, nullable=True),
        sa.Column("last_check_ok", sa.Boolean(), nullable=True),
        sa.Column("last_check", pg.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("update_offset", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.CheckConstraint("id = 1", name="singleton"),
        sa.CheckConstraint(
            "bot_username ~ '^[A-Za-z][A-Za-z0-9_]{1,28}[Bb][Oo][Tt]$'",
            name="bot_username_format",
        ),
        sa.CheckConstraint("(token_ct IS NULL) = (token_key_id IS NULL)", name="token_pair"),
        sa.PrimaryKeyConstraint("id", name="pk_telegram_settings"),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"],
            name="fk_telegram_settings_updated_by",
        ),
    )

    op.create_table(
        "telegram_link",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("linked_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("linked_by", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "username IS NULL OR char_length(username) <= 64", name="username_len"
        ),
        sa.CheckConstraint(
            "char_length(display_name) BETWEEN 1 AND 128", name="display_name_len"
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_telegram_link"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"],
            name="fk_telegram_link_user_id", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["linked_by"], ["app_user.id"],
            name="fk_telegram_link_linked_by",
        ),
        sa.UniqueConstraint("telegram_id", name="uq_telegram_link_telegram_id"),
    )

    op.create_table(
        "telegram_request",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("browser_hash", sa.LargeBinary(), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("match_code", sa.SmallInteger(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("ip", pg.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.CheckConstraint("char_length(id) = 16", name="id_len"),
        sa.CheckConstraint("purpose IN ('sign_in', 'link')", name="purpose"),
        sa.CheckConstraint(
            "match_code IS NULL OR match_code BETWEEN 10 AND 99", name="match_code"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'started', 'approved', 'refused', 'expired', 'consumed')",
            name="status",
        ),
        sa.CheckConstraint("purpose <> 'link' OR user_id IS NOT NULL", name="link_has_user"),
        sa.CheckConstraint(
            "purpose <> 'sign_in' OR (browser_hash IS NOT NULL AND match_code IS NOT NULL)",
            name="sign_in_has_browser",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_telegram_request"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"],
            name="fk_telegram_request_user_id", ondelete="CASCADE",
        ),
        sa.UniqueConstraint("token_hash", name="uq_telegram_request_token_hash"),
        sa.UniqueConstraint("browser_hash", name="uq_telegram_request_browser_hash"),
    )
    op.create_index(
        "ix_telegram_request_status_expires",
        "telegram_request",
        ["status", "expires_at"],
    )
    op.create_index(
        "ix_telegram_request_user_id", "telegram_request", ["user_id"]
    )

    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", _kinds(KINDS_006))


def downgrade() -> None:
    op.execute("DELETE FROM audit_event WHERE NOT " + _kinds(KINDS_005))
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", _kinds(KINDS_005))

    op.drop_index("ix_telegram_request_user_id", table_name="telegram_request")
    op.drop_index("ix_telegram_request_status_expires", table_name="telegram_request")
    op.drop_table("telegram_request")
    op.drop_table("telegram_link")
    op.drop_table("telegram_settings")
