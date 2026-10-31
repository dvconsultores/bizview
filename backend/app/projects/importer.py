"""Upgrade path of feature 020: the applied workspace and open drafts become projects (R10)."""
import hashlib
import logging
from datetime import UTC, date, datetime

from sqlalchemy import select

from app.models import Project
from app.projects import assets, compose, fs
from app.projects import service as project_service
from app.services import audit

log = logging.getLogger("app.projects")

SYSTEM = {"kind": "system", "user_id": None, "session_id": None, "command": "import"}

#: 044: images live in the workspace as files, never in the version's text tree, so they travel on
#: their own: a binary has no `content` to put in an `apply_ops` write.
ASSET_PREFIX = "assets/"


def workspace_assets(slug: str) -> dict[str, bytes]:
    """The images the applied workspace holds for one project: {path: bytes}.

    A workspace with `projects/` keeps them under `projects/<slug>/assets/`; one applied before
    that layout keeps a single project's assets at the top.
    """
    from pathlib import Path

    from app.config import get_settings

    root = Path(get_settings().workspace_path)
    base = root / "projects" / slug
    if not (base / "assets").is_dir():
        base = root
    folder = base / "assets"
    if not folder.is_dir():
        return {}
    out: dict[str, bytes] = {}
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(base).as_posix()
        if path.is_symlink() or not path.is_file():
            continue
        if not rel.startswith(ASSET_PREFIX):
            continue
        out[rel] = path.read_bytes()
    return out


def write_assets(project: Project, actor: dict, *, only_changed: bool = True) -> int:
    """Carry the workspace's images into the project folder; returns how many were written."""
    images = workspace_assets(project.slug)
    if not images:
        return 0
    listed, _ = fs.list_files(project.slug)
    written = 0
    for rel, data in images.items():
        if only_changed:
            current = listed.get(rel)
            if current is not None and current[1] == hashlib.sha256(data).hexdigest():
                continue
        try:
            fs.apply_asset(project.id, rel, data, actor)
            written += 1
        except (OSError, fs.ProjectPathError, assets.AssetRefused) as exc:
            log.warning("asset %s of project %s not imported (%s)", rel, project.slug, exc)
    return written


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
        write_assets(project, SYSTEM)
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




def upgrade(db) -> None:
    """Feature 020 upgrade steps, run by `bootstrap` at every start (both are idempotent)."""
    ensure_principal(db)
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
        # An image is not in `tree` (it has no text form), so it must be spared here: without
        # this the mirror deleted every picture of the project on each apply.
        ops += [{"op": "delete", "path": path, "base_sha256": digest}
                for path, digest in sorted(current.items())
                if path not in tree and not path.startswith(ASSET_PREFIX)]
        if ops:
            try:
                fs.apply_ops(project.id, ops, GIT)
            except (OSError, fs.ProjectPathError) as exc:
                log.warning("git project %s not mirrored (%s)", slug, exc)
        # The images travel on their own: the text tree above cannot carry a byte stream.
        write_assets(project, GIT)
