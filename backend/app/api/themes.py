"""The theme library (feature 047): the super user's themes, and the one a viewer needs to render.

A theme is data an author wrote outside Bizview against the published schema. Every door that lets
one in — the upload here, the project import, the bootstrap — goes through `app.services.themes`, so
"may this theme exist" has one answer. `GET /api/themes/{id}` is readable by any signed-in viewer
because a report cannot paint without it, and it is cacheable: the row's `updated_at` is the ETag.
"""

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth.deps import client_ip, current_user, require_superuser
from app.db import DB
from app.errors import ApiError, not_found
from app.i18n import M
from app.models import PALETTE_PRESET_IDS, AppearanceSettings, AppUser
from app.services import audit, themes

router = APIRouter()

YAML_TYPE = "text/yaml; charset=utf-8"


class ThemeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    yaml: str = Field(max_length=themes.MAX_UPLOAD_CHARS)


class SettingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme_id: str = Field(max_length=40)


def _invalid(problems) -> ApiError:
    """A refusal the upload dialog can act on: the reasons, each with its path."""
    return ApiError(422, "theme_invalid", M("themes.invalid"),
                    extra={"problems": [{"path": p.path, "code": p.code, "message": p.message}
                                        for p in problems]})


def _find(db: Session, theme_id: str):
    row = themes.get(db, theme_id)
    if row is None:
        raise not_found(M("themes.not_found", id=theme_id))
    return row


def _builtin_refusal(theme_id: str) -> ApiError:
    return ApiError(403, "theme_builtin", M("themes.builtin_immutable", id=theme_id))


@router.get("/api/admin/themes")
def list_themes(_actor: AppUser = Depends(require_superuser), db: Session = DB):
    return {"themes": [themes.body(row) for row in themes.listing(db)],
            "installation": themes.installation(db)}


@router.post("/api/admin/themes", status_code=201)
def upload_theme(
    body: ThemeIn,
    request: Request,
    replace: bool = Query(default=False),
    actor: AppUser = Depends(require_superuser),
    db: Session = DB,
):
    data, problems = themes.parse(body.yaml)
    if problems or data is None:
        raise _invalid(problems)

    theme_id = str(data["id"])
    existing = themes.get(db, theme_id)
    if existing is not None and existing.origin == themes.BUILTIN_ORIGIN:
        raise _builtin_refusal(theme_id)
    if existing is not None and not replace:
        raise ApiError(409, "theme_exists",
                       M("themes.exists", id=theme_id, version=existing.version),
                       extra={"id": theme_id, "version": existing.version})

    row, replaced = themes.save(db, data, created_by=actor.id)
    audit.record(db, "theme_replaced" if replaced else "theme_uploaded", actor_id=actor.id,
                 ip=client_ip(request), detail={"id": row.id, "version": row.version})
    return {"theme": themes.body(row)}


@router.delete("/api/admin/themes/{theme_id}", status_code=204)
def delete_theme(
    theme_id: str,
    request: Request,
    actor: AppUser = Depends(require_superuser),
    db: Session = DB,
):
    row = _find(db, theme_id)
    if row.origin == themes.BUILTIN_ORIGIN:
        raise _builtin_refusal(theme_id)
    used = themes.reports_using(db, theme_id)
    if used:
        raise ApiError(409, "theme_in_use", M("themes.in_use", id=theme_id, count=len(used)),
                       extra={"reports": used})
    audit.record(db, "theme_deleted", actor_id=actor.id, ip=client_ip(request),
                 detail={"id": theme_id, "origin": row.origin})
    db.delete(row)
    return Response(status_code=204)


@router.get("/api/admin/themes/{theme_id}/download")
def download_theme(theme_id: str, _actor: AppUser = Depends(require_superuser), db: Session = DB):
    row = _find(db, theme_id)
    return Response(content=themes.as_yaml(row), media_type=YAML_TYPE,
                    headers={"Content-Disposition": f'attachment; filename="{row.id}.yaml"'})


@router.get("/api/themes/{theme_id}")
def read_theme(theme_id: str, request: Request, response: Response,
               _user: AppUser = Depends(current_user), db: Session = DB):
    row = _find(db, theme_id)
    etag = themes.etag(row)
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, max-age=60"
    return {"id": row.id, "name": row.name, "name_en": row.name_en, "version": row.version,
            "origin": row.origin, "tokens": row.tokens,
            "light": themes.tokens(row, "light"), "dark": themes.tokens(row, "dark")}


@router.put("/api/admin/settings/theme")
def set_installation_theme(body: SettingIn, request: Request,
                           actor: AppUser = Depends(require_superuser), db: Session = DB):
    if themes.get(db, body.theme_id) is None:
        raise ApiError(422, "theme_unknown", M("themes.unknown", id=body.theme_id),
                       extra={"theme_id": body.theme_id})
    previous = themes.installation(db)
    row = db.get(AppearanceSettings, 1, with_for_update=True)
    if row is None:
        row = AppearanceSettings(id=1)
        db.add(row)
    row.theme_id = body.theme_id
    # The preset column cannot hold a custom id (its check lists the five), so it follows the
    # choice only when the choice is one of them: the chain reads `theme_id` first regardless.
    if body.theme_id in PALETTE_PRESET_IDS:
        row.palette_preset = body.theme_id
    row.updated_by = actor.id
    audit.record(db, "theme_applied", actor_id=actor.id, ip=client_ip(request),
                 detail={"theme_id": {"from": previous, "to": body.theme_id}})
    return {"theme_id": body.theme_id}
