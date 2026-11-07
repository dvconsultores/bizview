"""Queueing email sends (API side) and processing deliveries (worker side)."""

import base64
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select

from app.api import reports
from app.config import get_settings
from app.db import get_sessionmaker
from app.engine import report as engine
from app.errors import ApiError, validation
from app.i18n import M, localized, t, use_locale
from app.i18n import current as i18n_current
from app.mail import addresses as mail_addresses
from app.mail import lists as mail_lists
from app.mail import send as mail_send
from app.mail import settings as mail_settings
from app.mail.send import MailError
from app.models import (
    AppUser,
    Dashboard,
    DashboardAccess,
    EmailDelivery,
    EmailSend,
    ShareLink,
)
from app.reports import images, palette, pdf
from app.security import crypto
from app.services import audit, dashboards
from app.sharing import links

log = logging.getLogger("app.mail")

MAX_ATTEMPTS = 4
BACKOFF = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=15),
)
LEASE = timedelta(minutes=10)
CLAIM_LIMIT = 20
#: 058: how many deliveries one pass may claim once it has chosen its sends (a whole big send).
BULK_CLAIM_LIMIT = 5000
SUBJECT_MAX = 200
MESSAGE_MAX = 2000
MAX_FILTER_KEYS = 20
LINK_AAD = crypto.EMAIL_LINK_AAD
REUSE_MARGIN = timedelta(days=1)


def can_open(db, user: AppUser | None, dash: Dashboard, ctx) -> bool:
    if user is None or not user.is_active or dash.status != "available" or ctx is None:
        return False
    roles = (ctx.definition.get("access") or {}).get("roles") or ["admin"]
    if "user" in roles:
        return True
    return dashboards.can_see(db, user, dash)


@dataclass(frozen=True)
class Recipient:
    address: str
    user_id: int | None
    #: 058: the list this address came from, when it came from one.
    list_id: int | None = None
    #: 058: the display name kept with the address, when there is one.
    name: str | None = None


def resolve_recipients(
    db,
    dash: Dashboard,
    ctx,
    *,
    user_ids: list[int],
    emails: list[str],
    allowed_domains: list[str],
    list_ids: list[int] | None = None,
    sender_email: str | None = None,
    free_addresses: bool = True,
) -> list[Recipient]:
    errors: dict[str, str] = {}
    users_by_id: dict[int, AppUser] = {}
    if user_ids:
        rows = db.scalars(select(AppUser).where(AppUser.id.in_(set(user_ids)))).all()
        users_by_id = {u.id: u for u in rows}
        missing = [uid for uid in user_ids if uid not in users_by_id]
        if missing:
            errors["users"] = "no_access"
        else:
            blocked = [
                uid
                for uid in user_ids
                if not users_by_id[uid].is_active
                or not can_open(db, users_by_id[uid], dash, ctx)
            ]
            if blocked:
                errors["users"] = "no_access"

    user_emails = {users_by_id[uid].email for uid in users_by_id}

    # 058: free addresses and list members are parsed with one shared grammar, so the dialog's
    # counter and the deliveries cannot disagree about what an address is.
    normalized_emails: list[tuple[str, str | None]] = []
    if emails:
        for entry in emails:
            parsed, bad = mail_addresses.parse_recipients(str(entry or ""))
            if bad or not parsed:
                errors["emails"] = "invalid"
                break
            normalized_emails.extend(parsed)
    if not free_addresses and normalized_emails:
        # EMAIL_FREE_ADDRESSES_ROLE=admin: a non-administrator sends to users and lists, not to a
        # typed address. Installation users are always allowed — they are inside.
        errors["emails"] = "role_not_allowed"

    list_members = mail_lists.resolve(db, list(list_ids or []), exclude=sender_email)
    if list_ids:
        found = set(db.scalars(
            select(mail_lists.MailList.id).where(mail_lists.MailList.id.in_(set(list_ids)),
                                                  mail_lists.MailList.deleted_at.is_(None))))
        if len(found) != len(set(list_ids)):
            errors["lists"] = "not_found"

    if allowed_domains and not errors:
        # The filter is the installation's: it limits what a sender may reach *outside*, which is
        # exactly the free addresses and the members of a list. Users of the installation are not
        # external, and the sender's own address never reaches this list.
        bad_domains = []
        for addr, _ in normalized_emails:
            if addr in user_emails:
                continue
            if mail_settings.email_domain(addr) not in allowed_domains:
                bad_domains.append(addr)
        for member in list_members:
            if member["address"] in user_emails:
                continue
            if mail_settings.email_domain(member["address"]) not in allowed_domains:
                bad_domains.append(member["address"])
        if bad_domains:
            errors["emails"] = "domain_not_allowed"

    if errors:
        if errors.get("users") == "no_access":
            message = M("mail.users_no_access")
        elif errors.get("lists") == "not_found":
            message = M("mail.list_not_found")
        elif errors.get("emails") == "invalid":
            message = M("mail.invalid_emails")
        elif errors.get("emails") == "role_not_allowed":
            message = M("mail.free_addresses_admins")
        elif errors.get("emails") == "domain_not_allowed":
            if allowed_domains:
                message = M("mail.domains_only", domains=", ".join(allowed_domains))
            else:
                message = M("mail.no_domains_allowed")
        else:
            message = M("common.validation")
        raise validation(errors, message=message)

    recipients: list[Recipient] = []
    seen: set[str] = set()
    for uid in user_ids:
        if uid in users_by_id:
            user = users_by_id[uid]
            # 058: the sender is dropped from a pasted block or a list — they are the sender — but
            # an installation user the sender picked on purpose may still receive their own send
            # ("send me a copy"), which is what the dialog has always allowed.
            if user.email not in seen:
                recipients.append(Recipient(user.email, user.id, name=user.full_name))
                seen.add(user.email)
    for member in list_members:
        addr = member["address"]
        if addr in seen:
            continue
        recipients.append(Recipient(addr, None, list_id=member["list_id"], name=member["name"]))
        seen.add(addr)
    for addr, name in normalized_emails:
        if addr == sender_email or addr in seen:
            continue
        recipients.append(Recipient(addr, None, name=name))
        seen.add(addr)

    if not recipients:
        raise validation({"recipients": "empty"}, M("mail.select_recipient"))
    return recipients


