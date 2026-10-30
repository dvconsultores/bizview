"""BI projects API (feature 020)."""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from bizview_cli import layout
from fastapi import APIRouter, Body, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import Auth, client_ip, recent_reauth, require_superuser
from app.config import get_settings
from app.db import DB
from app.errors import ApiError, not_found, validation
from app.i18n import M
from app.models import AppUser, AssistantSession, Project
from app.projects import fs, history, specs
from app.projects import service as projects

router = APIRouter(prefix="/api/projects")

CLIENT_ERRORS = ("path_not_allowed", "path_unsafe", "path_outside_project", "too_large",
                 "not_text", "project_too_large", "spec_number", "file_changed")


def path_error(e: fs.ProjectPathError) -> ApiError:
    """HTTP error for a project file error (422 for bad input, 409 for conflicts, else 503)."""
    if e.code == "project_not_found":
        return ApiError(404, "not_found", e.message)
    status = 409 if e.code == "file_changed" else 422 if e.code in CLIENT_ERRORS else 503
    return ApiError(status, e.code, e.message, extra={"current": getattr(e, "current", None)}
                    if e.code == "file_changed" else None)


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    slug: str | None = None
    description: str = Field(default="", max_length=500)


class ProjectPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    slug: str | None = None


@router.get("")
def list_projects(actor: AppUser = Depends(require_superuser), db: Session = DB):
    projects.purge_trash(db)   # lazy 30-day trash purge (also run by bootstrap)
    return {"projects": projects.list_projects(db), "folder_writable": fs.check_dir()}


@router.get("/slug")
def suggest_slug(name: str = Query(min_length=1, max_length=80),
                 actor: AppUser = Depends(require_superuser), db: Session = DB):
    return {"slug": projects.suggest_slug(db, name)}


@router.post("", status_code=201)
def create_project(body: ProjectCreate, request: Request,
                   actor: AppUser = Depends(require_superuser), db: Session = DB):
    project = projects.create(db, actor, body.name, body.slug, body.description,
                              client_ip(request))
    return projects.project_json(project)


@router.get("/{slug}")
def get_project(slug: str, actor: AppUser = Depends(require_superuser), db: Session = DB):
    return projects.detail(db, projects.get(db, slug), actor)


@router.patch("/{slug}")
def patch_project(slug: str, body: ProjectPatch, request: Request,
                  actor: AppUser = Depends(require_superuser), db: Session = DB):
    from app.services import audit

    p = projects.get(db, slug)
    old_slug = p.slug
    wanted = {"name": body.name.strip() if body.name is not None else None,
              "slug": body.slug or None, "description": body.description}
    changed = [field for field, value in wanted.items()
               if value is not None and value != getattr(p, field)]
    moved: tuple | None = None
    if body.slug and body.slug != p.slug:
        if p.first_applied_at is not None:
            raise ApiError(409, "slug_locked", M("projects.slug_locked"))
        if not layout.ID_RE.match(body.slug):
            raise validation({"slug": "pattern"}, M("projects.slug_pattern"))
        taken = db.scalar(select(Project.id).where(Project.slug == body.slug,
                                                   Project.deleted_at.is_(None)))
        new_root = fs.project_root(body.slug)
        if taken or new_root.exists():
            raise ApiError(409, "slug_taken", M("projects.slug_taken", slug=body.slug))
        old_root = fs.project_root(p.slug)
        if old_root.exists():
            old_root.rename(new_root)
            moved = (new_root, old_root)
        p.slug = body.slug
    if body.name is not None:
        p.name = body.name.strip()
    if body.description is not None:
        p.description = body.description
    if changed:                                                   # plan §2 audit kinds
        audit.record(db, "project_updated", actor_id=actor.id, ip=client_ip(request),
                     detail={"project_id": p.id, "project": p.slug, "fields": changed,
                             **({"old_slug": old_slug, "new_slug": p.slug}
                                if p.slug != old_slug else {})})
    created = p.created_at.date().isoformat()
    try:
        db.commit()
    except Exception:
        if moved:
            moved[0].rename(moved[1])
        raise
    try:
        fs.apply_ops(p.id, [{
            "op": "write", "path": "project.yaml",
            "content": projects.project_yaml(p.name, p.slug, p.description, created),
            "base_sha256": None, "force": True,
        }], {"kind": "user", "user_id": actor.id, "session_id": None, "command": "rename"})
    except fs.ProjectPathError as e:
        raise path_error(e) from e
    db.refresh(p)
    return projects.detail(db, p, actor)


