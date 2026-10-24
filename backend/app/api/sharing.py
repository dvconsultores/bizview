"""Share links, email, and scheduled sends of a dashboard (feature 018)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import client_ip, current_user, require_admin
from app.config import get_settings
from app.db import DB
from app.errors import validation
from app.mail import sends, subscriptions
from app.mail import settings as mail_settings
from app.models import AppUser, EmailSubscription
from app.services import dashboards
from app.sharing import links

router = APIRouter(prefix="/api/dashboards")

Email = Annotated[str, Field(max_length=254)]
SelectionValue = str | list[Annotated[str, Field(max_length=200)]]


class LinkIn(BaseModel):
    days: int = Field(default=links.DEFAULT_DAYS, ge=links.MIN_DAYS, le=links.MAX_DAYS)
    note: str | None = Field(default=None, max_length=links.NOTE_MAX)
    # Feature 030 (T047): the theme the shared view applies on its first load.
    theme: Literal["light", "dark"] | None = None


class EmailIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    users: list[int] = Field(default_factory=list, max_length=50)
    emails: list[Email] = Field(default_factory=list, max_length=50)
    subject: str | None = Field(None, max_length=200)
    message: str | None = Field(None, max_length=2000)
    selection: dict[str, SelectionValue] | None = None
    attach_pdf: bool = True
    link_days: int | None = None


class SubscriptionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frequency: Literal["daily", "weekly", "monthly"]
    hour: int = Field(ge=0, le=23)
    weekday: int | None = Field(None, ge=0, le=6)
    monthday: int | None = Field(None, ge=1, le=28)
    period: str = Field(min_length=1, max_length=40)
    attach_pdf: bool = True
    link_days: int | None = Field(None, ge=1, le=90)
    users: list[int] = Field(default_factory=list, max_length=50)
    emails: list[Email] = Field(default_factory=list, max_length=50)
    paused: bool = False


class SubscriptionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frequency: Literal["daily", "weekly", "monthly"] | None = None
    hour: int | None = Field(None, ge=0, le=23)
    weekday: int | None = Field(None, ge=0, le=6)
    monthday: int | None = Field(None, ge=1, le=28)
    period: str | None = Field(None, min_length=1, max_length=40)
    attach_pdf: bool | None = None
    link_days: int | None = Field(None, ge=1, le=90)
    users: list[int] | None = Field(None, max_length=50)
    emails: list[Email] | None = Field(None, max_length=50)
    paused: bool | None = None


@router.get("/{code}/links")
def list_links(
    code: str,
    user: AppUser = Depends(require_admin),
    db: Session = DB,
):
    dash = dashboards.get_for_open(db, user, code)
    return {
        "items": links.list_for(db, dash),
        "sharing_enabled": links.sharing_enabled(),
        "max_active": links.MAX_ACTIVE,
        "active_count": links.counted_active(db, dash),
        "days": {
            "min": links.MIN_DAYS,
            "max": links.MAX_DAYS,
            "default": links.DEFAULT_DAYS,
        },
    }


@router.post("/{code}/links", status_code=201)
def create_link(
    code: str,
    body: LinkIn,
    request: Request,
    user: AppUser = Depends(require_admin),
    db: Session = DB,
):
    dash = dashboards.get_for_open(db, user, code)
    link, raw = links.create(
        db,
        user,
        dash,
        days=body.days,
        note=body.note,
        theme=body.theme,
        ip=client_ip(request),
    )
    return {
        **links.to_json(link, user.full_name),
        "token": raw,
        "url": links.link_url(links.public_base(request, get_settings()), raw),
    }


@router.delete("/{code}/links/{link_id}", status_code=204)
def revoke_link(
    code: str,
    link_id: int,
    request: Request,
    user: AppUser = Depends(require_admin),
    db: Session = DB,
):
    dash = dashboards.get_for_open(db, user, code)
    links.revoke(
        db,
        user,
        dash,
        link_id,
        ip=client_ip(request),
    )
    return Response(status_code=204)


@router.get("/{code}/email")
def get_email_options(
    code: str,
    user: AppUser = Depends(current_user),
    db: Session = DB,
):
    dash = dashboards.get_for_open(db, user, code)
    result = {
        "available": mail_settings.available(),
        "can_link": user.role == "admin" and links.sharing_enabled(),
        "allowed_domains": mail_settings.allowed_domains(),
        "max_recipients": sends.MAX_RECIPIENTS,
        "link_days": {
            "min": links.MIN_DAYS,
            "max": links.MAX_DAYS,
            "default": links.DEFAULT_DAYS,
        },
        "items": sends.list_sends(db, user, dash),
    }
    if user.role == "admin":
        result["links_active"] = links.counted_active(db, dash)
        result["links_max"] = links.MAX_ACTIVE
    return result


@router.get("/{code}/email/recipients")
def get_email_recipients(
    code: str,
    user: AppUser = Depends(current_user),
    q: str | None = Query(None, max_length=100),
    db: Session = DB,
):
    dash = dashboards.get_for_open(db, user, code)
    ctx = links.report_context(db, dash)
    if ctx is None:
        return {"items": []}
    return {"items": sends.recipient_options(db, user, dash, ctx, q)}


@router.post("/{code}/email", status_code=201)
def post_email(
    code: str,
    body: EmailIn,
    request: Request,
    user: AppUser = Depends(current_user),
    db: Session = DB,
):
    dash = dashboards.get_for_open(db, user, code)
    send = sends.queue_send(
        db,
        user,
        dash,
        user_ids=body.users,
        emails=body.emails,
        subject=body.subject,
        message=body.message,
        selection=body.selection,
        attach_pdf=body.attach_pdf,
        link_days=body.link_days,
        base_url=links.public_base(request, get_settings()),
        ip=client_ip(request),
    )
    return sends.send_json(db, send)


def _sub_json(db: Session, sub: EmailSubscription) -> dict:
    user_ids: set[int] = {sub.created_by}
    for entry in sub.recipients:
        if "user_id" in entry:
            user_ids.add(entry["user_id"])
    names: dict[int, str] = {}
    if user_ids:
        users = db.scalars(select(AppUser).where(AppUser.id.in_(user_ids))).all()
        names = {u.id: u.full_name for u in users}
    return subscriptions.to_json(sub, names, subscriptions.project_map(db, [sub]))


@router.get("/{code}/subscriptions")
def get_subscriptions(
    code: str,
    user: AppUser = Depends(require_admin),
    db: Session = DB,
):
    dash = dashboards.get_for_open(db, user, code)
    return {
        "items": subscriptions.list_for(db, dash),
        "available": mail_settings.available(),
        "can_link": links.sharing_enabled(),
        "timezone": get_settings().timezone,
    }


@router.post("/{code}/subscriptions", status_code=201)
def create_subscription(
    code: str,
    body: SubscriptionIn,
    request: Request,
    user: AppUser = Depends(require_admin),
    db: Session = DB,
):
    dash = dashboards.get_for_open(db, user, code)
    sub = subscriptions.create(
        db,
        user,
        dash,
        frequency=body.frequency,
        hour=body.hour,
        weekday=body.weekday,
        monthday=body.monthday,
        period=body.period,
        attach_pdf=body.attach_pdf,
        link_days=body.link_days,
        user_ids=body.users,
        emails=body.emails,
        paused=body.paused,
        ip=client_ip(request),
    )
    db.flush()
    return _sub_json(db, sub)


@router.patch("/{code}/subscriptions/{sub_id}")
def patch_subscription(
    code: str,
    sub_id: int,
    body: SubscriptionPatch,
    request: Request,
    user: AppUser = Depends(require_admin),
    db: Session = DB,
):
    dash = dashboards.get_for_open(db, user, code)
    changes = body.model_dump(exclude_unset=True)
    required_fields = (
        "frequency",
        "hour",
        "period",
        "attach_pdf",
        "users",
        "emails",
        "paused",
    )
    for field in required_fields:
        if field in changes and changes[field] is None:
            raise validation({field: "required"})
    if "users" in changes:
        changes["user_ids"] = changes.pop("users")
    sub = subscriptions.update(
        db,
        user,
        dash,
        sub_id,
        changes,
        ip=client_ip(request),
    )
    db.flush()
    return _sub_json(db, sub)


@router.delete("/{code}/subscriptions/{sub_id}", status_code=204)
def delete_subscription(
    code: str,
    sub_id: int,
    request: Request,
    user: AppUser = Depends(require_admin),
    db: Session = DB,
):
    dash = dashboards.get_for_open(db, user, code)
    subscriptions.delete(
        db,
        user,
        dash,
        sub_id,
        ip=client_ip(request),
    )
    return Response(status_code=204)
