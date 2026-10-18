"""Supabase data sources (feature 016): new data_source kind 'supabase'.

Revision ID: 0010_supabase_source
Revises: 0009_assistant
Create Date: 2026-10-03
"""
import sqlalchemy as sa

from alembic import op

revision = "0010_supabase_source"
down_revision = "0009_assistant"
branch_labels = None
depends_on = None

KIND_CHECK = "ck_data_source_kind"   # created by 0003 (name="kind" + naming convention)


def upgrade() -> None:
    op.drop_constraint(op.f(KIND_CHECK), "data_source", type_="check")
    op.create_check_constraint(op.f(KIND_CHECK), "data_source",
                               "kind IN ('postgresql', 'soap', 'rest', 'supabase')")


def downgrade() -> None:
    # Refuse rather than silently delete configured sources (and their encrypted secrets).
    count = op.get_bind().execute(
        sa.text("SELECT count(*) FROM data_source WHERE kind = 'supabase'")).scalar()
    if count:
        raise RuntimeError(f"{count} fuente(s) Supabase existen: elimínalas antes de bajar de 0010")
    op.drop_constraint(op.f(KIND_CHECK), "data_source", type_="check")
    op.create_check_constraint(op.f(KIND_CHECK), "data_source",
                               "kind IN ('postgresql', 'soap', 'rest')")
