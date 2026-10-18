"""Audit trail (FR-022). Details never carry secrets."""
from datetime import timedelta

from sqlalchemy import delete, func
from sqlalchemy.orm import Session

from app.models import AUDIT_KINDS, AuditEvent

_SECRET_MARKERS = ("password", "hash", "token", "sid", "secret")


def record(db: Session, kind: str, *, actor_id: int | None = None, target_id: int | None = None,
           ip: str | None = None, detail: dict | None = None) -> None:
    assert kind in AUDIT_KINDS, kind
    detail = detail or {}
    leaked = [k for k in detail if any(m in k.lower() for m in _SECRET_MARKERS)]
    assert not leaked, f"secret-like keys in audit detail: {leaked}"
    db.add(AuditEvent(kind=kind, actor_id=actor_id, target_id=target_id, ip=ip, detail=detail))


def purge_older_than(db: Session, days: int = 365) -> int:
    res = db.execute(delete(AuditEvent).where(
        AuditEvent.occurred_at < func.now() - timedelta(days=days)))
    return res.rowcount or 0
