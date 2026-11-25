"""Dashboard widgets: one dashboard embedded in another web page (feature 065).

A widget is a **standing, revocable permission**: no expiry unless the admin sets one, at most 50
active per dashboard (counted apart from the 20 share links of feature 018), and a key stored as its
SHA-256 only. The public door is `/api/widgets/{token}`; the framed document is the SPA at
`/w/<key>`,
whose framing permission is the widget's own site list and nothing else.

Feature 018's code paths are reused, never copied: `links.report_context`, `links.sharing_enabled`
and `links.public_base` decide what a widget may serve and from which address.
"""

import base64
import hashlib
import hmac
import html
import ipaddress
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import case, func, select
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.engine import report as engine
from app.errors import ApiError, forbidden, not_found, validation
from app.i18n import M
from app.models import AppUser, Dashboard, DashboardWidget, DashboardWidgetSite
from app.services import audit
from app.sharing import links

KEY_BYTES = 32                 # secrets.token_urlsafe(32) → 43 chars, 256 bits
MAX_ACTIVE = 50                # FR-006: per dashboard, counted apart from the 20 share links
MAX_SITES = 10                 # FR-009
NAME_MAX = 80                  # FR-001
PREVIEW_MINUTES = 30           # how long the admin test page may keep framing one widget
UNAVAILABLE = M("widget.unavailable")

_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{20,128}$")
_TICKET_PREFIX = "pv."
_TICKET_RE = re.compile(r"^pv\.(\d+)\.(\d+)\.([A-Za-z0-9_-]{16,64})$")
_HOST_RE = re.compile(r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
                      r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$")
DEFAULT_PORTS = {"http": 80, "https": 443}
#: `period`/`compare`/`from`/`to` with `filter.<dimension>`: what the filter controls change.
#: With the controls switched off the widget ignores them, so editing its address changes nothing
#: (FR-024).
CONTROL_PARAMS = frozenset({"period", "compare", "from", "to"})

#: The site policy the edge applies to every route, with the framing directive decided here.
#: The edge keeps the same string with `frame-ancestors 'none'`;
#: `test_widget_csp_matches_the_edge_default` fails if the two drift.
_CSP_HEAD = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
             "script-src 'self'; connect-src 'self'; font-src 'self'; object-src 'none'")
_CSP_TAIL = "base-uri 'self'; form-action 'self'"
PUBLIC_HEADERS = {
    "X-Robots-Tag": "noindex, nofollow",
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
}


# ---------------------------------------------------------------------------- enabling and keys

def widgets_enabled() -> bool:
    """FR-007: off until the operator enables it, and only ever together with share links."""
    settings = get_settings()
    return bool(settings.embed_widgets_enabled and settings.share_links_enabled)


def new_key() -> str:
    return secrets.token_urlsafe(KEY_BYTES)


def key_hash(raw: str) -> bytes:
    return hashlib.sha256(raw.encode()).digest()


def unavailable() -> ApiError:
    """One neutral answer: revoked, expired, unknown, withdrawn and disabled look the same."""
    return not_found(UNAVAILABLE)