@router.get("/{slug}/tree")
def project_tree(slug: str, actor: AppUser = Depends(require_superuser), db: Session = DB):
    p = projects.get(db, slug)
    history.sync_external(db, p)
    db.commit()
    files, ignored = fs.list_files(p.slug)
    folders: set[str] = set()
    root = fs.project_root(p.slug)
    if root.is_dir():
        for dirpath, dirnames, _files in os.walk(root, followlinks=False):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") or d == ".specify"]
            rel_dir = os.path.relpath(dirpath, root)
            if rel_dir != "." and layout.is_allowed_folder(rel_dir):
                folders.add(rel_dir)
    for path in files:
        parent = os.path.dirname(path)
        while parent:
            if layout.is_allowed_folder(parent):
                folders.add(parent)
            parent = os.path.dirname(parent)
    spec_info = {f"specs/{s['folder']}": {"kind": s["kind"], "stage": s["stage"],
                                          "converged": s["converged"]}
                 for s in specs.list_specs(db, p)}
    return {
        "files": [{"path": path, "size": size, "sha256": digest}
                  for path, (size, digest) in sorted(files.items())],
        "specs": spec_info,
        "status": projects.status(db, p)[0],
        "folders": sorted(folders),
        "ignored": ignored,
    }


@router.get("/{slug}/file")
def project_file(slug: str, path: str = Query(min_length=1, max_length=240),
                 actor: AppUser = Depends(require_superuser), db: Session = DB):
    p = projects.get(db, slug)
    try:
        content = fs.read_text(p.slug, path)
    except FileNotFoundError:
        raise not_found(M("projects.file_not_found", path=path)) from None
    except fs.ProjectPathError as e:
        raise path_error(e) from e
    rev = history.latest(db, p.id, path)
    return {"path": path, "content": content, "sha256": history.sha(content),
            "revision_id": rev.id if rev else None}


class FileSave(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=240)
    content: str = Field(max_length=600_000)
    base_sha256: str | None = None
    force: bool = False


class OpsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ops: list[dict] = Field(min_length=1, max_length=50)


OP_COMMANDS = {"rename": "rename", "delete": "delete", "rmdir": "delete", "mkdir": "edit"}


def _user(actor: AppUser, command: str) -> dict:
    return {"kind": "user", "user_id": actor.id, "session_id": None, "command": command}


@router.put("/{slug}/file")
def save_file(slug: str, body: FileSave, actor: AppUser = Depends(require_superuser),
              db: Session = DB):
    p = projects.get(db, slug)
    projects.ensure_editable(p)
    db.commit()  # apply_ops writes in its own transaction
    try:
        res = fs.apply_ops(p.id, [{"op": "write", "path": body.path, "content": body.content,
                                   "base_sha256": body.base_sha256, "force": body.force}],
                           _user(actor, "edit"))
    except fs.ProjectPathError as e:
        raise path_error(e) from e
    return {"file": {"path": body.path, "sha256": res[0]["sha256"],
                     "revision_id": res[0]["revision_id"]},
            **projects.revalidate(db, p)}


@router.post("/{slug}/ops")
def file_ops(slug: str, body: OpsBody, actor: AppUser = Depends(require_superuser),
             db: Session = DB):
    p = projects.get(db, slug)
    projects.ensure_editable(p)
    if any(op.get("op") not in OP_COMMANDS for op in body.ops):
        raise validation({"ops": "op"})
    db.commit()
    results = []
    for op in body.ops:
        try:
            results.extend(fs.apply_ops(p.id, [op], _user(actor, OP_COMMANDS[op["op"]])))
        except fs.ProjectPathError as e:
            raise path_error(e) from e
    return {"results": results, **projects.revalidate(db, p)}


@router.get("/{slug}/changes")
def project_changes(slug: str, after: int = Query(0, ge=0),
                    actor: AppUser = Depends(require_superuser), db: Session = DB):
    return projects.changes(db, projects.get(db, slug), after)


@router.post("/{slug}/validate")
def validate(slug: str, actor: AppUser = Depends(require_superuser), db: Session = DB):
    return projects.revalidate(db, projects.get(db, slug), check_origin=True)


