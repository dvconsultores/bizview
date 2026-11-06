"""The starter pack of feature 057, on the server side.

One renderer (`bizview_cli.starter`) writes every file; here we add the optional structure of a
registered source, measure the result against the two import allowances of 049, and answer the
bytes. Nothing else in the product renders a starter zip, so the download, the published template
and `bizview init project` cannot disagree.
"""
from __future__ import annotations

import os
from pathlib import Path

from bizview_cli import budgets as shared_budgets
from bizview_cli import layout
from bizview_cli import starter as pack
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import ApiError, not_found
from app.i18n import M
from app.projects import budgets as project_budgets
from app.projects import zip as project_zip

#: Where a deployment keeps the committed template. The repository root is the default: the file is
#: committed there and the image copies it.
TEMPLATE_ENV = "STARTER_TEMPLATE_PATH"


def _source_structure(db: Session, source: str) -> tuple[dict[str, str], str | None]:
    """`sources/<name>/structure.{md,json}` for one registered source, or no files and a reason.

    Structure only: the generator of 048/052 never carries a credential, a host or a row value
    (constitution VIII). A source that cannot be read does not fail the download — the author still
    needs the pack — but the answer says the structure is missing."""
    from bizview_cli.structure import enriched_json, enriched_markdown

    from app.sources import service as source_service
    from app.sources import structure as structure_service

    src = source_service.by_name(db, source)
    if src is None:
        raise not_found(M("sources.not_found"))
    folder = f"sources/{layout.plain_slug(src.name)}"
    try:
        document = structure_service.build(db, src, get_settings())
    except Exception:                                   # unreachable source: the pack still serves
        return {}, "unavailable"
    return {f"{folder}/structure.md": enriched_markdown(document),
            f"{folder}/structure.json": enriched_json(document)}, "included"


def build(db: Session, *, name: str, source: str | None = None, lang: str = "es",
          kind: str = "integration") -> dict:
    """The starter zip for one project: bytes, filename and whether the structure came along."""
    display = name.strip()
    if not display:
        raise ApiError(422, "name_required", M("projects.starter_name_required"))
    slug = layout.plain_slug(display)
    try:
        files = pack.render(name=display, slug=slug, lang=lang, kind=kind)
    except pack.PackError as e:
        raise ApiError(422, "starter_invalid", str(e)) from e
    structure, structure_state = ({}, None)
    if source:
        structure, structure_state = _source_structure(db, source)
        files.update(structure)
    limits = project_budgets.effective(db)
    report = shared_budgets.tally(
        [(path, len(text.encode("utf-8")), text.encode("utf-8")) for path, text in files.items()],
        limits)
    if report.refusal is not None:
        raise project_zip.refusal_error(report.refusal)
    return {"data": pack.zip_bytes(files), "filename": pack.filename(slug),
            "structure": structure_state, "files": len(files)}


def template_path() -> Path | None:
    """The committed template, when this deployment has it."""
    override = os.environ.get(TEMPLATE_ENV, "").strip()
    if override:
        path = Path(override).expanduser()
        return path if path.is_file() else None
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / pack.TEMPLATE_NAME
        if candidate.is_file():
            return candidate
    return None


def template() -> dict:
    """The generic template: the committed bytes, or the same render when the file is absent."""
    path = template_path()
    if path is not None:
        return {"data": path.read_bytes(), "filename": pack.TEMPLATE_NAME}
    return {"data": pack.zip_bytes(pack.render(template=True, lang="es")),
            "filename": pack.TEMPLATE_NAME}
