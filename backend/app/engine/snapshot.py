"""Nightly figures for a direct report (feature 048, FR-009).

A report may set `materialize: daily` when its source is a warehouse that is expensive to query.
Once a day the worker runs the report's own query once and stores **the payload the engine already
produces** — the same JSON a tile receives — so every viewer reads that instead of the source. It is
not an ETL: no rows are stored, no `ds_` schema is created, and the typing and retention are the
ones the cache has always had.

The dashboard says how old the figures are; a day without a run leaves yesterday's in place rather
than blanking the page.
"""
import hashlib
import json
import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

log = logging.getLogger("app.snapshot")

KEEP_DAYS = 30
MATERIALIZE_DAILY = "daily"


def fingerprint(selection: dict, filters: dict) -> str:
    """The parameters the figures answer for: a snapshot covers one set, never «whatever»."""
    blob = json.dumps({"selection": selection, "filters": filters}, sort_keys=True,
                      ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def store(db: Session, report_id: str, *, selection: dict, filters: dict, payload: dict,
          source: str, day: date | None = None) -> None:
    """Keep today's figures, replacing today's row if the worker ran twice."""
    from app.models import DirectSnapshot

    key = fingerprint(selection, filters)
    day = day or datetime.now(UTC).date()
    row = db.scalar(select(DirectSnapshot).where(
        DirectSnapshot.report_id == report_id, DirectSnapshot.day == day,
        DirectSnapshot.selection_hash == key))
    if row is None:
        db.add(DirectSnapshot(report_id=report_id, day=day, selection_hash=key,
                              selection={"selection": selection, "filters": filters},
                              payload=payload, source=source))
    else:
        row.payload, row.source = payload, source
    db.flush()


def latest(db: Session, report_id: str, *, selection: dict, filters: dict) -> dict | None:
    """The newest stored figures for these parameters, or None when there are none yet."""
    from app.models import DirectSnapshot

    row = db.scalar(select(DirectSnapshot).where(
        DirectSnapshot.report_id == report_id,
        DirectSnapshot.selection_hash == fingerprint(selection, filters))
        .order_by(DirectSnapshot.day.desc()).limit(1))
    return None if row is None else {"payload": row.payload, "day": row.day.isoformat()}


def prune(db: Session) -> int:
    """Drop snapshots older than the window: figures are cheap to regenerate, not to keep."""
    from app.models import DirectSnapshot

    cutoff = datetime.now(UTC).date() - timedelta(days=KEEP_DAYS)
    result = db.execute(delete(DirectSnapshot).where(DirectSnapshot.day < cutoff))
    return result.rowcount or 0


def labelled(payload: dict, day: str) -> dict:
    """The stored payload with the notice that says how old it is."""
    freshness = dict(payload.get("freshness") or {})
    freshness.update({"mode": "snapshot", "snapshot_day": day})
    return {**payload, "freshness": freshness}


def is_daily(definition: dict) -> bool:
    return isinstance(definition, dict) and definition.get("materialize") == MATERIALIZE_DAILY


def snapshot_all(sessionmaker, app) -> int:
    """Run every `materialize: daily` direct report of the active version, once (worker job)."""
    from app.api import reports as reports_api
    from app.engine import report as engine
    from app.workspace import service as workspace

    stored = 0
    with sessionmaker() as db:
        version = workspace.active(db)
        if version is None:
            return 0
        for report_id, item in (version.artifacts.get("reports") or {}).items():
            definition = item.get("definition") or {}
            if not is_daily(definition) or not isinstance(definition.get("direct"), dict):
                continue
            try:
                ctx = engine.cached_context(version, report_id)
                sel, filters = engine.selection(ctx, [], datetime.now(UTC).date())
                payload = reports_api._data(db, ctx, [])
                store(db, report_id, selection=sel.to_json(), filters=filters,
                      payload={k: v for k, v in payload.items() if k != "etag"},
                      source=str(definition["direct"].get("source", "")))
                stored += 1
            except Exception:
                # One warehouse having a bad night must not stop the others, and yesterday's
                # figures stay where they are.
                log.exception("snapshot of %s failed", report_id)
        prune(db)
        db.commit()
    if stored:
        log.info("stored %d daily snapshot(s)", stored)
    return stored


def counts(db: Session) -> dict:
    """How many snapshots there are and how old the newest is (for the operator pages)."""
    from app.models import DirectSnapshot

    total = db.scalar(select(func.count()).select_from(DirectSnapshot)) or 0
    newest = db.scalar(select(func.max(DirectSnapshot.day)))
    return {"snapshots": total, "newest_day": newest.isoformat() if newest else None}