def recipient_kinds(
    db, recipients: list[Recipient], *, user_ids: list[int], list_ids: list[int],
) -> dict:
    """What a send carried, for the history and the audit: counts and list **names** only.

    An address never lands here: the audit event and the `email_send.kinds` column are read by more
    people than the send itself (FR-018)."""
    names = []
    if list_ids:
        rows = db.scalars(select(mail_lists.MailList)
                          .where(mail_lists.MailList.id.in_(set(list_ids)))
                          .order_by(mail_lists.MailList.name)).all()
        names = [row.name for row in rows]
    return {
        "users": len({uid for uid in user_ids}),
        "lists": names,
        "emails": sum(1 for r in recipients if r.user_id is None and r.list_id is None),
        "total": len(recipients),
    }


def selection_params(selection: dict[str, str | list[str]] | None) -> list[list[str]]:
    if not selection:
        return []
    pairs: list[list[str]] = []
    filter_keys = 0
    for key, value in selection.items():
        if not isinstance(key, str):
            raise validation({"selection": "invalid"})
        if key not in ("period", "from", "to", "compare") and not key.startswith("filter."):
            raise validation({"selection": "invalid"})
        values = [value] if isinstance(value, str) else value
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise validation({"selection": "invalid"})
        if key in ("period", "from", "to", "compare") and len(values) != 1:
            raise validation({"selection": "invalid"})
        if key.startswith("filter."):
            filter_keys += 1
            if filter_keys > MAX_FILTER_KEYS:
                raise validation({"selection": "invalid"})
            if len(values) > engine.MAX_FILTER_VALUES:
                raise validation({"selection": "invalid"})
        for v in values:
            if len(v) > 200:
                raise validation({"selection": "invalid"})
            pairs.append([key, v])
    pairs.sort(key=lambda p: p[0])
    return pairs


