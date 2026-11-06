"""BI projects API (feature 020)."""

import os

from bizview_cli import layout
from fastapi import APIRouter, Body, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import Auth, client_ip, recent_reauth, require_superuser
from app.db import DB
from app.errors import ApiError, not_found, validation
from app.i18n import M
from app.models import AppUser, Project
from app.projects import budgets as project_budgets
from app.projects import fs, history, specs
from app.projects import service as projects

router = APIRouter(prefix="/api/projects")

CLIENT_ERRORS = ("path_not_allowed", "path_unsafe", "path_outside_project", "too_large",
                 "not_text", "project_too_large", "spec_number", "file_changed",
                 "asset_not_restorable")


def path_error(e: fs.ProjectPathError) -> ApiError:
    """HTTP error for a project file error (422 for bad input, 409 for conflicts, else 503)."""
    if e.code == "project_not_found":
        return ApiError(404, "not_found", e.message)
    status = 409 if e.code == "file_changed" else 422 if e.code in CLIENT_ERRORS else 503
    return ApiError(status, e.code, e.message, extra={"current": getattr(e, "current", None)}
                    if e.code == "file_changed" else None)


class ProjectPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    slug: str | None = None


@router.get("")
def list_projects(actor: AppUser = Depends(require_superuser), db: Session = DB):
    projects.purge_trash(db)   # lazy 30-day trash purge (also run by bootstrap)
    return {"projects": projects.list_projects(db), "folder_writable": fs.check_dir()}


#: A project is authored outside Bizview and imported (owner decision, feature 049). The route stays
#: declared so an old client reads why instead of guessing at a 404 or a 405.
CREATION_REMOVED = 410


@router.post("", status_code=CREATION_REMOVED)
def create_project():
    raise ApiError(CREATION_REMOVED, "project_creation_removed",
                   M("projects.creation_removed"))


class LimitsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact_max_files: int | None = Field(default=None, ge=1, le=100_000)
    artifact_max_kb: int | None = Field(default=None, ge=1, le=1_048_576)
    artifact_max_mb: int | None = Field(default=None, ge=1, le=500)
    asset_max_files: int | None = Field(default=None, ge=1, le=100_000)
    asset_max_kb: int | None = Field(default=None, ge=1, le=1_048_576)
    asset_max_mb: int | None = Field(default=None, ge=1, le=2000)


@router.get("/limits")
def import_limits(actor: AppUser = Depends(require_superuser), db: Session = DB):
    """The two import allowances in force, so the browser can refuse before uploading (049)."""
    return project_budgets.json(project_budgets.effective(db), project_budgets.stored(db))


@router.put("/limits")
def save_import_limits(body: LimitsIn, actor: AppUser = Depends(require_superuser),
                       _: Auth = Depends(recent_reauth), db: Session = DB):
    """Change the allowances. A field left null goes back to the deployment default."""
    return project_budgets.store(db, body.model_dump(), actor)


