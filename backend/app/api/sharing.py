"""Share links, email, and scheduled sends of a dashboard (feature 018)."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import client_ip, current_user, require_admin
from app.config import get_settings
from app.db import DB
from app.errors import validation
from app.i18n import M
from app.mail import lists as mail_lists
from app.mail import sends, subscriptions
from app.mail import settings as mail_settings
from app.models import AppUser, EmailSend, EmailSubscription
from app.services import dashboards
from app.sharing import links, widgets

router = APIRouter(prefix="/api/dashboards")
WidgetTheme = Literal["light", "dark"]
WidgetLanguage = Literal["es", "en"]

Email = Annotated[str, Field(max_length=254)]
SelectionValue = str | list[Annotated[str, Field(max_length=200)]]


class LinkIn(BaseModel):
    days: int = Field(default=links.DEFAULT_DAYS, ge=links.MIN_DAYS, le=links.MAX_DAYS)
    note: str | None = Field(default=None, max_length=links.NOTE_MAX)
    # Feature 030 (T047): the theme the shared view applies on its first load.
    theme: Literal["light", "dark"] | None = None


class WidgetIn(BaseModel):
    """Feature 065: one dashboard embedded in other sites (FR-001/009/024)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=widgets.NAME_MAX)
    #: At most ten are kept; the bound here only stops an absurd body from being parsed.
    sites: list[str] = Field(min_length=1, max_length=50)
    theme: WidgetTheme | None = None
    language: WidgetLanguage | None = None
    show_title: bool = True
    show_filters: bool = True
    #: FR-024: the PDF is off unless the admin asks for it.
    pdf: bool = False
    #: FR-005: absent means it never expires.
    expires_at: datetime | None = None


class WidgetPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=widgets.NAME_MAX)
    sites: list[str] | None = Field(default=None, min_length=1, max_length=50)
    #: Explicit null follows the visitor; an absent key leaves the value alone.
    theme: WidgetTheme | None = None
    language: WidgetLanguage | None = None
    show_title: bool | None = None
    show_filters: bool | None = None
    pdf: bool | None = None
    expires_at: datetime | None = None


class EmailIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    users: list[int] = Field(default_factory=list)
    #: 058: free addresses, typed or pasted. No ceiling: the provider governs the volume.
    emails: list[Email] = Field(default_factory=list)
    #: 058: the lists to include, by id.
    lists: list[int] = Field(default_factory=list)
    #: 058: save the free addresses of this send as a personal list with this name.
    save_as_list: str | None = Field(None, max_length=mail_lists.NAME_MAX)
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
    users: list[int] = Field(default_factory=list)
    emails: list[Email] = Field(default_factory=list)
    #: 058: the lists to deliver to; their members resolve at delivery time.
    lists: list[int] = Field(default_factory=list)
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
    users: list[int] | None = None
    emails: list[Email] | None = None
    #: 058: the lists to deliver to; an empty list removes them.
    lists: list[int] | None = None
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
        # 058: no recipient ceiling anywhere — `null` is the contract, and the dialog renders none.
        "max_recipients": None,
        "free_addresses_role": get_settings().email_free_addresses_role,
        "sending_paused": get_settings().email_sending_paused,
        "batch_size": get_settings().email_batch_size,
        "send_rate": get_settings().email_send_rate,
        "individual_messages": get_settings().email_individual_messages,
        "from_mode": get_settings().email_from_mode,
        "lists": mail_lists.usable(db, user),
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
        list_ids=body.lists,
        save_as_list=body.save_as_list,
        subject=body.subject,
        message=body.message,
        selection=body.selection,
        attach_pdf=body.attach_pdf,
        link_days=body.link_days,
        base_url=links.public_base(request, get_settings()),
        ip=client_ip(request),
    )
    return sends.send_json(db, send)


@router.get("/{code}/email/sends")
def get_sends(
    code: str,
    limit: int = Query(50, ge=1, le=200),
    user: AppUser = Depends(current_user),
    db: Session = DB,
):
    """The send history of one dashboard (FR-016): who sent what, when, and how each address went."""
    dash = dashboards.get_for_open(db, user, code)
    items = []
    for send in db.scalars(
            select(EmailSend).where(EmailSend.dashboard_id == dash.id)
            .order_by(EmailSend.id.desc()).limit(limit)).all():
        items.append(sends.send_json(
            db, send, full_addresses=user.role == "admin" or send.requested_by == user.id))
    return {"items": items}


@router.post("/{code}/email/sends/{send_id}/resend-failed", status_code=201)
def post_resend_failed(
    code: str,
    send_id: int,
    request: Request,
    user: AppUser = Depends(current_user),
    db: Session = DB,
):
    dash = dashboards.get_for_open(db, user, code)
    send = sends.resend_failed(db, user, dash, send_id, ip=client_ip(request))
    return sends.send_json(db, send, full_addresses=True)


