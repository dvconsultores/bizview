"""The Google sign-in policy (feature 054): domains, provisioning and role rules.

Feature 027 linked Google identities to accounts that already existed; this migration gives the
installation the policy that decides *who may come in and as what*: a singleton `google_settings`
(domains, alta automática, default role and access, whether rules touch existing accounts) and the
ordered `google_rule` list. Two player columns follow from provisioning: `app_user.password_hash`
becomes nullable (a Google account has none until an admin sets one) and `app_user.auth_provider`
records how the account was created. The audit vocabulary gains the six kinds the card and the
callback write; the kinds 0050 wrote stay in the constraint, because history is immutable.

Revision ID: 0051_google_rbac
Revises: 0050_structure_pack
Create Date: 2026-11-04
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0051_google_rbac"
down_revision = "0050_structure_pack"
branch_labels = None
depends_on = None

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"

#: 0050's list, unchanged: a migration never drops a kind a database may already contain.
KINDS_0050 = (
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
    "assistant_profile_deleted", "project_limits_changed",
    "source_structure_notes_updated", "source_structure_flag_changed", "source_sample_created",
    "source_sample_updated", "source_sample_deleted", "source_sample_run",
    "source_chat_asked", "source_chat_cleared", "source_structure_generated",
)
#: What 0051 adds.
KINDS_0051 = (
    *KINDS_0050,
    "google_settings_updated", "google_rule_created", "google_rule_updated",
    "google_rule_deleted", "google_user_provisioned", "google_rule_applied",
)


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.add_column("app_user", sa.Column("auth_provider", sa.Text(), nullable=False,
                                       server_default=sa.text("'password'")))
    op.alter_column("app_user", "password_hash", existing_type=sa.Text(), nullable=True)
    op.create_check_constraint("ck_app_user_auth_provider", "app_user",
                               "auth_provider IN ('password', 'google')")

    op.create_table(
        "google_settings",
        sa.Column("id", sa.SmallInteger(), primary_key=True, autoincrement=False),
        sa.Column("allowed_domains", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("auto_provision", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("default_role", sa.Text(), nullable=False, server_default=sa.text("'user'")),
        sa.Column("default_access", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{\"mode\": \"none\"}'::jsonb")),
        sa.Column("apply_rules_to_existing", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_by", sa.BigInteger(),
                  sa.ForeignKey("app_user.id", name="fk_google_settings_updated_by")),
        sa.CheckConstraint("id = 1", name="ck_google_settings_singleton"),
        sa.CheckConstraint("default_role IN ('admin', 'user')", name="ck_google_default_role"),
        sa.CheckConstraint("jsonb_typeof(allowed_domains) = 'array'",
                           name="ck_google_domains_array"),
        sa.CheckConstraint("jsonb_typeof(default_access) = 'object'",
                           name="ck_google_access_object"),
    )

    op.create_table(
        "google_rule",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("condition", sa.Text(), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("access", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{\"mode\": \"none\"}'::jsonb")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_by", sa.BigInteger(),
                  sa.ForeignKey("app_user.id", name="fk_google_rule_updated_by")),
        sa.CheckConstraint("condition IN ('domain', 'email', 'group')", name="ck_google_condition"),
        sa.CheckConstraint("role IN ('admin', 'user')", name="ck_google_rule_role"),
        sa.CheckConstraint("jsonb_typeof(value) = 'array'", name="ck_google_rule_value_array"),
        sa.CheckConstraint("jsonb_typeof(access) = 'object'", name="ck_google_rule_access_object"),
        sa.CheckConstraint("position >= 0", name="ck_google_rule_position"),
    )
    op.create_index("ix_google_rule_position", "google_rule", ["position"])

    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_0051)}")


def downgrade() -> None:
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_0050)}")
    op.drop_index("ix_google_rule_position", table_name="google_rule")
    op.drop_table("google_rule")
    op.drop_table("google_settings")
    op.drop_constraint("ck_app_user_auth_provider", "app_user", type_="check")
    op.drop_column("app_user", "auth_provider")
    # `password_hash` keeps its NULLability on purpose: restoring NOT NULL would either fail on a
    # provisioned account or invent a credential for it, and inventing one is worse than a column
    # that accepts NULL and is never read that way by 0050's code.
