"""Telegram conversation (feature 007, contracts/bot.md): `/start <token>` and button presses.

Called once per update inside the caller's transaction. Malformed input is ignored; Telegram
credential/webhook errors propagate so the poller can flag the bot. Payloads are never logged.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.i18n import normalize, t, use_locale
from app.models import AppUser, TelegramLink
from app.services import audit
from app.telegram import service
from app.telegram.client import BotClient, TelegramError

log = logging.getLogger(__name__)

CODE_RANGE = range(10, 100)
INVALID = "telegram.invalid"  # catalogue id, rendered per update


def _product_label() -> str:
    s = get_settings()
    label = s.product_name
    if s.organization_name:
        label += f" · {s.organization_name}"
    return label


def _browser_family(user_agent: str | None) -> str:
    if not user_agent:
        return t("telegram.unknown")
    if "Edg/" in user_agent:
        return "Edge"
    if "Chrome" in user_agent:
        return "Chrome"
    if "Firefox" in user_agent:
        return "Firefox"
    if "Safari" in user_agent:
        return "Safari"
    return "desconocido"


def _display_name(data: dict) -> str:
    parts = [data.get("first_name") or "", data.get("last_name") or ""]
    display = " ".join(p for p in parts if p).strip()
    if not display:
        display = data.get("username") or "Telegram"
    return display[:128]


def _local_hhmm(ts: datetime, iana: str) -> str:
    return ts.astimezone(ZoneInfo(iana)).strftime("%H:%M")


def _codes(code: int) -> list[int]:
    """The request's code plus two distinct decoys, shuffled."""
    rng = secrets.SystemRandom()
    chosen = [*rng.sample([n for n in CODE_RANGE if n != code], 2), code]
    rng.shuffle(chosen)
    return chosen


def _link_of(db: Session, telegram_id: int) -> TelegramLink | None:
    return db.query(TelegramLink).filter(TelegramLink.telegram_id == telegram_id).one_or_none()


def _language(db: Session, sender: dict[str, Any]) -> str | None:
    """language = linked account → Telegram language_code → DEFAULT_LOCALE (feature 022)."""
    locale = normalize(sender.get("language_code"))
    if isinstance(sender.get("id"), int):
        link = _link_of(db, sender["id"])
        if link:
            user = db.get(AppUser, link.user_id)
            if user and user.locale in {"es", "en"}:
                locale = user.locale
    return locale or get_settings().default_locale


def handle_update(db: Session, bot: BotClient, update: dict) -> None:
    """Process one Telegram update. Never raises for malformed input."""
    try:
        payload = update.get("message") or update.get("callback_query") or {}
        sender = payload.get("from") or {}
        with use_locale(_language(db, sender)):
            if "message" in update:
                _handle_message(db, bot, update["message"])
            elif "callback_query" in update:
                _handle_callback(db, bot, update["callback_query"])
    except TelegramError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError):
        # Bad or unknown input must not stop the poller; no payload in logs.
        log.debug("telegram update ignored")


def _handle_message(db: Session, bot: BotClient, message: dict) -> None:
    chat = message.get("chat") or {}
    if chat.get("type") != "private":
        return
    text = (message.get("text") or "").strip()
    sender = message.get("from") or {}
    product = _product_label()

    if not text.startswith("/start"):
        return
    parts = text.split(maxsplit=1)
    if len(parts) == 1:
        _safe_send(bot, chat["id"], t("telegram.use_button", product=product))
        return

    found = service.find_by_token(db, parts[1])
    req = service.find_by_id(db, found.id, lock=True) if found else None
    if req is None or req.status != "pending" or not service.is_live(req):
        _safe_send(bot, chat["id"],
                   t("telegram.link_expired", product=product))
        return

    req.telegram_id = sender["id"]
    req.chat_id = chat["id"]
    req.status = "started"
    expires_hhmm = _local_hhmm(req.expires_at, get_settings().timezone)

    if req.purpose == "sign_in":
        if _link_of(db, sender["id"]) is None:
            req.status = "refused"
            req.reason = "not_linked"
            _safe_send(bot, chat["id"],
                       t("telegram.not_linked", product=product))
            return
        keyboard = [
            [(str(c), f"c:{req.id}:{c}") for c in _codes(req.match_code)],
            [(t("telegram.cancel"), f"x:{req.id}")],
        ]
        text = t(
            "telegram.sign_in_request",
            product=product,
            browser=_browser_family(req.user_agent),
            ip=req.ip or t("telegram.unknown_ip"),
            expires=expires_hhmm,
        )
    else:
        user = db.get(AppUser, req.user_id)
        email = service.masked_email(user.email) if user else t("telegram.your_account")
        keyboard = [[(t("telegram.confirm"), f"ok:{req.id}"),
                     (t("telegram.cancel"), f"x:{req.id}")]]
        text = t("telegram.link_request", email=email, product=product, expires=expires_hhmm)

    result = _safe_send(bot, chat["id"], text, keyboard)
    if result:
        req.message_id = result["message_id"]