def _conversation(db: Session, p: Project, actor: AppUser):
    """The caller's latest conversation of the project (preview requests run in one).

    Feature 037: filtered by the caller, not only by project. Taking any user's newest conversation
    wrote the request, its outcome message and the project's `preview` into a conversation the
    caller was not looking at, so the result appeared in somebody else's chat.
    """
    from app.assistant import service as assistant

    session = db.scalars(select(AssistantSession)
                         .where(AssistantSession.project_id == p.id,
                                AssistantSession.created_by == actor.id)
                         .order_by(AssistantSession.updated_at.desc()).limit(1)).first()
    return session or assistant.create_session(db, actor, project_id=p.id)


@router.post("/{slug}/apply")
def apply_project(slug: str, request: Request, actor: AppUser = Depends(require_superuser),
                  _: Auth = Depends(recent_reauth), db: Session = DB):
    from app.projects import apply as project_apply
    from app.workspace import service as workspace_service

    p = projects.get(db, slug)
    version, revalidated = project_apply.apply_project(db, actor, p, client_ip(request))
    db.refresh(p)
    return {"version": workspace_service.version_json(version), "revalidated": revalidated,
            "project": projects.detail(db, p, actor)}


class FixIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    file: str = Field(min_length=1, max_length=400)
    json_path: str = Field(min_length=1, max_length=400)
    op: str = Field(min_length=3, max_length=10)
    value: object = None
    base_sha256: str | None = None
    problem_id: str | None = Field(default=None, max_length=400)


class FixesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fixes: list[FixIn] = Field(min_length=1, max_length=50)


@router.post("/{slug}/fix")
def apply_fixes(slug: str, body: FixesIn, request: Request,
                actor: AppUser = Depends(require_superuser),
                _: Auth = Depends(recent_reauth), db: Session = DB):
    """Apply the deterministic corrections validation published (035 FR-011/FR-012).

    Works with the AI off: it never touches the provider. The response carries the applied diffs
    and the new validation, so the panel updates without a second round trip.
    """
    from app.api.appearance import preset_of
    from app.projects import fixes as project_fixes

    p = projects.get(db, slug)
    db.commit()                                     # apply_ops writes in its own transaction
    return project_fixes.apply_fixes(db, actor, p, [f.model_dump() for f in body.fixes],
                                     client_ip(request),
                                     installation_palette=preset_of(db))


@router.delete("/{slug}", status_code=204)
def delete_project(slug: str, request: Request, actor: AppUser = Depends(require_superuser),
                   _: Auth = Depends(recent_reauth), db: Session = DB):
    projects.delete_project(db, actor, projects.get(db, slug), client_ip(request))
    return Response(status_code=204)


@router.post("/{slug}/preview")
def request_preview(slug: str, actor: AppUser = Depends(require_superuser), db: Session = DB):
    from app.assistant import preview as assistant_preview
    from app.assistant import service as assistant

    session = _conversation(db, projects.get(db, slug), actor)
    assistant.ensure_idle(db, session, get_settings())
    return {"preview": assistant_preview.request_preview(db, actor, session)}


@router.get("/{slug}/preview/report/{report_id}")
def preview_report(slug: str, report_id: str, actor: AppUser = Depends(require_superuser),
                   db: Session = DB):
    from app.assistant import preview as assistant_preview

    session = _conversation(db, projects.get(db, slug), actor)
    return assistant_preview.report_definition(db, session, report_id)


def _preview_data(db: Session, session, report_id: str, request: Request) -> dict:
    from app.assistant import preview as assistant_preview

    settings = get_settings()
    return assistant_preview.report_data(
        db, session, report_id, request.query_params.multi_items(),
        datetime.now(ZoneInfo(settings.timezone)).date(), settings.timezone)


@router.get("/{slug}/preview/report/{report_id}/data")
def preview_report_data(slug: str, report_id: str, request: Request,
                        actor: AppUser = Depends(require_superuser), db: Session = DB):
    return _preview_data(db, _conversation(db, projects.get(db, slug), actor), report_id,
                         request)


