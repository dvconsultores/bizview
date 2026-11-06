"""Re-importing a project (feature 055): the same project, a new revision.

The import path of 020/043/049 creates a project. This module is the other half of that decision:
when the slug of the archive already belongs to a project, the archive is a *revision* of it — the
folder is replaced in full (a file the zip no longer carries is removed, images included), the
project keeps its id, its slug, its shares, its grants and its history, and nothing is applied
until **Aplicar**.

The archive parsing and the two allowances stay in `app/projects/zip.py`; this module receives the
file map and the images and answers two questions: what would change (`plan`) and change it
(`execute`).
"""
from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import AppUser, Project
from app.projects import fs, revisions
from app.projects import service as project_service
from app.services import audit

log = logging.getLogger("app.projects")


#: Files the product owns *for* a project. A zip that does not carry them — an author zips only
#: what they edited — must not delete them: the constitution is generated at creation and the layout
#: requires it, so deleting it would break the project instead of replacing it.
PRODUCT_OWNED = (".specify/memory/constitution.md",)


def _actor(actor_id: int | None) -> dict:
    return {"kind": "user", "user_id": actor_id, "session_id": None, "command": "import"}


def plan(db: Session, project: Project, files: dict[str, str],
         images: dict[str, bytes]) -> dict:
    """The diff of writing this archive over the project, without writing anything (FR-009).

    The base is the newest revision when there is one; a project that has none yet (an import that
    predates this feature, its folder never read) compares against its folder, so a dry run never
    claims every file is new when the files are there."""
    base = revisions.current(db, project) or revisions.ensure_baseline(db, project)
    before = (base.files if base is not None else None) or revisions.snapshot(project.slug)
    after = archive_hashes(files, images)
    # What the product owns for the project is not removed by a zip that omits it, so the diff must
    # not promise a removal `execute` will not perform.
    after.update({path: digest for path, digest in before.items()
                  if path in PRODUCT_OWNED and path not in after})
    diff = revisions.diff_maps(before, after)
    return {**diff, "base_revision": base.number if base is not None else None}


SLUG_LINE = re.compile(r"^slug:.*$", re.MULTILINE)


def pin_slug(files: dict[str, str], slug: str) -> None:
    """The manifest carries the project's own slug, whatever the archive says.

    An author's zip is usually written by the export and brings `slug: ""` (or the slug of the copy
    it was made from). The project keeps its slug (FR-010), and a manifest left empty fails the
    apply's schema, so the line is rewritten before the revision is planned or written."""
    text = files.get("project.yaml")
    if text is None:
        return
    if SLUG_LINE.search(text):
        files["project.yaml"] = SLUG_LINE.sub(f"slug: {slug}", text, count=1)


def archive_hashes(files: dict[str, str], images: dict[str, bytes]) -> dict[str, str]:
    """The map the archive would produce. `images` holds what the product stores: an SVG comes back
    sanitised from `assets.prepare`, so the digest is the stored file's, not the zip's."""
    import hashlib

    out = {path: hashlib.sha256(text.encode("utf-8")).hexdigest() for path, text in files.items()}
    out.update({path: hashlib.sha256(data).hexdigest() for path, data in images.items()})
    return out


def execute(db: Session, actor: AppUser, project: Project, *, files: dict[str, str],
            images: dict[str, bytes], ip: str | None,
            replace_draft: bool = False) -> dict:
    """Write the archive as the project's new draft revision; returns the revision and its diff."""
    project_service.ensure_editable(project)
    diff = plan(db, project, files, images)
    if revisions.draft_has_editor_changes(db, project) and not replace_draft:
        # A question, not a refusal: the page offers "Reemplazar borrador / Cancelar" and re-sends
        # with `replace_draft` when the author accepts (FR-014).
        return {"needs_confirmation": True, "revision": None, "diff": diff}
    current = revisions.snapshot(project.slug)
    actor_dict = _actor(actor.id)
    writes = [{"op": "write", "path": path, "content": text, "base_sha256": None, "force": True}
              for path, text in sorted(files.items())]
    # Full replacement: what the zip does not carry leaves the folder (FR-005). An image is deleted
    # like any other file — `apply_ops` unlinks it and records the deletion in the history.
    deletes = [{"op": "delete", "path": path, "base_sha256": digest}
               for path, digest in sorted(current.items()) if path not in files
               and path not in images and path not in PRODUCT_OWNED]
    db.commit()                                   # apply_ops writes in its own transaction
    try:
        if writes or deletes:
            fs.apply_ops(project.id, writes + deletes, actor_dict)
        for path, data in sorted(images.items()):
            fs.apply_asset(project.id, path, data, actor_dict)
    except fs.ProjectPathError as e:
        # `apply_ops` already rolled the folder back; nothing half-imported stays behind.
        raise ApiError(422, e.code, e.message) from e

    # The revision is written after the last write, so the number is never handed out for a folder
    # that failed halfway (research R7).
    _rename_if_asked(db, project, files)
    db.refresh(project)
    # The snapshot is read from the folder: it is what really landed, sanitised SVG included.
    revision = revisions.create(db, project, source="import", status="draft",
                                files=revisions.snapshot(project.slug), summary=diff,
                                actor_id=actor.id)
    audit.record(db, "project_reimported", actor_id=actor.id, ip=ip,
                 detail={"project_id": project.id, "project": project.slug,
                         "revision": revision.number, "files": len(files),
                         "images": len(images), "changed": diff["counts"],
                         "replaced": diff["base_revision"]})
    db.flush()
    return {"needs_confirmation": False, "revision": revision, "diff": diff}


