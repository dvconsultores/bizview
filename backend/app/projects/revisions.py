"""A project's own revisions (feature 055): snapshots, diffs, retention and going back.

Feature 020 records one row per *file* change (`project_file_revision`) and one workspace version
per *apply*; neither answers "what did this project's folder hold at revision 3". That is what a
re-import needs: the diff is computed against it, the download serves it, and the revert writes it
back.

A revision is a **map of hashes** (`path -> sha256`), never the contents: the text of every version
is already in `project_file_revision`, so a revision costs a row plus its diff instead of a copy of
the project. Images are kept by hash only since 044, so a download resolves text from the history
and takes an image from disk while the file still carries that hash — the same limit the product
already states for restoring an image, said out loud instead of silently skipped.
"""
from __future__ import annotations

from datetime import UTC, datetime

from bizview_cli import layout
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AppUser, Project, ProjectFileRevision, ProjectRevision
from app.projects import fs
from app.services import audit

#: How many paths a diff lists per kind; the counts stay exact (FR-010).
DIFF_LIMIT = 500

#: `assets/` travels in the same map: a re-import removes an image the zip no longer carries.
ASSET_PREFIX = layout.ASSET_PREFIX


def _now() -> datetime:
    return datetime.now(UTC)


# --- snapshots --------------------------------------------------------------------------------

def snapshot(slug: str) -> dict[str, str]:
    """The folder as `{path: sha256}` — every allowed file, images included."""
    listed, _ = fs.list_files(slug)
    return {path: digest for path, (_size, digest) in listed.items()}


def artifact_id(path: str) -> tuple[str, str] | None:
    """`(kind, id)` of a path that names an artifact, or None for everything else."""
    parts = path.split("/")
    if len(parts) >= 3 and parts[0] == "integrations" and parts[-1] == "integration.yaml":
        return ("integrations", parts[1])
    if len(parts) == 3 and parts[0] == "reports" and parts[-1] == "report.yaml":
        return ("reports", parts[1])
    if len(parts) == 2 and parts[0] == "distributions" and parts[-1].endswith(".yaml"):
        return ("distributions", parts[1][:-len(".yaml")])
    if len(parts) == 2 and parts[0] == "themes" and parts[-1].endswith((".yaml", ".yml")):
        return ("themes", parts[1].rsplit(".", 1)[0])
    return None


def spec_folder(path: str) -> str | None:
    parts = path.split("/")
    if len(parts) >= 3 and parts[0] == "specs" and layout.SPEC_FOLDER_RE.match(parts[1]):
        return parts[1]
    return None


def _ids(files: dict[str, str]) -> set[str]:
    return {f"{kind}/{ident}" for path in files if (found := artifact_id(path))
            for kind, ident in (found,)}


def _specs(files: dict[str, str]) -> set[str]:
    return {folder for path in files if (folder := spec_folder(path))}


def diff_maps(before: dict[str, str], after: dict[str, str]) -> dict:
    """What changed between two file maps: paths, specs and artifact ids, with exact counts."""
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(path for path in after if path in before and before[path] != after[path])
    specs_before, specs_after = _specs(before), _specs(after)
    ids_before, ids_after = _ids(before), _ids(after)
    specs_added = sorted(specs_after - specs_before)
    specs_removed = sorted(specs_before - specs_after)
    ids_added, ids_removed = sorted(ids_after - ids_before), sorted(ids_before - ids_after)
    truncated = any(len(group) > DIFF_LIMIT for group in (added, removed, changed))
    return {
        "added": added[:DIFF_LIMIT], "changed": changed[:DIFF_LIMIT],
        "removed": removed[:DIFF_LIMIT],
        "specs": {"added": specs_added, "removed": specs_removed},
        "ids": {"added": ids_added, "removed": ids_removed},
        "counts": {"added": len(added), "changed": len(changed), "removed": len(removed),
                   "specs_added": len(specs_added), "specs_removed": len(specs_removed),
                   "ids_added": len(ids_added), "ids_removed": len(ids_removed)},
        "truncated": truncated,
    }


