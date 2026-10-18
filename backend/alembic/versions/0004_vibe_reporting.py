"""Vibe reporting: applied workspace versions, integration runs, report cache, API tokens.

Revision ID: 0004_vibe_reporting
Revises: 0003_sources_security
Create Date: 2026-09-29
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0004_vibe_reporting"
down_revision = "0003_sources_security"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)
AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"   # see 0003
KINDS_004 = (
    "login_ok", "login_failed", "login_locked", "logout",
    "user_created", "user_updated", "user_deactivated", "user_reactivated", "role_changed",
    "password_changed", "password_reset", "dashboard_granted", "dashboard_revoked",
    "superuser_created", "superuser_promoted", "superuser_recovered",
    "source_created", "source_updated", "source_deleted", "source_tested", "source_enabled",
    "source_disabled", "source_imported", "mfa_enabled", "mfa_disabled", "mfa_reset",
    "recovery_code_used", "recovery_codes_regenerated", "reauth_ok", "reauth_failed",
    "login_rate_limited", "admin_address_refused", "secret_key_rotated",
)
KINDS_005 = (*KINDS_004, "workspace_validated", "workspace_applied", "workspace_rolled_back",
             "integration_run_requested", "token_created", "token_revoked", "source_described")


def _kinds(kinds) -> str:
    return "kind IN (" + ", ".join(f"'{k}'" for k in kinds) + ")"


def upgrade() -> None:
    op.create_table(
        "workspace_version",
        sa.Column("id", sa.BigInteger, sa.Identity(), nullable=False),
        sa.Column("commit", sa.Text),
        sa.Column("checksum", sa.Text, nullable=False),
        sa.Column("lock", pg.JSONB, nullable=False),
        sa.Column("artifacts", pg.JSONB, nullable=False),
        sa.Column("specs", pg.JSONB, nullable=False),
        sa.Column("state", sa.Text, nullable=False),
        sa.Column("applied_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("applied_by", sa.BigInteger,
                  sa.ForeignKey("app_user.id", name="fk_workspace_version_applied_by")),
        sa.PrimaryKeyConstraint("id", name="pk_workspace_version"),
        sa.CheckConstraint("state IN ('active', 'previous', 'archived')", name="state"),
    )
    op.create_index("uq_workspace_version_active", "workspace_version", ["state"], unique=True,
                    postgresql_where=sa.text("state = 'active'"))

    op.create_table(
        "integration_run",
        sa.Column("id", sa.BigInteger, sa.Identity(), nullable=False),
        sa.Column("integration_id", sa.Text, nullable=False),
        sa.Column("version_id", sa.BigInteger,
                  sa.ForeignKey("workspace_version.id", name="fk_integration_run_version_id")),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("window_start", TS),
        sa.Column("window_end", TS),
        sa.Column("started_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", TS),
        sa.Column("rows", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("checks", pg.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("message", sa.Text),
        sa.Column("requested_by", sa.BigInteger,
                  sa.ForeignKey("app_user.id", name="fk_integration_run_requested_by")),
        sa.PrimaryKeyConstraint("id", name="pk_integration_run"),
        sa.CheckConstraint("kind IN ('incremental', 'full', 'manual_incremental', "
                           "'manual_full')", name="kind"),
        sa.CheckConstraint("status IN ('running', 'succeeded', 'failed', 'skipped')",
                           name="status"),
    )
    op.create_index("ix_integration_run_integration_started", "integration_run",
                    ["integration_id", sa.text("started_at DESC")])

    op.create_table(
        "integration_run_request",
        sa.Column("id", sa.BigInteger, sa.Identity(), nullable=False),
        sa.Column("integration_id", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("requested_by", sa.BigInteger,
                  sa.ForeignKey("app_user.id", name="fk_integration_run_request_requested_by")),
        sa.Column("requested_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("taken_at", TS),
        sa.Column("run_id", sa.BigInteger,
                  sa.ForeignKey("integration_run.id", name="fk_integration_run_request_run_id")),
        sa.PrimaryKeyConstraint("id", name="pk_integration_run_request"),
    )

    op.create_table(
        "report_cache",
        sa.Column("report_id", sa.Text, nullable=False),
        sa.Column("selection_hash", sa.Text, nullable=False),
        sa.Column("data_version", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False, server_default="data"),
        sa.Column("payload", pg.JSONB, nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("report_id", "selection_hash", "data_version", "kind",
                                name="pk_report_cache"),
    )

    op.create_table(
        "api_token",
        sa.Column("id", sa.BigInteger, sa.Identity(), nullable=False),
        sa.Column("user_id", sa.BigInteger,
                  sa.ForeignKey("app_user.id", ondelete="CASCADE",
                                name="fk_api_token_user_id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("token_hash", sa.LargeBinary, nullable=False),
        sa.Column("scopes", pg.ARRAY(sa.Text), nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("last_used_at", TS),
        sa.Column("revoked_at", TS),
        sa.PrimaryKeyConstraint("id", name="pk_api_token"),
        sa.UniqueConstraint("token_hash", name="uq_api_token_token_hash"),
        sa.CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 60", name="name_len"),
    )
    op.create_index("ix_api_token_user_id", "api_token", ["user_id"])

    op.add_column("dashboard", sa.Column("report_id", sa.Text))
    op.add_column("dashboard", sa.Column("managed_by", sa.Text, nullable=False,
                                         server_default="product"))
    op.create_unique_constraint("uq_dashboard_report_id", "dashboard", ["report_id"])

    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", _kinds(KINDS_005))


def downgrade() -> None:
    op.execute("DELETE FROM audit_event WHERE NOT " + _kinds(KINDS_004))
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", _kinds(KINDS_004))
    op.drop_constraint("uq_dashboard_report_id", "dashboard", type_="unique")
    op.drop_column("dashboard", "managed_by")
    op.drop_column("dashboard", "report_id")
    op.drop_table("api_token")
    op.drop_table("report_cache")
    op.drop_table("integration_run_request")
    op.drop_table("integration_run")
    op.drop_table("workspace_version")
