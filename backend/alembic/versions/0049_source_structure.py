"""The structure pack, the sample requests and the structure chat (feature 052).

Four things reach the database:

* `data_source.notes` — the "Observaciones" the structure pack prints;
* `source_sample_request` — the saved sample requests of a REST/Supabase source (path and query
  parameters only, never a secret; the last shape is keys and types, never a value);
* `source_structure_flag` — the super user's override of the personal-data heuristic per column;
* `source_chat_message` — one row per chat turn, which is also the usage the daily cap reads
  (the question text is only stored when the installation asks for it).

The audit vocabulary grows by eight kinds, so the `audit_event.kind` check constraint is recreated
with the full list — what may be written today plus what history already holds.

Revision ID: 0049_source_structure
Revises: 0048_official_themes
Create Date: 2026-11-03
"""
import sqlalchemy as sa

from alembic import op

revision = "0049_source_structure"
down_revision = "0048_official_themes"
branch_labels = None
depends_on = None

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"

#: 0047's list, unchanged: a migration never drops a kind a database may already contain.
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
    "assistant_profile_deleted", "project_limits_changed",
)
KINDS_0049 = KINDS_0047 + (
    "source_structure_notes_updated", "source_structure_flag_changed", "source_sample_created",
    "source_sample_updated", "source_sample_deleted", "source_sample_run",
    "source_chat_asked", "source_chat_cleared",
)


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_0049)}")

    op.add_column("data_source", sa.Column("notes", sa.Text(), nullable=False,
                                           server_default=sa.text("''")))

    op.create_table(
        "source_sample_request",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("source_id", sa.BigInteger(),
                  sa.ForeignKey("data_source.id",
                                name="fk_source_sample_request_source_id",
                                ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("method", sa.Text(), server_default=sa.text("'GET'"), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("params", sa.dialects.postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"),
                  nullable=False),
        sa.Column("notes", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("last_shape", sa.dialects.postgresql.JSONB()),
        sa.Column("last_suggestions", sa.dialects.postgresql.JSONB()),
        sa.Column("last_status", sa.Integer()),
        sa.Column("last_error", sa.Text()),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.CheckConstraint("method IN ('GET')", name=op.f("ck_source_sample_request_method")),
        sa.CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 80",
                           name=op.f("ck_source_sample_request_name_len")),
        sa.CheckConstraint("path NOT LIKE '%://%' AND path NOT LIKE '/%'",
                           name=op.f("ck_source_sample_request_path_relative")),
        sa.CheckConstraint("char_length(notes) <= 1000",
                           name=op.f("ck_source_sample_request_notes_len")),
    )
    op.create_index("uq_source_sample_request_name_ci", "source_sample_request",
                    ["source_id", sa.text("lower(name)")], unique=True)

    op.create_table(
        "source_structure_flag",
        sa.Column("source_id", sa.BigInteger(),
                  sa.ForeignKey("data_source.id",
                                name="fk_source_structure_flag_source_id",
                                ondelete="CASCADE"), primary_key=True),
        sa.Column("schema_name", sa.Text(), primary_key=True),
        sa.Column("table_name", sa.Text(), primary_key=True),
        sa.Column("column_name", sa.Text(), primary_key=True),
        sa.Column("personal", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    )

    op.create_table(
        "source_chat_message",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("source_id", sa.BigInteger(),
                  sa.ForeignKey("data_source.id", name="fk_source_chat_message_source_id",
                                ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.BigInteger(),
                  sa.ForeignKey("app_user.id", name="fk_source_chat_message_user_id",
                                ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("body", sa.Text()),
        sa.Column("tokens_in", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("tokens_out", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.CheckConstraint("role IN ('question', 'answer')",
                           name=op.f("ck_source_chat_message_role")),
        sa.CheckConstraint("tokens_in >= 0 AND tokens_out >= 0",
                           name=op.f("ck_source_chat_message_tokens")),
    )
    op.create_index("ix_source_chat_message_turn", "source_chat_message",
                    ["source_id", "user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_source_chat_message_turn", table_name="source_chat_message")
    op.drop_table("source_chat_message")
    op.drop_table("source_structure_flag")
    op.drop_index("uq_source_sample_request_name_ci", table_name="source_sample_request")
    op.drop_table("source_sample_request")
    op.drop_column("data_source", "notes")
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_0047)}")
