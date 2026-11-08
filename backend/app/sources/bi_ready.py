"""A source declared BI-ready (feature 048): its scope, its limits, and the proof it is read-only.

Principle II allows a direct read by exception; this module is what turns the exception into a
declared contract. The declaration lives on the source row (`data_source.bi_ready`) and answers one
question for everybody else:

    may this source be read, and may this object be read from it?

`permitted()` is the single answer — the validator and the engine both call it, because a rule
implemented twice drifts. The deny-list is never overridable: a declaration can narrow what the
product already refuses, never widen it.

`prove_read_only()` is empirical on purpose. Reading `pg_roles` says nothing about ownership or
membership; attempting a write that must fail, inside a transaction that is rolled back, says
exactly what the customer needs to know.
"""
import logging
from datetime import UTC, datetime
from typing import Any

from app.i18n import M

log = logging.getLogger("app.sources.bi_ready")

#: The declaration's keys, and nothing else: an unknown key is a typo that does nothing.
KEYS = ("enabled", "schemas", "objects", "timeout_s", "cache_ttl_s", "max_rows", "max_parallel",
        "timezone", "verified_at", "verified_ok")
#: The limits a declaration may set, and the installation defaults it inherits (feature 019).
BOUNDS = {
    "timeout_s": (1, 300),
    "cache_ttl_s": (0, 86_400),
    "max_rows": (1, 1_000_000),
    "max_parallel": (1, 20),
}
DEFAULTS = {"timeout_s": 20, "cache_ttl_s": 300, "max_rows": 50_000, "max_parallel": 2,
            "timezone": "UTC"}

#: Schemas a declaration may never name, whatever it says.
RESERVED_SCHEMAS = ("pg_catalog", "information_schema", "pg_toast", "app_test_", "preview_")


class DeclarationError(ValueError):
    """A declaration that cannot be stored; `field` names the part the caller must fix."""

    def __init__(self, field: str, message: M | str) -> None:
        self.field, self.message = field, message
        super().__init__(field)


def declaration(src: Any) -> dict:
    """The declaration of a source row, or `{}` when it has none."""
    data = getattr(src, "bi_ready", None)
    return data if isinstance(data, dict) else {}


def enabled(src: Any) -> bool:
    """Whether reports may read this source directly.

    A source with a declaration answers for itself; a 019 source without one still answers from
    `direct_reports`, which is what the migration backfilled and what an older build wrote."""
    data = declaration(src)
    if data:
        return bool(data.get("enabled"))
    return bool(getattr(src, "direct_reports", False))


def limits(src: Any, app: Any = None) -> dict:
    """The numbers the engine runs with: the declaration's, else the installation's, else ours."""
    data = declaration(src)
    out = dict(DEFAULTS)
    for key, (low, high) in BOUNDS.items():
        value = data.get(key)
        if isinstance(value, int) and low <= value <= high:
            out[key] = value
    if not data:                       # 019 source: the installation-wide knobs decide
        out["max_parallel"] = int(getattr(app, "direct_report_concurrency", out["max_parallel"]))
    timezone = data.get("timezone")
    if isinstance(timezone, str) and timezone:
        out["timezone"] = timezone
    elif app is not None:
        out["timezone"] = getattr(app, "timezone", None) or out["timezone"]
    return out


def reserved(schema: str) -> bool:
    lowered = (schema or "").strip().lower()
    return any(lowered == name or lowered.startswith(name) for name in RESERVED_SCHEMAS)


def validate(data: dict) -> dict:
    """Normalise and check a declaration; raises `DeclarationError` naming the field.

    An empty scope is legal and means nothing is readable — never everything. That asymmetry is on
    purpose: a declaration that forgot its scope must fail closed.
    """
    if not isinstance(data, dict):
        raise DeclarationError("bi_ready", M("sources.bi_ready_object"))
    unknown = sorted(set(data) - set(KEYS))
    if unknown:
        raise DeclarationError("bi_ready", M("sources.bi_ready_unknown", keys=", ".join(unknown)))
    schemas = data.get("schemas") or []
    objects = data.get("objects") or []
    if not isinstance(schemas, list) or not all(isinstance(s, str) and s.strip() for s in schemas):
        raise DeclarationError("bi_ready.schemas", M("sources.bi_ready_schemas"))
    if not isinstance(objects, list) or not all(isinstance(o, str) and o.strip() for o in objects):
        raise DeclarationError("bi_ready.objects", M("sources.bi_ready_objects"))
    bad = [s for s in schemas if reserved(s)]
    if bad:
        raise DeclarationError("bi_ready.schemas",
                               M("sources.bi_ready_reserved", names=", ".join(sorted(bad))))
    for name in objects:
        if "." not in name:
            raise DeclarationError("bi_ready.objects", M("sources.bi_ready_object_name", name=name))
        if reserved(name.split(".", 1)[0]):
            raise DeclarationError("bi_ready.objects",
                                   M("sources.bi_ready_reserved", names=name))
    out: dict[str, Any] = {"enabled": bool(data.get("enabled", False)),
                           "schemas": sorted({s.strip() for s in schemas}),
                           "objects": sorted({o.strip() for o in objects})}
    for key, (low, high) in BOUNDS.items():
        value = data.get(key)
        if value is None:
            continue
        if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
            raise DeclarationError(f"bi_ready.{key}",
                                   M("sources.bi_ready_bound", field=key, low=low, high=high))
        out[key] = value
    timezone = data.get("timezone")
    if timezone is not None:
        if not isinstance(timezone, str) or not timezone.strip():
            raise DeclarationError("bi_ready.timezone", M("sources.bi_ready_timezone"))
        out["timezone"] = timezone.strip()
    for key in ("verified_at", "verified_ok"):
        if key in data:
            out[key] = data[key]
    return out


