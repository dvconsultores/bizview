"""A source can be declared BI-ready: its scope and its limits are data (feature 048).

`data_source.bi_ready` holds the declaration a super user writes on a PostgreSQL source — the
schemas and objects reports may read, the query timeout, the cache lifetime, the row cap, the
concurrency, the timezone — plus when its credential was last proven read-only. `{}` means "not
BI-ready", which is what every source has until somebody declares one.

The declaration replaces an installation-wide switch, so the migration backfills it from the 019
boolean: an installation that turned direct reports on keeps exactly the reach it has today (no
scope, which the engine reads as "everything the deny-list allows"), and nothing narrows behind the
owner's back.

Revision ID: 0044_bi_ready_sources
Revises: 0042_themes
Create Date: 2026-11-01
"""
import sqlalchemy as sa

from alembic import op

revision = "0044_bi_ready_sources"
down_revision = "0042_themes"
branch_labels = None
depends_on = None

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"
KINDS_0044 = (
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
    "source_bi_ready_changed", "source_bi_ready_verified", "source_bi_ready_unverified",
)


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_0044)}")

    op.add_column("data_source", sa.Column(
        "bi_ready", sa.dialects.postgresql.JSONB(), nullable=False,
        server_default=sa.text("'{}'::jsonb")))

    # 019's switch becomes a declaration with no scope: the same reach, in the new shape.
    op.execute(
        "UPDATE data_source SET bi_ready = jsonb_build_object("
        "'enabled', true, 'schemas', '[]'::jsonb, 'objects', '[]'::jsonb, "
        "'timeout_s', 20, 'cache_ttl_s', 300, 'max_rows', 50000, "
        "'max_parallel', 2, 'timezone', 'UTC') "
        "WHERE direct_reports = true AND kind = 'postgresql'")


def downgrade() -> None:
    """Refuses: dropping the column would silently widen every declared source again.

    An installation that wants the 019 behaviour back turns the declaration off (one field), which
    is a decision with an audit trail — not a schema rollback.
    """
    raise RuntimeError(
        "0044_bi_ready_sources cannot be downgraded: reverting it would drop every source's "
        "declared scope and limits, widening what reports may read without anybody deciding it"
    )