def _handle_callback(db: Session, bot: BotClient, query: dict) -> None:
    data = (query.get("data") or "").strip()
    sender = query.get("from") or {}
    query_id = query.get("id", "")
    product = _product_label()

    action, _, rest = data.partition(":")
    req_id, _, code_text = rest.partition(":")
    req = service.find_by_id(db, req_id, lock=True) if req_id else None
    valid = (
        req is not None
        and req.status == "started"
        and service.is_live(req)
        and req.telegram_id == sender.get("id")
    )
    if not valid:
        _safe_answer(bot, query_id, t(INVALID))
        return

    if action == "x":
        req.status, req.reason = "refused", "cancelled"
        final = t("telegram.final.cancelled")
    elif action == "c" and req.purpose == "sign_in" and code_text.isdigit():
        link = _link_of(db, req.telegram_id)
        if link is None:   # unlinked after /start
            req.status, req.reason = "refused", "not_linked"
            final = t("telegram.final.unlinked")
        elif int(code_text) == req.match_code:
            req.status = "approved"
            req.user_id = link.user_id
            link.username = (sender.get("username") or "")[:64] or None
            link.display_name = _display_name(sender)
            final = t("telegram.final.approved", product=product)
        else:
            req.status, req.reason = "refused", "wrong_code"
            final = t("telegram.final.wrong_code")
    elif action == "ok" and req.purpose == "link":
        final = _link(db, req, sender)
    else:
        _safe_answer(bot, query_id, t(INVALID))
        return

    _safe_answer(bot, query_id)
    if req.message_id and req.chat_id:
        _safe_edit(bot, req.chat_id, req.message_id, final)


def _link(db: Session, req, sender: dict) -> str:
    if db.get(TelegramLink, req.user_id) is not None:
        req.status, req.reason = "refused", "already_linked_self"
        return t("telegram.final.self_linked")
    username = (sender.get("username") or "")[:64] or None
    try:
        # SAVEPOINT: a Telegram account already linked elsewhere must refuse, not abort.
        with db.begin_nested():
            db.add(TelegramLink(user_id=req.user_id, telegram_id=req.telegram_id,
                                username=username, display_name=_display_name(sender),
                                linked_by=req.user_id))
    except IntegrityError:
        req.status, req.reason = "refused", "already_linked"
        return t("telegram.final.other_linked")
    req.status = "consumed"
    audit.record(db, "telegram_linked", actor_id=req.user_id, target_id=req.user_id,
                 detail={"telegram_username": username})
    return t("telegram.final.linked")


def _safe_send(bot: BotClient, chat_id: int, text: str,
               keyboard: list | None = None) -> dict | None:
    """Send a message; Telegram errors other than credential/webhook are ignored."""
    try:
        return bot.send_message(chat_id, text, keyboard)
    except TelegramError as exc:
        if exc.code in ("invalid_credential", "webhook_conflict"):
            raise
        log.debug("telegram send failed (%s)", exc.code)
        return None


def _safe_edit(bot: BotClient, chat_id: int, message_id: int, text: str) -> None:
    try:
        bot.edit_message(chat_id, message_id, text)
    except TelegramError as exc:
        if exc.code in ("invalid_credential", "webhook_conflict"):
            raise
        log.debug("telegram edit failed (%s)", exc.code)


def _safe_answer(bot: BotClient, query_id: str, text: str | None = None) -> None:
    try:
        bot.answer_callback(query_id, text)
    except TelegramError as exc:
        if exc.code in ("invalid_credential", "webhook_conflict"):
            raise
        log.debug("telegram answer failed (%s)", exc.code)
