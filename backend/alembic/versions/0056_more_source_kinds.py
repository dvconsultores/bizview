"""Five more kinds of data source (feature 061).

A customer's ERP runs on MySQL or SQL Server, a small system exports a `.sqlite` file, a consultant
lands data in BigQuery and a business keeps prices in a Google Sheet. Until now the `data_source`
kind could only be PostgreSQL, Supabase, REST or SOAP, so none of those customers could be served.

The column keeps its shape and only the CHECK widens. The list of kinds the product shows comes from
`app/sources/connectors/registry.py`; this constraint mirrors it so a kind that is not in the code
cannot be stored. Downgrading refuses while any of the new kinds exists, exactly as 0010 did for
Supabase: dropping the constraint would otherwise leave rows the old CHECK forbids.

Revision ID: 0056_more_source_kinds
Revises: 0055_source_connection_limits
Create Date: 2026-11-08
"""
import re

import sqlalchemy as sa

from alembic import op

revision = "0056_more_source_kinds"
down_revision = "0055_source_connection_limits"
branch_labels = None
depends_on = None

KIND_CHECK = "ck_data_source_kind"

#: The audit CHECK, double-prefixed by the naming convention because 0055 named it explicitly.
#: 0055 rebuilt it from a frozen copy of 0054's list, and two literals of that copy ran together
#: (`"project_reverted"` + newline + `"starter_downloaded""mail_list_created"`), so Python
#: concatenated three names into one: the constraint it created forbade `starter_downloaded`, the
#: three `mail_list_*` kinds and `mail_send_resent`. A database that ran it refuses the audit event
#: of a starter download and of every mailing-list action. This revision rebuilds it.
AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"

#: Every audit kind the constraint must accept: what the product writes today plus every kind a
#: database may already hold — the removed in-app agent's `assistant_*` events and 052's first
#: `source_chat_*` pass, because audit history is immutable and a migration may not delete or
#: rewrite it. Frozen here on purpose: importing `app.models` (which this revision did at first)
#: makes an applied migration change its meaning whenever the model is edited, and `AUDIT_KINDS`
#: alone is what may be *written*, not what may be *found* — building the CHECK from it is exactly
#: what made this upgrade fail on an installation with historical rows.
AUDIT_KINDS_0056 = (
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
    "email_test_sent", "email_sent", "email_subscription_created", "email_subscription_updated",
    "email_subscription_deleted", "source_direct_reports_changed", "project_created",
    "project_updated", "project_deleted", "project_purged", "project_applied",
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
    "mail_send_resent", "integration_busy",
)

#: Frozen copies: a database that already holds these breaks here if the list is shortened, so the
#: migration keeps its own list instead of reading `models.SOURCE_KINDS`.
KINDS_0055 = ("postgresql", "soap", "rest", "supabase")
KINDS_0056 = ("postgresql", "soap", "rest", "supabase", "sqlite", "mysql", "mssql", "bigquery",
              "sheets")


def _check(kinds: tuple[str, ...]) -> str:
    return "kind IN (" + ", ".join(f"'{kind}'" for kind in kinds) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(KIND_CHECK), "data_source", type_="check")
    op.create_check_constraint(op.f(KIND_CHECK), "data_source", _check(KINDS_0056))
    _repair_audit_kinds()


def _repair_audit_kinds() -> None:
    """Rebuild the audit CHECK so it grows and never narrows.

    The list above is complete for every kind this repository has ever written, but an
    installation may hold a kind nobody here knows about (a build that shipped one and was rolled
    back). Reading what the live constraint already accepts and unioning it keeps the promise 0048
    wrote down: this constraint may only ever grow.
    """
    accepted = list(AUDIT_KINDS_0056)
    for kind in _accepted_now():
        if kind not in accepted:
            accepted.append(kind)
    op.drop_constraint(op.f(AUDIT_CHECK), "audit_event", type_="check")
    op.create_check_constraint(op.f(AUDIT_CHECK), "audit_event", _check(tuple(accepted)))


def _accepted_now() -> list[str]:
    """The kinds the constraint in place accepts today, in the order it lists them."""
    row = op.get_bind().execute(
        sa.text("SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
                "WHERE c.conname = :name AND c.conrelid = to_regclass('audit_event')"),
        {"name": AUDIT_CHECK}).first()
    if row is None:
        return []
    return re.findall(r"'([a-z0-9_]+)'", str(row[0]))


def downgrade() -> None:
    # Refuse rather than silently delete configured sources (and their encrypted secrets).
    count = op.get_bind().execute(
        sa.text("SELECT count(*) FROM data_source WHERE kind <> ALL(:kinds)"),
        {"kinds": list(KINDS_0055)}).scalar()
    if count:
        raise RuntimeError(
            f"{count} fuente(s) de los tipos nuevos existen: elimínalas antes de bajar de 0056")
    op.drop_constraint(op.f(KIND_CHECK), "data_source", type_="check")
    op.create_check_constraint(op.f(KIND_CHECK), "data_source", _check(KINDS_0055))
    # The audit repair is not undone: the list it left is the one the code writes, and no kind
    # 0055 carried is missing from it.
