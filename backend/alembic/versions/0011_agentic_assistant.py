"""Agentic assistant columns, stats and budget-extension audit kind (feature 017).

Revision ID: 0011_agentic_assistant
Revises: 0010_supabase_source
Create Date: 2026-10-03
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0011_agentic_assistant"
down_revision = "0010_supabase_source"
branch_labels = None
depends_on = None

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"   # see 0003
KINDS_010 = (
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
)
KINDS_011 = (*KINDS_010, "assistant_budget_extended")


def _kinds(kinds) -> str:
    return "kind IN (" + ", ".join(f"'{k}'" for k in kinds) + ")"


def upgrade() -> None:
    op.add_column("assistant_session",
                  sa.Column("working_state", pg.JSONB(), nullable=True))
    op.add_column("assistant_session",
                  sa.Column("query_checks", pg.JSONB(), nullable=True))
    op.add_column("assistant_session",
                  sa.Column("stats", pg.JSONB(), nullable=False,
                            server_default=sa.text("'{}'::jsonb")))
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", _kinds(KINDS_011))


def downgrade() -> None:
    count = op.get_bind().execute(
        sa.text("SELECT count(*) FROM audit_event "
                "WHERE kind = 'assistant_budget_extended'")).scalar()
    if count:
        raise RuntimeError(
            f"{count} evento(s) de auditoría 'assistant_budget_extended' existen: "
            "elimínalos antes de bajar de 0011")
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", _kinds(KINDS_010))
    op.drop_column("assistant_session", "stats")
    op.drop_column("assistant_session", "query_checks")
    op.drop_column("assistant_session", "working_state")
