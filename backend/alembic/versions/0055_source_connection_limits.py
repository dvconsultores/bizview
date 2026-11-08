"""A busy origin is a pause, not a failure (feature 060).

The reported incident: an hourly run of an integration failed with `FATAL: lo siento, ya tenemos
demasiados clientes` (SQLSTATE 53300) because the ERP that owns the origin had taken every
connection slot. Bizview marked a healthy hour as a defect and told nobody why.

A run that exhausts its retries against a full origin now ends `skipped_busy` — amber, touching no
dataset — and `integration_run.busy` keeps what happened (`sqlstate`, `attempts`, `waited_s`, the
origin's own words already redacted) so the run list can explain the delay. Gaining the state widens
the CHECK on `integration_run.status`; nothing else changes. The audit trail gains one kind,
`integration_busy`, written once per streak of busy runs when the operators are told.

Revision ID: 0055_source_connection_limits
Revises: 0054_mail_lists
Create Date: 2026-11-07
"""
import sqlalchemy as sa
from alembic import op

revision = "0055_source_connection_limits"
down_revision = "0054_mail_lists"
branch_labels = None
depends_on = None

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"
RUN_STATUS_CHECK = "ck_integration_run_status"

#: Frozen copy of what 0054 left in the database — a database that already holds these breaks here
#: if the list is shortened, so the migration keeps its own copy instead of reading the models.
KINDS_0054 = (
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
"starter_downloaded""mail_list_created", "mail_list_updated", "mail_list_deleted",
              "mail_send_resent")

#: What 0055 adds: the event written when a streak of busy runs was reported.
KINDS_0055 = (*KINDS_0054, "integration_busy")

STATUSES_0054 = ("running", "succeeded", "failed", "skipped", "stopped")
STATUSES_0055 = (*STATUSES_0054, "skipped_busy")


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.add_column("integration_run", sa.Column(
        "busy", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.drop_constraint(op.f(RUN_STATUS_CHECK), "integration_run", type_="check")
    op.create_check_constraint(op.f(RUN_STATUS_CHECK), "integration_run",
                               f"status IN {_in(STATUSES_0055)}")
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_0055)}")


def downgrade() -> None:
    # A run left in the new state cannot satisfy the old constraint: it becomes the nearest old
    # value that also means "nothing was loaded".
    op.execute("UPDATE integration_run SET status = 'skipped' WHERE status = 'skipped_busy'")
    op.execute("DELETE FROM audit_event WHERE kind = 'integration_busy'")
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_0054)}")
    op.drop_constraint(op.f(RUN_STATUS_CHECK), "integration_run", type_="check")
    op.create_check_constraint(op.f(RUN_STATUS_CHECK), "integration_run",
                               f"status IN {_in(STATUSES_0054)}")
    op.drop_column("integration_run", "busy")
