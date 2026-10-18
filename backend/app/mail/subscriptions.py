"""Scheduled email deliveries of dashboards."""

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.config import get_settings
from app.engine import report as engine
from app.errors import ApiError, not_found, validation
from app.i18n import M, t
from app.mail import sends
from app.mail import settings as mail_settings
from app.models import (
    SUBSCRIPTION_FREQUENCIES,
    AppUser,
    Dashboard,
    EmailDelivery,
    EmailSend,
    EmailSubscription,
    Project,
)
from app.reports import pdf
from app.services import audit
from app.sharing import links

log = logging.getLogger("app.mail")

MAX_PER_DASHBOARD = 20
TICK_LIMIT = 20


def next_due(
    frequency: str,
    hour: int,
    weekday: int | None,
    monthday: int | None,
    after: datetime,
    tz: str,
) -> datetime:
    zone = ZoneInfo(tz)
    after_local = after.astimezone(zone)
    if frequency == "daily":
        candidate = datetime(
            after_local.year,
            after_local.month,
            after_local.day,
            hour,
            tzinfo=zone,
        )
        if candidate <= after:
            candidate += timedelta(days=1)
        return candidate.astimezone(UTC)
    if frequency == "weekly":
        for days_ahead in range(400):
            candidate = datetime(
                after_local.year,
                after_local.month,
                after_local.day,
                hour,
                tzinfo=zone,
            ) + timedelta(days=days_ahead)
            if candidate.weekday() == weekday and candidate > after:
                return candidate.astimezone(UTC)
        raise ValueError("weekly next_due loop exhausted")
    if frequency == "monthly":
        year = after_local.year
        month = after_local.month
        candidate = datetime(year, month, monthday, hour, tzinfo=zone)
        if candidate <= after:
            month += 1
            if month > 12:
                month = 1
                year += 1
            candidate = datetime(year, month, monthday, hour, tzinfo=zone)
        return candidate.astimezone(UTC)
    raise ValueError(f"unknown frequency {frequency}")


def role_users(db, role: str) -> list[AppUser]:
    """Active users of a role (recipients `{"role": r}` of project distributions)."""
    return list(db.scalars(select(AppUser).where(
        AppUser.is_active.is_(True), AppUser.role == role).order_by(AppUser.id)))


def project_map(db, subs) -> dict[int, Project]:
    """Projects owning the given subscriptions (feature 020)."""
    ids = {s.project_id for s in subs if s.project_id is not None}
    if not ids:
        return {}
    return {p.id: p for p in db.scalars(select(Project).where(Project.id.in_(ids)))}


def owned_guard(db, sub: EmailSubscription) -> None:
    """Subscriptions of a project distribution change only through the project's files."""
    if sub.project_id is not None:
        project = db.get(Project, sub.project_id)
        name = (project.name or project.slug) if project is not None else "?"
        raise ApiError(409, "managed_by_project", M("projects.managed_by_project", project=name))


def _validate(
    db,
    dash: Dashboard,
    ctx,
    *,
    frequency: str,
    hour: int,
    weekday: int | None,
    monthday: int | None,
    period: str,
    attach_pdf: bool,
    link_days: int | None,
    user_ids: list[int],
    emails: list[str],
) -> list[dict]:
    errors: dict[str, str] = {}
    if frequency not in SUBSCRIPTION_FREQUENCIES:
        errors["frequency"] = "invalid"
    if hour < 0 or hour > 23:
        errors["hour"] = "range"
    if frequency == "weekly":
        if weekday is None:
            errors["weekday"] = "required"
        elif weekday < 0 or weekday > 6:
            errors["weekday"] = "range"
    if frequency == "monthly":
        if monthday is None:
            errors["monthday"] = "required"
        elif monthday < 1 or monthday > 28:
            errors["monthday"] = "range"

    definition = engine.definition_json(ctx)
    if period not in definition["periods"]["allowed"] or period == "custom":
        errors["period"] = "not_allowed"
    if link_days is not None and (
        link_days < links.MIN_DAYS or link_days > links.MAX_DAYS
    ):
        errors["link_days"] = "range"
    if attach_pdf and not definition["pdf"]:
        errors["attach_pdf"] = "not_allowed"
    if not attach_pdf and link_days is None:
        errors["attach_pdf"] = "nothing_to_send"

    recipients = sends.resolve_recipients(
        db,
        dash,
        ctx,
        user_ids=user_ids,
        emails=emails,
        allowed_domains=mail_settings.allowed_domains(),
    )
    if errors:
        raise validation(errors)
    result: list[dict] = []
    for recipient in recipients:
        if recipient.user_id is not None:
            result.append({"user_id": recipient.user_id})
        else:
            result.append({"email": recipient.address})
    return result