@router.get("/{slug}")
def get_project(slug: str, actor: AppUser = Depends(require_superuser), db: Session = DB):
    from app.projects import revisions

    p = projects.get(db, slug)
    # 055: a project that predates the revisions table gets its revision 1 here — the migration must
    # not read PROJECTS_DIR (research R8). Idempotent: a project with revisions pays one query.
    if revisions.current(db, p) is None:
        revisions.ensure_baseline_quietly(db, p)
        db.commit()
    return projects.detail(db, p, actor)


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
    # `converged` was the in-app agent's flag; 045 removed its producer and both the frontend type
    # and this response were left asking for it, so every project with a spec folder answered 500.
    spec_info = {f"specs/{s['folder']}": {"kind": s["kind"], "stage": s["stage"]}
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


def _editor_revision(db: Session, p: Project, actor: AppUser) -> None:
    """One revision per save (055, FR-008): the folder after the write, whoever wrote it."""
    from app.projects import revisions

    try:
        revisions.register_editor_revision(db, p, _user(actor, "edit"))
        db.commit()
    except (OSError, fs.ProjectPathError):      # the save itself already succeeded
        db.rollback()


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
    _editor_revision(db, p, actor)
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
    _editor_revision(db, p, actor)
    return {"results": results, **projects.revalidate(db, p)}


@router.get("/{slug}/changes")
def project_changes(slug: str, after: int = Query(0, ge=0),
                    actor: AppUser = Depends(require_superuser), db: Session = DB):
    return projects.changes(db, projects.get(db, slug), after)


@router.post("/{slug}/validate")
def validate(slug: str, check_origin: bool = True,
             actor: AppUser = Depends(require_superuser), db: Session = DB):
    """Validate the project; `check_origin` runs every query against its source (the button).

    The editor refreshes problems and readiness with `check_origin=false` after a file changes:
    the source check belongs to the explicit action, not to every keystroke."""
    return projects.revalidate(db, projects.get(db, slug), check_origin=check_origin)


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
               themes: str = Query("skip", pattern="^(skip|replace|rename)$"),
               copy: bool = Query(False), dry_run: bool = Query(False),
               replace_draft: bool = Query(False),
               actor: AppUser = Depends(require_superuser), _: Auth = Depends(recent_reauth),
               db: Session = DB):
    """A zip with one project (raw `application/zip` body): imports it or re-imports it.

    `themes` answers a theme id the installation already has: skip it (default), replace it, or
    rename the project's copy so both survive (047). Feature 055: a slug that already belongs to a
    project makes this a new *revision* of that project; `copy=true` asks for a second project
    instead, `dry_run=true` answers the diff and writes nothing, and `replace_draft=true` accepts
    overwriting editor changes the draft holds."""
    from app.projects import zip as project_zip

    try:
        return project_zip.import_zip(db, actor, data, name=name, slug=slug,
                                      themes_on_conflict=themes, ip=client_ip(request),
                                      copy=copy, dry_run=dry_run, replace_draft=replace_draft)
    except project_zip.ZipRejected as e:
        raise ApiError(413 if e.code == "too_large" else 422, e.code, e.message) from e


@router.get("/{slug}/revisions")
def project_revisions(slug: str, actor: AppUser = Depends(require_superuser), db: Session = DB):
    """The project's own revisions, newest first (feature 055)."""
    from app.projects import revisions

    return revisions.listing(db, projects.get(db, slug))


@router.get("/{slug}/revisions/{number}/zip")
def project_revision_zip(slug: str, number: int, request: Request,
                         actor: AppUser = Depends(require_superuser), db: Session = DB):
    """One revision as a zip with the shape **Exportar** produces."""
    from app.projects import revisions
    from app.projects import zip as project_zip

    p = projects.get(db, slug)
    row = revisions.by_number(db, p, number)
    if row is None:
        raise not_found(M("projects.revision_not_found", number=number))
    data, missing = project_zip.export_revision(db, actor, p, row, client_ip(request))
    headers = {"Content-Disposition": f'attachment; filename="{p.slug}-rev{number}.zip"'}
    if missing:
        # The caller sees which paths the zip could not carry, without failing the download.
        headers["X-Bizview-Missing"] = ",".join(missing)[:1000]
    return Response(data, media_type="application/zip", headers=headers)


@router.post("/{slug}/revisions/{number}/revert")
def revert_revision(slug: str, number: int, request: Request,
                    actor: AppUser = Depends(require_superuser),
                    _: Auth = Depends(recent_reauth), db: Session = DB):
    """Write that revision back as a new draft and apply it (feature 055, FR-012)."""
    from app.projects import revisions

    p = projects.get(db, slug)
    projects.ensure_editable(p)
    result = revisions.revert_to(db, actor, p, number, client_ip(request))
    db.refresh(p)
    return {**result, "project": projects.detail(db, p, actor)}


@router.get("/{slug}/assets/{path:path}")
def project_asset(slug: str, path: str, request: Request,
                  actor: AppUser = Depends(require_superuser), db: Session = DB):
    """An image shipped in the project (044): bytes, ETag and a year of cache.

    Private caching on purpose: the same file is versioned with the project, so the browser may
    keep it, but it is never a public resource — share links read it in the same origin.
    """
    from app.projects import assets as asset_rules

    p = projects.get(db, slug)
    rel = f"assets/{path}"          # the folder is part of the route, not of the caller's string
    try:
        data, content_type, digest = fs.read_asset(p.slug, rel)
    except FileNotFoundError:
        raise not_found(M("projects.file_not_found", path=path)) from None
    except asset_rules.AssetRefused as e:
        raise validation({"path": e.reason}) from e
    except fs.ProjectPathError as e:
        raise path_error(e) from e

    etag = f'"{digest}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(data, media_type=content_type, headers={
        "ETag": etag,
        "Cache-Control": "private, max-age=31536000, immutable",
    })
