"""A fresh installation starts with no dashboards (owner, 2026-11-01).

0002 seeded a placeholder "Ventas" dashboard in `coming_soon`. The product ships no dashboard: one
appears when a project is applied (020) or when an administrator creates it. This removes the
placeholder from the installations that already ran 0002, and 0002 no longer inserts it.

Only the row the seed created is touched — `managed_by = 'product'`, no report behind it, code
`ventas`. A dashboard a workspace owns (`managed_by = 'workspace'`, with `report_id`) or one an
administrator added is never deleted.

Revision ID: 0046_no_default_dashboards
Revises: 0045_direct_snapshot
Create Date: 2026-11-01
"""
import sqlalchemy as sa

from alembic import op

revision = "0046_no_default_dashboards"
down_revision = "0045_direct_snapshot"
branch_labels = None
depends_on = None

#: The exact row 0002 used to insert, kept here so the guard and the downgrade cannot drift.
PLACEHOLDER = ("ventas", "Ventas", "Resumen, tendencias y productos de tus ventas.",
               "chart-line", 10, "coming_soon")


def upgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM dashboard WHERE code = 'ventas' AND managed_by = 'product' "
        "AND report_id IS NULL"))


def downgrade() -> None:
    code, name, description, icon, order, status = PLACEHOLDER
    op.get_bind().execute(
        sa.text("INSERT INTO dashboard (code, name, description, icon, sort_order, status) "
                "SELECT :c, :n, :d, :i, :o, :s WHERE NOT EXISTS "
                "(SELECT 1 FROM dashboard WHERE code = :c)"),
        {"c": code, "n": name, "d": description, "i": icon, "o": order, "s": status})
