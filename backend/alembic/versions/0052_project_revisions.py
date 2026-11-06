"""A project's own revisions (feature 055).

Feature 020 records one row per *file* change and one workspace version per *apply*; nothing records
"the project's folder as a whole at this moment", which is what a re-import needs to diff against,
to download and to go back to.

This migration adds `project_revision` -- a numbered snapshot stored as a map of `path -> sha256`,
never the contents -- and `project.revision_seq`, the counter that hands the numbers out. It also
widens the audit vocabulary with the two events of the flow.

A re-import therefore replaces the project instead of creating `ventas-marca-2`, `-3`.

Revision ID: 0052_project_revisions
Revises: 0051_google_rbac
Create Date: 2026-11-05
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0052_project_revisions"
down_revision = "0051_google_rbac"
branch_labels = None
depends_on = None

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"

#: 0051's list, unchanged: a migration never drops a kind a database may already contain.
KINDS_0051 = (
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
    "google_rule_updated", "google_rule_deleted", "google_user_provisioned", "google_rule_applied"
)
#: What 0052 adds.
KINDS_0052 = (*KINDS_0051, "project_reimported", "project_reverted")


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.add_column("project", sa.Column("revision_seq", sa.Integer(), nullable=False,
                                       server_default=sa.text("0")))
    op.create_table(
        "project_revision",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("source", sa.Text(), nullable=False, server_default=sa.text("'import'")),
        sa.Column("files", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("summary", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], name="fk_project_revision_project",
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"],
                                name="fk_project_revision_created_by"),
        sa.CheckConstraint("number >= 1", name="ck_project_revision_revision_number"),
        sa.CheckConstraint("status IN ('draft', 'applied', 'previous', 'replaced')",
                           name="ck_project_revision_revision_status"),
        sa.CheckConstraint("source IN ('import', 'editor')",
                           name="ck_project_revision_revision_source"),
        sa.CheckConstraint("jsonb_typeof(files) = 'object'",
                           name="ck_project_revision_revision_files_object"),
        sa.CheckConstraint("jsonb_typeof(summary) = 'object'",
                           name="ck_project_revision_revision_summary_object"),
        sa.UniqueConstraint("project_id", "number", name="uq_project_revision_number"),
    )
    op.create_index("ix_project_revision_number_desc", "project_revision",
                    ["project_id", sa.text("number DESC")])

    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_0052)}")


def downgrade() -> None:
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_0051)}")
    op.drop_index("ix_project_revision_number_desc", table_name="project_revision")
    op.drop_table("project_revision")
    op.drop_column("project", "revision_seq")
