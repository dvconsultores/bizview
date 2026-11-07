"""Mailing lists, and the recipients a send may carry (feature 058).

Two guards of feature 018 disappear from the product — the per-send ceiling and the per-hour ceiling
— and the tables that make "send it to these 140 people, every month" possible arrive: a list is an
owned, optionally shared, optionally dynamic-by-role row, and its members are the only personal data
this feature stores. `email_send.kinds` records *what kinds* a send carried (counts and list names,
never an address), `email_delivery.list_id` says which list an address came from, and
`email_subscription.paused_reason` lets the product pause a delivery whose list was deleted without
pretending its owner did it.

Revision ID: 0054_mail_lists
Revises: 0053_starter_pack
Create Date: 2026-11-06
"""
import sqlalchemy as sa
from alembic import op

revision = "0054_mail_lists"
down_revision = "0053_starter_pack"
branch_labels = None
depends_on = None

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"

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
#: What 0053 added on top of 0052 — kept, or a database that already holds it breaks here.
KINDS_0053 = (*KINDS_0052, "starter_downloaded")
#: What 0054 adds: the lists, and a resend that is its own event.
KINDS_0054 = (*KINDS_0053, "mail_list_created", "mail_list_updated", "mail_list_deleted",
              "mail_send_resent")


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.create_table(
        "mail_list",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("owner_id", sa.BigInteger(),
                  sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("visibility", sa.Text(), nullable=False, server_default="personal"),
        sa.Column("kind", sa.Text(), nullable=False, server_default="members"),
        sa.Column("role", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 80", name="name_len"),
        sa.CheckConstraint("description IS NULL OR char_length(description) <= 200",
                           name="description_len"),
        sa.CheckConstraint("visibility IN ('personal', 'compartida')", name="visibility"),
        sa.CheckConstraint("kind IN ('members', 'role')", name="kind"),
        sa.CheckConstraint("(kind = 'role') = (role IS NOT NULL)", name="role_kind"),
        sa.CheckConstraint("role IS NULL OR role IN ('user', 'admin')", name="role_value"),
    )
    op.create_index("uq_mail_list_owner_name", "mail_list", ["owner_id", sa.text("lower(name)")],
                    unique=True, postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_mail_list_owner", "mail_list", ["owner_id"],
                    postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_table(
        "mail_list_member",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("list_id", sa.BigInteger(),
                  sa.ForeignKey("mail_list.id", ondelete="CASCADE"), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("name", sa.Text()),
        sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint("char_length(address) BETWEEN 3 AND 254", name="address_len"),
        sa.CheckConstraint("name IS NULL OR char_length(name) <= 120", name="name_len"),
        sa.UniqueConstraint("list_id", "address", name="uq_mail_list_member"),
    )
    op.create_index("ix_mail_list_member_list", "mail_list_member", ["list_id"])
    op.add_column("email_send", sa.Column("kinds", sa.dialects.postgresql.JSONB(),
                                          nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("email_delivery", sa.Column("list_id", sa.BigInteger(),
                                              sa.ForeignKey("mail_list.id", ondelete="SET NULL")))
    op.add_column("email_subscription", sa.Column("paused_reason", sa.Text()))
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_0054)}")


def downgrade() -> None:
    op.execute("DELETE FROM audit_event WHERE kind LIKE 'mail_list%' OR kind = 'mail_send_resent'")
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_0053)}")
    op.drop_column("email_subscription", "paused_reason")
    op.drop_column("email_delivery", "list_id")
    op.drop_column("email_send", "kinds")
    op.drop_index("ix_mail_list_member_list", table_name="mail_list_member")
    op.drop_table("mail_list_member")
    op.drop_index("ix_mail_list_owner", table_name="mail_list")
    op.drop_index("uq_mail_list_owner_name", table_name="mail_list")
    op.drop_table("mail_list")
