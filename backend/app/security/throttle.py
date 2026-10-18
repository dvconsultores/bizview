"""Per-address rate limiting (feature 004, FR-020, FR-005, research R6).

Fixed windows stored in PostgreSQL (works across Uvicorn workers). Sign-in is checked before any
password or code is verified; failures of passwords, codes, and re-authentication all count.

Sign-in and public share-link guessing share the login_throttle table but use separate key
spaces on window_start: sign-in windows are whole-minute aligned, share-link windows are the
same alignment shifted by one second (SHARE_KEY_OFFSET), so they never collide while purge()
still cleans both.
"""
import threading
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import ApiError
from app.i18n import M
from app.models import LoginThrottle
from app.services import audit

SHARE_GUESS_LIMIT = 30
SHARE_GUESS_WINDOW_MINUTES = 10
SHARE_KEY_OFFSET = timedelta(seconds=1)


def _window_start(minutes: int, now: datetime) -> datetime:
    epoch_min = int(now.timestamp() // 60)
    return datetime.fromtimestamp((epoch_min - epoch_min % minutes) * 60, UTC)


def _window(settings: Settings, now: datetime) -> datetime:
    return _window_start(settings.login_rate_window_minutes, now)


def check(db: Session, ip: str | None, settings: Settings) -> None:
    """Raise 429 when the address is over the limit for the current window."""
    if not ip:
        return
    now = datetime.now(UTC)
    start = _window(settings, now)
    row = db.scalar(select(LoginThrottle).where(LoginThrottle.ip == ip,
                                                LoginThrottle.window_start == start))
    if row is None or row.failures < settings.login_rate_limit:
        return
    if not row.limited_audited:
        row.limited_audited = True
        audit.record(db, "login_rate_limited", ip=ip, detail={"failures": row.failures})
        db.commit()
    retry = int((start + timedelta(minutes=settings.login_rate_window_minutes) - now)
                .total_seconds()) + 1
    raise ApiError(429, "rate_limited",
                   M("network.throttled"),
                   extra={"retry_after_seconds": max(1, retry)})


def register_failure(db: Session, ip: str | None, settings: Settings) -> None:
    if not ip:
        return
    db.execute(text(
        "INSERT INTO login_throttle (ip, window_start, failures) VALUES (:ip, :w, 1) "
        "ON CONFLICT (ip, window_start) DO UPDATE SET failures = login_throttle.failures + 1"),
        {"ip": ip, "w": _window(settings, datetime.now(UTC))})


def _share_window(now: datetime) -> datetime:
    return _window_start(SHARE_GUESS_WINDOW_MINUTES, now) + SHARE_KEY_OFFSET


def share_check(db: Session, ip: str | None) -> None:
    """Raise 429 when the address has too many unknown share-link attempts."""
    if not ip:
        return
    now = datetime.now(UTC)
    start = _share_window(now)
    row = db.scalar(select(LoginThrottle).where(LoginThrottle.ip == ip,
                                                LoginThrottle.window_start == start))
    if row is None or row.failures < SHARE_GUESS_LIMIT:
        return
    if not row.limited_audited:
        row.limited_audited = True
        audit.record(
            db,
            "login_rate_limited",
            ip=ip,
            detail={"failures": row.failures, "cause": "share_link"},
        )
        db.commit()
    retry = int((
        start - SHARE_KEY_OFFSET + timedelta(minutes=SHARE_GUESS_WINDOW_MINUTES) - now
    ).total_seconds()) + 1
    raise ApiError(429, "rate_limited",
                   M("network.rate_limited"),
                   extra={"retry_after_seconds": max(1, retry)})


def share_register_failure(db: Session, ip: str | None) -> None:
    if not ip:
        return
    db.execute(text(
        "INSERT INTO login_throttle (ip, window_start, failures) VALUES (:ip, :w, 1) "
        "ON CONFLICT (ip, window_start) DO UPDATE SET failures = login_throttle.failures + 1"),
        {"ip": ip, "w": _share_window(datetime.now(UTC))})


def purge(db: Session) -> int:
    res = db.execute(delete(LoginThrottle).where(
        LoginThrottle.window_start < datetime.now(UTC) - timedelta(days=1)))
    return res.rowcount or 0


PUBLIC_LIMIT_PER_MINUTE = 240

_public_hits: dict[str, tuple[int, int]] = {}
_public_lock = threading.Lock()


def public_check(ip: str | None, limit: int | None = None) -> None:
    """Per-process cap on public share-link requests per address and minute."""
    if not ip:
        return
    now = datetime.now(UTC)
    minute = int(now.timestamp() // 60)
    effective_limit = PUBLIC_LIMIT_PER_MINUTE if limit is None else limit
    with _public_lock:
        if ip in _public_hits:
            stored_minute, count = _public_hits[ip]
            if stored_minute != minute:
                count = 0
        else:
            count = 0

        count += 1
        _public_hits[ip] = (minute, count)

        if count > effective_limit:
            retry_after = max(1, 60 - now.second)
            raise ApiError(
                429,
                "rate_limited",
                M("network.rate_limited"),
                extra={"retry_after_seconds": retry_after},
            )

        if len(_public_hits) > 10_000:
            for key in [k for k, (m, _) in _public_hits.items() if m != minute]:
                del _public_hits[key]
