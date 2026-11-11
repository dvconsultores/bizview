"""Removing a password is an audited event (convergence 054b follow-up).

An administrator could give a password-less Google/Telegram account a temporary password, but could
not do the reverse: an existing account marked «Clave temporal» stayed that way for ever, even when
the person only ever signs in with Google. The new action removes the hash and the flag, and this
migration adds its audit kind while preserving every kind the live constraint already accepts.

Revision ID: 0058_password_removal
Revises: 0057_session_credential
Create Date: 2026-11-11
"""
import re

import sqlalchemy as sa

from alembic import op

revision = "0058_password_removal"
down_revision = "0057_session_credential"
branch_labels = None
depends_on = None

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"

#: Every kind this repository has written, frozen on purpose: importing `app.models` makes an
#: applied migration change its meaning (0056's lesson). The live constraint is unioned in below,
#: so history a rolled-back build left behind is never lost.
AUDIT_KINDS_0058 = (
    "login_ok", "login_failed", "login_locked", "logout", "user_created",
    "user_created_without_password", "user_updated", "user_deactivated", "user_reactivated",
    "role_changed", "password_changed", "password_reset", "password_removed", "dashboard_granted",
    "dashboard_revoked", "superuser_created", "superuser_promoted", "superuser_recovered",
    "source_created", "source_updated", "source_deleted", "source_tested", "source_enabled",
    "source_disabled", "source_imported", "mfa_enabled", "mfa_disabled", "mfa_reset",
    "recovery_code_used", "recovery_codes_regenerated", "reauth_ok", "reauth_failed",
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
    "assistant_budget_extended", "assistant_conversation_repaired",
    "assistant_attachment_uploaded", "assistant_attachment_deleted", "assistant_mode_changed",
    "assistant_contract_confirmed", "assistant_run_started", "assistant_run_applied",
    "assistant_run_stopped", "assistant_run_rolled_back", "assistant_profile_created",
    "assistant_profile_edited", "assistant_profile_deleted", "project_limits_changed",
    "source_structure_notes_updated", "source_structure_flag_changed", "source_sample_created",
    "source_sample_updated", "source_sample_deleted", "source_sample_run", "source_chat_asked",
    "source_chat_cleared", "source_structure_generated", "google_settings_updated",
    "google_rule_created", "google_rule_updated", "google_rule_deleted",
    "google_user_provisioned", "google_rule_applied", "project_reimported", "project_reverted",
    "starter_downloaded", "mail_list_created", "mail_list_updated", "mail_list_deleted",
    "mail_send_resent", "integration_busy",
)



def upgrade() -> None:
    accepted = list(AUDIT_KINDS_0058)
    for kind in _accepted_now():
        if kind not in accepted:
            accepted.append(kind)
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event",
                               f"kind IN {_in(tuple(accepted))}")


def _accepted_now() -> list[str]:
    """The kinds the live constraint accepts today, so the rebuild only ever grows."""
    row = op.get_bind().execute(
        sa.text("SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
                "WHERE c.conname = :name AND c.conrelid = to_regclass('audit_event')"),
        {"name": AUDIT_CHECK}).first()
    if row is None:
        return []
    return re.findall(r"'([a-z0-9_]+)'", str(row[0]))


def _in(values: tuple[str, ...]) -> str:
    return "(" + ", ".join(f"'{value}'" for value in values) + ")"


def downgrade() -> None:
    # The CHECK is not narrowed: audit history is immutable and no kind 0057 accepted is missing.
    pass
