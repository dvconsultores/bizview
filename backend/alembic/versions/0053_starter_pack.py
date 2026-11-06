"""The audit records who downloaded a starter pack (feature 057).

The starter download is the product's front door for an author without a terminal: it names the
project, renders the pack and may carry a source's structure. Recording it is what makes "who handed
which structure to which tool" answerable, exactly like `source_described` is for the structure tab.

Revision ID: 0053_starter_pack
Revises: 0052_project_revisions
Create Date: 2026-11-06
"""
from alembic import op

revision = "0053_starter_pack"
down_revision = "0052_project_revisions"
branch_labels = None
depends_on = None

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"

#: 0052's list, unchanged: a migration never drops a kind a database may already contain.
KINDS_0052 = (
    "login_ok", "login_failed", "login_locked", "logout", "user_created", "user_updated",
    "user_deactivated", "user_reactivated", "role_changed", "password_changed", "password_reset",
    "dashboard_granted", "dashboard_revoked", "superuser_created", "superuser_promoted",
    "superuser_recovered", "source_created", "source_updated", "source_deleted", "source_tested",
    "source_enabled", "source_disabled", "source_imported", "mfa_enabled", "mfa_disabled",
    "mfa_reset", "recovery_code_used", "recovery_codes_regenerated", "reauth_ok", "reauth_failed",
    "login_rate_limited", "admin_address_refused", "secret_key_rotated", "workspace_validated",
    "workspace_applied", "workspace_rolled_back", "integration_run_requested", "token_created",
    "token_revoked", "source_described", "telegram_settings_updated", "telegram_checked",
    "telegram_enabled", "telegram_disabled", "telegram_linked", "telegram_unlinked",
    "integration_paused", "integration_resumed", "integration_schedule_changed",
    "integration_run_stopped", "share_link_created", "share_link_revoked", "sharing_toggled",
    "email_settings_updated", "email_test_sent", "email_sent", "email_subscription_created",
    "email_subscription_updated", "email_subscription_deleted", "source_direct_reports_changed",
    "project_created", "project_updated", "project_deleted", "project_purged", "project_applied",
    "project_withdrawn", "project_imported", "project_exported", "project_converted",
    "project_fix_applied", "google_sign_in", "google_sign_in_refused", "google_linked",
    "appearance_updated", "theme_uploaded", "theme_replaced", "theme_deleted", "theme_applied",
    "source_bi_ready_changed", "source_bi_ready_verified", "source_bi_ready_unverified",
    "assistant_draft_applied", "assistant_session_archived", "assistant_session_deleted",
    "assistant_budget_extended", "assistant_conversation_repaired", "assistant_attachment_uploaded",
    "assistant_attachment_deleted", "assistant_mode_changed", "assistant_contract_confirmed",
    "assistant_run_started", "assistant_run_applied", "assistant_run_stopped",
    "assistant_run_rolled_back", "assistant_profile_created", "assistant_profile_edited",
    "assistant_profile_deleted", "project_limits_changed", "source_structure_notes_updated",
    "source_structure_flag_changed", "source_sample_created", "source_sample_updated",
    "source_sample_deleted", "source_sample_run", "source_chat_asked", "source_chat_cleared",
    "source_structure_generated", "google_settings_updated", "google_rule_created",
    "google_rule_updated", "google_rule_deleted", "google_user_provisioned", "google_rule_applied",
    "project_reimported", "project_reverted"
)
#: What 0053 adds.
KINDS_0053 = (*KINDS_0052, "starter_downloaded")


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_0053)}")


def downgrade() -> None:
    """Narrows the list again; this kind's events must go first (0052 does the same)."""
    op.execute("DELETE FROM audit_event WHERE kind = 'starter_downloaded'")
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_0052)}")

