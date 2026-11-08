"""A busy origin: the wait, the streak and the one notification (feature 060).

Three jobs, all of them about the same fact — the origin database had no free connection slot:

* `delays` / `wait` — the jittered exponential backoff a run uses between attempts, sleepable in
  slices so a stop request or the run's own deadline interrupts it;
* `streak` / `notify_if_due` — how many consecutive `skipped_busy` runs an integration has, and the
  single Telegram message the operators get for the whole streak;
* `hint` — the quietest hour, offered only when the run history actually shows congestion.

The notification goes through the bot the installation already configured (feature 007): it is the
only per-person outbound channel the product owns, and 013 never shipped a notification setting, so
this feature does not invent one. When no bot is enabled, the `integration_busy` audit event is the
record — the run list already shows the amber state to whoever looks.
"""
import logging
import random
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppUser, AuditEvent, IntegrationRun, TelegramLink, TelegramSettings
from app.services import audit
from app.telegram import service as telegram

log = logging.getLogger("app.engine.busy")

#: The streak length that earns one message to the operators.
NOTIFY_AT = 3
#: How far back the quietest hour is derived from.
HINT_DAYS = 7
#: The scan stops here: a streak longer than this is already "many", and the query stays bounded.
MAX_STREAK = 200
#: A run waiting for the backoff must notice a stop request at least this often.
SLICE_SECONDS = 0.5


def delays(attempts: int, base: float, *, rng: random.Random | None = None) -> list[float]:
    """The waits between attempts: `base · 3**(n-1)` with ±20 % jitter, one per retry.

    Four attempts from a 15 s base give about 15 s, 45 s, 2 min and 5 min.
    """
    if attempts <= 1:
        return []
    pick = rng or random
    out = []
    for step in range(attempts - 1):
        wait = base * (3 ** step)
        jitter = wait * 0.2
        out.append(round(max(0.5, wait + pick.uniform(-jitter, jitter)), 1))
    return out


def wait(seconds: float, *, check: Callable[[], None] | None = None,
         deadline: float | None = None, sleep: Callable[[float], None] | None = None) -> bool:
    """Sleep `seconds`, letting `check` (a run's stop flag) and `deadline` cut it short.

    Returns False when the sleep was cut short by the deadline — the caller decides what that means.
    Raises whatever `check` raises (a stop request) instead of swallowing it.
    """
    end = time.monotonic() + max(0.0, seconds)
    while True:
        left = end - time.monotonic()
        if left <= 0:
            return True
        if deadline is not None and time.monotonic() >= deadline:
            return False
        if check is not None:
            check()
        (sleep or time.sleep)(min(SLICE_SECONDS, left))


def streak(db: Session, integration_id: str) -> int:
    """Consecutive `skipped_busy` runs of this integration, newest first.

    A `stopped` run is passed over: an operator stopping a run says nothing about the origin, so it
    neither extends nor resets the count.
    """
    rows = db.scalars(
        select(IntegrationRun.status)
        .where(IntegrationRun.integration_id == integration_id)
        .order_by(IntegrationRun.id.desc())
        .limit(MAX_STREAK)
    ).all()
    count = 0
    for status in rows:
        if status == "stopped":
            continue
        if status != "skipped_busy":
            break
        count += 1
    return count


def _notification_sent(db: Session, integration_id: str, since: datetime | None) -> bool:
    """Whether this streak was already announced: one `integration_busy` event belongs to it."""
    stmt = select(AuditEvent.id).where(
        AuditEvent.kind == "integration_busy",
        AuditEvent.detail["integration"].astext == integration_id,
    )
    if since is not None:
        stmt = stmt.where(AuditEvent.occurred_at >= since)
    return db.scalar(stmt.limit(1)) is not None