def create(
    db,
    user: AppUser,
    dash: Dashboard,
    *,
    frequency: str,
    hour: int,
    weekday: int | None,
    monthday: int | None,
    period: str,
    attach_pdf: bool,
    link_days: int | None,
    user_ids: list[int],
    emails: list[str],
    paused: bool = False,
    ip: str | None,
) -> EmailSubscription:
    if user.role != "admin":
        raise ApiError(403, "forbidden", M("common.forbidden"))
    if not mail_settings.available():
        raise ApiError(
            409,
            "email_unavailable",
            M("mail.not_configured"),
        )
    ctx = links.report_context(db, dash)
    if ctx is None:
        raise ApiError(
            409, "not_sendable", M("mail.not_sendable")
        )
    if link_days is not None and not links.sharing_enabled():
        raise ApiError(
            409,
            "sharing_disabled",
            M("sharing.disabled"),
        )
    count = db.scalar(
        select(func.count())
        .select_from(EmailSubscription)
        .where(EmailSubscription.dashboard_id == dash.id)
    )
    if count >= MAX_PER_DASHBOARD:
        raise ApiError(
            409,
            "too_many_subscriptions",
            M("mail.max_scheduled", n=MAX_PER_DASHBOARD),
        )
    recipients = _validate(
        db,
        dash,
        ctx,
        frequency=frequency,
        hour=hour,
        weekday=weekday if frequency == "weekly" else None,
        monthday=monthday if frequency == "monthly" else None,
        period=period,
        attach_pdf=attach_pdf,
        link_days=link_days,
        user_ids=user_ids,
        emails=emails,
    )
    next_due_at = next_due(
        frequency,
        hour,
        weekday if frequency == "weekly" else None,
        monthday if frequency == "monthly" else None,
        datetime.now(UTC),
        get_settings().timezone,
    )
    sub = EmailSubscription(
        dashboard_id=dash.id,
        created_by=user.id,
        recipients=recipients,
        frequency=frequency,
        hour=hour,
        weekday=weekday if frequency == "weekly" else None,
        monthday=monthday if frequency == "monthly" else None,
        period=period,
        attach_pdf=attach_pdf,
        link_days=link_days,
        paused=paused,
        next_due_at=next_due_at,
    )
    db.add(sub)
    db.flush()
    audit.record(
        db,
        "email_subscription_created",
        actor_id=user.id,
        ip=ip,
        detail={
            "subscription_id": sub.id,
            "dashboard": dash.code,
            "frequency": frequency,
            "recipients": len(recipients),
        },
    )
    return sub


def update(
    db,
    user: AppUser,
    dash: Dashboard,
    sub_id: int,
    changes: dict,
    *,
    ip: str | None,
) -> EmailSubscription:
    if user.role != "admin":
        raise ApiError(403, "forbidden", M("common.forbidden"))
    sub = db.scalar(
        select(EmailSubscription)
        .where(
            EmailSubscription.id == sub_id,
            EmailSubscription.dashboard_id == dash.id,
        )
        .with_for_update()
    )
    if sub is None:
        raise not_found(M("mail.scheduled_not_found"))

    if set(changes) <= {"paused"}:
        return _set_paused(
            db,
            user,
            dash,
            sub,
            changes.get("paused", sub.paused),
            ip=ip,
        )
    owned_guard(db, sub)

    ctx = links.report_context(db, dash)
    if ctx is None:
        raise ApiError(
            409, "not_sendable", M("mail.not_sendable")
        )

    frequency = changes.get("frequency", sub.frequency)
    hour = changes.get("hour", sub.hour)
    weekday = changes.get("weekday", sub.weekday)
    monthday = changes.get("monthday", sub.monthday)
    period = changes.get("period", sub.period)
    attach_pdf = changes.get("attach_pdf", sub.attach_pdf)
    link_days = changes.get("link_days", sub.link_days)
    paused = changes.get("paused", sub.paused)

    if frequency != "weekly":
        weekday = None
    if frequency != "monthly":
        monthday = None

    current_user_ids = [
        r["user_id"] for r in sub.recipients if "user_id" in r
    ]
    current_emails = [r["email"] for r in sub.recipients if "email" in r]
    user_ids = changes.get("user_ids", current_user_ids)
    emails = changes.get("emails", current_emails)

    if (
        "link_days" in changes
        and changes["link_days"] is not None
        and changes["link_days"] != sub.link_days
        and not links.sharing_enabled()
    ):
        raise ApiError(
            409,
            "sharing_disabled",
            M("sharing.disabled"),
        )

    recipients = _validate(
        db,
        dash,
        ctx,
        frequency=frequency,
        hour=hour,
        weekday=weekday,
        monthday=monthday,
        period=period,
        attach_pdf=attach_pdf,
        link_days=link_days,
        user_ids=user_ids,
        emails=emails,
    )

    schedule_changed = (
        (sub.frequency, sub.hour, sub.weekday, sub.monthday)
        != (frequency, hour, weekday, monthday)
        or (sub.paused and not paused)
    )

    changed_fields: list[str] = []
    for field, value in (
        ("frequency", frequency),
        ("hour", hour),
        ("weekday", weekday),
        ("monthday", monthday),
        ("period", period),
        ("attach_pdf", attach_pdf),
        ("link_days", link_days),
        ("paused", paused),
        ("recipients", recipients),
    ):
        if getattr(sub, field) != value:
            changed_fields.append(field)

    sub.frequency = frequency
    sub.hour = hour
    sub.weekday = weekday
    sub.monthday = monthday
    sub.period = period
    sub.attach_pdf = attach_pdf
    sub.link_days = link_days
    sub.paused = paused
    sub.recipients = recipients

    if schedule_changed:
        sub.next_due_at = next_due(
            frequency,
            hour,
            weekday,
            monthday,
            datetime.now(UTC),
            get_settings().timezone,
        )

    if changed_fields:
        audit.record(
            db,
            "email_subscription_updated",
            actor_id=user.id,
            ip=ip,
            detail={
                "subscription_id": sub.id,
                "dashboard": dash.code,
                "fields": sorted(changed_fields),
            },
        )
    return sub