def queue_send(
    db,
    user: AppUser,
    dash: Dashboard,
    *,
    user_ids: list[int],
    emails: list[str],
    subject: str | None,
    message: str | None,
    selection: dict | None,
    attach_pdf: bool,
    link_days: int | None,
    list_ids: list[int] | None = None,
    save_as_list: str | None = None,
    base_url: str | None = None,
    ip: str | None,
) -> EmailSend:
    if not mail_settings.available():
        raise ApiError(
            409,
            "email_unavailable",
            M("mail.not_configured"),
        )

    ctx = links.report_context(db, dash)
    if ctx is None or not can_open(db, user, dash, ctx):
        raise ApiError(
            409, "not_sendable", M("mail.not_sendable")
        )

    if link_days is not None:
        if user.role != "admin":
            raise validation(
                {"link_days": "admins_only"},
                M("mail.admin_link_only"),
            )
        if link_days < links.MIN_DAYS or link_days > links.MAX_DAYS:
            raise validation({"link_days": "range"})
        if not links.sharing_enabled():
            raise ApiError(
                409,
                "sharing_disabled",
                M("sharing.disabled"),
            )
        links.ensure_capacity(
            db,
            dash,
            message=M("mail.max_active_links", n=links.MAX_ACTIVE),
            fields={"link_days": "too_many_links"},
        )

    definition = engine.definition_json(ctx)
    if attach_pdf and not definition["pdf"]:
        raise validation(
            {"attach_pdf": "not_allowed"},
            M("report.pdf_not_allowed"),
        )
    if not attach_pdf and link_days is None:
        raise validation(
            {"attach_pdf": "nothing_to_send"},
            M("mail.pdf_or_link_required"),
        )

    clean_subject = (subject or "").strip()
    if not clean_subject:
        clean_subject = dash.name
    clean_subject = clean_subject.replace("\r", " ").replace("\n", " ")
    if len(clean_subject) > SUBJECT_MAX:
        raise validation({"subject": "too_long"})

    clean_message = (message or "").strip()
    if not clean_message:
        clean_message = None
    if clean_message is not None and len(clean_message) > MESSAGE_MAX:
        raise validation({"message": "too_long"})

    params = selection_params(selection)
    engine.selection(ctx, (tuple(p) for p in params), reports._today())

    # 058: `EMAIL_FREE_ADDRESSES_ROLE=admin` keeps typed addresses for administrators; lists and
    # installation users are unaffected, so a regular sender still reaches a whole list.
    free_allowed = (user.role == "admin"
                    or get_settings().email_free_addresses_role == "user")
    list_ids = list(dict.fromkeys(list_ids or []))
    recipients = resolve_recipients(
        db,
        dash,
        ctx,
        user_ids=user_ids,
        emails=emails,
        allowed_domains=mail_settings.allowed_domains(),
        list_ids=list_ids,
        sender_email=user.email,
        free_addresses=free_allowed,
    )
    send_selection = {"params": params}
    if (
        link_days is not None
        and base_url is not None
        and base_url.startswith(("http://", "https://"))
    ):
        send_selection["base"] = base_url
    kinds = recipient_kinds(db, recipients, user_ids=user_ids, list_ids=list_ids)
    send = EmailSend(
        dashboard_id=dash.id,
        requested_by=user.id,
        subject=clean_subject,
        message=clean_message,
        selection=send_selection,
        attach_pdf=attach_pdf,
        link_days=link_days,
        status="queued",
        kinds=kinds,
    )
    db.add(send)
    db.flush()
    for recipient in recipients:
        db.add(
            EmailDelivery(
                send_id=send.id,
                recipient=recipient.address,
                user_id=recipient.user_id,
                list_id=recipient.list_id,
                status="queued",
            )
        )
    db.flush()
    if save_as_list and save_as_list.strip():
        # The dialog's "save these recipients as a list": free addresses only, because users and
        # list members are already reachable by their own means.
        saved = [r for r in recipients if r.user_id is None and r.list_id is None]
        if saved:
            row = mail_lists.create(db, user, name=save_as_list, ip=ip)
            mail_lists.replace_members(
                db, user, row,
                [{"address": r.address, "name": r.name} for r in saved])
    audit.record(
        db,
        "email_sent",
        actor_id=user.id,
        ip=ip,
        detail={
            "send_id": send.id,
            "dashboard": dash.code,
            "recipients": len(recipients),
            "kinds": {"users": kinds["users"], "lists": kinds["lists"],
                      "emails": kinds["emails"]},
            "attach_pdf": attach_pdf,
            "link_days": link_days,
        },
    )
    return send


def send_json(db, send: EmailSend, *, full_addresses: bool = False) -> dict:
    """One send for the history.

    `full_addresses` is only true for whoever asked for the send: everybody else sees the masked
    form (`a***@dominio`), which is enough to recognise a person and not enough to build a list out
    of somebody else's send (FR-017, FR-018)."""
    deliveries = db.scalars(
        select(EmailDelivery)
        .where(EmailDelivery.send_id == send.id)
        .order_by(EmailDelivery.id)
    ).all()
    requester = None
    if send.requested_by is not None:
        user = db.get(AppUser, send.requested_by)
        if user is not None:
            requester = {"id": user.id, "name": user.full_name}
    return {
        "id": send.id,
        "subject": _shown_subject(db, send),
        "status": send.status,
        "created_at": send.created_at,
        "finished_at": send.finished_at,
        "attach_pdf": send.attach_pdf,
        "link_days": send.link_days,
        "subscription_id": send.subscription_id,
        "requested_by": requester,
        "kinds": send.kinds or {},
        "count": len(deliveries),
        "deliveries": [
            {
                "id": d.id,
                "recipient": d.recipient if full_addresses else mail_addresses.mask(d.recipient),
                "user_id": d.user_id,
                "list_id": d.list_id,
                "status": d.status,
                "attempts": d.attempts,
                "error": d.error,
                "sent_at": d.sent_at,
            }
            for d in deliveries
        ],
    }


