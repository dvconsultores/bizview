"""Unlimited AI: drop the conversation token budget (feature 017 budget retired).

The owner's rule (2026-10-21): "make the ai unlimited". `tokens_used` stays as telemetry — the run
summary and the status bar still report it — but nothing stops a turn or a run on it.

Revision ID: 0025_unlimited_ai
Revises: 0024_autonomous_mode
Create Date: 2026-10-21
"""
import sqlalchemy as sa

from alembic import op

revision = "0025_unlimited_ai"
down_revision = "0024_autonomous_mode"
branch_labels = None
depends_on = None

# 0009 created the CHECK as `name="token_budget"` and the metadata convention prefixed it twice, so
# the name in a running database is not derivable from here: look it up instead of guessing.
# (Downgrade recreates it with the name a 0009-built database has.)
LEGACY_CHECK = "ck_assistant_session_ck_assistant_session_token_budget"


def _check_name(bind) -> str | None:
    return bind.execute(sa.text(
        """
        SELECT c.conname
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE t.relname = 'assistant_session'
          AND n.nspname = current_schema()
          AND c.contype = 'c'
          AND pg_get_constraintdef(c.oid) ILIKE '%token_budget%'
        """
    )).scalar()


def upgrade() -> None:
    name = _check_name(op.get_bind())
    if name:
        op.execute(f'ALTER TABLE assistant_session DROP CONSTRAINT "{name}"')
    op.drop_column("assistant_session", "token_budget")


def downgrade() -> None:
    # The old column was NOT NULL with a CHECK; 200000 was what a new conversation started with.
    op.add_column("assistant_session",
                  sa.Column("token_budget", sa.Integer(), nullable=True,
                            server_default=sa.text("200000")))
    op.execute("UPDATE assistant_session SET token_budget = 200000 WHERE token_budget IS NULL")
    op.alter_column("assistant_session", "token_budget", nullable=False,
                    server_default=None)
    op.execute(f'ALTER TABLE assistant_session ADD CONSTRAINT "{LEGACY_CHECK}" '
               "CHECK (token_budget > 0)")
