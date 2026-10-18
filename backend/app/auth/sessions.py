"""Server-side sessions: the cookie carries a random id, the database only its SHA-256."""
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AppUser, UserSession

COOKIE_NAME = "sid"
IDLE_TIMEOUT = timedelta(days=7)
ABSOLUTE_TIMEOUT = timedelta(days=30)
TOUCH_EVERY = timedelta(minutes=5)
MFA_PENDING_TTL = timedelta(minutes=5)   # password ok, second factor not yet given
REAUTH_VALID = timedelta(minutes=5)      # step-up confirmation (feature 004, FR-021)


def _hash(raw: str) -> bytes:
    return hashlib.sha256(raw.encode()).digest()


def now() -> datetime:
    return datetime.now(UTC)


def create(db: Session, user: AppUser, user_agent: str | None, ip: str | None, *,
           mfa_pending: bool = False) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(UserSession(id_hash=_hash(raw), user_id=user.id, mfa_pending=mfa_pending,
                       user_agent=(user_agent or "")[:300] or None, ip=ip))
    db.flush()
    return raw


def lookup(db: Session, raw: str | None) -> tuple[UserSession, AppUser] | None:
    """Return the live session and its user, deleting it if it expired."""
    if not raw or len(raw) > 100:
        return None
    row = db.execute(
        select(UserSession, AppUser)
        .join(AppUser, AppUser.id == UserSession.user_id)
        .where(UserSession.id_hash == _hash(raw))
    ).first()
    if row is None:
        return None
    sess, user = row
    t = now()
    if t - sess.last_seen_at > IDLE_TIMEOUT or t - sess.created_at > ABSOLUTE_TIMEOUT \
            or not user.is_active or (sess.mfa_pending and t - sess.created_at > MFA_PENDING_TTL):
        db.delete(sess)
        db.flush()
        return None
    if t - sess.last_seen_at > TOUCH_EVERY:
        sess.last_seen_at = t
    return sess, user


def delete_one(db: Session, raw: str | None) -> None:
    if raw:
        db.execute(delete(UserSession).where(UserSession.id_hash == _hash(raw)))


def delete_all(db: Session, user_id: int, except_hash: bytes | None = None) -> None:
    stmt = delete(UserSession).where(UserSession.user_id == user_id)
    if except_hash is not None:
        stmt = stmt.where(UserSession.id_hash != except_hash)
    db.execute(stmt)


def purge_expired(db: Session) -> int:
    t = now()
    res = db.execute(delete(UserSession).where(
        (UserSession.last_seen_at < t - IDLE_TIMEOUT)
        | (UserSession.created_at < t - ABSOLUTE_TIMEOUT)))
    return res.rowcount or 0


def set_cookie(response: Response, raw: str) -> None:
    response.set_cookie(COOKIE_NAME, raw, max_age=int(ABSOLUTE_TIMEOUT.total_seconds()),
                        httponly=True, secure=get_settings().cookie_secure,
                        samesite="lax", path="/")


def clear_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True,
                           secure=get_settings().cookie_secure, samesite="lax")


def raw_hash(raw: str) -> bytes:
    return _hash(raw)


def reauth_valid_until(sess: UserSession) -> datetime | None:
    return sess.reauth_at + REAUTH_VALID if sess.reauth_at else None