def list_sends(db, user: AppUser, dash: Dashboard, *, limit: int = 50) -> list[dict]:
    query = select(EmailSend).where(EmailSend.dashboard_id == dash.id)
    if user.role != "admin":
        query = query.where(EmailSend.requested_by == user.id)
    query = query.order_by(EmailSend.id.desc()).limit(limit)
    sends = db.scalars(query).all()
    send_ids = [s.id for s in sends]
    deliveries_by_send: dict[int, list[dict]] = {sid: [] for sid in send_ids}
    if send_ids:
        rows = db.scalars(
            select(EmailDelivery)
            .where(EmailDelivery.send_id.in_(send_ids))
            .order_by(EmailDelivery.id)
        ).all()
        for d in rows:
            deliveries_by_send[d.send_id].append(
                {
                    "id": d.id,
                    "recipient": d.recipient,
                    "user_id": d.user_id,
                    "status": d.status,
                    "attempts": d.attempts,
                    "error": d.error,
                    "sent_at": d.sent_at,
                }
            )
    requester_ids = {s.requested_by for s in sends if s.requested_by is not None}
    requesters: dict[int, dict] = {}
    if requester_ids:
        users = db.scalars(select(AppUser).where(AppUser.id.in_(requester_ids))).all()
        requesters = {u.id: {"id": u.id, "name": u.full_name} for u in users}
    result: list[dict] = []
    for s in sends:
        requester = requesters.get(s.requested_by) if s.requested_by is not None else None
        result.append(
            {
                "id": s.id,
                "subject": _subject(s, dash, i18n_current()),
                "status": s.status,
                "created_at": s.created_at,
                "finished_at": s.finished_at,
                "attach_pdf": s.attach_pdf,
                "link_days": s.link_days,
                "subscription_id": s.subscription_id,
                "requested_by": requester,
                "deliveries": deliveries_by_send[s.id],
            }
        )
    return result


def recipient_options(
    db, user: AppUser, dash: Dashboard, ctx, q: str | None, limit: int = 50
) -> list[dict]:
    roles = (ctx.definition.get("access") or {}).get("roles") or ["admin"]
    query = select(AppUser).where(AppUser.is_active.is_(True))
    if "user" not in roles:
        query = query.where(
            or_(
                AppUser.role == "admin",
                AppUser.id.in_(
                    select(DashboardAccess.user_id).where(
                        DashboardAccess.dashboard_id == dash.id
                    )
                ),
            )
        )
    if q:
        escaped_q = q.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
        pattern = f"%{escaped_q}%"
        query = query.where(
            or_(
                AppUser.full_name.ilike(pattern, escape="\\"),
                AppUser.email.ilike(pattern, escape="\\"),
            )
        )
    query = query.order_by(AppUser.full_name).limit(limit)
    users = db.scalars(query).all()
    result = [{"id": u.id, "name": u.full_name} for u in users]
    if user.role == "admin":
        for item, u in zip(result, users, strict=True):
            item["email"] = u.email
    return result


def site_base() -> str:
    settings = get_settings()
    if settings.site_is_domain:
        base = settings.site_address.split()[0].rstrip("/")
        if not base.startswith(("http://", "https://")):
            base = f"https://{base}"
        return base
    base = "http://localhost"
    if settings.site_address.startswith(":") and settings.site_address != ":80":
        base += settings.site_address
    return base


def _fail(db, delivery_id: int, code: str, permanent: bool, now: datetime,
          row=None) -> None:
    delivery = row if row is not None else db.get(EmailDelivery, delivery_id)
    if delivery is None or delivery.status != "queued":
        return
    if permanent or delivery.attempts >= MAX_ATTEMPTS:
        delivery.status = "failed"
        delivery.error = mail_send.reason(code)
    else:
        delivery.status = "queued"
        delivery.error = mail_send.reason(code)
        backoff_idx = min(delivery.attempts - 1, 2)
        delivery.next_attempt_at = now + BACKOFF[backoff_idx]


