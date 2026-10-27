"""Reports of the active workspace version (feature 005, contracts/api.md). Access follows the
dashboard catalogue (feature 002): administrators always, users by grant, or every user when the
report spec declares `access.roles: [user]`."""
import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.ai import AIError
from app.auth.deps import current_user
from app.config import get_settings
from app.db import DB
from app.engine import direct, narrative
from app.engine import report as engine
from app.errors import ApiError, not_found
from app.i18n import M
from app.models import AppUser, Dashboard, ReportCache
from app.reports import palette, pdf
from app.services import dashboards
from app.workspace import service as workspace

router = APIRouter(prefix="/api/reports")
log = logging.getLogger("app.reports")


def _context(db: Session, user: AppUser, report_id: str) -> engine.Context:
    version = workspace.active_for_reads(db)
    dash = db.scalar(select(Dashboard).where(Dashboard.report_id == report_id))
    if version is None or dash is None or report_id not in version.artifacts.get("reports", {}):
        raise not_found(M("report.not_found"))
    ctx = engine.cached_context(version, report_id)
    access = ctx.definition.get("access") or {}
    roles = access.get("roles") or ["admin"]
    # `grants: true` in the report means per-user grants are **also** required (schema:
    # "si además se requieren permisos por usuario"): skipping the check because the report lists
    # the `user` role let any user read a report meant to be granted one by one (found while
    # reviewing the owner's ventas-facturacion report, 2026-10-22).
    per_user = access.get("grants") is True
    if per_user or "user" not in roles or dash.status != "available":
        dashboards.check_open(db, user, dash)
    return ctx


def _today():
    return datetime.now(ZoneInfo(get_settings().timezone)).date()


def _cached(db: Session, ctx: engine.Context, key: str, version: str, kind: str, build,
            *, looked_up: bool = False, hit: dict | None = None):
    """The stored payload for this selection and data version, built and stored on a miss.
    `looked_up`: the cache was already read together with the data version (`hit`)."""
    if looked_up:
        if hit is not None:
            return hit
    else:
        row = db.get(ReportCache, (ctx.report_id, key, version, kind))
        if row is not None:
            return row.payload
    payload = jsonable_encoder(build())
    # One round trip: drop entries of older data versions and store this one (a concurrent
    # request for the same key stores the same payload, so a conflict is simply skipped).
    stale = (delete(ReportCache)
             .where(ReportCache.report_id == ctx.report_id, ReportCache.kind == kind,
                    ReportCache.data_version != version)
             .returning(ReportCache.report_id).cte("stale"))
    db.execute(pg_insert(ReportCache)
               .values(report_id=ctx.report_id, selection_hash=key, data_version=version,
                       kind=kind, payload=payload)
               .on_conflict_do_nothing()
               .add_cte(stale))
    return payload


def _data(db: Session, ctx: engine.Context, params: Iterable[tuple[str, str]]) -> dict:
    tz = get_settings().timezone
    sel, filters = engine.selection(ctx, params, _today())
    key = engine.selection_hash(sel, filters)
    if ctx.direct is not None:
        payload = direct.cached_data(db, ctx, sel, filters, key, tz)
        fr = payload.get("freshness") or {}
        etag = (f'"{fr.get("data_version")}-{key}-stale"' if fr.get("stale")
                else f'"{fr.get("data_version")}-{key}"')
        return {**payload, "etag": etag}
    version, updated, hit = engine.data_version_and_cached(db, ctx, key, "data")
    reference = engine.render_reference()
    payload = _cached(db, ctx, key, version, "data", lambda: {
        "selection": sel.to_json(), "filters": filters,
        "render_reference": reference,
        "freshness": {"updated_at": updated, "data_version": version},
        "views": engine.run_views(engine.routed(db, ctx), sel, filters, tz,
                                  reference=reference)},
        looked_up=True, hit=hit)
    return {**payload, "etag": f'"{version}-{key}"'}


def filter_values(ctx: engine.Context, dimension: str, sel,
                  q: str | None, db: Session | None = None) -> tuple[list[str], bool]:
    """Filter options; for direct reports the source errors become API errors."""
    if db is not None:
        ctx = engine.routed(db, ctx)
    try:
        return engine.filter_options(ctx, dimension, sel, get_settings().timezone, q=q)
    except direct.DirectError as e:
        raise direct.api_error(e) from None


@router.get("/{report_id}")
def get_report(report_id: str, user: AppUser = Depends(current_user), db: Session = DB):
    return engine.definition_json(_context(db, user, report_id))


@router.get("/{report_id}/data")
def report_data(report_id: str, request: Request, response: Response,
                user: AppUser = Depends(current_user), db: Session = DB):
    payload = _data(db, _context(db, user, report_id), request.query_params.multi_items())
    etag = payload.pop("etag")
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    return payload


@router.get("/{report_id}/version")
def report_version(report_id: str, response: Response,
                   user: AppUser = Depends(current_user), db: Session = DB):
    version, updated = engine.data_version(db, _context(db, user, report_id))
    response.headers["Cache-Control"] = "no-store"
    return {"data_version": version, "updated_at": updated}


@router.get("/{report_id}/filters/{dimension}")
def filter_options(report_id: str, dimension: str, request: Request,
                   user: AppUser = Depends(current_user), db: Session = DB):
    ctx = _context(db, user, report_id)
    if dimension not in (ctx.definition.get("filters") or []):
        raise not_found(M("report.filter_not_found"))
    sel, _ = engine.selection(ctx, request.query_params.multi_items(), _today())
    q = request.query_params.get("q")
    items, truncated = filter_values(ctx, dimension, sel, q, db=db)
    return {"items": items, "truncated": truncated}


@router.get("/{report_id}/narrative")
def report_narrative(report_id: str, request: Request, user: AppUser = Depends(current_user),
                     db: Session = DB):
    ctx = _context(db, user, report_id)
    if not (ctx.definition.get("ai_narrative") or {}).get("enabled"):
        raise not_found(M("report.no_ai_summary"))
    settings = get_settings()
    if not settings.ai_enabled:
        raise ApiError(503, "ai_unavailable", M("report.ai_unavailable"))
    sel, filters = engine.selection(ctx, request.query_params.multi_items(), _today())
    version, _ = engine.data_version(db, ctx)
    key = engine.selection_hash(sel, filters, "narrative")
    try:
        return _cached(db, ctx, key, version, "narrative", lambda: {
            "text": narrative.generate(ctx, sel, filters, settings.timezone, settings),
            "generated_at": datetime.now(UTC)})
    except AIError as e:
        log.warning("narrative for %s failed: %s", report_id, e.code)
        raise ApiError(503, "ai_unavailable", e.message) from None
    except direct.DirectError as e:
        raise direct.api_error(e) from None


@router.post("/{report_id}/pdf")
def report_pdf(report_id: str, request: Request, user: AppUser = Depends(current_user),
               db: Session = DB):
    ctx = _context(db, user, report_id)
    definition = engine.definition_json(ctx)
    if not definition["pdf"]:
        raise not_found(M("report.pdf_not_allowed"))
    payload = _data(db, ctx, request.query_params.multi_items())
    settings = get_settings()
    content = pdf.render(definition, payload, organization=settings.organization_name,
                         product=settings.product_name, viewer=user.full_name,
                         palette=palette.resolve(definition, palette.installation_preset(db)))
    period = payload["selection"]["current"]
    name = f"{report_id}-{period['from']}-{period['to']}.pdf"
    return Response(content, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
