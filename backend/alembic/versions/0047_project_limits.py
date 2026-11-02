"""Import allowances as data, and the audit kind that records a change (feature 049).

031 measured every file of an import against one budget, and 044 added `assets/**` without giving
the images a budget of their own — so a project that ships a logo set was refused with a message
naming limits the author could not act on. This table stores the six numbers a super user may
override; a NULL means "use the deployment default" (`PROJECT_MAX_FILES` and friends), so an
installation whose operator set those in `.env` keeps them.

`kind` is frozen here on purpose: a migration may not import the live catalogue (the defect 045's
hotfix corrected), and this constraint may only ever grow.

Revision ID: 0047_project_limits
Revises: 0046_no_default_dashboards
Create Date: 2026-11-01
"""
import sqlalchemy as sa

from alembic import op

revision = "0047_project_limits"
down_revision = "0046_no_default_dashboards"
branch_labels = None
depends_on = None

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"

KINDS_0047 = (
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
    "assistant_profile_deleted", "project_limits_changed"
)


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.create_table(
        "project_limits",
        sa.Column("id", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("artifact_max_files", sa.Integer(), nullable=True),
        sa.Column("artifact_max_kb", sa.Integer(), nullable=True),
        sa.Column("artifact_max_mb", sa.Integer(), nullable=True),
        sa.Column("asset_max_files", sa.Integer(), nullable=True),
        sa.Column("asset_max_kb", sa.Integer(), nullable=True),
        sa.Column("asset_max_mb", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_by", sa.BigInteger(),
                  sa.ForeignKey("app_user.id", name="fk_project_limits_updated_by"),
                  nullable=True),
        sa.CheckConstraint("id = 1", name="singleton"),
        sa.CheckConstraint("artifact_max_files IS NULL OR artifact_max_files > 0",
                           name="ck_project_limits_artifact_max_files"),
        sa.CheckConstraint("artifact_max_kb IS NULL OR artifact_max_kb > 0",
                           name="ck_project_limits_artifact_max_kb"),
        sa.CheckConstraint("artifact_max_mb IS NULL OR artifact_max_mb > 0",
                           name="ck_project_limits_artifact_max_mb"),
        sa.CheckConstraint("asset_max_files IS NULL OR asset_max_files > 0",
                           name="ck_project_limits_asset_max_files"),
        sa.CheckConstraint("asset_max_kb IS NULL OR asset_max_kb > 0",
                           name="ck_project_limits_asset_max_kb"),
        sa.CheckConstraint("asset_max_mb IS NULL OR asset_max_mb > 0",
                           name="ck_project_limits_asset_max_mb"),
        sa.CheckConstraint("artifact_max_kb IS NULL OR artifact_max_mb IS NULL "
                           "OR artifact_max_kb <= artifact_max_mb * 1024",
                           name="ck_project_limits_artifact_kb_vs_mb"),
        sa.CheckConstraint("asset_max_kb IS NULL OR asset_max_mb IS NULL "
                           "OR asset_max_kb <= asset_max_mb * 1024",
                           name="ck_project_limits_asset_kb_vs_mb"),
        sa.PrimaryKeyConstraint("id", name="pk_project_limits"),
    )
    # One row, every column inherited: the table answers before anyone edits it.
    op.execute(sa.text("INSERT INTO project_limits (id) VALUES (1)"))

    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_0047)}")


def downgrade() -> None:
    # The audit constraint is left as it is on purpose: a row already written with
    # `project_limits_changed` would make a narrower constraint fail, and audit history is
    # immutable. The constraint may only ever grow (the rule 045's hotfix established).
    op.drop_table("project_limits")
