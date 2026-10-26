"""Project scope on preview work orders: the request says which project it belongs to (feature 037).

The incident: on `/proyectos/artemisa` the problems panel and the chat showed a *coinmarketcap*
problem, «Aplicar arreglo» answered «El archivo projects/coinmarketcap/… ya no existe», and the
worker failed four previews with «no ve ningún archivo del proyecto» — a message that named neither
the project nor the folder, so a wrong scope and a missing volume looked the same.

`assistant_preview_request` was the only project-scoped row that could not answer "which project?":
it carried `session_id` and the worker derived the folder from the conversation. This migration
adds `project_id`, backfills it from the session, and removes the work orders that cannot be
attributed (a queued preview without a conversation cannot run; they are work orders, not data).

Every other project-scoped table (`assistant_session`, `project_file_revision`,
`assistant_command_run`, `assistant_auto_run`) already carried `project_id` NOT NULL.

Revision ID: 0030_project_scope
Revises: 0029_assistant_history
Create Date: 2026-10-26
"""
import logging

import sqlalchemy as sa

from alembic import op

log = logging.getLogger("alembic.project_scope")

revision = "0030_project_scope"
down_revision = "0029_assistant_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assistant_preview_request",
                  sa.Column("project_id", sa.BigInteger(), nullable=True))
    bind = op.get_bind()

    # Backfill from the conversation; a request whose conversation is gone cannot be attributed.
    backfilled = bind.execute(sa.text(
        "UPDATE assistant_preview_request AS r "
        "SET project_id = s.project_id "
        "FROM assistant_session AS s "
        "WHERE s.id = r.session_id AND r.project_id IS NULL")).rowcount
    total = bind.execute(sa.text("SELECT count(*) FROM assistant_preview_request")).scalar() or 0
    orphans = bind.execute(sa.text(
        "SELECT count(*) FROM assistant_preview_request WHERE project_id IS NULL")).scalar() or 0
    if orphans:
        bind.execute(sa.text("DELETE FROM assistant_preview_request WHERE project_id IS NULL"))
    # The quarantine report: one line, exact counts, no secrets.
    log.info("project scope 0030: assistant_preview_request — %s rows, %s attributed from their "
             "conversation, %s quarantined (removed: a queue row without a conversation cannot "
             "run); other project-scoped tables already carried project_id NOT NULL",
             total, backfilled, orphans)

    op.alter_column("assistant_preview_request", "project_id", nullable=False)
    op.create_foreign_key(op.f("fk_assistant_preview_request_project_id"),
                          "assistant_preview_request", "project", ["project_id"], ["id"],
                          ondelete="CASCADE")
    op.create_index(op.f("ix_assistant_preview_request_project_id"),
                    "assistant_preview_request", ["project_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_assistant_preview_request_project_id"),
                  table_name="assistant_preview_request")
    op.drop_constraint(op.f("fk_assistant_preview_request_project_id"),
                       "assistant_preview_request", type_="foreignkey")
    op.drop_column("assistant_preview_request", "project_id")
