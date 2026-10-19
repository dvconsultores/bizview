"""BI projects: create, list, detail (feature 020, plan section 4)."""

import json
import re
import shutil
import unicodedata
from datetime import UTC, date, datetime, timedelta
from importlib import resources

from bizview_cli import layout
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found, validation
from app.i18n import M
from app.models import AppUser, AssistantSession, AuditEvent, Project, ProjectFileRevision
from app.projects import fs, specs
from app.services.audit import record as audit

FOLDERS = ("specs", "integrations", "reports", "distributions")


def suggest_slug(db: Session, name: str) -> str:
    """Suggest a unique slug from a project name."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    base = s if s and s[0].isalpha() else ("p-" + s if s else "proyecto")
    base = base[:50].rstrip("-")
    if not layout.ID_RE.match(base):
        base = "proyecto"
    existing = set(db.scalars(select(Project.slug).where(Project.deleted_at.is_(None))))
    if base not in existing:
        return base
    for i in range(2, 1000):
        candidate = f"{base[:46]}-{i}"
        if candidate not in existing:
            return candidate
    raise ApiError(409, "slug_taken", M("projects.slug_taken", slug=base))


def project_yaml(name: str, slug: str, description: str, created: str) -> str:
    """Render project.yaml content."""
    return (
        f"name: {json.dumps(name, ensure_ascii=False)}\n"
        f"slug: {slug}\n"
        f"description: {json.dumps(description, ensure_ascii=False)}\n"
        f'created: "{created}"\n'
    )


def constitution(name: str, today: str) -> str:
    """Project constitution from the workspace template."""
    template = resources.files("bizview_cli") / "workspace_template" / "files" / "constitution.md"
    return template.read_text(encoding="utf-8").format(name=name, date=today)


def create(db: Session, actor: AppUser, name: str, slug: str | None = None,
           description: str = "", ip: str | None = None) -> Project:
    """Create a BI project and its folder (project.yaml, constitution, empty layout folders)."""
    name = name.strip()
    if not 1 <= len(name) <= 80:
        raise validation({"name": "length"}, M("projects.name_length"))
    if len(description) > 500:
        raise validation({"description": "too_long"}, M("projects.description_length"))
    slug = slug or suggest_slug(db, name)
    if not layout.ID_RE.match(slug):
        raise validation({"slug": "pattern"}, M("projects.slug_pattern"))
    if db.scalar(select(Project).where(Project.slug == slug, Project.deleted_at.is_(None))):
        raise ApiError(409, "slug_taken", M("projects.slug_taken", slug=slug))
    if not fs.check_dir():
        raise ApiError(503, "not_writable", M("projects.not_writable"))

    root = fs.project_root(slug)
    existed = root.exists()
    if existed and any(root.iterdir()):
        # The database and the folders are not the same host: an installation whose database was
        # reused (or whose project row was deleted) still has the old tree here. Adopting it would
        # mix a previous project's specs and reports into the new one and surface them as
        # "changed externally", so the creation is refused until the folder is gone.
        raise ApiError(409, "folder_exists", M("projects.folder_exists", slug=slug))
    project = Project(slug=slug, name=name, description=description, created_by=actor.id)
    db.add(project)
    db.commit()

    today = date.today().isoformat()
    ops = [
        {"op": "write", "path": "project.yaml",
         "content": project_yaml(name, slug, description, today)},
        {"op": "write", "path": ".specify/memory/constitution.md",
         "content": constitution(name, today)},
        *({"op": "mkdir", "path": folder} for folder in FOLDERS),
    ]
    try:
        fs.apply_ops(project.id, ops, {"kind": "user", "user_id": actor.id,
                                       "session_id": None, "command": "create"})
    except Exception as err:
        db.rollback()
        db.delete(db.get(Project, project.id))
        db.commit()
        if not existed:
            shutil.rmtree(root, ignore_errors=True)
        if isinstance(err, fs.ProjectPathError):
            raise ApiError(503, err.code, err.message) from err
        raise

    # audit_event.target_id references app_user: the project goes in the detail.
    audit(db, "project_created", actor_id=actor.id, ip=ip,
          detail={"project_id": project.id, "slug": slug, "name": name})
    db.commit()
    db.refresh(project)
    return project


def get(db: Session, slug: str) -> Project:
    """Get a live project by slug."""
    project = db.scalar(select(Project).where(Project.slug == slug, Project.deleted_at.is_(None)))
    if project is None:
        raise not_found(M("projects.not_found"))
    return project


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def last_applied(db: Session, project: Project) -> dict | None:
    """The latest apply of the project (plan §4): version, time and who, from the audit log."""
    event = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.kind == "project_applied",
               AuditEvent.detail["project_id"].as_integer() == project.id)
        .order_by(AuditEvent.id.desc()).limit(1)).first()
    if event is None:
        return None
    actor = db.get(AppUser, event.actor_id) if event.actor_id else None
    return {"version": (event.detail or {}).get("version"), "at": _iso(event.occurred_at),
            "by": actor.full_name if actor else None}


def project_json(p: Project) -> dict:
    """Serialize a project to JSON."""
    return {
        "id": p.id, "slug": p.slug, "name": p.name, "description": p.description,
        "origin": p.origin, "spec_seq": p.spec_seq,
        "created_at": _iso(p.created_at), "updated_at": _iso(p.updated_at),
        "last_activity_at": _iso(p.last_activity_at),
        "first_applied_at": _iso(p.first_applied_at), "withdrawn_at": _iso(p.withdrawn_at),
    }


LEGACY_UNTRACKED = ("project.yaml", ".specify/memory/constitution.md")


def changed_files(applied: dict[str, str] | None, current: dict[str, str]) -> dict:
    """Paths added, changed and removed since the applied file map."""
    applied = applied or {}
    return {"added": sorted(set(current) - set(applied)),
            "changed": sorted(p for p in current if p in applied and applied[p] != current[p]),
            "removed": sorted(set(applied) - set(current))}


def status(db: Session, project: Project) -> tuple[str, dict]:
    """borrador | aplicado | cambios | retirado, and the changed files (feature 020 T059)."""
    listed, _ = fs.list_files(project.slug)
    current = {path: digest for path, (_size, digest) in listed.items()}
    applied = specs.applied_files(db, project)
    if applied is not None and "project.yaml" not in applied:
        # A version applied before feature 020 never tracked the project's own metadata.
        applied = {**applied, **{p: current[p] for p in LEGACY_UNTRACKED if p in current}}
    changes = changed_files(applied, current)
    if applied is None:
        return ("retirado" if project.withdrawn_at is not None else "borrador"), changes
    return ("cambios" if any(changes.values()) else "aplicado"), changes


def _spec_folders(slug: str) -> list[str]:
    """List spec folder names for a project."""
    specs_dir = fs.project_root(slug) / "specs"
    if not specs_dir.is_dir():
        return []
    return sorted(d.name for d in specs_dir.iterdir()
                  if d.is_dir() and not d.is_symlink() and layout.SPEC_FOLDER_RE.match(d.name))


ARTIFACT_GROUPS = ("integrations", "reports", "distributions")


def _folder_artifacts(slug: str) -> dict[str, list[str]]:
    """Integration, report and distribution ids in the project folder (plan §4 list)."""
    root = fs.project_root(slug)
    found: dict[str, list[str]] = {}
    for group, marker in (("integrations", "integration.yaml"), ("reports", "report.yaml")):
        base = root / group
        found[group] = sorted(d.name for d in base.iterdir()
                              if d.is_dir() and (d / marker).is_file()) if base.is_dir() else []
    base = root / "distributions"
    found["distributions"] = sorted(f.stem for f in base.glob("*.yaml")) if base.is_dir() else []
    return found


def list_projects(db: Session) -> list[dict]:
    """Live projects: status, spec count, artifacts in the folder and applied, conversations and
    the problems of the last validation (plan §4)."""
    from app.workspace.service import _version_projects, active

    projects = db.scalars(select(Project).where(Project.deleted_at.is_(None))
                          .order_by(Project.last_activity_at.desc())).all()
    counts = dict(db.execute(
        select(AssistantSession.project_id, func.count(AssistantSession.id))
        .where(AssistantSession.project_id.in_([p.id for p in projects]))
        .group_by(AssistantSession.project_id)).all()) if projects else {}
    version = active(db)
    applied = _version_projects(version) if version is not None else {}
    result = []
    for p in projects:
        item = project_json(p)
        item["status"] = status(db, p)[0]
        item["spec_count"] = len(_spec_folders(p.slug))
        item["conversations"] = counts.get(p.id, 0)
        item["artifacts"] = _folder_artifacts(p.slug)
        item["applied"] = {g: (applied.get(p.slug) or {}).get(g, []) for g in ARTIFACT_GROUPS}
        item["problems"] = (len((p.validation or {}).get("errors") or [])
                            if p.validation is not None else None)
        result.append(item)
    return result


def detail(db: Session, project: Project, viewer: AppUser) -> dict:
    """Get project detail with specs and the viewer's conversations."""
    data = project_json(project)
    data["status"], data["changed_files"] = status(db, project)
    data["last_applied"] = last_applied(db, project)
    data["specs"] = specs.list_specs(db, project)
    sessions = db.scalars(
        select(AssistantSession)
        .where(AssistantSession.project_id == project.id,
               AssistantSession.created_by == viewer.id)
        .order_by(AssistantSession.updated_at.desc())).all()
    from app.assistant.service import shown_title

    data["conversations"] = [
        {"id": s.id, "title": shown_title(s.title), "status": s.status, "read_only": s.read_only,
         "current_spec": s.current_spec, "updated_at": _iso(s.updated_at)}
        for s in sessions
    ]
    return data


