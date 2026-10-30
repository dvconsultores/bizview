"""Public, read-only access to one dashboard through a share link (feature 018).

No session is created; requests are throttled per address; AI narrative is disabled.
"""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api import reports
from app.auth.deps import client_ip
from app.config import get_settings
from app.db import DB
from app.engine import report as engine
from app.errors import not_found
from app.i18n import M
from app.reports import palette, pdf
from app.security import throttle
from app.sharing import links

router = APIRouter(prefix="/api/shared")

PUBLIC_HEADERS = {
    "X-Robots-Tag": "noindex, nofollow",
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
}


def shared_link(token: str, request: Request, db: Session = DB) -> links.Shared:
    ip = client_ip(request)
    throttle.public_check(ip)
    throttle.share_check(db, ip)

    link = links.find(db, token)
    if link is None:
        # Count only unknown tokens as failures (guessing); expired/revoked known
        # links are not failures.
        throttle.share_register_failure(db, ip)
        db.commit()
        raise links.unavailable()

    shared = links.usable(db, link)
    if shared is None:
        raise links.unavailable()
    return shared


@router.get("/{token}")
def get_shared(
    request: Request,
    share_token: str,
    shared: links.Shared = Depends(shared_link),
    db: Session = DB,
):
    links.record_visit(db, shared.link_id)
    definition = engine.definition_json(shared.ctx, assets_base=f"/api/shared/{share_token}/assets")
    definition["ai_narrative"] = False
    return {
        "dashboard": {"code": shared.dashboard.code, "name": shared.dashboard.name,
                      **({"name_en": definition["title_en"]}
                         if definition.get("title_en") else {})},
        "expires_at": shared.expires_at,
        "theme": shared.theme,
        "report": definition,
    }


@router.get("/{token}/assets/{set_name}/{key}")
def shared_asset(
    request: Request,
    token: str,
    set_name: str,
    key: str,
    shared: links.Shared = Depends(shared_link),
):
    """An image of the report this link points at (044): the same signed door as its data."""
    return reports.asset_response(shared.ctx, f"/api/shared/{token}/assets", set_name, key,
                                 request)


@router.get("/{token}/data")
def shared_data(
    request: Request,
    response: Response,
    shared: links.Shared = Depends(shared_link),
    db: Session = DB,
):
    payload = reports._data(db, shared.ctx, request.query_params.multi_items())
    etag = payload.pop("etag")
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    return payload


@router.get("/{token}/filters/{dimension}")
def shared_filter_options(
    dimension: str,
    request: Request,
    shared: links.Shared = Depends(shared_link),
    db: Session = DB,
):
    ctx = shared.ctx
    if dimension not in (ctx.definition.get("filters") or []):
        raise not_found(M("report.filter_not_found"))
    sel, _ = engine.selection(ctx, request.query_params.multi_items(), reports._today())
    q = request.query_params.get("q")
    items, truncated = reports.filter_values(ctx, dimension, sel, q, db=db)
    return {"items": items, "truncated": truncated}


@router.post("/{token}/pdf")
def shared_pdf(
    request: Request,
    shared: links.Shared = Depends(shared_link),
    db: Session = DB,
):
    ctx = shared.ctx
    definition = engine.definition_json(ctx)
    if not definition["pdf"]:
        raise not_found(M("report.pdf_not_allowed"))
    payload = reports._data(db, ctx, request.query_params.multi_items())
    settings = get_settings()
    content = pdf.render(
        definition,
        payload,
        organization=settings.organization_name,
        product=settings.product_name,
        viewer=None,
        palette=palette.resolve(definition, palette.installation_preset(db)),
    )
    period = payload["selection"]["current"]
    name = f"{ctx.report_id}-{period['from']}-{period['to']}.pdf"
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
