"""Expiring share links for dashboards (feature 018, FR-001..005).

Tokens are generated with 256 bits of randomness and only their SHA-256 digest is
stored. The full link is returned once at creation and never again. A valid link
grants read-only access to exactly one dashboard until it expires, is revoked,
sharing is disabled, or the dashboard becomes unavailable.
"""

import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.engine import report as engine
from app.errors import ApiError, forbidden, not_found, validation
from app.i18n import M
from app.models import AppUser, Dashboard, EmailSend, ShareLink
from app.services import audit
from app.workspace import service as workspace

TOKEN_BYTES = 32           # secrets.token_urlsafe(32) → 43 chars, 256 bits
MAX_ACTIVE = 20
TOO_MANY = M("sharing.too_many", n=MAX_ACTIVE)
MIN_DAYS, MAX_DAYS, DEFAULT_DAYS = 1, 90, 7
NOTE_MAX = 200
UNAVAILABLE = M("sharing.unavailable")

_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,128}$")


def token_hash(raw: str) -> bytes:
    return hashlib.sha256(raw.encode()).digest()


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def unavailable() -> ApiError:
    return not_found(UNAVAILABLE)


def sharing_enabled() -> bool:
    """Shared links are switched on by SHARE_LINKS_ENABLED in the installation environment."""
    return get_settings().share_links_enabled


def report_context(db: Session, dash: Dashboard | None) -> engine.Context | None:
    if dash is None or dash.status != "available" or not dash.report_id:
        return None
    version = workspace.active_for_reads(db)
    if version is None or dash.report_id not in version.artifacts.get("reports", {}):
        return None
    return engine.cached_context(version, dash.report_id)