def notify_if_due(db: Session, run: IntegrationRun, integration_id: str) -> bool:
    """One announcement per streak: True when this call made it.

    The announcement is the `integration_busy` event, which is always written; the bot message is a
    best-effort delivery whose outcome is recorded in the event's `notified`.

    Never raises: a notification is a courtesy and must not turn a busier hour into a failed run.
    """
    try:
        count = streak(db, integration_id)
        if count < NOTIFY_AT:
            return False
        first = db.scalar(
            select(IntegrationRun.started_at)
            .where(IntegrationRun.integration_id == integration_id,
                   IntegrationRun.status == "skipped_busy")
            .order_by(IntegrationRun.id.desc())
            .offset(count - 1)
        )
        if _notification_sent(db, integration_id, first):
            return False
        told = _send(db, integration_id, count, run)
        audit.record(db, "integration_busy", detail={
            "integration": integration_id,
            "streak": count,
            "attempts": int((run.busy or {}).get("attempts") or 0),
            "sqlstate": (run.busy or {}).get("sqlstate"),
            "notified": told,
        })
        db.commit()
        return True
    except Exception:       # never fail a run because the message failed
        log.warning("integration %s: the busy notification failed", integration_id, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        return False


def _send(db: Session, integration_id: str, count: int, run: IntegrationRun) -> bool:
    """The bot message, when the installation has one enabled and an operator linked it."""
    settings = db.get(TelegramSettings, 1)
    if settings is None or not settings.enabled:
        return False
    token = telegram.token_of(settings)
    if not token:
        return False
    chats = db.scalars(
        select(TelegramLink.telegram_id)
        .join(AppUser, AppUser.id == TelegramLink.user_id)
        .where(AppUser.role == "admin", AppUser.is_active.is_(True))
    ).all()
    if not chats:
        return False
    text = (
        f"BizView: «{integration_id}» no se pudo ejecutar {count} veces seguidas porque la fuente "
        f"no admite más conexiones ahora. Los tableros siguen mostrando los últimos datos.\n"
        f"Qué hacer: Ayuda → La fuente no admite más conexiones."
    )
    client = telegram.client_factory(token)
    sent = False
    for chat_id in chats:
        try:
            client.send_message(chat_id, text)
            sent = True
        except Exception:
            log.warning("busy notification to chat %s failed", chat_id, exc_info=True)
    return sent


def hint(db: Session, integration_id: str, *, tz: str | None = None,
         now: datetime | None = None) -> dict:
    """`{busy_today, quiet_hour}`: how busy the origin was for this integration, and when it is not.

    The quietest hour is derived from the runs that were refused — the only congestion signal the
    product observes. It is offered only with at least three busy runs today and at least two hours
    in the record: one busy hour cannot rank the rest.
    """
    zone = ZoneInfo(tz) if tz else UTC
    current = now or datetime.now(UTC)
    local_now = current.astimezone(zone)
    since = current - timedelta(days=HINT_DAYS)
    rows = db.execute(
        select(IntegrationRun.started_at, IntegrationRun.status)
        .where(IntegrationRun.integration_id == integration_id,
               IntegrationRun.started_at >= since)).all()
    busy_by_hour: dict[int, int] = {}
    ran_by_hour: dict[int, int] = {}
    busy_today = 0
    for started, status in rows:
        local = started.astimezone(zone)
        ran_by_hour[local.hour] = ran_by_hour.get(local.hour, 0) + 1
        if status == "skipped_busy":
            busy_by_hour[local.hour] = busy_by_hour.get(local.hour, 0) + 1
            if local.date() == local_now.date():
                busy_today += 1
    quiet = None
    # Only the hours the integration actually ran can be ranked: an hour nobody ever tried is not
    # "quiet", it is unknown, and suggesting it would be a guess dressed as data.
    if busy_today >= 3 and len(ran_by_hour) >= 2:
        quiet = min(ran_by_hour, key=lambda hour: (busy_by_hour.get(hour, 0), hour))
    return {"busy_today": busy_today, "quiet_hour": quiet}
