"""The four official identities, and the chrome tokens built-ins paint with (feature 051).

Feature 047 turned themes into data but left the application's own chrome outside the contract:
`index.css` held one set of literals per light/dark mode, so applying a theme repainted the charts
and nothing else. This migration brings the library up to the widened contract:

* `clasico` gains the full `app` token map, copied from the literals `index.css` carried, so its
  appearance cannot drift — the appearance the installation has today is now data, not a stylesheet
  default;
* `impacto` and `contraste` gain their identity (chrome tokens and the shape enums that make them
  different beyond colour), and `daltonico`/`monocromo` keep their palettes with a chrome of their
  own;
* `elegante` is added, and `appearance_settings.palette_preset` accepts it.

Nothing is deleted and no report loses the theme it names: the built-in rows are replaced by the
files this build ships, which is what 047 already declared a built-in to be.

Revision ID: 0048_official_themes
Revises: 0047_project_limits
Create Date: 2026-11-02
"""
import json
from pathlib import Path

import sqlalchemy as sa

from alembic import op

revision = "0048_official_themes"
down_revision = "0047_project_limits"
branch_labels = None
depends_on = None

THEMES_DIR = Path(__file__).resolve().parents[2] / "app" / "reports" / "themes"
BUILTINS = ("impacto", "clasico", "elegante", "monocromo", "contraste", "daltonico")
#: The ids the constraint accepted before this revision, and the one it adds.
BEFORE = ("impacto", "clasico", "monocromo", "contraste", "daltonico")
ADDED = "elegante"
# The conventional name `app/models.py` gives it: ck_<table>_<constraint>.
APPEARANCE_CHECK = "ck_appearance_settings_appearance_palette"


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def _rows() -> list[dict]:
    """The product's themes, from the files the web app and the PDF both read."""
    rows = []
    for theme_id in BUILTINS:
        data = json.loads((THEMES_DIR / f"{theme_id}.json").read_text(encoding="utf-8"))
        rows.append({"id": theme_id, "name": data["name"], "name_en": data["name_en"],
                     "version": int(data.get("version") or 1), "tokens": data})
    return rows


def upgrade() -> None:
    op.drop_constraint(op.f(APPEARANCE_CHECK), "appearance_settings", type_="check")
    op.create_check_constraint(op.f(APPEARANCE_CHECK), "appearance_settings",
                               f"palette_preset IN {_in(BUILTINS)}")

    # Upsert: a built-in row is the product's file, not the installation's, so the file wins.
    table = sa.table("theme", sa.column("id", sa.Text), sa.column("name", sa.Text),
                     sa.column("name_en", sa.Text), sa.column("version", sa.Integer),
                     sa.column("tokens", sa.dialects.postgresql.JSONB),
                     sa.column("origin", sa.Text))
    bind = op.get_bind()
    for row in _rows():
        present = bind.execute(
            sa.select(sa.func.count()).select_from(table).where(table.c.id == row["id"])
        ).scalar_one()
        if present:
            bind.execute(table.update().where(table.c.id == row["id"]).values(**row))
        else:
            bind.execute(table.insert().values(origin="builtin", **row))


def downgrade() -> None:
    """Back to the five ids — but only if nothing uses `elegante`.

    A report or an installation that names it keeps working if the row stays, so the downgrade
    refuses instead of leaving a dangling reference (the same rule 0042 applies to the library).
    """
    bind = op.get_bind()
    used = bind.execute(
        sa.text("SELECT count(*) FROM appearance_settings WHERE theme_id = :id OR palette_preset = :id"),
        {"id": ADDED},
    ).scalar_one()
    if used:
        raise RuntimeError(
            f"0048_official_themes cannot be downgraded while an installation uses '{ADDED}': "
            "choose another theme first"
        )
    bind.execute(sa.text("DELETE FROM theme WHERE id = :id AND origin = 'builtin'"), {"id": ADDED})
    op.drop_constraint(op.f(APPEARANCE_CHECK), "appearance_settings", type_="check")
    op.create_check_constraint(op.f(APPEARANCE_CHECK), "appearance_settings",
                               f"palette_preset IN {_in(BEFORE)}")