def empty_diff() -> dict:
    return diff_maps({}, {})


def is_empty(diff: dict) -> bool:
    return not any(diff["counts"].values())


# --- reading ----------------------------------------------------------------------------------

def current(db: Session, project: Project) -> ProjectRevision | None:
    """The newest revision: what the folder is now."""
    return db.scalars(select(ProjectRevision)
                      .where(ProjectRevision.project_id == project.id)
                      .order_by(ProjectRevision.number.desc()).limit(1)).first()


def applied(db: Session, project: Project) -> ProjectRevision | None:
    return db.scalars(select(ProjectRevision)
                      .where(ProjectRevision.project_id == project.id,
                             ProjectRevision.status == "applied")
                      .order_by(ProjectRevision.number.desc()).limit(1)).first()


def previous(db: Session, project: Project) -> ProjectRevision | None:
    return db.scalars(select(ProjectRevision)
                      .where(ProjectRevision.project_id == project.id,
                             ProjectRevision.status == "previous")
                      .order_by(ProjectRevision.number.desc()).limit(1)).first()


def by_number(db: Session, project: Project, number: int) -> ProjectRevision | None:
    return db.scalar(select(ProjectRevision)
                     .where(ProjectRevision.project_id == project.id,
                            ProjectRevision.number == number))


def draft_has_editor_changes(db: Session, project: Project) -> bool:
    """True when files were saved (by a person or the agent) since the last import or revert.

    A re-import would overwrite them, so it asks first (FR-014). A project with no import revision
    at all — an installation that upgraded — has nothing to compare against and asks nothing."""
    newest_import = db.scalars(
        select(ProjectFileRevision.created_at)
        .where(ProjectFileRevision.project_id == project.id,
               ProjectFileRevision.command.in_(("import", "revert")))
        .order_by(ProjectFileRevision.id.desc()).limit(1)).first()
    if newest_import is None:
        return False
    edited = db.scalars(
        select(ProjectFileRevision.id)
        .where(ProjectFileRevision.project_id == project.id,
               ProjectFileRevision.command.in_(("edit", "create", "delete", "rename", "restore")),
               ProjectFileRevision.created_at > newest_import).limit(1)).first()
    return edited is not None


def public(row: ProjectRevision) -> dict:
    return {
        "number": row.number, "status": row.status, "source": row.source,
        "files": len(row.files or {}), "diff": row.summary or empty_diff(),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "applied_at": row.applied_at.isoformat() if row.applied_at else None,
        "by": None,
    }


def listing(db: Session, project: Project, *, limit: int | None = None) -> dict:
    """The history, newest first, with the actors' names and the ceiling in force."""
    ensure_baseline(db, project)
    keep = max(1, get_settings().project_revisions_keep)
    rows = db.scalars(select(ProjectRevision)
                      .where(ProjectRevision.project_id == project.id)
                      .order_by(ProjectRevision.number.desc())
                      .limit(limit or keep)).all()
    ids = {row.created_by for row in rows if row.created_by}
    names = ({u.id: u.full_name for u in db.scalars(select(AppUser).where(AppUser.id.in_(ids)))}
             if ids else {})
    items = []
    for row in rows:
        item = public(row)
        item["by"] = names.get(row.created_by) if row.created_by else None
        items.append(item)
    return {"items": items, "keep": keep,
            "applied": (applied(db, project).number if applied(db, project) else None),
            "previous": (previous(db, project).number if previous(db, project) else None)}


def chip(db: Session, project: Project) -> dict | None:
    """What the editor's header shows: the draft (or the newest) and the applied one, plainly.

    Read-only on purpose: it is called while building a project's detail, and a GET that writes is
    a GET that can fail with the folder unwritable."""
    newest = current(db, project)
    if newest is None:
        return None
    applied_row = applied(db, project)
    previous_row = previous(db, project)
    return {
        "number": newest.number, "status": newest.status, "source": newest.source,
        "applied": applied_row.number if applied_row is not None else None,
        "previous": previous_row.number if previous_row is not None else None,
        "keep": max(1, get_settings().project_revisions_keep),
    }