def _roll_up(db, send_id: int, now: datetime) -> None:
    statuses = db.scalars(
        select(EmailDelivery.status).where(EmailDelivery.send_id == send_id)
    ).all()
    send = db.get(EmailSend, send_id)
    if send is None:
        return
    if "queued" in statuses:
        send.status = "sending"
        send.finished_at = None
    elif all(s == "sent" for s in statuses):
        send.status = "sent"
        send.finished_at = now
    elif not any(s == "sent" for s in statuses):
        send.status = "failed"
        send.finished_at = now
    else:
        send.status = "partial"
        send.finished_at = now
    if send.status != "sending" and send.subscription_id is None:
        sel = send.selection or {}
        if "link" in sel and sel["link"] and "ct" in sel["link"]:
            new_sel = dict(sel)
            new_sel["link"] = {k: v for k, v in sel["link"].items() if k in ("id", "sub")}
            send.selection = new_sel


def _decrypt_link(data: dict) -> str | None:
    try:
        return (
            crypto.get_keyring()
            .decrypt(base64.b64decode(data["ct"]), data["kid"], LINK_AAD)
            .decode()
        )
    except (crypto.CryptoError, ValueError, KeyError, TypeError):
        return None


def _expires_label(link, settings) -> str:
    """ISO date; mail_send.build_message renders it in each recipient's language."""
    return link.expires_at.astimezone(ZoneInfo(settings.timezone)).date().isoformat()


def _send_link(
    db, send_id: int, requester: AppUser, dash: Dashboard, base_url: str, settings
) -> tuple[str, str] | None:
    send = db.get(EmailSend, send_id, with_for_update=True, populate_existing=True)
    if send is None:
        return None
    stored = send.selection or {}
    link_data = stored.get("link")
    if link_data:
        link = db.get(ShareLink, link_data.get("id"))
        if (
            link is None
            or not links.is_active(link)
            or not links.sharing_enabled()
            or not link_data.get("ct")
        ):
            db.commit()
            return None
        raw = _decrypt_link(link_data)
        if raw is None:
            db.commit()
            return None
        db.commit()
        expires = _expires_label(link, settings)
        return links.link_url(stored.get("base") or base_url, raw), expires

    reuse: tuple[ShareLink, dict, str] | None = None
    if send.subscription_id is not None:
        now = datetime.now(UTC)
        rows = db.scalars(
            select(EmailSend)
            .where(
                EmailSend.subscription_id == send.subscription_id,
                EmailSend.id != send.id,
                EmailSend.selection["link"].has_key("ct"),
            )
            .order_by(EmailSend.id.desc())
            .with_for_update()
        ).all()
        for prev in rows:
            data = prev.selection["link"]
            link = db.get(ShareLink, data.get("id"))
            if reuse is None and (
                link is not None
                and link.dashboard_id == dash.id
                and link.created_by == requester.id
                and link.revoked_at is None
                and link.expires_at > now + REUSE_MARGIN
                and links.sharing_enabled()
            ):
                raw = _decrypt_link(data)
                if raw is not None:
                    reuse = (link, data, raw)
            if prev.status in ("sent", "partial", "failed"):
                prev.selection = {
                    **prev.selection,
                    "link": {"id": data.get("id"), "sub": send.subscription_id},
                }
        if reuse is not None:
            link, data, raw = reuse
            send.selection = {
                **(send.selection or {}),
                "link": {
                    "id": link.id,
                    "ct": data["ct"],
                    "kid": data["kid"],
                    "sub": send.subscription_id,
                },
            }
            db.commit()
            expires = _expires_label(link, settings)
            return links.link_url(stored.get("base") or base_url, raw), expires

    link, raw = links.create(
        db,
        requester,
        dash,
        days=send.link_days,
        note=t("mail.link_note", subject=send.subject)[:200],
        ip=None,
        counted=False,
    )
    keyring = crypto.get_keyring()
    crypto.ensure_key_check(db, keyring)
    blob, kid = keyring.encrypt(raw.encode(), LINK_AAD)
    link_payload = {
        "id": link.id,
        "ct": base64.b64encode(blob).decode(),
        "kid": kid,
    }
    if send.subscription_id is not None:
        link_payload["sub"] = send.subscription_id
    send.selection = {**(send.selection or {}), "link": link_payload}
    db.commit()
    expires = _expires_label(link, settings)
    return links.link_url(send.selection.get("base") or base_url, raw), expires


def _period_label(key: str | None, loc: str) -> str | None:
    with use_locale(loc):
        if key in pdf.PERIOD_LABELS:
            return t(f"pdf.period.{key}")
    return key


def _shown_subject(db, send) -> str:
    """The subject as the viewer reads it: automatic subjects in the request language (022)."""
    dash = db.get(Dashboard, send.dashboard_id)
    return _subject(send, dash, i18n_current()) if dash is not None else send.subject