def is_active(widget: DashboardWidget, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    return widget.revoked_at is None and (widget.expires_at is None or widget.expires_at > now)


def state(widget: DashboardWidget, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    if widget.revoked_at is not None:
        return "revoked"
    if widget.expires_at is not None and widget.expires_at <= now:
        return "expired"
    return "active"


def counted_active(db: Session, dash: Dashboard, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    return int(db.scalar(
        select(func.count(DashboardWidget.id)).where(
            DashboardWidget.dashboard_id == dash.id,
            DashboardWidget.revoked_at.is_(None),
            (DashboardWidget.expires_at.is_(None)) | (DashboardWidget.expires_at > now),
        )
    ) or 0)


def ensure_capacity(db: Session, dash: Dashboard) -> None:
    """Refuse the 51st active widget; two concurrent creations cannot both pass (FOR UPDATE)."""
    db.execute(select(Dashboard.id).where(Dashboard.id == dash.id).with_for_update())
    if counted_active(db, dash) >= MAX_ACTIVE:
        raise ApiError(409, "too_many_widgets", M("widget.too_many", n=MAX_ACTIVE),
                       extra={"max_active": MAX_ACTIVE})


# --------------------------------------------------------------------------------- allowed sites

def parse_site(raw: str) -> tuple[str, bool]:
    """One allowed site as a canonical origin, and whether it is a local development address.

    FR-009: a full site address (scheme, host, optional port). Paths, queries, user info, wildcards
    and malformed entries are refused with a message that names the offending value.
    """
    text = (raw or "").strip()
    if not text:
        raise validation({"sites": "required"}, M("widget.site_required"))
    if "*" in text:
        raise validation({"sites": "wildcard"}, M("widget.site_wildcard", site=text))
    parts = urlsplit(text)
    scheme = parts.scheme.lower()
    if not scheme:
        raise validation({"sites": "scheme"}, M("widget.site_scheme", site=text))
    if scheme not in DEFAULT_PORTS:
        raise validation({"sites": "scheme"}, M("widget.site_scheme", site=text))
    if parts.path not in ("", "/") or parts.query or parts.fragment:
        raise validation({"sites": "path"}, M("widget.site_path", site=text))
    if parts.username or parts.password:
        raise validation({"sites": "invalid"}, M("widget.site_invalid", site=text))
    host = (parts.hostname or "").strip().lower()
    if not host:
        raise validation({"sites": "invalid"}, M("widget.site_invalid", site=text))
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
        if not _HOST_RE.fullmatch(host) or host.endswith(".."):
            raise validation({"sites": "invalid"}, M("widget.site_invalid", site=text)) from None
    try:
        port = parts.port
    except ValueError:
        raise validation({"sites": "invalid"}, M("widget.site_invalid", site=text)) from None
    if port == 0:
        raise validation({"sites": "invalid"}, M("widget.site_invalid", site=text))
    origin = f"{scheme}://{host}"
    if port and port != DEFAULT_PORTS[scheme]:
        origin += f":{port}"
    return origin, _is_development(host, address)


def _is_development(
    host: str, address: "ipaddress.IPv4Address | ipaddress.IPv6Address | None"
) -> bool:
    """A local address is marked so it is not forgotten in a public list (FR-020)."""
    if host == "localhost" or host.endswith(".localhost"):
        return True
    if address is None:
        return False
    return bool(address.is_loopback or address.is_private or address.is_link_local)


def normalize_sites(raw_sites: list[str] | None) -> list[tuple[str, bool]]:
    sites: list[tuple[str, bool]] = []
    seen: set[str] = set()
    for raw in raw_sites or []:
        origin, development = parse_site(raw)
        if origin in seen:
            raise validation({"sites": "duplicate"}, M("widget.site_duplicate", site=origin))
        seen.add(origin)
        sites.append((origin, development))
    if not sites:
        raise validation({"sites": "required"}, M("widget.site_required"))
    if len(sites) > MAX_SITES:
        raise validation({"sites": "too_many"}, M("widget.too_many_sites", n=MAX_SITES))
    return sites


def site_origins(db: Session, widget_id: int) -> tuple[str, ...]:
    return tuple(db.scalars(
        select(DashboardWidgetSite.origin)
        .where(DashboardWidgetSite.widget_id == widget_id)
        .order_by(DashboardWidgetSite.id)
    ).all())


def _set_sites(db: Session, widget: DashboardWidget, sites: list[tuple[str, bool]]) -> None:
    db.execute(DashboardWidgetSite.__table__.delete().where(
        DashboardWidgetSite.widget_id == widget.id))
    for origin, development in sites:
        db.add(DashboardWidgetSite(widget_id=widget.id, origin=origin, development=development))


# ---------------------------------------------------------------------------- validation helpers

def clean_name(name: str | None) -> str:
    text = (name or "").strip()
    if not text:
        raise validation({"name": "required"}, M("widget.name_required"))
    if len(text) > NAME_MAX:
        raise validation({"name": "too_long"}, M("widget.name_len", n=NAME_MAX))
    return text


def clean_expiry(expires_at: datetime | None, now: datetime | None = None) -> datetime | None:
    if expires_at is None:
        return None
    moment = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
    if moment <= (now or datetime.now(UTC)):
        raise validation({"expires_at": "past"}, M("widget.expiry_past"))
    return moment


def _require_enabled() -> None:
    settings = get_settings()
    if not settings.embed_widgets_enabled:
        raise ApiError(409, "widgets_disabled", M("widget.disabled"))
    if not settings.share_links_enabled:
        raise ApiError(409, "sharing_disabled", M("widget.share_links_off"))


def shareable(db: Session, dash: Dashboard) -> bool:
    """Whether this dashboard may be embedded at all (share links on, report in the active version,
    the project allows sharing). The sharing screen shows the reason when it is false."""
    if not widgets_enabled():
        return False
    from app.projects.distributions import share_policy

    if dash.report_id:
        policy = share_policy(db, dash.report_id)
        if policy is not None and not policy["allowed"]:
            return False
    return links.report_context(db, dash) is not None


def _require_shareable(db: Session, dash: Dashboard) -> None:
    from app.projects.distributions import share_policy

    if dash.report_id:
        policy = share_policy(db, dash.report_id)
        if policy is not None and not policy["allowed"]:
            raise ApiError(409, "widget_not_shareable", M("widget.not_shareable"))
    if links.report_context(db, dash) is None:
        raise ApiError(409, "widget_not_shareable", M("widget.not_shareable"))


# ------------------------------------------------------------------------------------- admin side

def to_json(widget: DashboardWidget, creator_name: str | None,
            sites: list[DashboardWidgetSite] | None = None) -> dict:
    state_name = state(widget)
    return {
        "id": widget.id,
        "name": widget.name,
        "sites": [{"origin": site.origin, "development": site.development}
                  for site in sites or []],
        "created_by": {"id": widget.created_by, "name": creator_name},
        "created_at": widget.created_at,
        "expires_at": widget.expires_at,
        "revoked_at": widget.revoked_at,
        "state": state_name,
        "active": state_name == "active",
        "theme": widget.theme,
        "language": widget.language,
        "show_title": widget.show_title,
        "show_filters": widget.show_filters,
        "pdf": widget.pdf_enabled,
        "visits": widget.visits,
        "last_visit_at": widget.last_visit_at,
    }


def site_map(db: Session, widget_ids: list[int]) -> dict[int, list[DashboardWidgetSite]]:
    found: dict[int, list[DashboardWidgetSite]] = {}
    if not widget_ids:
        return found
    for site in db.scalars(
        select(DashboardWidgetSite)
        .where(DashboardWidgetSite.widget_id.in_(widget_ids))
        .order_by(DashboardWidgetSite.id)
    ).all():
        found.setdefault(site.widget_id, []).append(site)
    return found


def list_for(db: Session, dash: Dashboard) -> list[dict]:
    rows = db.execute(
        select(DashboardWidget, AppUser.full_name)
        .outerjoin(AppUser, AppUser.id == DashboardWidget.created_by)
        .where(DashboardWidget.dashboard_id == dash.id)
        .order_by(DashboardWidget.created_at.desc(), DashboardWidget.id.desc())
        .limit(200)
    ).all()
    found = site_map(db, [widget.id for widget, _ in rows])
    return [to_json(widget, name, found.get(widget.id)) for widget, name in rows]


def get(db: Session, dash: Dashboard, widget_id: int) -> DashboardWidget:
    widget = db.scalar(
        select(DashboardWidget).where(
            DashboardWidget.id == widget_id, DashboardWidget.dashboard_id == dash.id)
    )
    if widget is None:
        raise not_found(M("widget.not_found"))
    return widget


def create(
    db: Session,
    user: AppUser,
    dash: Dashboard,
    *,
    name: str | None,
    sites: list[str] | None,
    ip: str | None,
    theme: str | None = None,
    language: str | None = None,
    show_title: bool = True,
    show_filters: bool = True,
    pdf: bool = False,
    expires_at: datetime | None = None,
) -> tuple[DashboardWidget, str]:
    if user.role != "admin":
        raise forbidden()
    _require_enabled()
    clean = clean_name(name)
    parsed = normalize_sites(sites)
    expiry = clean_expiry(expires_at)
    _require_shareable(db, dash)
    ensure_capacity(db, dash)

    raw = new_key()
    widget = DashboardWidget(
        dashboard_id=dash.id,
        name=clean,
        key_hash=key_hash(raw),
        theme=theme,
        language=language,
        show_title=show_title,
        show_filters=show_filters,
        pdf_enabled=pdf,
        expires_at=expiry,
        created_by=user.id,
        rate_count=0,
    )
    db.add(widget)
    db.flush()
    _set_sites(db, widget, parsed)
    audit.record(
        db,
        "widget_created",
        actor_id=user.id,
        ip=ip,
        detail={
            "widget": widget.id,
            "dashboard": dash.code,
            "name": clean,
            "sites": [origin for origin, _ in parsed],
            "expires_at": expiry.isoformat() if expiry else None,
        },
    )
    db.refresh(widget)
    return widget, raw


def update(
    db: Session,
    user: AppUser,
    dash: Dashboard,
    widget_id: int,
    changes: dict,
    *,
    ip: str | None,
) -> DashboardWidget:
    """Rename, edit the sites, the appearance or the expiry. A revoked widget cannot come back."""
    if user.role != "admin":
        raise forbidden()
    _require_enabled()
    widget = get(db, dash, widget_id)
    if widget.revoked_at is not None:
        raise ApiError(409, "widget_revoked", M("widget.revoked"))

    changed: list[str] = []
    if "name" in changes:
        clean = clean_name(changes["name"])
        if clean != widget.name:
            widget.name = clean
            changed.append("name")
    if "sites" in changes:
        parsed = normalize_sites(changes["sites"])
        if [origin for origin, _ in parsed] != list(site_origins(db, widget.id)):
            _set_sites(db, widget, parsed)
            changed.append("sites")
    for field, column in (("theme", "theme"), ("language", "language")):
        if field in changes and changes[field] != getattr(widget, column):
            setattr(widget, column, changes[field] or None)
            changed.append(field)
    for field, column in (("show_title", "show_title"), ("show_filters", "show_filters"),
                          ("pdf", "pdf_enabled")):
        if field not in changes:
            continue
        if changes[field] is None:
            # The columns are NOT NULL: an explicit null is a client mistake, answered like every
            # other one in this module (422 with the field) instead of a 500 from the database.
            raise validation({field: "required"}, M("widget.control_required"))
        if changes[field] != getattr(widget, column):
            setattr(widget, column, changes[field])
            changed.append(field)
    if "expires_at" in changes:
        expiry = clean_expiry(changes["expires_at"])
        if expiry != widget.expires_at:
            widget.expires_at = expiry
            changed.append("expires_at")
    if changed:
        db.flush()
        audit.record(
            db,
            "widget_updated",
            actor_id=user.id,
                ip=ip,
            detail={
                "widget": widget.id,
                "dashboard": dash.code,
                "name": widget.name,
                "sites": list(site_origins(db, widget.id)),
                "changed": sorted(changed),
            },
        )
    return widget


def replace_key(
    db: Session, user: AppUser, dash: Dashboard, widget_id: int, *, ip: str | None
) -> tuple[DashboardWidget, str]:
    """FR-011/FR-022: a new snippet; the old key stops working at once, everything else stays."""
    if user.role != "admin":
        raise forbidden()
    _require_enabled()
    widget = get(db, dash, widget_id)
    if widget.revoked_at is not None:
        raise ApiError(409, "widget_revoked", M("widget.revoked"))
    raw = new_key()
    widget.key_hash = key_hash(raw)
    db.flush()
    audit.record(
        db,
        "widget_key_replaced",
        actor_id=user.id,
        ip=ip,
        detail={"widget": widget.id, "dashboard": dash.code},
    )
    return widget, raw


def revoke(
    db: Session, user: AppUser, dash: Dashboard, widget_id: int, *, ip: str | None
) -> DashboardWidget:
    if user.role != "admin":
        raise forbidden()
    widget = get(db, dash, widget_id)
    if widget.revoked_at is None:
        widget.revoked_at = datetime.now(UTC)
        widget.revoked_by = user.id
        audit.record(
            db,
            "widget_revoked",
            actor_id=user.id,
                ip=ip,
            detail={"widget": widget.id, "dashboard": dash.code},
        )
    return widget


# --------------------------------------------------------------------- the preview (test page)

def _secret() -> bytes | None:
    key = get_settings().bizview_secret_key
    if key is None:
        return None
    return hashlib.sha256(b"bizview-widget-preview:" + key.get_secret_value().encode()).digest()


def _sign(secret: bytes, payload: str) -> str:
    digest = hmac.new(secret, payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def preview_ticket(widget_id: int, *, minutes: int = PREVIEW_MINUTES,
                   now: datetime | None = None) -> tuple[str, datetime]:
    """A short-lived ticket for the in-product test page (research R4): the key stays one-way."""
    secret = _secret()
    if secret is None:
        raise ApiError(409, "widget_preview_unavailable", M("widget.preview_unavailable"))
    expires = (now or datetime.now(UTC)) + timedelta(minutes=minutes)
    payload = f"{_TICKET_PREFIX}{widget_id}.{int(expires.timestamp())}"
    return f"{payload}.{_sign(secret, payload)}", expires


def preview_widget_id(ticket: str, *, now: datetime | None = None) -> int | None:
    if not isinstance(ticket, str) or not ticket.startswith(_TICKET_PREFIX):
        return None
    match = _TICKET_RE.fullmatch(ticket)
    if match is None:
        return None
    widget_id, expires, signature = match.groups()
    secret = _secret()
    if secret is None:
        return None
    if not hmac.compare_digest(_sign(secret, f"{_TICKET_PREFIX}{widget_id}.{expires}"), signature):
        return None
    if int(expires) <= int((now or datetime.now(UTC)).timestamp()):
        return None
    return int(widget_id)


def preview(db: Session, user: AppUser, dash: Dashboard, widget_id: int) -> tuple[str, datetime]:
    if user.role != "admin":
        raise forbidden()
    _require_enabled()
    widget = get(db, dash, widget_id)
    if not is_active(widget):
        raise unavailable()
    return preview_ticket(widget.id)


# ------------------------------------------------------------------- the public door (FR-008..)

@dataclass(frozen=True)
class Access:
    widget: DashboardWidget
    dashboard: Dashboard
    ctx: engine.Context
    preview: bool
    token: str
    origins: tuple[str, ...]


def _widget_for_token(db: Session, token: str) -> tuple[DashboardWidget | None, bool]:
    if not isinstance(token, str) or not token:
        return None, False
    if _TICKET_PREFIX in token:
        widget_id = preview_widget_id(token)
        if widget_id is None:
            return None, True
        return db.get(DashboardWidget, widget_id), True
    if not _KEY_RE.fullmatch(token):
        return None, False
    return db.scalar(
        select(DashboardWidget).where(DashboardWidget.key_hash == key_hash(token))), False


def token_known(db: Session, token: str) -> bool:
    """Whether this token names a widget at all, whatever its state (guessing vs. not serving)."""
    widget, _ = _widget_for_token(db, token)
    return widget is not None


def access(db: Session, token: str) -> Access | None:
    """What this token may serve, or None for the one neutral answer.

    A widget that is revoked, expired, unknown, or whose dashboard was withdrawn or whose project
    stopped allowing sharing all land here as None: one message, no hint (FR-013).
    """
    if not widgets_enabled():
        return None
    widget, preview_mode = _widget_for_token(db, token)
    if widget is None or not is_active(widget):
        return None
    dash = db.get(Dashboard, widget.dashboard_id)
    ctx = links.report_context(db, dash)
    if ctx is None:
        return None
    if dash is not None and dash.report_id:
        from app.projects.distributions import share_policy

        policy = share_policy(db, dash.report_id)
        if policy is not None and not policy["allowed"]:
            return None
    return Access(widget=widget, dashboard=dash, ctx=ctx, preview=preview_mode, token=token,
                  origins=site_origins(db, widget.id))


def check_rate(db: Session, widget: DashboardWidget) -> None:
    """FR-015: one ceiling per widget per minute, across all visitors and workers.

    The counter is the widget's own row, bumped by one atomic statement, so a hammered widget locks
    nothing but itself and the signed-in dashboards of the installation are untouched (SC-009).
    """
    limit = get_settings().widget_rate_limit
    now = datetime.now(UTC)
    window = now.replace(second=0, microsecond=0)
    count = db.execute(
        sa_update(DashboardWidget)
        .where(DashboardWidget.id == widget.id)
        .values(
            rate_window_start=window,
            rate_count=case(
                (DashboardWidget.rate_window_start == window,
                 DashboardWidget.rate_count + 1),
                else_=1,
            ),
        )
        .returning(DashboardWidget.rate_count)
    ).scalar_one()
    # Commit now, before the request does any work. GET requests run on an AUTOCOMMIT session and
    # release the row at once, but a POST (the PDF download) uses a transactional session: without
    # this commit its UPDATE would keep the widget's row locked until the PDF had rendered, and
    # every other viewer of that widget would wait on it. The commit also makes the count visible
    # to the other Uvicorn workers immediately, which is what keeps the ceiling exact.
    db.commit()
    if count <= limit:
        return
    raise ApiError(429, "rate_limited", M("widget.rate_limited"),
                   extra={"retry_after_seconds": max(1, 60 - now.second)})


def record_visit(db: Session, widget_id: int) -> None:
    """One document shown; a preview visit is not a usage figure (FR-019)."""
    db.execute(
        sa_update(DashboardWidget)
        .where(DashboardWidget.id == widget_id)
        .values(visits=DashboardWidget.visits + 1, last_visit_at=func.now())
    )


def canonical_origin(value: str | None) -> str | None:
    """An `scheme://host[:port]` from a browser value (a Referer or an origin), or None.

    Lenient on purpose: this parses a query parameter, so a bad value means "no match", never a
    validation error.
    """
    if not value or len(value) > 2048:
        return None
    try:
        parts = urlsplit(value.strip())
        scheme = parts.scheme.lower()
        if scheme not in DEFAULT_PORTS or not parts.hostname:
            return None
        if parts.path not in ("", "/") or parts.query or parts.fragment:
            return None
        if parts.username or parts.password:
            return None
        port = parts.port
    except ValueError:
        return None
    origin = f"{scheme}://{parts.hostname.lower()}"
    if port and port != DEFAULT_PORTS[scheme]:
        origin += f":{port}"
    return origin


def confirmed_parent(access: Access, candidate: str | None,
                     installation_origin: str | None) -> str | None:
    """The one origin this document may post its height to, or None (FR-017).

    The page tells us the origin that framed it (from `document.referrer`); we answer with that
    origin **only** when the widget's own list allows it — or, for the admin's preview, when it is
    the installation itself. The response never publishes the list (FR-008 keeps that to the
    browser's policy), so one widget serving two customers cannot show either of them the other's
    domain, and the embedded page cannot enumerate the entries.
    """
    origin = canonical_origin(candidate)
    if origin is None:
        return None
    if origin in access.origins:
        return origin
    if access.preview and installation_origin and origin == installation_origin:
        return origin
    return None


def query_pairs(widget: DashboardWidget, pairs):
    """FR-024: with the filter controls switched off, the address cannot change what is served."""
    if widget.show_filters:
        return list(pairs)
    return [(key, value) for key, value in pairs
            if key not in CONTROL_PARAMS and not key.startswith("filter.")]


# ------------------------------------------------------------------------- framing (FR-008/014)

def csp_for(sources: list[str] | tuple[str, ...]) -> str:
    """The site policy with this document's own framing allowance."""
    allowed = " ".join(sources) if sources else "'none'"
    return f"{_CSP_HEAD}; frame-ancestors {allowed}; {_CSP_TAIL}"


def frame_headers(db: Session, token: str) -> dict[str, str]:
    """Caddy's `forward_auth` answer for `/w/<token>`: which sites may frame this document.

    Always answers, never fails: an unknown token gets `frame-ancestors 'none'`, so the failure mode
    is "nothing is framed", never "anything is framed". A widget that is no longer serving keeps its
    listed sites here on purpose, so its host page can render the neutral message (FR-013).
    """
    widget, preview_mode = _widget_for_token(db, token)
    if widget is None:
        return {**PUBLIC_HEADERS, "Content-Security-Policy": csp_for(["'none'"])}
    origins = site_origins(db, widget.id)
    sources: list[str] = ["'self'"] if preview_mode else []
    sources.extend(origins)
    return {**PUBLIC_HEADERS, "Content-Security-Policy": csp_for(sources)}


# --------------------------------------------------------------------------------- snippet/html

def widget_url(base: str, token: str) -> str:
    return f"{base.rstrip('/')}/w/{token}"


def snippet(base: str, token: str, widget: DashboardWidget) -> str:
    """The text a developer pastes (FR-002/017/025).

    The inline script only sizes the iframe: it receives `{type, widget, height}`, accepts a message
    only from this installation's origin, and never sees any dashboard data. The widget page applies
    the same rule in reverse: it posts only to the origin that framed it, when that origin is
    allowed.
    """
    url = widget_url(base, token)
    marker = f"bizview-widget-{widget.id}"
    title = html.escape(widget.name, quote=True)
    return (
        "<script>(function(){var m=\"" + marker + "\",o=new URL(\"" + url + "\").origin;"
        "function s(h){if(typeof h!==\"number\"||!isFinite(h))return;"
        "var p=Math.max(160,Math.min(6000,Math.round(h))),"
        "f=document.querySelectorAll('iframe[data-bizview-widget=\"'+m+'\"]');"
        "for(var i=0;i<f.length;i++){f[i].style.height=p+\"px\";}}"
        "window.addEventListener(\"message\",function(e){if(e.origin!==o)return;var d=e.data;"
        "if(!d||d.type!==\"bizview:height\"||d.widget!==m||typeof d.height!==\"number\")return;"
        "s(d.height);});})();</script>\n"
        "<iframe src=\"" + url + "\" title=\"" + title + "\" data-bizview-widget=\"" + marker +
        "\" loading=\"lazy\" style=\"width:100%;min-height:320px;border:0\""
        # The widget page reports its height only to the origin that framed it (FR-017), and the
        # backend confirms that origin against the widget's list. Asking the browser for at least
        # the origin keeps that working on a host page that hides its Referer.
        " referrerpolicy=\"origin\"></iframe>"
    )
