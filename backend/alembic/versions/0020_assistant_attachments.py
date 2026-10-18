"""Image briefs in the chat: attachments and the one-time privacy notice (feature 024).

Revision ID: 0020_assistant_attachments
Revises: 0019_command_runs
Create Date: 2026-10-12
"""
import sqlalchemy as sa

from alembic import op

revision = "0020_assistant_attachments"
down_revision = "0019_command_runs"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)
MEDIA_TYPES = ("image/png", "image/jpeg", "image/webp", "image/gif")

# The audit allowlist is an explicit list in every migration that extends it (see 0003/0011/
# 0013/0018); the two 024 kinds are appended to the 0018 list.
AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"
KINDS_020 = (
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
    "assistant_draft_applied", "assistant_session_archived", "assistant_budget_extended",
    "share_link_created", "share_link_revoked", "sharing_toggled", "email_settings_updated",
    "email_test_sent", "email_sent", "email_subscription_created", "email_subscription_updated",
    "email_subscription_deleted", "source_direct_reports_changed", "project_created",
    "project_updated", "project_deleted", "project_purged", "project_applied",
    "project_withdrawn", "project_imported", "project_exported", "project_converted",
    "assistant_attachment_uploaded", "assistant_attachment_deleted",
)
# The kinds 0018 knew (`KINDS_020` minus the two 024 kinds): what the downgrade restores.
KINDS_018 = KINDS_020[:-2]




def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_020)}")
    op.add_column("app_user", sa.Column("attachments_notice_at", TS, nullable=True))
    op.create_table(
        "assistant_attachment",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("original_name", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["session_id"], ["assistant_session.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["assistant_message.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"]),
        sa.CheckConstraint(f"media_type IN {_in(MEDIA_TYPES)}", name="media_type"),
        sa.CheckConstraint("byte_size > 0", name="byte_size"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
        sa.CheckConstraint("original_name IS NULL OR char_length(original_name) <= 120",
                           name="original_name_len"),
    )
    op.create_index("ix_assistant_attachment_session_id", "assistant_attachment", ["session_id"])
    op.create_index("ix_assistant_attachment_message_id", "assistant_attachment", ["message_id"])
    op.create_index("ix_assistant_attachment_sha256", "assistant_attachment", ["sha256"])


def downgrade() -> None:
    op.drop_index("ix_assistant_attachment_sha256", table_name="assistant_attachment")
    op.drop_index("ix_assistant_attachment_message_id", table_name="assistant_attachment")
    op.drop_index("ix_assistant_attachment_session_id", table_name="assistant_attachment")
    op.drop_table("assistant_attachment")
    op.drop_column("app_user", "attachments_notice_at")
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_018)}")