@router.post("/{slug}/preview/report/{report_id}/pdf")
def preview_report_pdf(slug: str, report_id: str, request: Request,
                       actor: AppUser = Depends(require_superuser), db: Session = DB):
    from app.assistant import preview as assistant_preview
    from app.reports import palette, pdf

    session = _conversation(db, projects.get(db, slug), actor)
    definition = assistant_preview.report_definition(db, session, report_id)
    if not definition["pdf"]:
        raise not_found(M("report.pdf_not_allowed"))
    settings = get_settings()
    content = pdf.render_preview(definition, _preview_data(db, session, report_id, request),
                                 report_id=report_id,
                                 organization=settings.organization_name,
                                 product=settings.product_name, viewer=actor.full_name,
                                 palette=palette.resolve(definition,
                                                          palette.installation_preset(db)))
    return Response(content, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{report_id}-vista-previa.pdf"'})


@router.get("/{slug}/history")
def project_history(slug: str, path: str | None = None, spec: str | None = None,
                    before: int | None = None, limit: int = Query(50, ge=1, le=100),
                    actor: AppUser = Depends(require_superuser), db: Session = DB):
    p = projects.get(db, slug)
    return history.list_revisions(db, p.id, path=path, spec=spec, before_id=before, limit=limit)


def _revision(db: Session, p: Project, rid: int):
    rev = history.get_revision(db, p.id, rid)
    if rev is None:
        raise not_found(M("projects.file_not_found", path=str(rid)))
    return rev


@router.get("/{slug}/history/{rid}")
def project_revision(slug: str, rid: int, actor: AppUser = Depends(require_superuser),
                     db: Session = DB):
    rev = _revision(db, projects.get(db, slug), rid)
    return {**history._rev_json(rev, {}), "content": rev.content}


@router.get("/{slug}/diff")
def project_diff(slug: str, from_: int = Query(alias="from"), to: int | None = None,
                 actor: AppUser = Depends(require_superuser), db: Session = DB):
    p = projects.get(db, slug)
    rev = _revision(db, p, from_)
    if to is not None:
        after = _revision(db, p, to).content
    else:
        try:
            after = fs.read_text(p.slug, rev.path)
        except FileNotFoundError:
            after = None
        except fs.ProjectPathError as e:
            raise path_error(e) from e
    return {"path": rev.path, **history.diff(rev.content, after)}


class RestoreBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_sha256: str | None = None


@router.post("/{slug}/history/{rid}/restore")
def restore_revision(slug: str, rid: int, body: RestoreBody,
                     actor: AppUser = Depends(require_superuser), db: Session = DB):
    p = projects.get(db, slug)
    projects.ensure_editable(p)
    db.commit()
    try:
        results = history.restore(db, p, rid, body.base_sha256, _user(actor, "restore"))
    except fs.ProjectPathError as e:
        raise path_error(e) from e
    return {"results": results, **projects.revalidate(db, p)}


@router.get("/{slug}/specs/{folder}/timeline")
def spec_timeline(slug: str, folder: str, actor: AppUser = Depends(require_superuser),
                  db: Session = DB):
    if not layout.SPEC_FOLDER_RE.match(folder):
        raise not_found(M("projects.spec_unknown", folder=folder))
    return history.spec_timeline(db, projects.get(db, slug), folder)


@router.post("/{slug}/convert")
def convert_project(slug: str, request: Request, actor: AppUser = Depends(require_superuser),
                    _: Auth = Depends(recent_reauth), db: Session = DB):
    """A `git` project becomes an app project (R9): Git applies with its slug are refused."""
    from app.services import audit

    p = projects.get(db, slug)
    if p.origin != "git":
        raise ApiError(409, "conflict", M("projects.not_git"))
    p.origin = "app"
    audit.record(db, "project_converted", actor_id=actor.id, ip=client_ip(request),
                 detail={"project_id": p.id, "project": p.slug})
    db.flush()
    return projects.detail(db, p, actor)


@router.get("/{slug}/export.zip")
def export_zip(slug: str, request: Request, actor: AppUser = Depends(require_superuser),
               db: Session = DB):
    from app.projects import zip as project_zip

    p = projects.get(db, slug)
    return Response(project_zip.export(db, actor, p, client_ip(request)),
                    media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{p.slug}.zip"'})


@router.post("/import")
def import_zip(request: Request, data: bytes = Body(..., media_type="application/zip"),
               name: str | None = Query(None, max_length=80),
               slug: str | None = Query(None, max_length=50),
               actor: AppUser = Depends(require_superuser), _: Auth = Depends(recent_reauth),
               db: Session = DB):
    """A zip with one project (raw `application/zip` body) becomes a new project (R13)."""
    from app.projects import zip as project_zip

    if len(data) > get_settings().project_max_mb * 1024 * 1024:
        raise ApiError(413, "too_large", M("projects.zip_invalid", reason="size"))
    try:
        return project_zip.import_zip(db, actor, data, name=name, slug=slug,
                                      ip=client_ip(request))
    except project_zip.ZipRejected as e:
        raise ApiError(413 if e.code == "too_large" else 422, e.code, e.message) from e