def readiness_view(db: Session, project: Project):
    """WorkView for project-level readiness: its latest conversation, or a blank one."""
    from types import SimpleNamespace

    from app.projects.workview import WorkView

    session = db.scalars(select(AssistantSession).where(AssistantSession.project_id == project.id)
                         .order_by(AssistantSession.updated_at.desc()).limit(1)).first()
    if session is None:
        session = SimpleNamespace(id=None, working_state={}, stats={}, status="open",
                                  current_spec=None)
    return WorkView(project, session)


def revalidate(db: Session, project: Project) -> dict:
    """Validate the project (stored on it) and compute its readiness."""
    from app.assistant import readiness
    from app.projects.compose import validate_project

    validation = validate_project(db, project)
    project.validation = validation
    db.flush()
    return {"validation": validation,
            "readiness": readiness.compute(readiness_view(db, project))}


def ensure_editable(project: Project) -> None:
    """Git projects are edited in their repository, never here."""
    if project.origin == "git":
        raise ApiError(409, "git_project", M("projects.git_project"))


def changes(db: Session, project: Project, after: int) -> dict:
    """Revisions after `after` (oldest first), the latest id and whether a chat is busy."""
    from app.assistant.service import is_busy
    from app.config import get_settings

    revisions = db.scalars(select(ProjectFileRevision).where(
        ProjectFileRevision.project_id == project.id, ProjectFileRevision.id > after,
    ).order_by(ProjectFileRevision.id).limit(500)).all()
    latest = db.scalar(select(func.max(ProjectFileRevision.id))
                       .where(ProjectFileRevision.project_id == project.id))
    sessions = db.scalars(select(AssistantSession).where(
        AssistantSession.project_id == project.id, AssistantSession.busy_since.is_not(None)))
    settings = get_settings()
    return {
        "items": [{"id": r.id, "path": r.path, "op": r.op, "actor": r.actor_kind,
                   "actor_id": r.actor_id, "command": r.command, "session_id": r.session_id,
                   "time": r.created_at.isoformat()} for r in revisions],
        "latest": latest if latest is not None else after,
        "busy": any(is_busy(s, settings) for s in sessions),
    }