# --- writing ----------------------------------------------------------------------------------

def _next_number(db: Session, project: Project) -> int:
    highest = db.scalar(select(ProjectRevision.number)
                        .where(ProjectRevision.project_id == project.id)
                        .order_by(ProjectRevision.number.desc()).limit(1))
    number = max(project.revision_seq or 0, highest or 0) + 1
    project.revision_seq = number
    return number


def create(db: Session, project: Project, *, source: str, status: str, files: dict[str, str],
           summary: dict, actor_id: int | None) -> ProjectRevision:
    """Record a snapshot and demote whatever draft was there (it was never applied)."""
    for row in db.scalars(select(ProjectRevision)
                          .where(ProjectRevision.project_id == project.id,
                                 ProjectRevision.status == "draft")):
        row.status = "replaced"
    row = ProjectRevision(project_id=project.id, number=_next_number(db, project), source=source,
                          status=status, files=files, summary=summary, created_by=actor_id,
                          applied_at=_now() if status == "applied" else None)
    db.add(row)
    db.flush()
    prune(db, project)
    return row


def mark_applied(db: Session, project: Project, row: ProjectRevision) -> ProjectRevision | None:
    """The draft becomes applied; the applied before it becomes `previous` (what a revert restores).

    Returns the revision that was applied until now, or None."""
    before = applied(db, project)
    for other in db.scalars(select(ProjectRevision)
                            .where(ProjectRevision.project_id == project.id,
                                   ProjectRevision.status.in_(("applied", "previous")))):
        if other.id == row.id:
            continue
        other.status = "previous" if other.id == (before.id if before else None) else "replaced"
    row.status = "applied"
    row.applied_at = _now()
    db.flush()
    return before


def prune(db: Session, project: Project) -> list[int]:
    """Keep the newest N revisions, always keeping the applied and the previous one (FR-017)."""
    keep = max(1, get_settings().project_revisions_keep)
    rows = db.scalars(select(ProjectRevision)
                      .where(ProjectRevision.project_id == project.id)
                      .order_by(ProjectRevision.number.desc())).all()
    if len(rows) <= keep:
        return []
    protected = {row.id for row in rows if row.status in ("applied", "previous")}
    removed: list[int] = []
    for row in rows[keep:]:
        if row.id in protected:
            continue
        removed.append(row.number)
        db.delete(row)
    db.flush()
    return removed


def ensure_baseline(db: Session, project: Project) -> ProjectRevision | None:
    """Revision 1 for a project that predates the table: the folder as it is, on first read.

    An upgrade cannot create it in the migration (PROJECTS_DIR may not be mounted where alembic
    runs), and a project with no revisions would show an empty chip and no diff base."""
    existing = current(db, project)
    if existing is not None:
        return existing
    if not fs.project_root(project.slug).is_dir():
        return None
    from app.projects import specs

    files = snapshot(project.slug)
    status = "applied" if specs.applied_files(db, project) is not None else "draft"
    return create(db, project, source="import", status=status, files=files,
                  summary={**empty_diff(), "created": True}, actor_id=project.created_by)


def ensure_baseline_quietly(db: Session, project: Project) -> None:
    """Same, for a read path that must not fail because the folder is missing."""
    try:
        ensure_baseline(db, project)
    except (OSError, fs.ProjectPathError):
        db.rollback()


# --- content for a download or a revert -------------------------------------------------------

