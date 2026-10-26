"""The installation's last AI outcome, for `/api/health` and the Auto refusal (feature 035).

Revision ID: 0028_ai_status
Revises: 0027_appearance_palette
Create Date: 2026-10-26
"""
import sqlalchemy as sa

from alembic import op

revision = "0028_ai_status"
down_revision = "0027_appearance_palette"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"
KINDS_026 = (
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
    "assistant_profile_edited", "assistant_profile_deleted",
)
KINDS_027 = (*KINDS_026, "appearance_updated")
KINDS_028 = (*KINDS_027, "project_fix_applied")

CODES = ("not_configured", "no_credit", "bad_key", "model_not_found", "rate_limited",
         "context_too_long", "provider_down", "invalid_tool_call", "refused", "provider_error")


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_028)}")

    op.create_table(
        "ai_status",
        sa.Column("id", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("last_ok_at", TS, nullable=True),
        sa.Column("last_error_code", sa.Text(), nullable=True),
        sa.Column("last_error_at", TS, nullable=True),
        sa.Column("last_error_detail", sa.Text(), nullable=True),
        sa.Column("last_model", sa.Text(), nullable=True),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_ai_status"),
        sa.CheckConstraint("id = 1", name="singleton"),
        sa.CheckConstraint(f"last_error_code IS NULL OR last_error_code IN {_in(CODES)}",
                           name="ai_status_code"),
        sa.CheckConstraint("last_error_detail IS NULL OR char_length(last_error_detail) <= 300",
                           name="ai_status_detail_len"),
    )


def downgrade() -> None:
    op.drop_table("ai_status")
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_027)}")
