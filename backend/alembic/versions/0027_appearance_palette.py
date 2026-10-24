"""Installation appearance: the palette preset and a share link's first-load theme (feature 030).

Revision ID: 0027_appearance_palette
Revises: 0026_preview_request_files
Create Date: 2026-10-23
"""
import sqlalchemy as sa

from alembic import op

revision = "0027_appearance_palette"
down_revision = "0026_preview_request_files"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

# The audit allowlist is an explicit list in every migration that extends it (see 0003/0013/
# 0024); `appearance_updated` is the only 030 kind.
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

PRESETS = ("impacto", "clasico", "monocromo", "contraste", "daltonico")
THEMES = ("light", "dark")
THEME_CHECK = "ck_share_link_theme"


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_027)}")

    op.create_table(
        "appearance_settings",
        sa.Column("id", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("palette_preset", sa.String(32), nullable=False,
                  server_default=sa.text("'impacto'")),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_appearance_settings"),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"],
                                name="fk_appearance_settings_updated_by"),
        sa.CheckConstraint("id = 1", name="singleton"),
        sa.CheckConstraint(f"palette_preset IN {_in(PRESETS)}", name="appearance_palette"),
    )

    op.add_column("share_link", sa.Column("theme", sa.String(5), nullable=True))
    op.create_check_constraint(op.f(THEME_CHECK), "share_link", f"theme IN {_in(THEMES)}")


def downgrade() -> None:
    op.drop_constraint(op.f(THEME_CHECK), "share_link", type_="check")
    op.drop_column("share_link", "theme")
    op.drop_table("appearance_settings")
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_026)}")
