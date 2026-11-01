"""Themes are data an author writes outside Bizview (feature 047).

A theme is a file of tokens — no CSS, no fonts, no markup — validated against
`cli/bizview_cli/schemas/theme.schema.json`. This migration creates the library, seeds the five
themes the product ships (from the same mirrored files the web app and the PDF read, so the install
starts with the look it had) and points `appearance_settings` at a theme instead of a preset.

`palette_preset` stays: an installation that chose before this feature keeps its look because the
built-in ids are unchanged, and `appearance_settings.theme_id` is backfilled from it.

Revision ID: 0042_themes
Revises: 0041_drop_authoring_agent
Create Date: 2026-11-05
"""
import json
from pathlib import Path

import sqlalchemy as sa

from alembic import op

revision = "0042_themes"
down_revision = "0041_drop_authoring_agent"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

# The audit allowlist is an explicit list in every migration that extends it (see 0003/0027/0041);
# the four 047 kinds are appended to the list `app.models.AUDIT_KINDS` carries.
AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"
KINDS_0042 = (
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
    "share_link_created", "share_link_revoked", "sharing_toggled", "email_settings_updated",
    "email_test_sent", "email_sent", "email_subscription_created",
    "email_subscription_updated", "email_subscription_deleted", "source_direct_reports_changed",
    "project_created", "project_updated", "project_deleted", "project_purged",
    "project_applied", "project_withdrawn", "project_imported", "project_exported",
    "project_converted", "project_fix_applied", "google_sign_in", "google_sign_in_refused",
    "google_linked", "appearance_updated",
    "theme_uploaded", "theme_replaced", "theme_deleted", "theme_applied",
)

ORIGINS = ("builtin", "upload", "project")
PRESETS = ("impacto", "clasico", "monocromo", "contraste", "daltonico")
THEMES_DIR = Path(__file__).resolve().parents[2] / "app" / "reports" / "themes"


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_0042)}")

    op.create_table(
        "theme",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_en", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("tokens", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False, server_default=sa.text("'upload'")),
        sa.Column("project_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_theme"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"],
                                name="fk_theme_project", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], name="fk_theme_created_by"),
        sa.CheckConstraint(f"origin IN {_in(ORIGINS)}", name="theme_origin"),
        sa.CheckConstraint("version >= 1", name="theme_version"),
    )
    op.create_index("ix_theme_project", "theme", ["project_id"])

    op.add_column("appearance_settings", sa.Column("theme_id", sa.Text(), nullable=True))
    op.create_foreign_key("fk_appearance_settings_theme", "appearance_settings", "theme",
                          ["theme_id"], ["id"])

    # The product's own five, from the files the app and the PDF read: a fresh install keeps the
    # look it shipped with, and `impacto` is guaranteed to exist for the fallback chain.
    table = sa.table("theme", sa.column("id", sa.Text), sa.column("name", sa.Text),
                     sa.column("name_en", sa.Text), sa.column("version", sa.Integer),
                     sa.column("tokens", sa.dialects.postgresql.JSONB),
                     sa.column("origin", sa.Text))
    op.bulk_insert(table, [
        {"id": preset, "name": data["name"], "name_en": data["name_en"],
         "version": int(data.get("version") or 1), "tokens": data, "origin": "builtin"}
        for preset in PRESETS
        for data in [json.loads((THEMES_DIR / f"{preset}.json").read_text(encoding="utf-8"))]
    ])

    # An installation that chose a preset before this feature keeps exactly that look.
    op.execute("UPDATE appearance_settings SET theme_id = palette_preset WHERE id = 1")


def downgrade() -> None:
    """Refuses: dropping the library would leave every report's `layout.theme.id` dangling.

    The audit allowlist is left as it is for the reason 0041 gives: narrowing it would delete the
    events of the kinds this feature recorded.
    """
    raise RuntimeError(
        "0042_themes cannot be downgraded: reverting it would lose the themes installations "
        "authored and the selection of every report that names one; restore a database backup"
    )
