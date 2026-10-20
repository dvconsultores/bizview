"""Autonomous mode: the conversation mode and the run contract (feature 028).

Revision ID: 0024_autonomous_mode
Revises: 0023_command_spec_resolution
Create Date: 2026-10-20
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0024_autonomous_mode"
down_revision = "0023_command_spec_resolution"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)
MODES = ("ask", "edit", "auto")
STATUSES = ("confirmed", "running", "applied", "stopped", "failed")
STAGES = ("discover", "specify", "clarify", "plan", "tasks", "implement", "converge",
          "preview", "apply")
WATCH = ("pending", "ok", "failed", "rolled_back")
AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"   # see 0003


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


KINDS_024 = (
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
    "assistant_profile_edited", "assistant_profile_deleted"
)

KINDS_023 = (
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
    "google_sign_in", "google_sign_in_refused", "google_linked"
)

def upgrade() -> None:
    op.create_table(
        "assistant_auto_run",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True,
                  nullable=False),
        sa.Column("session_id", sa.BigInteger(),
                  sa.ForeignKey("assistant_session.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.BigInteger(),
                  sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contract", pg.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'confirmed'")),
        sa.Column("stop_reason", sa.Text(), nullable=True),
        sa.Column("stage", sa.Text(), nullable=True),
        sa.Column("previews", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("applies", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("version_id", sa.BigInteger(),
                  sa.ForeignKey("workspace_version.id"), nullable=True),
        sa.Column("summary", pg.JSONB(), nullable=True),
        sa.Column("watch_integration", sa.Text(), nullable=True),
        sa.Column("watch_state", sa.Text(), nullable=True),
        sa.Column("confirmed_by", sa.BigInteger(), sa.ForeignKey("app_user.id"),
                  nullable=False),
        sa.Column("confirmed_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("confirmed_ip", pg.INET(), nullable=True),
        sa.Column("started_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("ended_at", TS, nullable=True),
        sa.CheckConstraint(f"status IN {_in(STATUSES)}", name="ck_assistant_auto_run_status"),
        sa.CheckConstraint("stop_reason IS NULL OR char_length(stop_reason) <= 120",
                           name="ck_assistant_auto_run_stop_reason_len"),
        sa.CheckConstraint(f"stage IS NULL OR stage IN {_in(STAGES)}",
                           name="ck_assistant_auto_run_stage"),
        sa.CheckConstraint("previews >= 0", name="ck_assistant_auto_run_previews"),
        sa.CheckConstraint("applies >= 0", name="ck_assistant_auto_run_applies"),
        sa.CheckConstraint("tokens >= 0", name="ck_assistant_auto_run_tokens"),
        sa.CheckConstraint(f"watch_state IS NULL OR watch_state IN {_in(WATCH)}",
                           name="ck_assistant_auto_run_watch_state"),
        sa.CheckConstraint("status <> 'applied' OR version_id IS NOT NULL",
                           name="ck_assistant_auto_run_applied_has_version"),
    )
    op.create_index("ux_auto_run_active", "assistant_auto_run", ["session_id"], unique=True,
                    postgresql_where=sa.text("status IN ('confirmed', 'running')"))
    op.create_index("ix_auto_run_session", "assistant_auto_run",
                    ["session_id", sa.text("started_at DESC")])
    op.create_index("ix_auto_run_watch", "assistant_auto_run", ["watch_state"],
                    postgresql_where=sa.text("watch_state = 'pending'"))

    op.create_table(
        "assistant_run_profile",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("contract", pg.JSONB(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", TS, nullable=True),
        sa.CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 60",
                           name="ck_assistant_run_profile_name_len"),
    )
    op.create_index("ux_run_profile_name", "assistant_run_profile", ["name"], unique=True,
                    postgresql_where=sa.text("deleted_at IS NULL"))

    op.add_column("assistant_session",
                  sa.Column("mode", sa.Text(), nullable=False, server_default=sa.text("'edit'")))

    op.create_check_constraint(op.f("ck_assistant_session_mode"), "assistant_session",
                               f"mode IN {_in(MODES)}")

    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_024)}")


def downgrade() -> None:
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_023)}")
    op.drop_constraint(op.f("ck_assistant_session_mode"), "assistant_session", type_="check")
    op.drop_column("assistant_session", "mode")
    op.drop_index("ux_run_profile_name", table_name="assistant_run_profile")
    op.drop_table("assistant_run_profile")
    op.drop_index("ix_auto_run_watch", table_name="assistant_auto_run")
    op.drop_index("ix_auto_run_session", table_name="assistant_auto_run")
    op.drop_index("ux_auto_run_active", table_name="assistant_auto_run")
    op.drop_table("assistant_auto_run")
