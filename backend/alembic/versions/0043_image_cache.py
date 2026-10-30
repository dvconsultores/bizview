"""The image cache: one row per URL a report asked a picture from (feature 044, US3).

A report may declare an integration column of kind `image_url`, and the worker fetches each new
value once so viewers never contact the third party. The bytes live on disk, content-addressed by
their hash (two URLs that return the same picture share one file); this table keeps the URL, the
hash, the size and the outcome.

`status` is `ok` or `failed`, and `sha256` is present exactly when the row succeeded — a failed
fetch keeps its reason in `error` and is retried at most once a day. No project foreign key on
purpose: a picture is shared by every project that asks for the same URL.

Revision ID: 0043_image_cache
Revises: 0040_auto_run_stages
Create Date: 2026-10-29
"""
import sqlalchemy as sa

from alembic import op

revision = "0043_image_cache"
down_revision = "0040_auto_run_stages"
branch_labels = None
depends_on = None

TABLE = "image_cache"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text()),
        sa.Column("ext", sa.Text()),
        sa.Column("bytes", sa.Integer()),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.UniqueConstraint("url", name=op.f("ux_image_cache_url")),
        sa.CheckConstraint("status IN ('ok', 'failed')", name=op.f("ck_image_cache_status")),
        sa.CheckConstraint("bytes IS NULL OR bytes >= 0", name=op.f("ck_image_cache_bytes")),
        sa.CheckConstraint("(status = 'ok') = (sha256 IS NOT NULL)",
                           name=op.f("ck_image_cache_sha_on_ok")),
    )
    op.create_index(op.f("ix_image_cache_sha256"), TABLE, ["sha256"])
    op.create_index(op.f("ix_image_cache_fetched"), TABLE, ["fetched_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_image_cache_fetched"), table_name=TABLE)
    op.drop_index(op.f("ix_image_cache_sha256"), table_name=TABLE)
    op.drop_table(TABLE)
