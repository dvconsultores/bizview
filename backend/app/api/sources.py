"""Data-source catalogue (feature 004): super user only; changes and tests need step-up."""
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.tokens import token_or_session
from app.auth.deps import Auth, client_ip, recent_reauth, require_superuser
from app.config import get_settings
from app.db import DB
from app.engine import direct
from app.engine.extract import ExtractError
from app.engine.runner import _safe_message
from app.errors import ApiError, not_found
from app.i18n import M
from app.models import ApiToken, AppUser
from app.services import audit
from app.sources import describe as describer
from app.sources import schemas, service

router = APIRouter(prefix="/api/sources")


class SourceIn(BaseModel):
    name: str = Field(max_length=200)
    kind: str = Field(max_length=20)
    description: str = Field(default="", max_length=300)
    enabled: bool = True
    direct_reports: bool | None = None
    settings: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str | None] = Field(default_factory=dict)


class SourcePatch(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    kind: str | None = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=300)
    enabled: bool | None = None
    direct_reports: bool | None = None
    settings: dict[str, Any] | None = None
    secrets: dict[str, str | None] | None = None


@router.get("/types")
def types(_: AppUser = Depends(require_superuser)):
    return schemas.types_for(get_settings())


@router.get("")
def list_sources(_: AppUser = Depends(require_superuser), db: Session = DB):
    return {"items": [service.to_json(s) for s in service.list_all(db)]}


@router.get("/{source_id}")
def get_source(source_id: int, _: AppUser = Depends(require_superuser), db: Session = DB):
    return service.to_json(service.get(db, source_id))


@router.post("", status_code=201)
def create_source(body: SourceIn, request: Request, actor: AppUser = Depends(require_superuser),
                  _: Auth = Depends(recent_reauth), db: Session = DB):
    src = service.create(db, actor, body.model_dump(), get_settings(), client_ip(request))
    db.flush()
    db.refresh(src)
    return service.to_json(src)


@router.patch("/{source_id}")
def update_source(source_id: int, body: SourcePatch, request: Request,
                  actor: AppUser = Depends(require_superuser), _: Auth = Depends(recent_reauth),
                  db: Session = DB):
    src = service.update(db, actor, service.get(db, source_id),
                         body.model_dump(exclude_unset=True), get_settings(), client_ip(request))
    db.refresh(src)
    return service.to_json(src)


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: int, request: Request, actor: AppUser = Depends(require_superuser),
                  _: Auth = Depends(recent_reauth), db: Session = DB):
    service.delete(db, actor, service.get(db, source_id), client_ip(request))
    return Response(status_code=204)


@router.post("/test")
def test_draft(body: SourceIn, _: AppUser = Depends(require_superuser),
               __: Auth = Depends(recent_reauth)):
    return service.test_draft(body.model_dump(), get_settings()).to_json()


@router.post("/{source_id}/test")
def test_source(source_id: int, request: Request, body: SourcePatch | None = None,
                actor: AppUser = Depends(require_superuser), _: Auth = Depends(recent_reauth),
                db: Session = DB):
    """Test the saved source; with unsaved changes in the body, test them merged with the stored
    credentials (nothing is saved and the last-test result is not updated)."""
    src = service.get(db, source_id)
    changes = body.model_dump(exclude_unset=True) if body else {}
    if changes.get("settings") is not None or changes.get("secrets"):
        return service.test_draft(changes, get_settings(), existing=src).to_json()
    return service.run_test(db, actor, src, get_settings(), client_ip(request)).to_json()


@router.get("/bi/describe")
def describe_bi_database(request: Request,
                         who: tuple[AppUser, ApiToken | None] = Depends(
                             token_or_session("describe")),
                         db: Session = DB):
    """Structure of the BI database for direct reports; never row values."""
    user, token = who
    if not get_settings().direct_reports_bi:
        raise direct.api_error(direct.DirectError("not_allowed"))
    audit.record(db, "source_described", actor_id=user.id, ip=client_ip(request),
                 detail={"source": "bi", "key_id": token.id if token else None})
    try:
        return direct.describe_bi()
    except direct.DirectError as e:
        raise direct.api_error(e) from None
    except Exception:
        raise ApiError(503, "source_error", M("sources.bi_unreadable")) from None


@router.get("/{name}/describe")
def describe_source(name: str, request: Request, path: str | None = None,
                    who: tuple[AppUser, ApiToken | None] = Depends(token_or_session("describe")),
                    db: Session = DB):
    """Structure only, for spec authors (`bizview describe`); never row values."""
    user, token = who
    src = service.by_name(db, name)
    if src is None:
        raise not_found(M("sources.not_found"))
    secrets = service.secrets_of(src)
    audit.record(db, "source_described", actor_id=user.id, ip=client_ip(request),
                 detail={"source": src.name, "key_id": token.id if token else None})
    try:
        return describer.describe(src.kind, src.settings, secrets, get_settings(), path)
    except ExtractError as e:
        raise ApiError(502, "source_error", _safe_message(e, secrets)) from None
    except Exception as e:
        raise ApiError(502, "source_error", _safe_message(e, secrets)) from None