def _subject(send, dash, loc: str, definition: dict | None = None) -> str:
    selection = send.selection or {}
    auto_subject = selection.get("auto_subject")
    name = (localized(definition, "title", loc) if definition else None) or dash.name
    if isinstance(auto_subject, dict) and "period" in auto_subject:
        return f"{name} · {_period_label(auto_subject['period'], loc)}"[:200]
    return send.subject


#: Feature 058: the sleep the pacer uses. Tests replace it to prove the pacing without waiting.
sleep = time.sleep


class _Pacer:
    """`EMAIL_SEND_RATE` messages per second, measured from the previous message (0 = no pause)."""

    def __init__(self, rate: int):
        self.interval = 1.0 / rate if rate and rate > 0 else 0.0
        self.last: float | None = None

    def wait(self) -> None:
        if not self.interval:
            return
        now = time.monotonic()
        if self.last is not None:
            remaining = self.interval - (now - self.last)
            if remaining > 0:
                sleep(remaining)
        self.last = time.monotonic()


def _envelopes(ids: list[int], locales: dict[int, str], size: int) -> list[list[int]]:
    """The deliveries grouped into messages: never two languages in one, at most `size` each."""
    groups: list[list[int]] = []
    for did in ids:
        if groups and len(groups[-1]) < size and locales[groups[-1][0]] == locales[did]:
            groups[-1].append(did)
        else:
            groups.append([did])
    return groups


