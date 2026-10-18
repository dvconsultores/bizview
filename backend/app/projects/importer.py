"""Upgrade path of feature 020: the applied workspace and open drafts become projects (R10)."""
import logging
from datetime import UTC, date, datetime

from sqlalchemy import select

from app.models import AssistantSession, Project
from app.projects import compose, fs
from app.projects import service as project_service
from app.services import audit

log = logging.getLogger("app.projects")

SYSTEM = {"kind": "system", "user_id": None, "session_id": None, "command": "import"}


def _write_tree(project: Project, tree: dict[str, str]) -> None:
    """Write the files (new spec folders in number order, as `apply_ops` requires)."""
    ops = [{"op": "write", "path": path, "content": text, "base_sha256": None, "force": True}
           for path, text in sorted(tree.items())]
    if ops:
        fs.apply_ops(project.id, ops, SYSTEM)


def _base_files(project: Project) -> dict[str, str]:
    return {
        "project.yaml": project_service.project_yaml(
            project.name, project.slug, project.description or "",
            project.created_at.date().isoformat()),
        ".specify/memory/constitution.md": project_service.constitution(
            project.name, date.today().isoformat()),
    }


def ensure_principal(db) -> bool:
    """Write the applied workspace into the `principal` project once (idempotent; retried at
    the next start when the folder cannot be written)."""
    from app.workspace.service import active

    project = db.scalar(select(Project).where(Project.slug == "principal",
                                              Project.imported_at.is_(None),
                                              Project.deleted_at.is_(None)))
    if project is None:
        return False
    version = active(db)
    tree = compose.version_projects(version).get("principal", {}) if version else {}
    files = {**_base_files(project), **tree}
    db.commit()   # apply_ops writes in its own transaction and updates the project row
    try:
        _write_tree(project, files)
    except (OSError, fs.ProjectPathError) as exc:
        log.warning("principal project not imported yet (%s); retrying at next start", exc)
        return False
    db.refresh(project)
    project.imported_at = datetime.now(UTC)
    audit.record(db, "project_imported", actor_id=None, ip=None,
                 detail={"project_id": project.id, "project": "principal",
                         "files": len(files), "source": "upgrade"})
    db.flush()
    return True


def import_open_drafts(db) -> int:
    """Each open conversation draft becomes its own project «<title> (borrador)» (idempotent)."""
    sessions = db.scalars(select(AssistantSession).where(
        AssistantSession.draft.is_not(None), AssistantSession.status != "applied",
    ).order_by(AssistantSession.id)).all()
    count = 0
    for session in sessions:
        if "imported_project" in (session.stats or {}):
            continue
        files = (session.draft or {}).get("files") or {}
        if not files:
            session.stats = {**(session.stats or {}), "imported_project": 0}
            db.flush()
            continue
        name = f"{(session.title or 'Borrador').strip()[:60]} (borrador)"      # FR-016
        project = Project(slug=project_service.suggest_slug(db, name), name=name[:80],
                          origin="app", created_by=session.created_by,
                          imported_at=datetime.now(UTC))
        db.add(project)
        db.flush()
        db.commit()
        try:
            _write_tree(project, {**_base_files(project), **compose.draft_tree(files)})
        except (OSError, fs.ProjectPathError) as exc:
            log.warning("draft of conversation %s not imported (%s)", session.id, exc)
            db.delete(project)
            db.commit()
            continue
        db.refresh(project)
        session.project_id = project.id
        session.read_only = False
        session.stats = {**(session.stats or {}), "imported_project": project.id}
        audit.record(db, "project_imported", actor_id=session.created_by, ip=None,
                     detail={"project_id": project.id, "project": project.slug,
                             "session": session.id, "source": "draft"})
        db.flush()
        count += 1
    return count


def upgrade(db) -> None:
    """Feature 020 upgrade steps, run by `bootstrap` at every start (both are idempotent)."""
    ensure_principal(db)
    import_open_drafts(db)
    db.flush()


GIT = {"kind": "git", "user_id": None, "session_id": None, "command": "git"}


def mirror_git_projects(db, version, git_slugs: list[str]) -> None:
    """Git projects of the applied version become read-only `git` projects in PROJECTS_DIR
    (never touching a project edited in the app)."""
    from app.projects import history

    # Reload first: JSONB reorders keys, and the applied map is always read from the database.
    db.flush()
    db.refresh(version)
    trees = compose.version_projects(version)
    for slug in git_slugs:
        tree = trees.get(slug) or {}
        project = db.scalar(select(Project).where(Project.slug == slug,
                                                  Project.deleted_at.is_(None)))
        if project is None:
            name = "Principal" if slug == "principal" else slug.replace("-", " ").capitalize()
            project = Project(slug=slug, name=name, origin="git", imported_at=datetime.now(UTC))
            db.add(project)
            db.flush()
        if project.origin != "git":
            continue
        db.commit()   # apply_ops writes in its own transaction
        listed, _ = fs.list_files(slug)
        current = {path: digest for path, (_size, digest) in listed.items()}
        ops = [{"op": "write", "path": path, "content": text, "base_sha256": None, "force": True}
               for path, text in sorted(tree.items()) if history.sha(text) != current.get(path)]
        ops += [{"op": "delete", "path": path, "base_sha256": digest}
                for path, digest in sorted(current.items()) if path not in tree]
        if ops:
            try:
                fs.apply_ops(project.id, ops, GIT)
            except (OSError, fs.ProjectPathError) as exc:
                log.warning("git project %s not mirrored (%s)", slug, exc)
