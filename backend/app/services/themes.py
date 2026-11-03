"""The theme library (feature 047): built-ins, uploads and the themes projects bring.

A theme is data an author wrote outside Bizview against `cli/bizview_cli/schemas/theme.schema.json`.
This module is the only place that decides whether a theme may enter, replace, leave or be applied:
the three callers (the super user's upload, the project import, the bootstrap) all come through
here, so an author cannot reach a different answer through a different door.
"""
from collections.abc import Iterable
from typing import Any

import yaml
from bizview_cli.theme import MAX_BYTES, Problem, derive_tokens, load_theme_text, validate_theme
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import THEME_ORIGINS, AppearanceSettings, Project, Theme

BUILTIN_ORIGIN = "builtin"
BUILTIN_IDS: tuple[str, ...] = ("impacto", "clasico", "elegante", "monocromo", "contraste",
                                "daltonico")
# A theme file is a few hundred bytes; the cap is the schema's, in characters so pydantic can hold
# the body before the validator measures bytes.
MAX_UPLOAD_CHARS = MAX_BYTES
UPLOAD_ORIGIN = "upload"
PROJECT_ORIGIN = "project"
DEFAULT_THEME = "impacto"


def parse(text: str) -> tuple[dict | None, list[Problem]]:
    """An authored file, and every reason it cannot be used (shape and look, one answer)."""
    data, problems = load_theme_text(text)
    if data is not None and not isinstance(data, dict):
        return None, [Problem("/", "unparsable", "a theme is a mapping of tokens")]
    return data, problems


def get(db: Session, theme_id: str) -> Theme | None:
    return db.get(Theme, theme_id)


def listing(db: Session) -> list[Theme]:
    """Every theme, built-ins first, then the install's own, then what projects brought."""
    order = {origin: index for index, origin in enumerate(THEME_ORIGINS)}
    rows = list(db.scalars(select(Theme)))
    return sorted(rows, key=lambda row: (order.get(row.origin, 99), row.name.lower()))


def body(row: Theme) -> dict[str, Any]:
    """A row as the API shows it: the tokens an author wrote, and where they came from."""
    return {"id": row.id, "name": row.name, "name_en": row.name_en, "version": row.version,
            "origin": row.origin, "project": row.project_id, "tokens": row.tokens}


def as_yaml(row: Theme) -> str:
    """The theme as the author wrote it, back out as a file."""
    return yaml.safe_dump(row.tokens, sort_keys=False, allow_unicode=True, width=100)


def etag(row: Theme) -> str:
    """A version of the row the browser can compare: the moment it last changed, and the count."""
    return f'"{row.updated_at.timestamp():.0f}-{row.version}"'


def tokens(row: Theme, mode: str) -> dict[str, str]:
    """The runtime roles a renderer reads for one mode (series1..8, kpi_text, …)."""
    return derive_tokens(row.tokens, mode)


def installation(db: Session) -> str:
    """The theme the installation uses: its choice, else the preset it chose before 047, else
    `impacto` — which the migration seeds and no door can delete."""
    row = db.get(AppearanceSettings, 1)
    if row is None:
        return DEFAULT_THEME
    if row.theme_id and db.get(Theme, row.theme_id) is not None:
        return row.theme_id
    if row.palette_preset and db.get(Theme, row.palette_preset) is not None:
        return row.palette_preset
    return DEFAULT_THEME


def names_theme(definition: Any, theme_id: str) -> bool:
    """Whether a report definition asks for this theme, by the new name or the deprecated one."""
    layout = definition.get("layout") if isinstance(definition, dict) else None
    theme = layout.get("theme") if isinstance(layout, dict) else None
    if not isinstance(theme, dict):
        return False
    return theme_id in (theme.get("id"), theme.get("palette"))


