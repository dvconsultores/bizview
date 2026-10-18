"""Spec Kit commands in the chat: one run per command, revisions linked to their run (feature 021).

Revision ID: 0019_command_runs
Revises: 0018_projects
Create Date: 2026-10-11
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0019_command_runs"
down_revision = "0018_projects"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)
STATUSES = ("running", "waiting", "completed", "interrupted", "failed")


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.create_table(
        "assistant_command_run",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("arguments", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("spec", sa.Text(), nullable=True),
        sa.Column("reserved_number", sa.SmallInteger(), nullable=True),
        sa.Column("locale", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("pending", pg.JSONB(), nullable=True),
        sa.Column("resumed_from", sa.BigInteger(), nullable=True),
        sa.Column("files", pg.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("ended_at", TS, nullable=True),
        sa.CheckConstraint("command ~ '^(speckit-[a-z]+|ayuda)$'",
                           name=op.f("ck_assistant_command_run_command")),
        sa.CheckConstraint("char_length(arguments) <= 4000",
                           name=op.f("ck_assistant_command_run_arguments_len")),
        sa.CheckConstraint("spec IS NULL OR spec ~ '^[0-9]{3}-[a-z0-9-]{1,60}$'",
                           name=op.f("ck_assistant_command_run_spec")),
        sa.CheckConstraint("locale IN ('es', 'en')", name=op.f("ck_assistant_command_run_locale")),
        sa.CheckConstraint(f"status IN {_in(STATUSES)}",
                           name=op.f("ck_assistant_command_run_status")),
        sa.CheckConstraint("tokens >= 0", name=op.f("ck_assistant_command_run_tokens")),
        sa.ForeignKeyConstraint(["session_id"], ["assistant_session.id"], ondelete="CASCADE",
                                name=op.f("fk_assistant_command_run_session_id")),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE",
                                name=op.f("fk_assistant_command_run_project_id")),
        sa.ForeignKeyConstraint(["message_id"], ["assistant_message.id"], ondelete="SET NULL",
                                name=op.f("fk_assistant_command_run_message_id")),
        sa.ForeignKeyConstraint(["resumed_from"], ["assistant_command_run.id"],
                                ondelete="SET NULL",
                                name=op.f("fk_assistant_command_run_resumed_from")),
    )
    # One active command per conversation (race-safe).
    op.create_index("ux_command_run_active", "assistant_command_run", ["session_id"],
                    unique=True, postgresql_where=sa.text("status IN ('running', 'waiting')"))
    op.create_index("ix_command_run_session", "assistant_command_run",
                    ["session_id", sa.text("started_at DESC")])
    op.create_index("ix_command_run_project", "assistant_command_run",
                    ["project_id", sa.text("started_at DESC")])
    op.add_column("project_file_revision",
                  sa.Column("command_run_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(op.f("fk_project_file_revision_command_run_id"),
                          "project_file_revision", "assistant_command_run",
                          ["command_run_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_project_file_revision_command_run", "project_file_revision",
                    ["command_run_id"])


def downgrade() -> None:
    op.drop_index("ix_project_file_revision_command_run", table_name="project_file_revision")
    op.drop_constraint(op.f("fk_project_file_revision_command_run_id"), "project_file_revision",
                       type_="foreignkey")
    op.drop_column("project_file_revision", "command_run_id")
    op.drop_table("assistant_command_run")
