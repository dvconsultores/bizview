"""Previews carry their draft: the worker no longer needs the projects folder.

The worker processes "Vista previa" requests, and it only mounted `attachments` in the deployed
compose file, so it read an empty project folder, recorded a "succeeded" preview over no files and
left the workspace saying "el borrador cambió desde la última vista previa" with Apply disabled
(owner report, 2026-10-22). The request now stores the draft the backend validated, and the worker
previews exactly those files. The volume mount is still added (it is the correct deployment), but a
preview no longer depends on it.

Revision ID: 0026_preview_request_files
Revises: 0025_unlimited_ai
Create Date: 2026-10-23
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0026_preview_request_files"
down_revision = "0025_unlimited_ai"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assistant_preview_request", sa.Column("files", pg.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("assistant_preview_request", "files")
