"""Apply a BI project as a new workspace version (feature 020, plan section 8).

Applying composes the project with the other applied projects of the active version (R3),
validates and locks the tree and activates it through `workspace.service.apply_tree`, which
stores the owners (`workspace_version.projects`) and syncs the owned subscriptions.
"""
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, update

from app.config import get_settings
from app.db import get_sessionmaker
from app.errors import ApiError
from app.i18n import M
from app.models import AssistantSession, Project
from app.services.audit import record as audit_record


def _detached(project_id: int) -> Project | None:
    """The project row outside the request transaction (WorkView setters write it apart)."""
    with get_sessionmaker()() as other:
        project = other.get(Project, project_id)
        if project is not None:
            other.expunge(project)
        return project


def _ensure_idle(db, project: Project, ignore_session_id: int | None = None) -> None:
    """No other conversation of the project may be writing.

    `ignore_session_id` is the conversation doing the apply: feature 028's `apply_draft` runs
    *inside* the agent's own turn, which holds the busy claim, so counting it would refuse every
    autonomous apply with `assistant_busy` (reported: the run ended "Auto · detenido" and left the
    last clicks to the human).
    """
    from app.assistant.service import is_busy

    settings = get_settings()
    sessions = db.scalars(select(AssistantSession).where(
        AssistantSession.project_id == project.id, AssistantSession.busy_since.is_not(None)))
    if any(is_busy(s, settings) for s in sessions if s.id != ignore_session_id):
        raise ApiError(409, "assistant_busy", M("assistant.busy"))


def _view(db, project: Project, session):
    from types import SimpleNamespace

    from app.projects.workview import WorkView

    if session is None:
        session = db.scalars(select(AssistantSession)
                             .where(AssistantSession.project_id == project.id)
                             .order_by(AssistantSession.updated_at.desc()).limit(1)).first()
    if session is None:
        session = SimpleNamespace(id=None, working_state={}, stats={}, status="open",
                                  current_spec=None)
    return WorkView(_detached(project.id), session)


def _errors(result) -> list[dict]:
    return [{k: v for k, v in i.as_dict().items() if k != "level"}
            for i in result.issues if i.level == "error"]


def _activate_composed(db, actor, ip, *, origin: str, include=None, exclude_slug=None,
                       changed: bool = False, dependants_of: str | None = None):
    """Compose, validate, lock and apply; returns the new version."""
    from bizview_cli import validate as wsv

    from app.engine import direct
    from app.projects import compose
    from app.sources.service import list_all
    from app.workspace import service as workspace_service

    with tempfile.TemporaryDirectory() as tmp:
        root = compose.compose(db, include=include, exclude_slug=exclude_slug, dest=Path(tmp))
        names = {s.name.lower() for s in list_all(db)}
        result = wsv.validate(root, known_sources=names, direct=direct.validation_context(db))
        if not result.ok:
            errors = _errors(result)
            if dependants_of is not None:
                owners = sorted({e["file"].split("/")[1] for e in errors
                                 if (e.get("file") or "").startswith("projects/")})
                raise ApiError(409, "project_dependants",
                               M("projects.project_dependants",
                                 projects=", ".join(owners) or "?"),
                               extra={"errors": errors, "projects": owners})
            message = M("assistant.version_changed" if changed else "assistant.invalid_draft")
            raise ApiError(409, "invalid_draft", message, extra={"errors": errors})
        wsv.write_lock(root, result.lock)
        return workspace_service.apply_tree(db, actor, root, ip, origin=origin)


def apply_project(db, actor, project: Project, ip, *, session=None):
    """Apply the project (all its files) as a new workspace version.

    Returns (version, revalidated): revalidated when the active version changed since the
    project was last validated (the composed tree was checked again against it)."""
    from app.assistant import origin, readiness
    from app.assistant.preview import drop_for_session
    from app.projects import fs
    from app.projects.workview import real
    from app.workspace import service as workspace_service

    if project.deleted_at is not None:
        raise ApiError(404, "not_found", M("projects.not_found"))
    owner_session = real(session) if session is not None else None
    _ensure_idle(db, project, getattr(owner_session, "id", None))
    view = _view(db, project, session)
    failures = origin.recheck_draft(db, view, get_settings())
    if failures:
        raise ApiError(409, "query_check_failed",
                       M("assistant.query_check_failed", path=failures[0]["path"],
                         error=failures[0]["error"]),
                       extra={"errors": failures})
    pending = readiness.compute(view)["pending"]
    if pending:
        raise ApiError(409, "not_ready", M("assistant.not_ready", detail=pending[0]["message"]),
                       extra={"pending": pending})

    # Serialise with other applies before reading the active version the tree is built on.
    workspace_service.lock_workspace(db)
    current = workspace_service.active(db)
    changed = (view.validation or {}).get("base_version") != (current.id if current else None)
    version = _activate_composed(db, actor, ip, origin=f"project:{project.slug}",
                                 include=view.project, changed=changed)

    now = datetime.now(UTC)
    values: dict = {"withdrawn_at": None, "last_activity_at": now}
    if project.first_applied_at is None:
        values["first_applied_at"] = now
    db.execute(update(Project).where(Project.id == project.id).values(values))
    if session is not None:
        session.applied_version_id = version.id
        session.updated_at = now
    files, _ = fs.list_files(project.slug)
    audit_record(db, "project_applied", actor_id=actor.id, ip=ip,
                 detail={"project_id": project.id, "project": project.slug,
                         "session": session.id if session is not None else None,
                         "version": version.id, "files": sorted(files)})
    db.flush()
    preview = (view.preview or {}).get("session_id")
    if preview:
        drop_for_session(preview)
    return version, changed


def leave_workspace(db, actor, project: Project, ip):
    """New version without the project; refused when other projects depend on it.

    Deleting an applied project runs this first: it is not an action of its own any more (owner,
    2026-10-25: «Retirar del espacio» is gone from the interface), and the guard stays because a
    report of another project may use this one.
    """
    from app.projects import specs
    from app.workspace import service as workspace_service

    _ensure_idle(db, project)
    workspace_service.lock_workspace(db)
    if specs.applied_files(db, project) is None:
        raise ApiError(409, "conflict", M("projects.not_applied"))
    version = _activate_composed(db, actor, ip, origin=f"project-withdraw:{project.slug}",
                                 exclude_slug=project.slug, dependants_of=project.slug)
    now = datetime.now(UTC)
    db.execute(update(Project).where(Project.id == project.id)
               .values(withdrawn_at=now, last_activity_at=now))
    audit_record(db, "project_withdrawn", actor_id=actor.id, ip=ip,
                 detail={"project_id": project.id, "project": project.slug,
                         "version": version.id})
    db.flush()
    return version
