"""A command's arguments may be as long as the message that carries them (feature 039).

The incident: pasting a real brief (7 629 characters, the `coinmarketcap` panorama prompt) into
`/speckit-all` answered «Los argumentos del comando no pueden superar 4000 caracteres». The
composer already caps a message at `MAX_USER_TEXT` (8 000), so the 4 000 ceiling on the command's
arguments only refused briefs the product otherwise accepts — and the brief *is* the message after
the command token.

This migration widens `assistant_command_run.arguments` to the message ceiling
(`MAX_USER_TEXT`, now 20 000 characters).

Revision ID: 0031_command_args_length
Revises: 0030_project_scope
Create Date: 2026-10-27
"""
from alembic import op

revision = "0031_command_args_length"
down_revision = "0030_project_scope"
branch_labels = None
depends_on = None

# The final name, as every migration of this repo does it: `op.f` marks it final at each call site
# (at module scope the proxy is not established yet, which breaks `alembic heads`).
CONSTRAINT = "ck_assistant_command_run_arguments_len"
TABLE = "assistant_command_run"
OLD = "char_length(arguments) <= 4000"
NEW = "char_length(arguments) <= 20000"


def upgrade() -> None:
    op.drop_constraint(op.f(CONSTRAINT), TABLE, type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), TABLE, NEW)


def downgrade() -> None:
    # A downgrade cannot keep rows above the old ceiling; say so instead of failing mid-way.
    op.execute(f"UPDATE {TABLE} SET arguments = left(arguments, 4000) "
               f"WHERE char_length(arguments) > 4000")
    op.drop_constraint(op.f(CONSTRAINT), TABLE, type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), TABLE, OLD)
