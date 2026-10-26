"""Replayable conversation history: pair tool results with their call (feature 036).

The incident: session 23 of the production installation answered `400` on every turn — «unexpected
`tool_use_id` found in `tool_result` blocks» — because a tool wrote its own note between the
assistant `tool_use` and the result, and the loader paired results by adjacency. This migration adds
the durable pairing and marks what cannot be replayed.

Revision ID: 0029_assistant_history
Revises: 0028_ai_status
Create Date: 2026-10-26
"""
import sqlalchemy as sa

from alembic import op

revision = "0029_assistant_history"
down_revision = "0028_ai_status"
branch_labels = None
depends_on = None

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"
KINDS_028 = (
    "login_ok", "login_failed", "login_locked", "logout", "user_created", "user_updated",
    "user_deactivated", "user_reactivated", "role_changed", "password_changed",
    "password_reset", "dashboard_granted", "dashboard_revoked", "superuser_created",
    "superuser_promoted", "superuser_recovered", "source_created", "source_updated",
    "source_deleted", "source_tested", "source_enabled", "source_disabled", "source_imported",
    "mfa_enabled", "mfa_disabled", "mfa_reset", "recovery_code_used",
    "recovery_codes_regenerated", "reauth_ok", "reauth_failed", "login_rate_limited",
    "admin_address_refused", "secret_key_rotated", "workspace_validated", "workspace_applied",
    "workspace_rolled_back", "integration_run_requested", "token_created", "token_revoked",
    "source_described", "telegram_settings_updated", "telegram_checked", "telegram_enabled",
    "telegram_disabled", "telegram_linked", "telegram_unlinked", "integration_paused",
    "integration_resumed", "integration_schedule_changed", "integration_run_stopped",
    "assistant_draft_applied", "assistant_session_archived", "assistant_session_deleted",
    "assistant_budget_extended", "share_link_created", "share_link_revoked", "sharing_toggled",
    "email_settings_updated", "email_test_sent", "email_sent", "email_subscription_created",
    "email_subscription_updated", "email_subscription_deleted", "source_direct_reports_changed",
    "project_created", "project_updated", "project_deleted", "project_purged",
    "project_applied", "project_withdrawn", "project_imported", "project_exported",
    "project_converted", "assistant_attachment_uploaded", "assistant_attachment_deleted",
    "google_sign_in", "google_sign_in_refused", "google_linked", "assistant_mode_changed",
    "assistant_contract_confirmed", "assistant_run_started", "assistant_run_applied",
    "assistant_run_stopped", "assistant_run_rolled_back", "assistant_profile_created",
    "assistant_profile_edited", "assistant_profile_deleted", "appearance_updated",
    "project_fix_applied",
)
KINDS_029 = (*KINDS_028, "assistant_conversation_repaired")


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.add_column("assistant_message", sa.Column("call_id", sa.Text(), nullable=True))
    op.add_column("assistant_message", sa.Column("assistant_message_id", sa.BigInteger(),
                                                 nullable=True))
    op.add_column("assistant_message", sa.Column("round", sa.Integer(), nullable=True))
    op.add_column("assistant_message", sa.Column("orphan", sa.Boolean(), nullable=False,
                                                 server_default=sa.text("false")))
    op.create_foreign_key(op.f("fk_assistant_message_assistant_message_id"),
                          "assistant_message", "assistant_message",
                          ["assistant_message_id"], ["id"], ondelete="SET NULL")
    op.create_index(op.f("ix_assistant_message_assistant_message_id"), "assistant_message",
                    ["assistant_message_id"])

    # Pair what can be paired and flag the rest, logging the orphan count per conversation.
    from app.assistant import repair

    repair.repair_everything(op.get_bind())

    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_029)}")


def downgrade() -> None:
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_028)}")
    op.drop_index(op.f("ix_assistant_message_assistant_message_id"),
                  table_name="assistant_message")
    op.drop_constraint(op.f("fk_assistant_message_assistant_message_id"),
                       "assistant_message", type_="foreignkey")
    for column in ("orphan", "round", "assistant_message_id", "call_id"):
        op.drop_column("assistant_message", column)
