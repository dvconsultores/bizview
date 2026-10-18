"""Attachments of the chat (feature 024): sniff, store, read, delete, sweep.

An image attached to a message is a *design brief*: it is stored outside the project folder,
never inside anything a customer exports, and its bytes only leave the installation when a
message carrying it is sent to the configured AI provider (after the one-time notice).
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import ApiError
from app.i18n import M
from app.models import AssistantAttachment

log = logging.getLogger("app")

PENDING_HOURS = 24

# Magic bytes decide the media type: a declared type or a file name is not evidence.
MAGIC: tuple[tuple[bytes, str, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"GIF87a", "image/gif", "gif"),
    (b"GIF89a", "image/gif", "gif"),
)
WEBP_PREFIX = b"RIFF"
WEBP_MARKER = b"WEBP"


@dataclass(frozen=True)
class Stored:
    """What the API returns and the service binds to a message."""

    id: int
    media_type: str
    byte_size: int
    sha256: str
    original_name: str | None


def sniff(data: bytes) -> tuple[str, str] | None:
    """`(media_type, extension)` from the first bytes, or None when it is not an image we take."""
    for magic, media_type, extension in MAGIC:
        if data.startswith(magic):
            return media_type, extension
    if data[:4] == WEBP_PREFIX and data[8:12] == WEBP_MARKER:
        return "image/webp", "webp"
    return None


def _path(session_id: int, digest: str, extension: str) -> Path:
    return Path(get_settings().attachments_dir) / str(session_id) / f"{digest}.{extension}"


def check(data: bytes) -> tuple[str, str]:
    """Validate an upload: it must be an image we accepted and within the size limit."""
    limit = get_settings().attachments_max_mb * 1024 * 1024
    if len(data) > limit:
        raise ApiError(413, "attachment_too_large",
                       M("attachments.too_large", max=get_settings().attachments_max_mb))
    sniffed = sniff(data)
    if sniffed is None:
        raise ApiError(415, "attachment_type", M("attachments.type"))
    return sniffed


def store(db: Session, session_id: int, data: bytes, original_name: str | None,
          actor_id: int | None) -> AssistantAttachment:
    """Write the file and its row (pending: no message yet). Identical bytes are stored once."""
    media_type, extension = check(data)
    _check_count(db, session_id)
    digest = hashlib.sha256(data).hexdigest()
    path = _path(session_id, digest, extension)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(data)
    row = AssistantAttachment(
        session_id=session_id, message_id=None, media_type=media_type, byte_size=len(data),
        sha256=digest, original_name=(original_name or None), created_by=actor_id)
    db.add(row)
    db.flush()
    return row


def _check_count(db: Session, session_id: int) -> None:
    """At most `ATTACHMENTS_MAX_PER_MESSAGE` images waiting to be sent in one conversation."""
    limit = get_settings().attachments_max_per_message
    pending = db.scalar(
        select(func.count(AssistantAttachment.id))
        .where(AssistantAttachment.session_id == session_id,
               AssistantAttachment.message_id.is_(None))) or 0
    if pending >= limit:
        raise ApiError(409, "attachment_limit", M("attachments.limit", max=limit))


def load(db: Session, attachment_id: int) -> bytes:
    row = db.get(AssistantAttachment, attachment_id)
    if row is None:
        raise ApiError(404, "attachment_not_found", M("attachments.not_found"))
    path = _path(row.session_id, row.sha256, _extension(row.media_type))
    try:
        return path.read_bytes()
    except OSError:
        log.warning("attachment %s: file missing", attachment_id)
        raise ApiError(404, "attachment_not_found", M("attachments.not_found")) from None


def remove(db: Session, row: AssistantAttachment) -> None:
    """Drop the row and its file; identical bytes are shared, so only the last row unlinks."""
    path = _path(row.session_id, row.sha256, _extension(row.media_type))
    session_id, digest = row.session_id, row.sha256
    db.delete(row)
    db.flush()
    if path.exists() and db.scalar(
            select(AssistantAttachment.id)
            .where(AssistantAttachment.session_id == session_id,
                   AssistantAttachment.sha256 == digest)) is None:
        try:
            path.unlink(missing_ok=True)
            path.parent.rmdir()
        except OSError:                       # another attachment still lives in the folder
            pass


def image_part(row: AssistantAttachment) -> Any:
    """The provider-neutral image part of a stored row (bytes read lazily, once)."""
    from app.ai import ImagePart

    path = _path(row.session_id, row.sha256, _extension(row.media_type))
    try:
        return ImagePart(media_type=row.media_type, data=path.read_bytes())
    except OSError:
        log.warning("attachment %s: file missing", row.id)
        return None


def sweep_pending(db: Session, *, now: datetime | None = None) -> int:
    """Delete uploads that never became a message (older than `PENDING_HOURS`)."""
    now = now or datetime.now(UTC)
    old = db.scalars(
        select(AssistantAttachment)
        .where(AssistantAttachment.message_id.is_(None),
               AssistantAttachment.created_at < now - timedelta(hours=PENDING_HOURS))).all()
    for row in old:
        remove(db, row)
    return len(old)


def forget_session(db: Session, session_id: int) -> None:
    """Remove every attachment of a conversation (rows via cascade, files here)."""
    rows = db.scalars(select(AssistantAttachment)
                      .where(AssistantAttachment.session_id == session_id)).all()
    for row in rows:
        remove(db, row)


def _extension(media_type: str) -> str:
    return {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp",
            "image/gif": "gif"}.get(media_type, "bin")
