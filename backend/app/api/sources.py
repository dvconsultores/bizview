"""Data-source catalogue (feature 004): super user only; changes and tests need step-up.

Feature 052 adds the structure pack (`structure.md`/`.json`), the sample requests of a REST source
and the AI-assisted generation of that pack. All of them are metadata: no route here returns a row
value."""
from datetime import UTC, datetime, timedelta
from typing import Any

from bizview_cli.structure import (
    enriched_json,
    enriched_markdown,
    structure_json,
    structure_markdown,
)
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
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
from app.models import ApiToken, AppUser, SourceSampleRequest
from app.services import audit
from app.sources import describe as describer
from app.sources import samples as sample_service
from app.sources import schemas, service, structure_ai
from app.sources import structure as structure_service

router = APIRouter(prefix="/api/sources")


class SourceIn(BaseModel):
    name: str = Field(max_length=200)
    kind: str = Field(max_length=20)
    description: str = Field(default="", max_length=300)
    enabled: bool = True
    direct_reports: bool | None = None
    #: Feature 048: the BI-ready declaration (scope and limits), when the source is one.
    bi_ready: dict[str, Any] | None = None
    settings: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str | None] = Field(default_factory=dict)


class SourcePatch(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    kind: str | None = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=300)
    enabled: bool | None = None
    direct_reports: bool | None = None
    bi_ready: dict[str, Any] | None = None
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
    """The source, its BI-ready declaration, and the last day of direct reads (feature 048)."""
    src = service.get(db, source_id)
    payload = service.to_json(src)
    payload["bi_ready_health"] = health(db, src)
    return payload


def health(db: Session, src) -> dict:
    """Counts and durations of the direct reads this source answered in the last 24 hours.

    Read from the log 019 already writes: a declaration nobody can observe is not a contract."""
    from sqlalchemy import select

    from app.models import DirectReadLog

    since = datetime.now(UTC) - timedelta(hours=24)
    rows = db.execute(
        select(DirectReadLog.duration_ms, DirectReadLog.outcome, DirectReadLog.stale_served)
        .where(DirectReadLog.source == src.name, DirectReadLog.occurred_at >= since)
    ).all()
    from app.sources import bi_ready

    return bi_ready.health_summary(
        [{"duration_ms": row[0], "outcome": row[1], "stale_served": row[2]} for row in rows])


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


# --- feature 052: the structure pack, its generation, the sample requests ----------------------

class NotesIn(BaseModel):
    notes: str = Field(default="", max_length=4000)


class ColumnFlagIn(BaseModel):
    schema_name: str = Field(default="", max_length=200)
    table: str = Field(max_length=200)
    column: str = Field(max_length=200)
    personal: bool


class SampleIn(BaseModel):
    name: str = Field(max_length=80)
    method: str = Field(default="GET", max_length=10)
    path: str = Field(max_length=500)
    params: dict[str, Any] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=1000)


class SamplePatch(BaseModel):
    path: str | None = Field(default=None, max_length=500)
    params: dict[str, Any] | None = None
    notes: str | None = Field(default=None, max_length=1000)


def _source_by_name(db: Session, name: str):
    src = service.by_name(db, name)
    if src is None:
        raise not_found(M("sources.not_found"))
    return src


def _source_error(e: Exception, secrets: dict) -> ApiError:
    return ApiError(502, "source_error", _safe_message(e, secrets))


def _pack(db: Session, src, path: str | None = None) -> dict:
    secrets = service.secrets_of(src)
    try:
        return structure_service.build(db, src, get_settings(), path=path)
    except Exception as e:
        raise _source_error(e, secrets) from None


