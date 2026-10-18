"""Daily rollups for materialized reports and per-run rollup outcomes (feature 005, amendment
2026-10-08, FR-A06/FR-A07).

Revision ID: 0016_run_transform
Revises: 0015_direct_reports
Create Date: 2026-10-09
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0016_run_transform"
down_revision = "0015_direct_reports"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "report_rollup",
        sa.Column("report_id", sa.Text(), nullable=False),
        sa.Column("schema_name", sa.Text(), nullable=False),
        sa.Column("table_name", sa.Text(), nullable=False),
        sa.Column("definition_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("source_runs", pg.JSONB(), server_default=sa.text("'{}'::jsonb"),
                  nullable=False),
        sa.Column("columns", pg.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("rows", sa.BigInteger(), nullable=True),
        sa.Column("built_at", TS, nullable=True),
        sa.Column("refreshed_at", TS, nullable=True),
        sa.Column("refresh_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('ready', 'stale', 'failed')", name="status"),
        sa.CheckConstraint("rows IS NULL OR rows >= 0", name="rows"),
        sa.CheckConstraint("refresh_ms IS NULL OR refresh_ms >= 0", name="refresh_ms"),
        sa.PrimaryKeyConstraint("report_id", name="pk_report_rollup"),
    )
    op.add_column("integration_run", sa.Column("rollups", pg.JSONB(),
                                               server_default=sa.text("'{}'::jsonb"),
                                               nullable=False))


def downgrade() -> None:
    op.drop_column("integration_run", "rollups")
    op.drop_table("report_rollup")