def _sub_json(db: Session, sub: EmailSubscription) -> dict:
    user_ids: set[int] = {sub.created_by}
    for entry in sub.recipients:
        if "user_id" in entry:
            user_ids.add(entry["user_id"])
    names: dict[int, str] = {}
    if user_ids:
        users = db.scalars(select(AppUser).where(AppUser.id.in_(user_ids))).all()
        names = {u.id: u.full_name for u in users}
    return subscriptions.to_json(sub, names, subscriptions.project_map(db, [sub]),
                                 subscriptions.list_map(db, [sub]))


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
        list_ids=body.lists,
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
        "lists",
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


# ------------------------------------------------------------------ widgets (feature 065)


def _widget_json(db: Session, widget) -> dict:
    sites = widgets.site_map(db, [widget.id]).get(widget.id, [])
    creator = db.scalar(select(AppUser.full_name).where(AppUser.id == widget.created_by))
    return widgets.to_json(widget, creator, sites)


def _snippet_body(request: Request, widget, raw: str) -> dict:
    """The one time the key leaves the product: at creation and at replacement (FR-002)."""
    base = links.public_base(request, get_settings())
    return {
        "key": raw,
        "url": widgets.widget_url(base, raw),
        "snippet": widgets.snippet(base, raw, widget),
    }


@router.get("/{code}/widgets")
def list_widgets(
    code: str,
    user: AppUser = Depends(require_admin),
    db: Session = DB,
):
    dash = dashboards.get_for_open(db, user, code)
    return {
        "items": widgets.list_for(db, dash),
        "enabled": widgets.widgets_enabled(),
        "embed_enabled": get_settings().embed_widgets_enabled,
        "share_links_enabled": links.sharing_enabled(),
        "shareable": widgets.shareable(db, dash),
        "max_active": widgets.MAX_ACTIVE,
        "active_count": widgets.counted_active(db, dash),
        "max_sites": widgets.MAX_SITES,
        "name_max": widgets.NAME_MAX,
    }


@router.post("/{code}/widgets", status_code=201)
def create_widget(
    code: str,
    body: WidgetIn,
    request: Request,
    user: AppUser = Depends(require_admin),
    db: Session = DB,
):
    dash = dashboards.get_for_open(db, user, code)
    widget, raw = widgets.create(
        db,
        user,
        dash,
        name=body.name,
        sites=body.sites,
        theme=body.theme,
        language=body.language,
        show_title=body.show_title,
        show_filters=body.show_filters,
        pdf=body.pdf,
        expires_at=body.expires_at,
        ip=client_ip(request),
    )
    return {**_widget_json(db, widget), **_snippet_body(request, widget, raw)}


@router.patch("/{code}/widgets/{widget_id}")
def patch_widget(
    code: str,
    widget_id: int,
    body: WidgetPatch,
    request: Request,
    user: AppUser = Depends(require_admin),
    db: Session = DB,
):
    dash = dashboards.get_for_open(db, user, code)
    changes = body.model_dump(exclude_unset=True)
    # These three drive NOT NULL columns. An explicit null is a client mistake, so it is answered
    # like every other one in this module (422 naming the field), not by failing at the database.
    for field in ("show_title", "show_filters", "pdf"):
        if field in changes and changes[field] is None:
            raise validation({field: "required"}, M("widget.control_required"))
    widget = widgets.update(db, user, dash, widget_id, changes, ip=client_ip(request))
    db.flush()
    return _widget_json(db, widget)


@router.post("/{code}/widgets/{widget_id}/replace")
def replace_widget_key(
    code: str,
    widget_id: int,
    request: Request,
    user: AppUser = Depends(require_admin),
    db: Session = DB,
):
    dash = dashboards.get_for_open(db, user, code)
    widget, raw = widgets.replace_key(db, user, dash, widget_id, ip=client_ip(request))
    db.flush()
    return {**_widget_json(db, widget), **_snippet_body(request, widget, raw)}


@router.delete("/{code}/widgets/{widget_id}", status_code=204)
def revoke_widget(
    code: str,
    widget_id: int,
    request: Request,
    user: AppUser = Depends(require_admin),
    db: Session = DB,
):
    dash = dashboards.get_for_open(db, user, code)
    widgets.revoke(db, user, dash, widget_id, ip=client_ip(request))
    return Response(status_code=204)


@router.delete("/{code}/widgets/{widget_id}/permanent", status_code=204)
def delete_widget(
    code: str,
    widget_id: int,
    request: Request,
    user: AppUser = Depends(require_admin),
    db: Session = DB,
):
    """Delete a widget for good, in any state: it stops working and leaves the list."""
    dash = dashboards.get_for_open(db, user, code)
    widgets.delete(db, user, dash, widget_id, ip=client_ip(request))
    return Response(status_code=204)


@router.post("/{code}/widgets/{widget_id}/frame")
def widget_test_frame(
    code: str,
    widget_id: int,
    request: Request,
    user: AppUser = Depends(require_admin),
    db: Session = DB,
):
    """The admin's test page (FR-018/019): a short-lived frame ticket, never the widget's key."""
    dash = dashboards.get_for_open(db, user, code)
    ticket, expires = widgets.preview(db, user, dash, widget_id)
    base = links.public_base(request, get_settings())
    return {"url": widgets.widget_url(base, ticket), "expires_at": expires}
