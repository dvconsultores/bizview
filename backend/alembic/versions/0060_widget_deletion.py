"""Deleting a widget (feature 065, follow-up): one more audit kind, `widget_deleted`.

A revoked or expired widget stayed in the dashboard's list for ever; an admin may now delete one,
in any state. No table changes: `dashboard_widget_site` already goes with its widget (ON DELETE
CASCADE). Only the audit CHECK grows, and it is rebuilt from what the database accepts today plus
the new kind, so it can never narrow (0056's lesson, the same rule 0059 follows).

Revision ID: 0060_widget_deletion
Revises: 0059_dashboard_widgets
Create Date: 2026-11-24
"""
import re

import sqlalchemy as sa

from alembic import op

revision = "0060_widget_deletion"
down_revision = "0059_dashboard_widgets"
branch_labels = None
depends_on = None

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"
NEW_KINDS = ("widget_deleted",)


def upgrade() -> None:
    accepted = _accepted_now()
    if not accepted:
        # 0059 always leaves this constraint behind; without it there is nothing safe to rebuild.
        raise RuntimeError(f"audit_event has no {AUDIT_CHECK} constraint to extend")
    for kind in NEW_KINDS:
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
    # Order kept, duplicates dropped: a repeated literal would only make the CHECK longer.
    return list(dict.fromkeys(re.findall(r"'([a-z0-9_]+)'", str(row[0]))))


def _in(values: tuple[str, ...]) -> str:
    return "(" + ", ".join(f"'{value}'" for value in values) + ")"


def downgrade() -> None:
    # The audit CHECK is not narrowed: audit history is immutable, and a `widget_deleted` row
    # written after this upgrade must stay readable.
    pass