TRASH_DAYS = 30


def _trash_name(slug: str, when) -> str:
    return f"{slug}--{when.astimezone(UTC).strftime('%Y%m%d%H%M%S')}"


def delete_project(db: Session, actor: AppUser, project: Project, ip: str | None) -> None:
    """Move the folder to `.papelera` and mark the project deleted (refused while applied)."""
    from app.projects import fs, specs

    if specs.applied_files(db, project) is not None:
        raise ApiError(409, "project_applied", M("projects.project_applied"))
    now = datetime.now(UTC)
    root = fs.project_root(project.slug)
    if root.exists():
        trash = fs.projects_dir() / fs.TRASH
        trash.mkdir(parents=True, exist_ok=True)
        root.rename(trash / _trash_name(project.slug, now))
    project.deleted_at = now
    db.flush()
    audit(db, "project_deleted", actor_id=actor.id, ip=ip,
          detail={"project_id": project.id, "project": project.slug})


def purge_trash(db: Session, now=None) -> int:
    """Remove projects deleted more than TRASH_DAYS ago: trash folder, owned rows, row."""
    from app.assistant import attachments as chat_attachments
    from app.models import AssistantSession, EmailSubscription
    from app.projects import fs

    now = now or datetime.now(UTC)
    old = db.scalars(select(Project).where(
        Project.deleted_at.is_not(None), Project.deleted_at < now - timedelta(days=TRASH_DAYS)))
    count = 0
    for project in old:
        folder = fs.projects_dir() / fs.TRASH / _trash_name(project.slug, project.deleted_at)
        if folder.is_dir() and not folder.is_symlink():
            shutil.rmtree(folder)
        # Feature 024: the images of the project's conversations live outside that folder, so
        # they are removed here and not by the folder tree (their rows cascade with the project).
        for session_id in db.scalars(select(AssistantSession.id).where(
                AssistantSession.project_id == project.id)):
            chat_attachments.forget_session(db, session_id)
        db.execute(delete(EmailSubscription).where(EmailSubscription.project_id == project.id))
        audit(db, "project_purged", actor_id=None, ip=None,
              detail={"project_id": project.id, "project": project.slug})
        db.delete(project)
        count += 1
    db.flush()
    return count