def resolve_files(db: Session, project: Project, row: ProjectRevision) -> tuple[dict[str, str],
                                                                               list[str]]:
    """Text of each path of a revision, and the images that could not be read back.

    Text is exact: a `(path, sha256)` match in the history cannot be another file. An image comes
    from disk only while the file still has that hash — 044 keeps images by hash, never by content —
    and everything else is listed so the caller can say it instead of skipping silently."""
    files: dict[str, str] = {}
    missing: list[str] = []
    for path, digest in sorted((row.files or {}).items()):
        if path.startswith(ASSET_PREFIX):
            try:
                data, _kind, current_digest = fs.read_asset(project.slug, path)
            except (FileNotFoundError, OSError, fs.ProjectPathError):
                missing.append(path)
                continue
            if current_digest != digest:
                missing.append(path)
                continue
            files[path] = data.decode("latin-1")   # only its presence matters for the zip
            continue
        content = db.scalar(select(ProjectFileRevision.content)
                            .where(ProjectFileRevision.project_id == project.id,
                                   ProjectFileRevision.path == path,
                                   ProjectFileRevision.sha256 == digest).limit(1))
        if content is None:
            missing.append(path)
            continue
        files[path] = content
    return files, missing


def binary_paths(row: ProjectRevision) -> set[str]:
    return {path for path in (row.files or {}) if path.startswith(ASSET_PREFIX)}


def revert_to(db: Session, actor: AppUser, project: Project, number: int,
              ip: str | None) -> dict:
    """Write an older revision back as a new draft and apply it (FR-012).

    The new revision, not the old one, is what carries the state forward: the history is append-only
    and the chip must keep moving forward, so a revert is a forward step that happens to hold the
    older content."""
    from app.projects import apply as project_apply

    target = by_number(db, project, number)
    if target is None:
        from app.errors import not_found
        from app.i18n import M

        raise not_found(M("projects.revision_not_found", number=number))
    if target.status == "draft":
        from app.errors import ApiError
        from app.i18n import M

        raise ApiError(409, "revision_is_draft", M("projects.revision_is_draft", number=number))
    files, missing = resolve_files(db, project, target)
    if missing and any(not path.startswith(ASSET_PREFIX) for path in missing):
        from app.errors import ApiError
        from app.i18n import M

        gone = ", ".join(p for p in missing if not p.startswith(ASSET_PREFIX))[:300]
        raise ApiError(409, "revision_unavailable",
                       M("projects.revision_unavailable", paths=gone))

    current_map = snapshot(project.slug)
    actor_dict = {"kind": "user", "user_id": actor.id, "session_id": None, "command": "revert"}
    ops: list[dict] = [{"op": "write", "path": path, "content": text, "base_sha256": None,
                        "force": True}
                       for path, text in sorted(files.items()) if not path.startswith(ASSET_PREFIX)]
    ops += [{"op": "delete", "path": path, "base_sha256": digest}
            for path, digest in sorted(current_map.items()) if path not in target.files]
    db.commit()                                     # apply_ops writes in its own transaction
    if ops:
        fs.apply_ops(project.id, ops, actor_dict)
    revision = create(db, project, source="import", status="draft",
                      files=snapshot(project.slug),
                      summary=diff_maps(current_map, target.files or {}), actor_id=actor.id)
    db.commit()

    version, _ = project_apply.apply_project(db, actor, project, ip)
    audit.record(db, "project_reverted", actor_id=actor.id, ip=ip,
                 detail={"project_id": project.id, "project": project.slug,
                         "revision": number, "applied_revision": revision.number,
                         "version": version.id, "images_missing": len(missing)})
    db.flush()
    return {"revision": public(revision), "restored": number,
            "missing": sorted(missing), "version": version.id}


def register_editor_revision(db: Session, project: Project, actor: dict,
                             summary: dict | None = None) -> ProjectRevision | None:
    """One revision per save (FR-008), whatever wrote the files — a person or the agent.

    `fs.apply_ops` already committed; the snapshot is read from the folder, so it is the truth even
    when the caller's session is stale."""
    actor_id = actor.get("user_id") if actor.get("kind") == "user" else None
    files = snapshot(project.slug)
    base = (current(db, project).files if current(db, project) else {}) or {}
    return create(db, project, source="editor", status="draft", files=files,
                  summary=summary or diff_maps(base, files), actor_id=actor_id)
