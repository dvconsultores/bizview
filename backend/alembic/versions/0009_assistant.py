"""Assistant: stored vibe-reporting conversations, messages and preview requests (feature 014).

Revision ID: 0009_assistant
Revises: 0008_integration_control
Create Date: 2026-10-02
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0009_assistant"
down_revision = "0008_integration_control"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"   # see 0003
KINDS_008 = (
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
)
KINDS_009 = (*KINDS_008, "assistant_draft_applied", "assistant_session_archived")


def _kinds(kinds) -> str:
    return "kind IN (" + ", ".join(f"'{k}'" for k in kinds) + ")"


def upgrade() -> None:
    op.create_table(
        "assistant_session",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'open'"), nullable=False),
        sa.Column("draft", pg.JSONB(), nullable=True),
        sa.Column("validation", pg.JSONB(), nullable=True),
        sa.Column("preview", pg.JSONB(), nullable=True),
        sa.Column("applied_version_id", sa.BigInteger(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("token_budget", sa.Integer(), nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("char_length(btrim(title)) BETWEEN 1 AND 120", name="title_len"),
        sa.CheckConstraint("status IN ('open', 'applied', 'archived')", name="status"),
        sa.CheckConstraint("tokens_used >= 0", name="tokens_used"),
        sa.CheckConstraint("token_budget > 0", name="token_budget"),
        sa.CheckConstraint("status <> 'applied' OR applied_version_id IS NOT NULL",
                           name="applied_has_version"),
        sa.PrimaryKeyConstraint("id", name="pk_assistant_session"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"],
                                name="fk_assistant_session_created_by"),
        sa.ForeignKeyConstraint(["applied_version_id"], ["workspace_version.id"],
                                name="fk_assistant_session_applied_version_id"),
    )
    op.create_index("ix_assistant_session_updated_at", "assistant_session",
                    [sa.text("updated_at DESC")])

    op.create_table(
        "assistant_message",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=True),
        sa.Column("tool_payload", pg.JSONB(), nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant', 'tool')", name="role"),
        sa.CheckConstraint("role <> 'tool' OR tool_name IS NOT NULL", name="tool_has_name"),
        sa.PrimaryKeyConstraint("id", name="pk_assistant_message"),
        sa.ForeignKeyConstraint(["session_id"], ["assistant_session.id"], ondelete="CASCADE",
                                name="fk_assistant_message_session_id"),
    )
    op.create_index("ix_assistant_message_session_id", "assistant_message", ["session_id"])

    op.create_table(
        "assistant_preview_request",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("requested_by", sa.BigInteger(), nullable=True),
        sa.Column("requested_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("taken_at", TS, nullable=True),
        sa.Column("finished_at", TS, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_assistant_preview_request"),
        sa.ForeignKeyConstraint(["requested_by"], ["app_user.id"],
                                name="fk_assistant_preview_request_requested_by"),
        sa.ForeignKeyConstraint(["session_id"], ["assistant_session.id"], ondelete="CASCADE",
                                name="fk_assistant_preview_request_session_id"),
    )
    op.create_index("ix_assistant_preview_request_session_id", "assistant_preview_request",
                    ["session_id"])

    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", _kinds(KINDS_009))


def downgrade() -> None:
    op.execute("DELETE FROM audit_event WHERE NOT " + _kinds(KINDS_008))
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", _kinds(KINDS_008))

    op.drop_index("ix_assistant_preview_request_session_id",
                  table_name="assistant_preview_request")
    op.drop_table("assistant_preview_request")
    op.drop_index("ix_assistant_message_session_id", table_name="assistant_message")
    op.drop_table("assistant_message")
    op.drop_index("ix_assistant_session_updated_at", table_name="assistant_session")
    op.drop_table("assistant_session")
