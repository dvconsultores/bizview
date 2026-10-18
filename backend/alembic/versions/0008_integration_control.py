"""Integration controls: per-integration operational overrides and run stop requests
(feature 013).

Revision ID: 0008_integration_control
Revises: 0007_telegram_poll_health
Create Date: 2026-10-02
"""
import sqlalchemy as sa

from alembic import op

revision = "0008_integration_control"
down_revision = "0007_telegram_poll_health"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"   # see 0003
KINDS_007 = (
    "login_ok", "login_failed", "login_locked", "logout",
    "user_created", "user_updated", "user_deactivated", "user_reactivated", "role_changed",
    "password_changed", "password_reset", "dashboard_granted", "dashboard_revoked",
    "superuser_created", "superuser_promoted", "superuser_recovered",
    "source_created", "source_updated", "source_deleted", "source_tested", "source_enabled",
    "source_disabled", "source_imported", "mfa_enabled", "mfa_disabled", "mfa_reset",
    "recovery_code_used", "recovery_codes_regenerated", "reauth_ok", "reauth_failed",
    "login_rate_limited", "admin_address_refused", "secret_key_rotated",
    "workspace_validated", "workspace_applied", "workspace_rolled_back",
    "integration_run_requested", "token_created", "token_revoked", "source_described",
    "telegram_settings_updated", "telegram_checked", "telegram_enabled", "telegram_disabled",
    "telegram_linked", "telegram_unlinked",
)
KINDS_008 = (*KINDS_007, "integration_paused", "integration_resumed",
             "integration_schedule_changed", "integration_run_stopped")


def _kinds(kinds) -> str:
    return "kind IN (" + ", ".join(f"'{k}'" for k in kinds) + ")"


def upgrade() -> None:
    op.create_table(
        "integration_control",
        sa.Column("integration_id", sa.Text(), nullable=False),
        sa.Column("paused", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("schedule", sa.Text(), nullable=True),
        sa.Column("full_rebuild_cron", sa.Text(), nullable=True),
        sa.Column("window_start", sa.Time(), nullable=True),
        sa.Column("window_end", sa.Time(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("(window_start IS NULL) = (window_end IS NULL)", name="window_pair"),
        sa.CheckConstraint(
            "schedule IS NULL OR char_length(schedule) BETWEEN 9 AND 100",
            name="schedule_len",
        ),
        sa.CheckConstraint(
            "full_rebuild_cron IS NULL OR char_length(full_rebuild_cron) BETWEEN 9 AND 100",
            name="full_rebuild_cron_len",
        ),
        sa.PrimaryKeyConstraint("integration_id", name="pk_integration_control"),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"],
            name="fk_integration_control_updated_by",
        ),
    )

    op.add_column("integration_run", sa.Column("stop_requested_at", TS, nullable=True))
    op.add_column("integration_run", sa.Column("stop_requested_by", sa.BigInteger(),
                                               nullable=True))
    op.create_foreign_key(
        "fk_integration_run_stop_requested_by",
        "integration_run", "app_user",
        ["stop_requested_by"], ["id"],
    )

    op.drop_constraint(op.f("ck_integration_run_status"), "integration_run", type_="check")
    op.create_check_constraint(
        op.f("ck_integration_run_status"),
        "integration_run",
        "status IN ('running', 'succeeded', 'failed', 'skipped', 'stopped')",
    )

    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", _kinds(KINDS_008))


def downgrade() -> None:
    op.execute("UPDATE integration_run SET status = 'failed' WHERE status = 'stopped'")
    op.drop_constraint(op.f("ck_integration_run_status"), "integration_run", type_="check")
    op.create_check_constraint(
        op.f("ck_integration_run_status"),
        "integration_run",
        "status IN ('running', 'succeeded', 'failed', 'skipped')",
    )
    op.drop_constraint("fk_integration_run_stop_requested_by", "integration_run",
                       type_="foreignkey")
    op.drop_column("integration_run", "stop_requested_by")
    op.drop_column("integration_run", "stop_requested_at")

    op.execute("DELETE FROM audit_event WHERE NOT " + _kinds(KINDS_007))
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", _kinds(KINDS_007))

    op.drop_table("integration_control")