def _process_send(    send_id: int, delivery_ids: list[int], now: datetime, base_url: str
) -> None:
    db = get_sessionmaker()()
    try:
        send = db.get(EmailSend, send_id)
        if send is None:
            return
        dash = db.get(Dashboard, send.dashboard_id)
        if dash is None:
            return
        # 058: a send may now carry thousands of recipients, and the product database is often a
        # remote one (~200 ms per round trip). Load the batch once and work from memory: one query
        # for the deliveries, one for the users they name — never a `db.get` per address.
        rows = {row.id: row for row in db.scalars(
            select(EmailDelivery).where(EmailDelivery.id.in_(delivery_ids))).all()}
        user_ids = {row.user_id for row in rows.values() if row.user_id is not None}
        users = ({u.id: u for u in db.scalars(
            select(AppUser).where(AppUser.id.in_(user_ids))).all()} if user_ids else {})

        def queued() -> list:
            return [row for row in rows.values() if row.status == "queued"]

        ctx = links.report_context(db, dash)
        requester = users.get(send.requested_by) if send.requested_by else None
        if requester is None and send.requested_by is not None:
            requester = db.get(AppUser, send.requested_by)
        if not mail_settings.available():
            for delivery in queued():
                delivery.attempts -= 1
                delivery.next_attempt_at = now + BACKOFF[0]
            db.commit()
            return
        if ctx is None:
            for delivery in queued():
                delivery.status = "skipped"
                delivery.error = mail_send.reason("unavailable")
            _roll_up(db, send.id, now)
            db.commit()
            return
        if not can_open(db, requester, dash, ctx):
            for delivery in queued():
                delivery.status = "skipped"
                delivery.error = mail_send.reason("requester_no_access")
            _roll_up(db, send.id, now)
            db.commit()
            return

        eligible: list[int] = []
        for delivery in queued():
            if delivery.user_id is not None:
                recipient_user = users.get(delivery.user_id)
                if recipient_user is None or not recipient_user.is_active:
                    delivery.status = "skipped"
                    delivery.error = mail_send.reason("no_access")
                    continue
                if not can_open(db, recipient_user, dash, ctx):
                    delivery.status = "skipped"
                    delivery.error = mail_send.reason("no_access")
                    continue
            eligible.append(delivery.id)
        db.commit()
        if not eligible:
            _roll_up(db, send.id, now)
            db.commit()
            return

        settings = get_settings()
        params = [tuple(p) for p in send.selection.get("params", [])]
        definition = engine.definition_json(ctx)
        locales: dict[int, str] = {}
        for did in eligible:
            delivery = rows[did]
            user = users.get(delivery.user_id) if delivery.user_id is not None else None
            if user is not None and user.locale in ("es", "en"):
                locales[did] = user.locale
            else:
                locales[did] = settings.default_locale
        attachments: dict[str, tuple[str, bytes]] = {}
        too_large_by: dict[str, bool] = {}
        if send.attach_pdf:
            send_pk = send.id
            try:
                payload = reports._data(db, ctx, params)
            except ApiError as e:
                if ctx.direct is None:
                    raise
                db.rollback()
                for did in eligible:
                    delivery = rows[did]
                    if delivery.status == "queued":
                        delivery.status = "failed"
                        delivery.error = t("mail.pdf_failed", detail=e.message)
                _roll_up(db, send_pk, now)
                db.commit()
                log.warning("email send %s: direct report unavailable (%s)",
                            send_pk, e.code)
                return
            period = payload["selection"]["current"]
            filename = f"{ctx.report_id}-{period['from']}-{period['to']}.pdf"
            for loc in sorted(set(locales.values())):
                content = pdf.render(
                    definition,
                    payload,
                    organization=settings.organization_name,
                    product=settings.product_name,
                    viewer=requester.full_name if send.subscription_id is None else None,
                    locale=loc,
                    palette=palette.resolve(definition, palette.installation_preset(db), db),
                    images=images.reader(ctx),
                )
                if len(content) > mail_send.MAX_ATTACHMENT:
                    too_large_by[loc] = True
                else:
                    attachments[loc] = (filename, content)
            period_key = payload["selection"]["period"]
        else:
            period_key = dict(params).get("period") or definition["periods"]["default"]

        link_url = None
        link_expires = None
        if send.link_days is not None:
            code: str | None = None
            try:
                result = _send_link(db, send.id, requester, dash, base_url, settings)
            except (ApiError, crypto.CryptoError) as e:
                db.rollback()
                log.warning(
                    "link creation failed for send %s: %s",
                    send_id,
                    getattr(e, "code", type(e).__name__),
                )
                code = "link_failed"
            else:
                if result is None:
                    code = "link_unavailable"
                else:
                    link_url, link_expires = result
            if code is not None:
                for did in eligible:
                    delivery = rows[did]
                    if delivery.status == "queued":
                        delivery.status = "failed"
                        delivery.error = mail_send.reason(code)
                _roll_up(db, send.id, now)
                db.commit()
                return

        sendable: list[int] = []
        for did in eligible:
            delivery = rows[did]
            if delivery.status != "queued":
                continue
            loc = locales[did]
            if link_url is None and loc not in attachments:
                delivery.status = "failed"
                delivery.error = mail_send.reason(
                    "too_large" if too_large_by.get(loc) else "nothing_to_send"
                )
                continue
            sendable.append(did)
        if not sendable:
            _roll_up(db, send.id, now)
            db.commit()
            return

        cfg = mail_settings.smtp_config()
        logo_url = mail_send.logo_src(
            settings.logo_url, (send.selection or {}).get("base") or base_url
        )
        # 058: one SMTP message per EMAIL_BATCH_SIZE recipients (BCC, the sender in To) — or one per
        # address when the installation asks for it, which is what SES recommends for per-address
        # bounce handling. `EMAIL_SEND_RATE` paces the messages, never the recipients: it is the only
        # guard the product keeps, and it protects the provider, not the product's own quota.
        batch_size = 1 if settings.email_individual_messages else settings.email_batch_size
        batch_size = max(1, batch_size)
        sender_address = requester.email if requester is not None else None
        from_mode_user = settings.email_from_mode == "user" and sender_address is not None
        pace = _Pacer(settings.email_send_rate)
        envelopes = _envelopes(sendable, locales, batch_size)
        for group in envelopes:
            pace.wait()
            loc = locales[group[0]]
            addresses = [rows[did].recipient for did in group]
            batched = len(addresses) > 1
            msg = mail_send.build_message(
                cfg=cfg,
                to=(sender_address or cfg.sender_address) if batched else addresses[0],
                bcc=addresses if batched else None,
                from_address=sender_address if from_mode_user else None,
                reply_to=sender_address if sender_address else None,
                sent_by=(requester.full_name if requester is not None else None),
                subject=_subject(send, dash, loc, definition),
                organization=settings.organization_name,
                product=settings.product_name,
                dashboard_name=localized(definition, "title", loc) or dash.name,
                period_label=_period_label(period_key, loc),
                note=send.message,
                link_url=link_url,
                link_expires=link_expires,
                attachment=attachments.get(loc),
                logo_url=logo_url,
                locale=loc,
            )
            try:
                mail_send.deliver(cfg, msg)
                for did in group:
                    delivery = rows[did]
                    delivery.status = "sent"
                    delivery.sent_at = now
                    delivery.error = None
            except MailError as e:
                for did in group:
                    _fail(db, did, e.code, e.permanent, now, row=rows[did])
                log.warning("email batch failed: %s deliveries, code %s", len(group), e.code)
            db.commit()
        _roll_up(db, send.id, now)
        db.commit()
    finally:
        db.close()


