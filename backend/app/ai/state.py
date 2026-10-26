"""The installation's AI status: last success, last failure, and whether to refuse a run (035).

One row (`ai_status`), written in its own short session so a failed turn — whose transaction is
rolled back — still records why it failed. Nothing here ever stores a key, a token or a message
body: only the code, a redacted ≤300-char provider line, the model and two timestamps.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.ai.errors import MAX_DETAIL, blocking
from app.db import get_sessionmaker

log = logging.getLogger("app.ai")


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _row(db, create: bool):
    from app.models import AIStatus

    row = db.get(AIStatus, 1)
    if row is None and create:
        row = AIStatus(id=1)
        db.add(row)
    return row


def read() -> dict[str, Any]:
    """The stored outcome, with nulls when there is none yet.

    A lost row, a missing table or a dead database answers nulls: health must never fail because
    the AI status could not be read.
    """
    empty = {"last_ok_at": None, "last_error_code": None, "last_error_at": None,
             "last_error_detail": None, "last_model": None}
    try:
        with get_sessionmaker()() as db:
            row = _row(db, create=False)
            if row is None:
                return empty
            return {"last_ok_at": _iso(row.last_ok_at), "last_error_code": row.last_error_code,
                    "last_error_at": _iso(row.last_error_at),
                    "last_error_detail": row.last_error_detail,
                    "last_model": row.last_model}
    except Exception as e:                       # migration not run, database gone, ...
        log.warning("ai status unreadable: %s", type(e).__name__)
        return empty


def record_ok(model: str | None) -> None:
    """A provider call worked: clear the error so refusals and the pill go back to healthy."""
    try:
        with get_sessionmaker()() as db:
            row = _row(db, create=True)
            row.last_ok_at = datetime.now(UTC)
            row.last_model = model or None
            row.last_error_code = None
            row.last_error_at = None
            row.last_error_detail = None
            db.commit()
    except Exception as e:
        log.warning("ai status not recorded (ok): %s", type(e).__name__)


def record_error(code: str, detail: str | None = None, model: str | None = None) -> None:
    """A provider call failed: keep the reason, without touching the last success."""
    try:
        with get_sessionmaker()() as db:
            row = _row(db, create=True)
            row.last_error_code = code
            row.last_error_at = datetime.now(UTC)
            row.last_error_detail = detail[:MAX_DETAIL] if detail else None
            row.last_model = model or row.last_model
            db.commit()
    except Exception as e:
        log.warning("ai status not recorded (error): %s", type(e).__name__)


def blocked_reason(db=None) -> str | None:
    """The code that makes every run pointless right now, or None.

    Blocking means: the last failure is one only the super user can fix (`no_credit`, `bad_key`,
    `model_not_found`) and it is newer than the last success — an old failure that a later call
    cleared is not a reason to refuse anything.
    """
    state = read()
    code = state["last_error_code"]
    if not blocking(code):
        return None
    if state["last_error_at"] and state["last_ok_at"] \
            and state["last_ok_at"] >= state["last_error_at"]:
        return None
    return code


def healthy() -> bool:
    state = read()
    return not state["last_error_code"] or (
        bool(state["last_ok_at"]) and state["last_ok_at"] >= (state["last_error_at"] or ""))