def _set_paused(
    db,
    user: AppUser,
    dash: Dashboard,
    sub: EmailSubscription,
    paused: bool,
    *,
    ip: str | None,
) -> EmailSubscription:
    changed = sub.paused != paused
    if changed:
        sub.paused = paused
        if not paused:
            sub.next_due_at = next_due(
                sub.frequency,
                sub.hour,
                sub.weekday,
                sub.monthday,
                datetime.now(UTC),
                get_settings().timezone,
            )
        audit.record(
            db,
            "email_subscription_updated",
            actor_id=user.id,
            ip=ip,
            detail={
                "subscription_id": sub.id,
                "dashboard": dash.code,
                "fields": ["paused"],
            },
        )
    return sub


def delete(
    db,
    user: AppUser,
    dash: Dashboard,
    sub_id: int,
    *,
    ip: str | None,
) -> None:
    if user.role != "admin":
        raise ApiError(403, "forbidden", M("common.forbidden"))
    sub = db.scalar(
        select(EmailSubscription).where(
            EmailSubscription.id == sub_id,
            EmailSubscription.dashboard_id == dash.id,
        )
    )
    if sub is None:
        raise not_found(M("mail.scheduled_not_found"))
    owned_guard(db, sub)
    for prev in db.scalars(
        select(EmailSend)
        .where(
            EmailSend.subscription_id == sub.id,
            EmailSend.selection["link"].has_key("ct"),
            EmailSend.status.in_(("sent", "partial", "failed")),
        )
    ).all():
        data = prev.selection["link"]
        prev.selection = {
            **prev.selection,
            "link": {"id": data.get("id"), "sub": sub.id},
        }
    db.delete(sub)
    audit.record(
        db,
        "email_subscription_deleted",
        actor_id=user.id,
        ip=ip,
        detail={"subscription_id": sub.id, "dashboard": dash.code},
    )


def to_json(sub: EmailSubscription, names: dict[int, str],
            projects: dict[int, Project] | None = None) -> dict:
    recipients = []
    for entry in sub.recipients:
        if "user_id" in entry:
            recipients.append(
                {"user_id": entry["user_id"], "name": names.get(entry["user_id"])}
            )
        elif "role" in entry:
            recipients.append({"role": entry["role"]})
        else:
            recipients.append({"email": entry["email"]})
    managed_by = None
    if sub.project_id is not None:
        project = (projects or {}).get(sub.project_id)
        managed_by = {"project": project.name if project else None,
                      "slug": project.slug if project else None,
                      "distribution": sub.distribution_id}
    return {
        "id": sub.id,
        "frequency": sub.frequency,
        "hour": sub.hour,
        "weekday": sub.weekday,
        "monthday": sub.monthday,
        "period": sub.period,
        "period_label": (t(f"pdf.period.{sub.period}") if sub.period in pdf.PERIOD_LABELS
                         else sub.period),           # request language (022 T049)
        "attach_pdf": sub.attach_pdf,
        "link_days": sub.link_days,
        "paused": sub.paused,
        "last_due_at": sub.last_due_at,
        "next_due_at": sub.next_due_at,
        "created_at": sub.created_at,
        "updated_at": sub.updated_at,
        "created_by": {
            "id": sub.created_by,
            "name": names.get(sub.created_by),
        },
        "recipients": recipients,
        "managed_by": managed_by,
    }