def resend_failed(
    db,
    user: AppUser,
    dash: Dashboard,
    send_id: int,
    *,
    ip: str | None = None,
) -> EmailSend:
    """Queue a new send with the addresses that failed in `send_id`, and nothing else (FR-016).

    The reason a sender asks for this is a provider hiccup or a wrong mailbox fixed later, so the
    new send repeats the subject, the message and the selection of the original and points at it in
    `selection.resend_of`; the history shows two sends, which is the truth."""
    original = db.get(EmailSend, send_id)
    if original is None or original.dashboard_id != dash.id:
        raise validation({"send": "not_found"}, M("mail.send_not_found"))
    if user.role != "admin" and original.requested_by != user.id:
        raise ApiError(403, "forbidden", M("common.forbidden"))
    failed = db.scalars(
        select(EmailDelivery)
        .where(EmailDelivery.send_id == send_id, EmailDelivery.status == "failed")
        .order_by(EmailDelivery.id)).all()
    if not failed:
        raise validation({"send": "nothing_failed"}, M("mail.nothing_failed"))
    selection = dict(original.selection or {})
    selection["resend_of"] = original.id
    new = EmailSend(
        dashboard_id=original.dashboard_id,
        requested_by=user.id,
        subscription_id=original.subscription_id,
        subject=original.subject,
        message=original.message,
        selection=selection,
        attach_pdf=original.attach_pdf,
        link_days=original.link_days,
        status="queued",
        kinds={"users": sum(1 for d in failed if d.user_id is not None),
               "lists": [], "emails": sum(1 for d in failed
                                          if d.user_id is None and d.list_id is None),
               "total": len(failed), "resend_of": original.id},
    )
    db.add(new)
    db.flush()
    for delivery in failed:
        db.add(EmailDelivery(send_id=new.id, recipient=delivery.recipient,
                             user_id=delivery.user_id, list_id=delivery.list_id,
                             status="queued"))
    db.flush()
    audit.record(db, "mail_send_resent", actor_id=user.id, ip=ip,
                 detail={"send_id": new.id, "from": original.id, "recipients": len(failed)})
    return new


def process_due(
    now: datetime | None = None,
    *,
    base_url: str | None = None,
    limit: int = CLAIM_LIMIT,
) -> int:
    if now is None:
        now = datetime.now(UTC)
    if get_settings().email_sending_paused:
        # 058: the operator's panic switch. The queue keeps accepting sends and the worker holds
        # them, so the decision costs nobody the message they already composed.
        return 0
    base = base_url or site_base()
    claimed: list[tuple[int, int]] = []
    with get_sessionmaker().begin() as db:
        # 058: claim whole sends, not a slice of one. A send of 1.500 recipients has to reach the
        # provider as ⌈1500/EMAIL_BATCH_SIZE⌉ messages (SC-002); claiming in pieces of twenty would
        # turn it into 75 tiny messages. `limit` bounds the *sends* per pass, and the deliveries of
        # those sends come together, up to the bulk ceiling that keeps one pass finite.
        due_sends = (
            select(EmailDelivery.send_id)
            .where(EmailDelivery.status == "queued", EmailDelivery.next_attempt_at <= now)
            .distinct()
            .limit(limit)
        )
        rows = db.scalars(
            select(EmailDelivery)
            .where(
                EmailDelivery.status == "queued",
                EmailDelivery.next_attempt_at <= now,
                EmailDelivery.send_id.in_(due_sends),
            )
            .order_by(EmailDelivery.next_attempt_at, EmailDelivery.id)
            .with_for_update(skip_locked=True)
            .limit(BULK_CLAIM_LIMIT)
        ).all()
        send_ids = set()
        for delivery in rows:
            delivery.attempts += 1
            delivery.next_attempt_at = now + LEASE
            claimed.append((delivery.id, delivery.send_id))
            send_ids.add(delivery.send_id)
        if send_ids:
            sends = db.scalars(
                select(EmailSend).where(EmailSend.id.in_(send_ids))
            ).all()
            for send in sends:
                if send.status == "queued":
                    send.status = "sending"
    handled = 0
    by_send: dict[int, list[int]] = {}
    for delivery_id, send_id in claimed:
        by_send.setdefault(send_id, []).append(delivery_id)
    for send_id, delivery_ids in by_send.items():
        try:
            _process_send(send_id, delivery_ids, now, base)
            handled += len(delivery_ids)
        except Exception:
            log.exception("email send %s failed", send_id)
            with get_sessionmaker().begin() as db:
                for delivery_id in delivery_ids:
                    _fail(db, delivery_id, "internal", permanent=False, now=now)
                _roll_up(db, send_id, now)
            handled += len(delivery_ids)
    return handled
