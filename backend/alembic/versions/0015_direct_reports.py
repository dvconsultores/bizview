"""Direct-source reports: per-source permission flag and the direct read log (feature 019).

Revision ID: 0015_direct_reports
Revises: 0014_email_settings_env
Create Date: 2026-10-08
"""
import sqlalchemy as sa

from alembic import op

revision = "0015_direct_reports"
down_revision = "0014_email_settings_env"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"  # see 0003/0011/0013
DIRECT_CHECK = "ck_data_source_direct_reports_kind"
KINDS_014 = (
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
    "integration_paused", "integration_resumed", "integration_schedule_changed",
    "integration_run_stopped",
    "assistant_draft_applied", "assistant_session_archived",
    "assistant_budget_extended",
    "share_link_created", "share_link_revoked", "sharing_toggled",
    "email_settings_updated", "email_test_sent", "email_sent",
    "email_subscription_created", "email_subscription_updated",
    "email_subscription_deleted",
)
KINDS_015 = (*KINDS_014, "source_direct_reports_changed")
NEW_KINDS = KINDS_015[len(KINDS_014):]
OUTCOMES = ("ok", "timeout", "unreachable", "busy", "structure_changed", "not_allowed",
            "product_table", "error")


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_015)}")

    op.add_column("data_source", sa.Column("direct_reports", sa.Boolean(),
                                           server_default=sa.text("false"), nullable=False))
    op.create_check_constraint(op.f(DIRECT_CHECK), "data_source",
                               "direct_reports = false OR kind = 'postgresql'")

    op.create_table(
        "direct_read_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("occurred_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("report_id", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("rows", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("stale_served", sa.Boolean(), server_default=sa.text("false"),
                  nullable=False),
        sa.CheckConstraint(f"outcome IN {_in(OUTCOMES)}", name="outcome"),
        sa.CheckConstraint("duration_ms >= 0", name="duration_ms"),
        sa.CheckConstraint("rows >= 0", name="rows"),
        sa.PrimaryKeyConstraint("id", name="pk_direct_read_log"),
    )
    op.create_index("ix_direct_read_log_occurred_at", "direct_read_log",
                    [sa.text("occurred_at DESC")])
    op.create_index("ix_direct_read_log_report_occurred_at", "direct_read_log",
                    ["report_id", sa.text("occurred_at DESC")])


def downgrade() -> None:
    bind = op.get_bind()
    count = bind.execute(sa.text(
        f"SELECT count(*) FROM audit_event WHERE kind IN {_in(NEW_KINDS)}")).scalar()
    if count:
        raise RuntimeError(
            f"{count} evento(s) de auditoría de reportes directos existen: "
            "elimínalos antes de bajar de 0015")
    enabled = bind.execute(sa.text(
        "SELECT count(*) FROM data_source WHERE direct_reports")).scalar()
    if enabled:
        raise RuntimeError(
            f"{enabled} fuente(s) permiten reportes directos: desactívalo antes de bajar de 0015")

    op.drop_index("ix_direct_read_log_report_occurred_at", table_name="direct_read_log")
    op.drop_index("ix_direct_read_log_occurred_at", table_name="direct_read_log")
    op.drop_table("direct_read_log")

    op.drop_constraint(op.f(DIRECT_CHECK), "data_source", type_="check")
    op.drop_column("data_source", "direct_reports")

    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", f"kind IN {_in(KINDS_014)}")