def is_active(link: ShareLink, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    return link.revoked_at is None and link.expires_at > now


def counted_active(db: Session, dash: Dashboard, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    subscription_link = (
        select(EmailSend.id)
        .where(
            EmailSend.selection["link"]["id"].as_integer() == ShareLink.id,
            or_(
                EmailSend.subscription_id.is_not(None),
                EmailSend.selection["link"].has_key("sub"),
            ),
        )
        .exists()
    )
    active_count = db.scalar(
        select(func.count(ShareLink.id)).where(
            ShareLink.dashboard_id == dash.id,
            ShareLink.revoked_at.is_(None),
            ShareLink.expires_at > now,
            ~subscription_link,
        )
    )
    pending_email = db.scalar(
        select(func.count(EmailSend.id)).where(
            EmailSend.dashboard_id == dash.id,
            EmailSend.subscription_id.is_(None),
            EmailSend.link_days.is_not(None),
            EmailSend.status.in_(("queued", "sending")),
            ~EmailSend.selection.has_key("link"),
        )
    )
    return int(active_count or 0) + int(pending_email or 0)


def ensure_capacity(
    db: Session,
    dash: Dashboard,
    *,
    message: "M | str" = TOO_MANY,
    fields: dict[str, str] | None = None,
) -> None:
    db.execute(
        select(Dashboard.id).where(Dashboard.id == dash.id).with_for_update()
    )
    if counted_active(db, dash) >= MAX_ACTIVE:
        raise ApiError(409, "too_many_links", message, fields=fields)


def origins(db: Session, link_ids: list[int]) -> dict[int, str]:
    if not link_ids:
        return {}
    rows = db.execute(
        select(
            EmailSend.selection["link"]["id"].as_integer(),
            EmailSend.subscription_id,
            EmailSend.selection["link"].has_key("sub"),
        ).where(EmailSend.selection["link"]["id"].as_integer().in_(link_ids))
    ).all()
    result: dict[int, str] = {}
    for link_id, subscription_id, has_sub in rows:
        if subscription_id is not None or has_sub:
            result[int(link_id)] = "subscription"
        else:
            result.setdefault(int(link_id), "email")
    return result


def to_json(link: ShareLink, creator_name: str | None, origin: str = "manual") -> dict:
    return {
        "id": link.id,
        "note": link.note,
        "created_by": {"id": link.created_by, "name": creator_name},
        "created_at": link.created_at,
        "expires_at": link.expires_at,
        "revoked_at": link.revoked_at,
        "visits": link.visits,
        "last_visit_at": link.last_visit_at,
        "active": is_active(link),
        "origin": origin,
        "counted": origin != "subscription",
    }


def list_for(db: Session, dash: Dashboard) -> list[dict]:
    rows = db.execute(
        select(ShareLink, AppUser.full_name)
        .outerjoin(AppUser, AppUser.id == ShareLink.created_by)
        .where(ShareLink.dashboard_id == dash.id)
        .order_by(ShareLink.created_at.desc(), ShareLink.id.desc())
        .limit(100)
    ).all()
    found = origins(db, [link.id for link, _ in rows])
    return [to_json(link, name, found.get(link.id, "manual")) for link, name in rows]


def create(
    db: Session,
    user: AppUser,
    dash: Dashboard,
    *,
    days: int,
    note: str | None,
    ip: str | None,
    counted: bool = True,
) -> tuple[ShareLink, str]:
    if user.role != "admin":
        raise forbidden()
    if not MIN_DAYS <= days <= MAX_DAYS:
        raise validation({"days": "range"})
    from app.projects.distributions import share_policy

    policy = share_policy(db, dash.report_id) if dash.report_id else None
    if policy is not None and not policy["allowed"]:
        raise ApiError(409, "sharing_disabled_by_project", M("sharing.disabled_by_project"))
    if policy is not None and policy["max_days"] is not None and days > policy["max_days"]:
        raise ApiError(422, "share_days_exceed_project",
                       M("sharing.max_days_by_project", max=policy["max_days"]),
                       extra={"max_days": policy["max_days"]})
    clean_note = note.strip() if note else ""
    if not clean_note:
        clean_note = None
    if clean_note is not None and len(clean_note) > NOTE_MAX:
        raise validation({"note": "too_long"})
    if not sharing_enabled():
        raise ApiError(
            409,
            "sharing_disabled",
            M("sharing.disabled"),
        )
    if report_context(db, dash) is None:
        raise ApiError(
            409, "not_shareable", M("sharing.not_shareable")
        )

    if counted:
        ensure_capacity(db, dash)

    now = datetime.now(UTC)
    raw = new_token()
    link = ShareLink(
        dashboard_id=dash.id,
        token_hash=token_hash(raw),
        note=clean_note,
        created_by=user.id,
        expires_at=now + timedelta(days=days),
    )
    db.add(link)
    db.flush()
    audit.record(
        db,
        "share_link_created",
        actor_id=user.id,
        ip=ip,
        detail={
            "link_id": link.id,
            "dashboard": dash.code,
            "days": days,
            "expires_at": link.expires_at.isoformat(),
        },
    )
    db.refresh(link)
    return link, raw


def revoke(
    db: Session,
    user: AppUser,
    dash: Dashboard,
    link_id: int,
    *,
    ip: str | None,
) -> ShareLink:
    link = db.scalar(
        select(ShareLink).where(
            ShareLink.id == link_id, ShareLink.dashboard_id == dash.id
        )
    )
    if link is None:
        raise not_found(M("sharing.not_found"))
    if link.revoked_at is None:
        link.revoked_at = datetime.now(UTC)
        link.revoked_by = user.id
        audit.record(
            db,
            "share_link_revoked",
            actor_id=user.id,
            ip=ip,
            detail={"link_id": link.id, "dashboard": dash.code},
        )
    return link


@dataclass(frozen=True)
class Shared:
    link_id: int
    expires_at: datetime
    dashboard: Dashboard
    ctx: engine.Context


def find(db: Session, raw: str | None) -> ShareLink | None:
    if not isinstance(raw, str) or not _TOKEN_RE.fullmatch(raw):
        return None
    return db.scalar(select(ShareLink).where(ShareLink.token_hash == token_hash(raw)))


def usable(db: Session, link: ShareLink, now: datetime | None = None) -> Shared | None:
    now = now or datetime.now(UTC)
    if not is_active(link, now) or not sharing_enabled():
        return None
    dash = db.get(Dashboard, link.dashboard_id)
    ctx = report_context(db, dash)
    if ctx is None:
        return None
    return Shared(link_id=link.id, expires_at=link.expires_at, dashboard=dash, ctx=ctx)


def resolve(db: Session, raw: str | None) -> Shared | None:
    link = find(db, raw)
    if link is None:
        return None
    return usable(db, link)


def record_visit(db: Session, link_id: int) -> None:
    db.execute(
        update(ShareLink)
        .where(ShareLink.id == link_id)
        .values(visits=ShareLink.visits + 1, last_visit_at=func.now())
    )


def public_base(request: Request, settings: Settings) -> str:
    if settings.site_is_domain:
        domain = settings.site_address.strip().split()[0].rstrip("/")
        if domain.startswith("http://") or domain.startswith("https://"):
            return domain
        return f"https://{domain}"
    return str(request.base_url).rstrip("/")


def link_url(base: str, raw: str) -> str:
    return f"{base}/s/{raw}"
