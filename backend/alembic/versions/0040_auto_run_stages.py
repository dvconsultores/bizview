"""`analyze` and `verify` are stages of an Auto run (feature 040, Step 0).

The production `/speckit-all` run ended with «Ocurrió un error inesperado (IntegrityError)» right
after the converge stage: 039 added `/speckit-verify` and mapped it to the stage `verify`, but the
CHECK constraint on `assistant_auto_run.stage` still listed only the stages of 028, so writing it
violated `ck_assistant_auto_run_stage`.

Revision ID: 0040_auto_run_stages
Revises: 0031_command_args_length
Create Date: 2026-10-28
"""
from alembic import op

revision = "0040_auto_run_stages"
down_revision = "0031_command_args_length"
branch_labels = None
depends_on = None

TABLE = "assistant_auto_run"
# 0024 created the constraint with its full name, so the naming convention prefixed it again:
# the object in the database is `ck_assistant_auto_run_ck_assistant_auto_run_stage`.
CONSTRAINT = "ck_assistant_auto_run_ck_assistant_auto_run_stage"
OLD = ("discover", "specify", "clarify", "plan", "tasks", "implement", "converge", "preview",
       "apply")
NEW = ("discover", "specify", "clarify", "plan", "tasks", "analyze", "implement", "converge",
       "verify", "preview", "apply")


def _clause(values: tuple[str, ...]) -> str:
    listed = ", ".join(f"'{value}'" for value in values)
    return f"stage IS NULL OR stage IN ({listed})"


def upgrade() -> None:
    op.drop_constraint(op.f(CONSTRAINT), TABLE, type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), TABLE, _clause(NEW))


def downgrade() -> None:
    # A row in a stage the old constraint does not know would block the downgrade: clear it first,
    # so the constraint can be recreated (the stage is bookkeeping, not data).
    op.execute(f"UPDATE {TABLE} SET stage = NULL WHERE stage IN ('analyze', 'verify')")
    op.drop_constraint(op.f(CONSTRAINT), TABLE, type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), TABLE, _clause(OLD))