@router.get("/{name}/structure")
def source_structure(name: str, request: Request, format: str = "json",
                     path: str | None = None, mode: str = "pack",
                     who: tuple[AppUser, ApiToken | None] = Depends(
                         token_or_session("describe")),
                     db: Session = DB):
    """The pack this source produces: `structure.json` (default) or `structure.md`, as a download.

    Since the convergence of 052 the generated pack is what both files carry; `mode=scan` forces the
    plain describe when a super user wants to see the raw catalogue. Structure only, never a row
    value; audited the same way a describe is (FR-003)."""
    user, token = who
    src = _source_by_name(db, name)
    generated = (src.structure_pack or {}) if mode != "scan" else {}
    audit.record(db, "source_described", actor_id=user.id, ip=client_ip(request),
                 detail={"source": src.name, "format": format, "mode": mode,
                         "key_id": token.id if token else None})
    if generated:
        if format == "md":
            return Response(content=enriched_markdown(generated),
                            media_type="text/markdown; charset=utf-8",
                            headers={"Content-Disposition":
                                     'attachment; filename="structure.md"'})
        return Response(content=enriched_json(generated), media_type="application/json",
                        headers={"Content-Disposition":
                                 'attachment; filename="structure.json"'})
    pack = _pack(db, src, path)
    if format == "md":
        return Response(content=structure_markdown(pack),
                        media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="structure.md"'})
    return Response(content=structure_json(pack), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="structure.json"'})


def _pack_document(db: Session, src, path: str | None = None) -> dict:
    """What the tab renders: whether a generated pack exists and what the scan says right now."""
    generated = dict(src.structure_pack or {})
    previous = dict(src.structure_pack_prev or {})
    secrets = service.secrets_of(src)
    try:
        scan_pack = structure_service.build(db, src, get_settings(), path=path)
    except Exception as e:
        scan_pack = None
        error = _safe_message(e, secrets)
    else:
        error = None
    return {"generated": generated or None, "previous": previous or None,
            "scan": scan_pack, "scan_error": error,
            "ai": {"enabled": get_settings().ai_enabled,
                   "model": get_settings().ai_model_effective,
                   "ceiling": get_settings().ai_structure_tokens}}


@router.get("/{name}/structure/pack")
def source_structure_pack(name: str, _: AppUser = Depends(require_superuser), db: Session = DB):
    """The tab's own read: the generated pack, the previous one and the live scan."""
    return _pack_document(db, _source_by_name(db, name))


@router.post("/{name}/structure/generate")
def generate_structure(name: str, request: Request,
                       actor: AppUser = Depends(require_superuser),
                       _: Auth = Depends(recent_reauth), db: Session = DB):
    """One internal pass: scan, AI, verify, save. The super user types nothing (052, FR-004)."""
    src = _source_by_name(db, name)
    if not get_settings().ai_enabled:
        raise ApiError(409, "ai_not_configured", M("sourceStructure.ai_off"),
                       extra={"ai": {"action": "admin_ai"}})
    try:
        result = structure_ai.generate(db, src, get_settings())
    except ApiError:
        raise
    except Exception as e:                 # an unreachable source, a refused credential, ...
        raise _source_error(e, service.secrets_of(src)) from None
    pack = result["pack"]
    audit.record(db, "source_structure_generated", actor_id=actor.id, ip=client_ip(request),
                 # counts only: `tokens` is in the guard's secret vocabulary, so it nests under
                 # `usage` — the audit records what a run cost, never what it read.
                 detail={"source": src.name, "model": pack["generator"].get("model"),
                         "tables": len(pack.get("tables") or []),
                         "dropped": len(pack.get("dropped") or []),
                         "usage": {"total": pack["generator"].get("tokens", 0)}})
    return {**result, "previous": dict(src.structure_pack_prev or {}) or None}


@router.put("/{name}/structure/notes")
def structure_notes(name: str, body: NotesIn, request: Request,
                    actor: AppUser = Depends(require_superuser),
                    _: Auth = Depends(recent_reauth), db: Session = DB):
    src = _source_by_name(db, name)
    src.notes = body.notes
    audit.record(db, "source_structure_notes_updated", actor_id=actor.id, ip=client_ip(request),
                 detail={"source": src.name, "chars": len(body.notes)})
    return {"notes": src.notes}


@router.put("/{name}/structure/columns")
def structure_column(name: str, body: ColumnFlagIn, request: Request,
                     actor: AppUser = Depends(require_superuser),
                     _: Auth = Depends(recent_reauth), db: Session = DB):
    """Toggle one column's personal flag; only a column the describe returns may be set."""
    src = _source_by_name(db, name)
    pack = _pack(db, src)
    known = {str(column.get("name"))
             for table in pack["structure"].get("tables") or []
             if str(table.get("name")) == body.table
             and str(table.get("schema") or "") == body.schema_name
             for column in table.get("columns") or []}
    if body.column not in known:
        raise ApiError(422, "validation", M("sourceStructure.column_not_found"),
                       fields={"column": "unknown"})
    structure_service.set_flag(db, src, schema=body.schema_name, table=body.table,
                               column=body.column, personal=body.personal)
    audit.record(db, "source_structure_flag_changed", actor_id=actor.id, ip=client_ip(request),
                 detail={"source": src.name, "schema": body.schema_name, "table": body.table,
                         "column": body.column, "personal": body.personal})
    return {"schema": body.schema_name, "table": body.table, "column": body.column,
            "personal": body.personal}


def _sample_json(sample) -> dict:
    return {"id": sample.id, "name": sample.name, "method": sample.method, "path": sample.path,
            "params": sample.params or {}, "notes": sample.notes, "last_shape": sample.last_shape,
            "last_suggestions": sample.last_suggestions, "last_status": sample.last_status,
            "last_error": sample.last_error, "last_run_at": sample.last_run_at}


def _require_sample_kind(src) -> None:
    if src.kind not in structure_service.SAMPLE_KINDS:
        raise ApiError(422, "validation", M("sourceStructure.samples_unsupported"),
                       fields={"kind": "unsupported"})


def _sample_of(db: Session, src, sample_id: int):
    sample = db.get(SourceSampleRequest, sample_id)
    if sample is None or sample.source_id != src.id:
        raise not_found(M("sourceStructure.sample_not_found"))
    return sample


@router.get("/{name}/samples")
def list_samples(name: str, _: AppUser = Depends(require_superuser), db: Session = DB):
    src = _source_by_name(db, name)
    rows = db.scalars(select(SourceSampleRequest)
                      .where(SourceSampleRequest.source_id == src.id)
                      .order_by(func.lower(SourceSampleRequest.name))).all()
    return {"items": [_sample_json(row) for row in rows]}


@router.post("/{name}/samples", status_code=201)
def create_sample(name: str, body: SampleIn, request: Request,
                  actor: AppUser = Depends(require_superuser),
                  _: Auth = Depends(recent_reauth), db: Session = DB):
    src = _source_by_name(db, name)
    _require_sample_kind(src)
    clean_name = body.name.strip()
    duplicate = db.scalar(select(SourceSampleRequest).where(
        SourceSampleRequest.source_id == src.id,
        func.lower(SourceSampleRequest.name) == clean_name.lower()))
    if duplicate is not None:
        raise ApiError(409, "conflict", M("sourceStructure.sample_duplicate"))
    try:
        path = sample_service.clean_path(body.path)
        params = sample_service.clean_params(body.params)
    except ExtractError as e:
        raise ApiError(422, "validation", str(e), fields={"path": "invalid"}) from None
    sample = SourceSampleRequest(source_id=src.id, name=clean_name, method=body.method,
                                 path=path, params=params, notes=body.notes)
    db.add(sample)
    db.flush()
    audit.record(db, "source_sample_created", actor_id=actor.id, ip=client_ip(request),
                 detail={"source": src.name, "name": sample.name})
    return _sample_json(sample)


@router.patch("/{name}/samples/{sample_id}")
def update_sample(name: str, sample_id: int, body: SamplePatch, request: Request,
                  actor: AppUser = Depends(require_superuser),
                  _: Auth = Depends(recent_reauth), db: Session = DB):
    src = _source_by_name(db, name)
    sample = _sample_of(db, src, sample_id)
    if body.path is not None:
        try:
            sample.path = sample_service.clean_path(body.path)
        except ExtractError as e:
            raise ApiError(422, "validation", str(e), fields={"path": "invalid"}) from None
    if body.params is not None:
        try:
            sample.params = sample_service.clean_params(body.params)
        except ExtractError as e:
            raise ApiError(422, "validation", str(e), fields={"params": "invalid"}) from None
    if body.notes is not None:
        sample.notes = body.notes
    audit.record(db, "source_sample_updated", actor_id=actor.id, ip=client_ip(request),
                 detail={"source": src.name, "name": sample.name})
    return _sample_json(sample)


@router.delete("/{name}/samples/{sample_id}", status_code=204)
def delete_sample(name: str, sample_id: int, request: Request,
                  actor: AppUser = Depends(require_superuser),
                  _: Auth = Depends(recent_reauth), db: Session = DB):
    src = _source_by_name(db, name)
    sample = _sample_of(db, src, sample_id)
    audit.record(db, "source_sample_deleted", actor_id=actor.id, ip=client_ip(request),
                 detail={"source": src.name, "name": sample.name})
    db.delete(sample)
    return Response(status_code=204)


@router.post("/{name}/samples/{sample_id}/run")
def run_sample(name: str, sample_id: int, request: Request,
               actor: AppUser = Depends(require_superuser),
               _: Auth = Depends(recent_reauth), db: Session = DB):
    """Run one sample through the source's credential and keep its shape (never a value)."""
    src = _source_by_name(db, name)
    _require_sample_kind(src)
    sample = _sample_of(db, src, sample_id)
    if sample.method != "GET":
        raise ApiError(422, "validation", M("sourceStructure.sample_method"),
                       fields={"method": "unsupported"})
    secrets = service.secrets_of(src)
    try:
        result = sample_service.run(src, secrets, get_settings(), sample.path, sample.params)
    except Exception as e:
        sample.last_error = _safe_message(e, secrets)[:200]
        sample.last_run_at = datetime.now(UTC)
        audit.record(db, "source_sample_run", actor_id=actor.id, ip=client_ip(request),
                     detail={"source": src.name, "name": sample.name, "status": "error"})
        # The error is answered, so the request's transaction would roll these two writes back:
        # what the sample did is history, and history is committed before the refusal leaves.
        db.commit()
        raise _source_error(e, secrets) from None
    sample.last_shape = result["shape"]
    sample.last_suggestions = {key: result[key]
                               for key in ("records", "fields", "types", "timestamp_units",
                                           "pagination")}
    sample.last_status = result["status"]
    sample.last_error = None
    sample.last_run_at = datetime.now(UTC)
    audit.record(db, "source_sample_run", actor_id=actor.id, ip=client_ip(request),
                 detail={"source": src.name, "name": sample.name, "status": result["status"]})
    return result