def permitted(src: Any, schema: str, obj: str | None = None) -> bool:
    """Whether `schema.object` may be read from this source.

    A source without a declaration answers from the 019 switch, whose reach is the deny-list alone —
    exactly what every existing direct report relies on. A declared source answers from its scope,
    and the deny-list still applies on top.
    """
    if not enabled(src):
        return False
    if reserved(schema):
        return False
    data = declaration(src)
    if not data:
        return True                     # 019 source: the caller's deny-list is the only scope
    schemas = {s.lower() for s in data.get("schemas") or ()}
    if not schemas or schema.strip().lower() not in schemas:
        return False
    if obj is None:
        return True
    objects = {o.lower() for o in data.get("objects") or ()}
    return not objects or f"{schema}.{obj}".lower() in objects


def now() -> str:
    return datetime.now(UTC).isoformat()


def prove_read_only(src: Any, describe: Any, app: Any) -> tuple[bool, str]:
    """Whether this source's credential refuses to write, and why not.

    `describe` reads the source (it owns the connection and the crypto); this function decides what
    to attempt and what the answer means. A credential that can create a temporary table can write,
    whatever its grants look like on paper.
    """
    try:
        report = describe(src, write_probe=True)
    except Exception as exc:                # unreachable, refused, misconfigured
        log.info("read-only proof failed for source %s: %s", getattr(src, "name", "?"), exc)
        return False, "unreachable"
    wrote = report.get("write_allowed")
    if wrote is None:
        return False, "unknown"
    return (not wrote), ("writable" if wrote else "read_only")


def health_summary(rows: list[dict]) -> dict:
    """The 24-hour picture the source page shows, from the rows the engine already logged."""
    durations = sorted(row["duration_ms"] for row in rows if isinstance(row["duration_ms"], int))
    total = len(rows)
    failures = sum(1 for row in rows if row["outcome"] != "ok")
    served = sum(1 for row in rows if row.get("stale_served"))
    return {
        "runs": total,
        "failures": failures,
        "p50_ms": durations[len(durations) // 2] if durations else None,
        "p95_ms": durations[min(len(durations) - 1, int(len(durations) * 0.95))] if durations
        else None,
        "served_from_cache": served,
        "cache_share": (served / total) if total else None,
    }


def recheck_all(sessionmaker: Any, app: Any) -> int:
    """Re-prove every declared source's credential, once a day (FR-002).

    A credential that stops being read-only, or a source that stops answering, is recorded and
    audited with `source_bi_ready_unverified` — the audit page is where an administrator sees it,
    and the source page shows the badge and the date. Sources are not disabled automatically: a
    warehouse having a bad afternoon must not take every dashboard down with it.
    """
    from app.services import audit

    changed = 0
    with sessionmaker() as db:
        rows = db.scalars(select_source_rows()).all()
        for src in rows:
            data = declaration(src)
            if not data or not data.get("enabled"):
                continue

            try:
                probe = service_ok(src, app)
            except Exception:
                log.exception("BI-ready proof crashed for %s", getattr(src, "name", "?"))
                continue
            ok, reason = probe
            was = data.get("verified_ok")
            src.bi_ready = {**data, "verified_at": now(), "verified_ok": ok}
            if was != ok:
                changed += 1
                audit.record(db, "source_bi_ready_verified" if ok
                             else "source_bi_ready_unverified",
                             detail={"source": src.name, "reason": reason})
        db.commit()
    return changed


def select_source_rows():
    from sqlalchemy import select

    from app.models import DataSource

    return select(DataSource).where(DataSource.kind == "postgresql")


def service_ok(src: Any, app: Any) -> tuple[bool, str]:
    """The proof, for a saved source: its stored settings and decrypted secret."""
    from app.sources import describe as describer
    from app.sources import service

    def describe(source: Any, write_probe: bool = False) -> dict:
        return describer.describe("postgresql", source.settings, service.secrets_of(source), app,
                                  write_probe=write_probe, name=source.name)

    return prove_read_only(src, describe, app)