def reports_using(db: Session, theme_id: str) -> list[str]:
    """The report ids that name this theme — the applied snapshot and every live project.

    The applied snapshot is what the product renders today; a project's working copy matters
    because its next apply would break the same way. A theme in use cannot be deleted (FR-015).
    """
    found: set[str] = set()
    from app.workspace.service import active

    version = active(db)
    for report_id, item in ((version.artifacts.get("reports") if version is not None else {})
                            or {}).items():
        if names_theme(item.get("definition"), theme_id):
            found.add(report_id)
    from app.projects import fs

    for project in db.scalars(select(Project).where(Project.deleted_at.is_(None))):
        folder = fs.project_root(project.slug) / "reports"
        for path in folder.glob("*/report.yaml"):
            try:
                definition = yaml.safe_load(path.read_text("utf-8"))
            except (OSError, yaml.YAMLError, UnicodeDecodeError):
                continue
            if names_theme(definition, theme_id):
                found.add(path.parent.name)
    return sorted(found)


def save(db: Session, data: dict, *, origin: str = UPLOAD_ORIGIN, project_id: int | None = None,
         created_by: int | None = None) -> tuple[Theme, bool]:
    """Store a validated theme; returns the row and whether it replaced an earlier one.

    Replacing bumps `version` — the author's counter is the file's, this one says how many times
    the installation took a new copy — and keeps the origin and the project it belongs to.
    """
    assert origin in THEME_ORIGINS, origin
    row = db.get(Theme, str(data["id"]))
    if row is None:
        row = Theme(id=str(data["id"]), name=str(data["name"]), name_en=str(data["name_en"]),
                    version=int(data.get("version") or 1), tokens=data, origin=origin,
                    project_id=project_id, created_by=created_by)
        db.add(row)
        db.flush()
        return row, False
    row.name, row.name_en = str(data["name"]), str(data["name_en"])
    row.version = int(row.version) + 1
    row.tokens = data
    db.flush()
    return row, True


def builtin_files() -> list[dict]:
    """The product's own themes, as authored: the files the web app and the PDF both read."""
    from app.reports.palette import PRESET_IDS, load_theme

    return [load_theme(preset) for preset in PRESET_IDS]


def refresh_builtins(db: Session, themes: Iterable[dict]) -> int:
    """Bring the product's own themes up to date in an installation that never touched them.

    A shipped colour correction has to reach installations that already migrated, so a `builtin`
    row is rewritten from the product's file when it differs; a `version` the author did not bump
    is not an edit, the tokens are what changed. Returns how many rows were rewritten.
    """
    changed = 0
    for data in themes:
        row = db.get(Theme, str(data["id"]))
        if row is None:
            save(db, data, origin=BUILTIN_ORIGIN)
            changed += 1
        elif row.origin == BUILTIN_ORIGIN and (row.tokens != data or row.name != data["name"]
                                              or row.name_en != data["name_en"]):
            row.tokens, row.name, row.name_en = data, str(data["name"]), str(data["name_en"])
            changed += 1
    return changed


def validated(data: dict) -> list[Problem]:
    """The look checks, for a theme that arrived parsed by some other route."""
    return validate_theme(data)


def project_themes(db: Session, project_id: int) -> list[Theme]:
    """The themes a project brought, newest first: what its export and its deletion care about."""
    return list(db.scalars(select(Theme).where(Theme.project_id == project_id)
                           .order_by(Theme.id)))


def drop_project_themes(db: Session, project_id: int) -> int:
    """Remove the themes a project brought (FR-016): they were never the installation's."""
    rows = project_themes(db, project_id)
    for row in rows:
        db.delete(row)
    db.flush()
    return len(rows)


def free_id(db: Session, theme_id: str) -> str:
    """`<id>-2`, `<id>-3`…: the first id neither the library nor the product is using."""
    if get(db, theme_id) is None and theme_id not in BUILTIN_IDS:
        return theme_id
    for suffix in range(2, 100):
        candidate = f"{theme_id[:36]}-{suffix}"
        if get(db, candidate) is None and candidate not in BUILTIN_IDS:
            return candidate
    raise ValueError(f"no free id for {theme_id}")
