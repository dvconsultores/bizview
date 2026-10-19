"""Deleting a conversation: its audit kind (feature 014 follow-up).

Revision ID: 0022_chat_delete
Revises: 0021_google_sign_in
Create Date: 2026-10-18
"""
import sqlalchemy as sa

from alembic import op

revision = "0022_chat_delete"
down_revision = "0021_google_sign_in"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

# The audit allowlist is an explicit list in every migration that extends it (see 0003/0011/
# 0013/0018/0020/0021); the 014 kind is appended to the 0021 list.
AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"
KINDS_022 = (
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
    "assistant_budget_extended",
    "share_link_created", "share_link_revoked", "sharing_toggled", "email_settings_updated",
    "email_test_sent", "email_sent", "email_subscription_created", "email_subscription_updated",
    "email_subscription_deleted", "source_direct_reports_changed", "project_created",
    "project_updated", "project_deleted", "project_purged", "project_applied",
    "project_withdrawn", "project_imported", "project_exported", "project_converted",
    "assistant_attachment_uploaded", "assistant_attachment_deleted",
    "google_sign_in", "google_sign_in_refused", "google_linked",
)
# The kinds 0021 knew (`KINDS_022` minus the one added here): what the downgrade restores.
KINDS_021 = tuple(k for k in KINDS_022 if k != "assistant_session_deleted")


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_022)}")


def downgrade() -> None:
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_021)}")
