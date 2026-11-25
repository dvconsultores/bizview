"""Dashboard widgets: a dashboard embedded in another web page (feature 065).

A widget is a standing permission to show one dashboard inside a named list of sites, with no
expiry unless the admin sets one. It is deliberately **not** a kind of share link: `share_link`
keeps its NOT NULL expiry, its 1..90 day rule and its 20-link count untouched (research R1).

Revision ID: 0059_dashboard_widgets
Revises: 0058_password_removal
Create Date: 2026-11-24
"""
import re

import sqlalchemy as sa

from alembic import op

revision = "0059_dashboard_widgets"
down_revision = "0058_password_removal"
branch_labels = None
depends_on = None

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"

#: Every kind this repository has written, frozen on purpose: importing `app.models` makes an
#: applied migration change its meaning (0056's lesson). The live constraint is unioned in below.
AUDIT_KINDS_0059 = (
    "login_ok", "login_failed", "login_locked", "logout", "user_created",
    "user_created_without_password", "user_updated", "user_deactivated", "user_reactivated",
    "role_changed", "password_changed", "password_reset", "password_removed", "dashboard_granted",
    "dashboard_revoked", "superuser_created", "superuser_promoted", "superuser_recovered",
    "source_created", "source_updated", "source_deleted", "source_tested", "source_enabled",
    "source_disabled", "source_imported", "mfa_enabled", "mfa_disabled", "mfa_reset",
    "recovery_code_used", "recovery_codes_regenerated", "reauth_ok", "reauth_failed",
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
    "assistant_budget_extended", "assistant_conversation_repaired",
    "assistant_attachment_uploaded", "assistant_attachment_deleted", "assistant_mode_changed",
    "assistant_contract_confirmed", "assistant_run_started", "assistant_run_applied",
    "assistant_run_stopped", "assistant_run_rolled_back", "assistant_profile_created",
    "assistant_profile_edited", "assistant_profile_deleted", "project_limits_changed",
    "source_structure_notes_updated", "source_structure_flag_changed", "source_sample_created",
    "source_sample_updated", "source_sample_deleted", "source_sample_run", "source_chat_asked",
    "source_chat_cleared", "source_structure_generated", "google_settings_updated",
    "google_rule_created", "google_rule_updated", "google_rule_deleted",
    "google_user_provisioned", "google_rule_applied", "project_reimported", "project_reverted",
    "starter_downloaded", "mail_list_created", "mail_list_updated", "mail_list_deleted",
    "mail_send_resent", "integration_busy", "widget_created", "widget_updated",
    "widget_key_replaced", "widget_revoked",
)


def upgrade() -> None:
    op.create_table(
        "dashboard_widget",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("dashboard_id", sa.SmallInteger(),
                  sa.ForeignKey("dashboard.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        # Only the SHA-256 of the key is stored: a copy of the database reveals no key (FR-011).
        sa.Column("key_hash", sa.LargeBinary(), nullable=False, unique=True),
        sa.Column("theme", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("show_title", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("show_filters", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("pdf_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        # NULL: a widget never expires (FR-005). Only an admin's date makes it expire.
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.BigInteger(), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("visits", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_visit_at", sa.DateTime(timezone=True), nullable=True),
        # The per-widget request ceiling (FR-015): one counter per widget and minute, bumped with a
        # single atomic UPDATE so it is exact across Uvicorn workers.
        sa.Column("rate_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rate_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 80", name="name_len"),
        sa.CheckConstraint("expires_at IS NULL OR expires_at > created_at", name="expiry"),
        sa.CheckConstraint("visits >= 0", name="visits"),
        sa.CheckConstraint("rate_count >= 0", name="rate"),
        sa.CheckConstraint("theme IS NULL OR theme IN ('light', 'dark')",
                           name="theme"),
        sa.CheckConstraint("language IS NULL OR language IN ('es', 'en')",
                           name="language"),
    )
    op.create_index("ix_dashboard_widget_dashboard_id", "dashboard_widget", ["dashboard_id"])
    op.create_index(
        "ix_dashboard_widget_active", "dashboard_widget", ["dashboard_id", "expires_at"],
        postgresql_where=sa.text("revoked_at IS NULL"))

    op.create_table(
        "dashboard_widget_site",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("widget_id", sa.BigInteger(),
                  sa.ForeignKey("dashboard_widget.id", ondelete="CASCADE"), nullable=False),
        # Canonical origin (scheme://host[:port]); paths and wildcards are refused before this.
        sa.Column("origin", sa.Text(), nullable=False),
        # A local development address, marked wherever the sites are shown (FR-020).
        sa.Column("development", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("widget_id", "origin", name="uq_dashboard_widget_site_widget_id"),
    )
    op.create_index("ix_dashboard_widget_site_widget_id", "dashboard_widget_site", ["widget_id"])

    accepted = list(AUDIT_KINDS_0059)
    for kind in _accepted_now():
        if kind not in accepted:
            accepted.append(kind)
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event",
                               f"kind IN {_in(tuple(accepted))}")


def _accepted_now() -> list[str]:
    """The kinds the live constraint accepts today, so the rebuild only ever grows."""
    row = op.get_bind().execute(
        sa.text("SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
                "WHERE c.conname = :name AND c.conrelid = to_regclass('audit_event')"),
        {"name": AUDIT_CHECK}).first()
    if row is None:
        return []
    return re.findall(r"'([a-z0-9_]+)'", str(row[0]))


def _in(values: tuple[str, ...]) -> str:
    return "(" + ", ".join(f"'{value}'" for value in values) + ")"


def downgrade() -> None:
    op.drop_index("ix_dashboard_widget_site_widget_id", table_name="dashboard_widget_site")
    op.drop_table("dashboard_widget_site")
    op.drop_index("ix_dashboard_widget_active", table_name="dashboard_widget")
    op.drop_index("ix_dashboard_widget_dashboard_id", table_name="dashboard_widget")
    op.drop_table("dashboard_widget")
    # The audit CHECK is not narrowed: audit history is immutable and no kind 0058 accepted is
    # missing from the new list.