def plan_needs_confirmation(db: Session, project: Project) -> bool:
    """Would `execute` refuse until the author says "replace the draft"? (FR-014)"""
    return revisions.draft_has_editor_changes(db, project)


def revision_json(row) -> dict:
    """The revision as the API answers it: number, status, source and the counts of its diff."""
    return revisions.public(row)


def _rename_if_asked(db: Session, project: Project, files: dict[str, str]) -> None:
    """The name follows `project.yaml` when the archive changed it (FR-006); the slug never does."""
    import yaml

    try:
        meta = yaml.safe_load(files.get("project.yaml") or "")
    except yaml.YAMLError:
        return
    if not isinstance(meta, dict):
        return
    name = meta.get("name")
    if not isinstance(name, str):
        return
    wanted = name.strip()[:80]
    if wanted and wanted != project.name:
        audit_detail = {"project_id": project.id, "project": project.slug, "fields": ["name"],
                        "from": project.name, "to": wanted}
        project.name = wanted
        audit.record(db, "project_updated", actor_id=project.created_by, ip=None,
                     detail=audit_detail)
        db.flush()


def rename_ids(files: dict[str, str], images: dict[str, bytes], suffix: str) -> None:
    """Give a *copy* its own artifact ids, and repoint what it references (FR-003).

    A copy that kept the original's ids could never apply: the composition refuses two projects
    owning the same id (037). The suffix is the copy's own number, so the id names its project.
    """

    def trimmed(value: str) -> str:
        room = 50 - len(suffix)
        return f"{value[:room]}{suffix}"

    moves: list[tuple[str, str, str, str]] = []          # old path, new path, old id, new id
    for path in list(files) + list(images):
        found = revisions.artifact_id(path)
        if found is None:
            continue
        kind, ident = found
        new_id = trimmed(ident)
        if new_id == ident:
            continue
        rest = path[len(f"{kind}/"):]
        moves.append((path, f"{kind}/{new_id}{rest[len(ident):]}", ident, new_id))

    for old, new, _ident, _new_id in moves:
        if old in files:
            files[new] = files.pop(old)
        else:
            images[new] = images.pop(old)

    renamed: dict[tuple[str, str], str] = {}
    for old, _new, ident, new_id in moves:
        found = revisions.artifact_id(old)
        if found is not None:
            renamed[(found[0], ident)] = new_id

    def article(kind: str, ident: str) -> str | None:
        return renamed.get((kind, ident))

    for _old, new, _ident, new_id in moves:
        if new not in files:
            continue                      # an image carries no id inside
        kind, _ = revisions.artifact_id(new)
        # The file names the artifact twice: in its own `id:` and in the path. Renaming only the
        # folder would not validate (the contract asks both to agree).
        text = _rename_id(files[new], new_id)
        if kind == "reports":
            files[new] = _repoint_report(text, article)
        elif kind == "distributions":
            files[new] = _repoint_distribution(text, article)
        else:
            files[new] = text


def _rename_id(text: str, new_id: str) -> str:
    """The `id:` of an artifact's own file, rewritten for a copy."""
    import re

    return re.sub(r"^(id:\s*)[a-z][a-z0-9-]{1,49}\s*$", rf"\g<1>{new_id}", text,
                  count=1, flags=re.MULTILINE)


def _repoint_report(text: str, article) -> str:
    """`uses` aliases and the `theme:` block of a copied report."""
    import re

    lines = text.splitlines()
    uses_indent: int | None = None
    theme_indent: int | None = None
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if stripped.startswith("uses:"):
            uses_indent = indent
            out.append(line)
            continue
        if stripped == "theme:":
            theme_indent = indent
            out.append(line)
            continue
        if uses_indent is not None:
            if stripped and indent <= uses_indent:
                uses_indent = None
            else:
                match = re.match(r"^(\s*[A-Za-z0-9_]+:\s*)([a-z][a-z0-9-]{1,49})\.(.+)$", line)
                if match:
                    new_id = article("integrations", match.group(2))
                    if new_id:
                        out.append(f"{match.group(1)}{new_id}.{match.group(3)}")
                        continue
        if theme_indent is not None:
            if stripped and indent <= theme_indent and not stripped.startswith(("id:", "palette:")):
                theme_indent = None
            else:
                match = re.match(r"^(\s*(?:id|palette):\s*)([a-z][a-z0-9-]{1,39})\s*$", line)
                if match:
                    new_id = article("themes", match.group(2))
                    if new_id:
                        out.append(f"{match.group(1)}{new_id}")
                        continue
        out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def _repoint_distribution(text: str, article) -> str:
    import re

    lines = text.splitlines()
    out = []
    for line in lines:
        match = re.match(r"^(\s*report:\s*)([a-z][a-z0-9-]{1,49})\s*$", line)
        if match:
            new_id = article("reports", match.group(2))
            if new_id:
                out.append(f"{match.group(1)}{new_id}")
                continue
        out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")
