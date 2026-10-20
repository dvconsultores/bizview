"""Commands resolve their spec from the argument; misrouted and budget runs (028 defect fix).

Revision ID: 0023_command_spec_resolution
Revises: 0022_chat_delete
Create Date: 2026-10-19
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0023_command_spec_resolution"
down_revision = "0022_chat_delete"
branch_labels = None
depends_on = None

STATUSES = ("running", "waiting", "completed", "misrouted", "budget", "interrupted", "failed")
OLD_STATUSES = ("running", "waiting", "completed", "interrupted", "failed")
RESOLVE_SOURCES = ("argument", "number", "title", "current")
CHECK = "ck_assistant_command_run_status"


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.add_column("assistant_command_run", sa.Column("resolved_from", sa.Text(), nullable=True))
    op.add_column("assistant_command_run",
                  sa.Column("forced", sa.Boolean(), nullable=False,
                            server_default=sa.text("false")))
    op.add_column("assistant_command_run", sa.Column("result", pg.JSONB(), nullable=True))
    op.create_check_constraint(
        op.f("ck_assistant_command_run_resolved_from"), "assistant_command_run",
        f"resolved_from IS NULL OR resolved_from IN {_in(RESOLVE_SOURCES)}")
    op.drop_constraint(op.f(CHECK), "assistant_command_run", type_="check")
    op.create_check_constraint(op.f(CHECK), "assistant_command_run",
                               f"status IN {_in(STATUSES)}")


def downgrade() -> None:
    # The old constraint does not know the two new statuses; map them to the closest old one.
    op.execute("UPDATE assistant_command_run SET status = 'completed' "
               "WHERE status = 'misrouted'")
    op.execute("UPDATE assistant_command_run SET status = 'interrupted' WHERE status = 'budget'")
    op.drop_constraint(op.f(CHECK), "assistant_command_run", type_="check")
    op.create_check_constraint(op.f(CHECK), "assistant_command_run",
                               f"status IN {_in(OLD_STATUSES)}")
    op.drop_constraint(op.f("ck_assistant_command_run_resolved_from"),
                       "assistant_command_run", type_="check")
    op.drop_column("assistant_command_run", "result")
    op.drop_column("assistant_command_run", "forced")
    op.drop_column("assistant_command_run", "resolved_from")
