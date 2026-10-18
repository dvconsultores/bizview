"""Telegram sign-in service (feature 007): request primitives, then bot settings."""

from __future__ import annotations

import hashlib
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.errors import ApiError, validation
from app.i18n import M
from app.models import AppUser, TelegramRequest, TelegramSettings
from app.security import crypto, mfa
from app.services import audit
from app.telegram.client import BotClient, TelegramError

REQUEST_TTL = timedelta(minutes=5)
POLL_FRESH = timedelta(minutes=2)   # the long poll lasts up to 25 s
RETENTION = timedelta(days=1)


def now() -> datetime:
    return datetime.now(UTC)


def sha256(value: str) -> bytes:
    return hashlib.sha256(value.encode()).digest()


@dataclass
class NewRequest:
    request: TelegramRequest
    start_token: str
    browser_secret: str | None


def new_request(
    db: Session,
    purpose: str,
    *,
    user_id: int | None = None,
    ip: str | None,
    user_agent: str | None,
) -> NewRequest:
    """Create a short-lived approval request; store only hashes of secrets."""
    start_token = secrets.token_urlsafe(32)
    public_id = secrets.token_urlsafe(12)  # 16 chars
    browser_secret = None
    match_code = None
    if purpose == "sign_in":
        browser_secret = secrets.token_urlsafe(32)
        match_code = secrets.randbelow(90) + 10

    request = TelegramRequest(
        id=public_id,
        purpose=purpose,
        token_hash=sha256(start_token),
        browser_hash=sha256(browser_secret) if browser_secret else None,
        user_id=user_id,
        match_code=match_code,
        status="pending",
        ip=ip,
        user_agent=user_agent[:300] if user_agent else None,
        expires_at=now() + REQUEST_TTL,
    )
    db.add(request)
    db.flush()
    return NewRequest(request=request, start_token=start_token, browser_secret=browser_secret)


def find_by_token(db: Session, token: str) -> TelegramRequest | None:
    """Find a pending, live request by its start token hash."""
    return (
        db.query(TelegramRequest)
        .filter(
            TelegramRequest.token_hash == sha256(token),
            TelegramRequest.status == "pending",
            TelegramRequest.expires_at > now(),
        )
        .one_or_none()
    )


def find_by_browser(db: Session, secret: str) -> TelegramRequest | None:
    """Find a request of any status by browser secret hash."""
    return (
        db.query(TelegramRequest)
        .filter(TelegramRequest.browser_hash == sha256(secret))
        .one_or_none()
    )


def find_by_id(db: Session, public_id: str, *, lock: bool = False) -> TelegramRequest | None:
    query = db.query(TelegramRequest).filter(TelegramRequest.id == public_id)
    if lock:
        query = query.with_for_update()
    return query.one_or_none()


def is_live(req: TelegramRequest) -> bool:
    return req.status in ("pending", "started") and req.expires_at > now()


def expire_due(db: Session) -> int:
    """Mark non-final past-expiry rows as expired."""
    return (
        db.query(TelegramRequest)
        .filter(
            TelegramRequest.expires_at <= now(),
            TelegramRequest.status.in_(("pending", "started")),
        )
        .update({"status": "expired", "reason": "expired"}, synchronize_session=False)
    )


def purge_old(db: Session) -> int:
    """Delete rows older than the retention window."""
    return (
        db.query(TelegramRequest)
        .filter(TelegramRequest.created_at < now() - RETENTION)
        .delete(synchronize_session=False)
    )


def deep_link(bot_username: str, token: str) -> str:
    return f"https://t.me/{bot_username}?start={token}"


def qr(link: str) -> str:
    return mfa.qr_svg_data_uri(link)


def claim_approved(db: Session, req_id: str) -> TelegramRequest | None:
    """Atomically consume an approved request; returns None if already consumed."""
    req = find_by_id(db, req_id, lock=True)
    if req is None or req.expires_at <= now():
        return None
    if req.status != "approved":
        return None
    req.status = "consumed"
    db.flush()
    return req


def masked_email(email: str) -> str:
    """ana.perez@example.com → a•••@example.com"""
    local, _, domain = email.partition("@")
    return f"{local[0]}•••@{domain}" if local else email


# --- settings (US1) ---

BOT_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{1,28}[Bb][Oo][Tt]$")
TOKEN_FORMAT = re.compile(r"^\d+:[A-Za-z0-9_-]+$")
# Tests replace this to inject a fake transport.
def _default_client(token: str) -> BotClient:
    return BotClient(token)


client_factory: Callable[[str], BotClient] = _default_client


def settings_row(db: Session, *, lock: bool = False) -> TelegramSettings:
    row = db.get(TelegramSettings, 1, with_for_update=lock)
    if row is None:
        row = TelegramSettings(id=1, enabled=False)
        db.add(row)
        db.flush()
    return row