def list_for(db, dash: Dashboard) -> list[dict]:
    subs = db.scalars(
        select(EmailSubscription)
        .where(EmailSubscription.dashboard_id == dash.id)
        .order_by(EmailSubscription.id.desc())
    ).all()
    user_ids: set[int] = set()
    for sub in subs:
        user_ids.add(sub.created_by)
        for entry in sub.recipients:
            if "user_id" in entry:
                user_ids.add(entry["user_id"])
    names: dict[int, str] = {}
    if user_ids:
        users = db.scalars(select(AppUser).where(AppUser.id.in_(user_ids))).all()
        names = {u.id: u.full_name for u in users}
    projects = project_map(db, subs)
    return [to_json(sub, names, projects) for sub in subs]


def tick(db, now: datetime | None = None, *, limit: int = TICK_LIMIT) -> int:
    if now is None:
        now = datetime.now(UTC)
    tz = get_settings().timezone
    allowed_domains = set(mail_settings.allowed_domains())
    created = 0
    subs = db.scalars(
        select(EmailSubscription)
        .where(
            EmailSubscription.paused.is_(False),
            EmailSubscription.next_due_at <= now,
        )
        .order_by(EmailSubscription.next_due_at, EmailSubscription.id)
        .with_for_update(skip_locked=True)
        .limit(limit)
    ).all()
    for sub in subs:
        due = sub.next_due_at
        sub.last_due_at = due
        sub.next_due_at = next_due(
            sub.frequency,
            sub.hour,
            sub.weekday,
            sub.monthday,
            max(now, due),
            tz,
        )
        dash = db.get(Dashboard, sub.dashboard_id)
        if dash is None:
            continue
        ctx = links.report_context(db, dash)
        if ctx is None or not mail_settings.available():
            log.info("subscription %s skipped: not sendable", sub.id)
            continue
        creator = db.get(AppUser, sub.created_by)
        if creator is None or not sends.can_open(db, creator, dash, ctx):
            log.info("subscription %s skipped: no access", sub.id)
            continue
        if creator.role != "admin":
            log.info("subscription %s skipped: not admin", sub.id)
            continue
        recipients: list[sends.Recipient] = []
        seen: set[str] = set()
        for entry in sub.recipients:
            if "role" in entry:
                for member in role_users(db, entry["role"]):
                    if member.email not in seen and sends.can_open(db, member, dash, ctx):
                        recipients.append(sends.Recipient(member.email, member.id))
                        seen.add(member.email)
                continue
            if "user_id" in entry:
                recipient_user = db.get(AppUser, entry["user_id"])
                if (
                    recipient_user is None
                    or not recipient_user.is_active
                    or not sends.can_open(db, recipient_user, dash, ctx)
                ):
                    continue
                if recipient_user.email not in seen:
                    recipients.append(
                        sends.Recipient(recipient_user.email, recipient_user.id)
                    )
                    seen.add(recipient_user.email)
            else:
                addr = mail_settings.normalize_email(entry.get("email", ""))
                if addr is None:
                    continue
                if mail_settings.email_domain(addr) not in allowed_domains:
                    continue
                if addr not in seen:
                    recipients.append(sends.Recipient(addr, None))
                    seen.add(addr)
        if not recipients:
            continue
        link_days = sub.link_days if links.sharing_enabled() else None
        if not sub.attach_pdf and link_days is None:
            continue
        label = pdf.PERIOD_LABELS.get(sub.period, sub.period)
        subject = f"{dash.name} · {label}"[:200]
        send = EmailSend(
            dashboard_id=dash.id,
            requested_by=sub.created_by,
            subscription_id=sub.id,
            subject=subject,
            message=None,
            selection={"params": [["period", sub.period]],
                       "auto_subject": {"period": sub.period}},
            attach_pdf=sub.attach_pdf,
            link_days=link_days,
            status="queued",
        )
        db.add(send)
        db.flush()
        for recipient in recipients:
            db.add(
                EmailDelivery(
                    send_id=send.id,
                    recipient=recipient.address,
                    user_id=recipient.user_id,
                    status="queued",
                    next_attempt_at=now,
                )
            )
        created += 1
    return created
