"""Public, read-only access to one dashboard through a widget (feature 065).

Same shape as `app.api.shared` (feature 018) and the same rules: no session is created or read, the
AI narrative is off, the answer is cached by nobody and indexed by nobody. What differs is the
framing: this module also answers Caddy's `forward_auth` question for the framed document, with the
one widget's own list of sites (FR-008) — the site-wide refusal is untouched (research R2).
"""

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.api import reports
from app.auth.deps import client_ip
from app.config import get_settings
from app.db import DB
from app.engine import report as engine
from app.errors import not_found
from app.i18n import M
from app.reports import images, palette, pdf
from app.security import throttle
from app.sharing import widgets

router = APIRouter(prefix="/api/widgets")


def _widget_access(token: str, request: Request, db: Session, *, counted: bool) -> widgets.Access:
    ip = client_ip(request)
    throttle.public_check(ip)
    throttle.share_check(db, ip)

    found = widgets.access(db, token)
    if found is None:
        # Only an unknown key is a guessing attempt; a widget that stopped serving is not.
        if not widgets.token_known(db, token):
            throttle.share_register_failure(db, ip)
            db.commit()
        raise widgets.unavailable()
    if counted:
        widgets.check_rate(db, found.widget)
    return found


def widget_access(token: str, request: Request, db: Session = DB) -> widgets.Access:
    """The token's widget or the one neutral answer, after the address limits of feature 018.

    Also spends one request of the widget's ceiling (FR-015)."""
    return _widget_access(token, request, db, counted=True)


def widget_image_access(token: str, request: Request, db: Session = DB) -> widgets.Access:
    """The same door for images and assets, without spending the ceiling.

    The ceiling protects the database from heavy report queries (FR-015, SC-009); an image is a file
    already on disk. A dashboard with many image tiles makes dozens of requests per view, and the
    responses are `no-store`, so counting them would exhaust 300 a minute with very few visitors.
    The address limits and every validity check still apply.
    """
    return _widget_access(token, request, db, counted=False)


@router.get("/frame/{token}")
def widget_frame(token: str, db: Session = DB):
    """Caddy's question for `/w/<token>`: which sites may frame this document, and nothing else.

    It must never fail, or the host page would show a broken navigation instead of the widget's own
    message; it reads no cookie, counts no visit and is not subject to the request ceiling.
    """
    return Response(status_code=200, headers=widgets.frame_headers(db, token))


@router.get("/{token}")
def get_widget(
    request: Request,
    token: str,
    parent: str | None = Query(default=None, max_length=2048),
    found: widgets.Access = Depends(widget_access),
    db: Session = DB,
):
    ctx = found.ctx
    definition = engine.definition_json(
        ctx, assets_base=f"/api/widgets/{token}/assets",
        images_base=f"/api/widgets/{token}/images")
    # FR-024: the report's own switch AND the widget's. Off means off for the page and the route.
    definition["pdf"] = bool(definition["pdf"] and found.widget.pdf_enabled)
    if not found.preview:
        widgets.record_visit(db, found.widget.id)
    return {
        # FR-008/FR-017: the page gets the one origin it may post its height to (the one that framed
        # it, when the widget's list allows it) and never the list itself, nor the admin's internal
        # name: one widget serving two customers shows neither of them the other's domain.
        "widget": {
            "id": found.widget.id,
            "theme": found.widget.theme,
            "language": found.widget.language,
            "show_title": found.widget.show_title,
            "show_filters": found.widget.show_filters,
            "pdf": definition["pdf"],
            "preview": found.preview,
            "expires_at": found.widget.expires_at,
            "parent_origin": widgets.confirmed_parent(
                found, parent, widgets.canonical_origin(str(request.base_url))),
        },
        "dashboard": {"code": found.dashboard.code, "name": found.dashboard.name,
                      **({"name_en": definition["title_en"]}
                         if definition.get("title_en") else {})},
        "report": definition,
    }


@router.get("/{token}/images/{name}")
def widget_cached_image(
    name: str,
    request: Request,
    found: widgets.Access = Depends(widget_image_access),
):
    """A cached URL image of the widget's report: the same door as its data (044)."""
    return reports.cached_image_response(name, request)


@router.get("/{token}/assets/{set_name}/{key}")
def widget_asset(
    token: str,
    set_name: str,
    key: str,
    request: Request,
    found: widgets.Access = Depends(widget_image_access),
):
    """An image of the widget's report (044): the same door as its data."""
    return reports.asset_response(found.ctx, f"/api/widgets/{token}/assets", set_name, key,
                                  request)


@router.get("/{token}/data")
def widget_data(
    request: Request,
    response: Response,
    found: widgets.Access = Depends(widget_access),
    db: Session = DB,
):
    pairs = widgets.query_pairs(found.widget, request.query_params.multi_items())
    payload = reports._data(db, found.ctx, pairs)
    etag = payload.pop("etag")
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    return payload


@router.get("/{token}/filters/{dimension}")
def widget_filter_options(
    dimension: str,
    request: Request,
    found: widgets.Access = Depends(widget_access),
    db: Session = DB,
):
    ctx = found.ctx
    if dimension not in (ctx.definition.get("filters") or []):
        raise not_found(M("report.filter_not_found"))
    pairs = widgets.query_pairs(found.widget, request.query_params.multi_items())
    sel, _ = engine.selection(ctx, pairs, reports._today())
    q = request.query_params.get("q")
    items, truncated = reports.filter_values(ctx, dimension, sel, q, db=db)
    return {"items": items, "truncated": truncated}


@router.post("/{token}/pdf")
def widget_pdf(
    request: Request,
    found: widgets.Access = Depends(widget_access),
    db: Session = DB,
):
    ctx = found.ctx
    definition = engine.definition_json(ctx)
    # FR-024: a control switched off is refused when requested directly, not just hidden.
    if not definition["pdf"] or not found.widget.pdf_enabled:
        raise not_found(M("report.pdf_not_allowed"))
    pairs = widgets.query_pairs(found.widget, request.query_params.multi_items())
    payload = reports._data(db, ctx, pairs)
    settings = get_settings()
    content = pdf.render(
        definition,
        payload,
        organization=settings.organization_name,
        product=settings.product_name,
        viewer=None,
        palette=palette.resolve(definition, palette.installation_preset(db), db),
        images=images.reader(ctx),
    )
    period = payload["selection"]["current"]
    name = f"{ctx.report_id}-{period['from']}-{period['to']}.pdf"
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