def public_state(row: TelegramSettings) -> dict:
    return {
        "enabled": row.enabled,
        "bot_username": row.bot_username,
        "token_configured": row.token_ct is not None,
        "token_changed_at": row.token_changed_at,
        "last_check_at": row.last_check_at,
        "last_check_ok": row.last_check_ok,
        "last_check": row.last_check,
    }


def update_settings(
    db: Session,
    actor: AppUser,
    *,
    bot_username: str,
    token: str | None,
    ip: str | None,
) -> TelegramSettings:
    row = settings_row(db, lock=True)
    changed: list[str] = []

    username = bot_username.strip().lstrip("@")
    if not BOT_NAME.match(username):
        raise validation(
            {"bot_username": "invalid"},
            M("telegram.bad_bot_name"),
        )
    if row.bot_username != username:
        row.bot_username = username
        changed.append("bot_username")

    if token is not None and token != "":
        token = token.strip()
        if not (20 <= len(token) <= 100) or not TOKEN_FORMAT.match(token):
            raise validation(
                {"token": "invalid"},
                M("telegram.bad_token"),
            )
        keyring = crypto.get_keyring()
        crypto.ensure_key_check(db, keyring)
        # A fresh nonce makes every save a change, so a re-entered token is checked again.
        row.token_ct, row.token_key_id = keyring.encrypt(token.encode(), crypto.TELEGRAM_AAD)
        row.token_changed_at = now()
        changed.append("bot_credential")
    elif token == "" and row.token_ct is not None:
        row.token_ct = None
        row.token_key_id = None
        row.token_changed_at = now()
        changed.append("bot_credential")

    if changed:
        # A changed bot must be checked again before it can be enabled (FR-004).
        row.last_check_ok = None
        row.last_check = None
        row.last_check_at = None
        row.enabled = False
        row.updated_at = now()
        row.updated_by = actor.id
        audit.record(db, "telegram_settings_updated", actor_id=actor.id, ip=ip,
                     detail={"fields": changed})
    return row


def token_of(row: TelegramSettings) -> str | None:
    if row.token_ct is None or row.token_key_id is None:
        return None
    keyring = crypto.get_keyring()
    return keyring.decrypt(row.token_ct, row.token_key_id, crypto.TELEGRAM_AAD).decode()


def check(db: Session, actor: AppUser, *, ip: str | None) -> dict:
    row = settings_row(db, lock=True)
    token = token_of(row)
    if not row.bot_username or not token:
        raise ApiError(409, "telegram_not_configured",
                       M("telegram.not_configured"))

    client = client_factory(token)
    reason: str | None = None
    bot_name: str | None = None
    try:
        me = client.get_me()
        if str(me.get("username", "")).lower() != row.bot_username.lower():
            reason = "name_mismatch"
        elif client.get_webhook_info().get("url"):
            reason = "webhook_conflict"
        else:
            bot_name = me.get("first_name") or me["username"]
    except TelegramError as exc:
        reason = exc.code
    finally:
        client.close()

    ok = reason is None
    row.last_check_at = now()
    row.last_check_ok = ok
    row.last_check = {"bot_name": bot_name} if ok else {"reason": reason}
    if not ok:
        row.enabled = False
    row.updated_at = now()
    row.updated_by = actor.id
    audit.record(db, "telegram_checked", actor_id=actor.id, ip=ip,
                 detail={"ok": ok, **({} if ok else {"reason": reason})})
    return {"ok": True, "bot_name": bot_name} if ok else {"ok": False, "reason": reason}


def set_enabled(db: Session, actor: AppUser, enabled: bool, *, ip: str | None) -> TelegramSettings:
    row = settings_row(db, lock=True)
    if enabled and row.last_check_ok is not True:
        raise ApiError(409, "telegram_check_required",
                       M("telegram.check_first"))
    if row.enabled != enabled:
        row.enabled = enabled
        row.updated_at = now()
        row.updated_by = actor.id
        audit.record(db, "telegram_enabled" if enabled else "telegram_disabled",
                     actor_id=actor.id, ip=ip)
    return row


def is_available(row: TelegramSettings | None) -> bool:
    return bool(row and row.enabled and row.last_check_ok is True and row.token_ct
                and row.bot_username)


def is_reachable(row: TelegramSettings) -> bool:
    """True when the worker reached Telegram recently (FR-013)."""
    return row.last_poll_ok_at is not None and row.last_poll_ok_at > now() - POLL_FRESH


def ensure_reachable(row: TelegramSettings) -> None:
    if not is_reachable(row):
        raise ApiError(503, "telegram_unavailable",
                       M("telegram.unavailable"))
