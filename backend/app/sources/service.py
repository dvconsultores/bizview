"""Data-source catalogue: CRUD, encrypted secrets, tests, legacy import (feature 004)."""
import logging
from datetime import UTC, datetime
from urllib.parse import parse_qs, unquote, urlsplit

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import ApiError, not_found, validation
from app.i18n import M, t
from app.models import AppUser, DataSource, SecurityState
from app.security import crypto
from app.security.crypto import source_aad
from app.services import audit
from app.sources import schemas
from app.sources.connectors import TestResult, test_source

log = logging.getLogger("app.sources")


def secrets_of(src: DataSource) -> dict:
    if src.secrets_ct is None:
        return {}
    return crypto.get_keyring().decrypt_json(src.secrets_ct, src.secrets_key_id,
                                             source_aad(src.id))


def _store_secrets(db: Session, src: DataSource, secrets: dict) -> None:
    if secrets:
        keyring = crypto.get_keyring()
        src.secrets_ct, src.secrets_key_id = keyring.encrypt_json(secrets, source_aad(src.id))
        crypto.ensure_key_check(db, keyring)
    else:
        src.secrets_ct = src.secrets_key_id = None
    src.secret_fields = sorted(secrets)


def to_json(src: DataSource) -> dict:
    last = None
    if src.last_test_at:
        last = {"at": src.last_test_at, "ok": src.last_test_ok, **(src.last_test or {})}
    return {"id": src.id, "name": src.name, "kind": src.kind, "description": src.description,
            "enabled": src.enabled, "settings": src.settings, "secret_fields": src.secret_fields,
            "imported": src.imported, "last_test": last, "created_at": src.created_at,
            "updated_at": src.updated_at, "direct_reports": bool(src.direct_reports)}


def get(db: Session, source_id: int) -> DataSource:
    src = db.get(DataSource, source_id)
    if src is None:
        raise not_found(M("sources.not_found"))
    return src


def by_name(db: Session, name: str) -> DataSource | None:
    return db.scalar(select(DataSource).where(func.lower(DataSource.name) == name.strip().lower()))


def list_all(db: Session) -> list[DataSource]:
    return list(db.scalars(select(DataSource).order_by(func.lower(DataSource.name))))


def _check_name(db: Session, name: str, exclude_id: int | None = None) -> str:
    name = (name or "").strip()
    if not 1 <= len(name) <= 80:
        raise validation({"name": "invalid"}, t("sources.name_invalid"))
    if name.lower() == "bi":
        raise validation({"name": "reserved"}, t("sources.name_reserved"))
    other = by_name(db, name)
    if other is not None and other.id != exclude_id:
        raise ApiError(409, "conflict", t("sources.name_conflict"))
    return name


def _validated(kind: str, settings_in: dict, secrets_in: dict, existing: dict,
               app: Settings) -> schemas.Result:
    result = schemas.validate(kind, settings_in or {}, secrets_in or {}, existing, app)
    if result.errors:
        raise validation(result.errors, t("sources.config_invalid"))
    return result


def _invalidate_direct() -> None:
    try:
        from app.engine import direct
        direct.clear_cache()
    except Exception as e:  # pragma: no cover - defensive
        log.warning("direct cache not cleared (%s)", type(e).__name__)


def create(db: Session, actor: AppUser, data: dict, app: Settings, ip: str | None) -> DataSource:
    name = _check_name(db, data.get("name", ""))
    kind = data.get("kind")
    direct_reports = bool(data.get("direct_reports"))
    if direct_reports and kind != "postgresql":
        raise validation({"direct_reports": "not_allowed"},
                         M("sources.direct_postgresql_only"))
    result = _validated(kind, data.get("settings"), data.get("secrets"), {}, app)
    src = DataSource(name=name, kind=kind, description=(data.get("description") or "")[:300],
                     enabled=bool(data.get("enabled", True)), settings=result.settings,
                     secret_fields=[], created_by=actor.id, updated_by=actor.id,
                     direct_reports=direct_reports)
    db.add(src)
    db.flush()  # id first: the ciphertext is bound to it
    _store_secrets(db, src, result.secrets)
    audit.record(db, "source_created", actor_id=actor.id, ip=ip,
                 detail={"source": name, "kind": kind, "credential_fields": src.secret_fields})
    if direct_reports:
        audit.record(db, "source_direct_reports_changed", actor_id=actor.id, ip=ip,
                     detail={"source": name, "before": False, "value": True})
    _invalidate_direct()
    return src


def update(db: Session, actor: AppUser, src: DataSource, data: dict, app: Settings,
           ip: str | None) -> DataSource:
    if "kind" in data and data["kind"] != src.kind:
        raise validation({"kind": "immutable"}, M("sources.kind_immutable"))
    if "direct_reports" in data and data["direct_reports"] is not None \
            and src.kind != "postgresql" and bool(data["direct_reports"]):
        raise validation({"direct_reports": "not_allowed"},
                         M("sources.direct_postgresql_only"))
    changes: dict = {}
    if "name" in data and data["name"] != src.name:
        src.name = _check_name(db, data["name"], exclude_id=src.id)
        changes["name"] = True
    if "direct_reports" in data and data["direct_reports"] is not None:
        new_direct = bool(data["direct_reports"])
        old_direct = bool(src.direct_reports)
        if new_direct != old_direct:
            src.direct_reports = new_direct
            audit.record(db, "source_direct_reports_changed", actor_id=actor.id, ip=ip,
                         detail={"source": src.name, "before": old_direct, "value": new_direct})
    elif src.kind != "postgresql" and src.direct_reports:
        src.direct_reports = False
    if "description" in data:
        src.description = (data["description"] or "")[:300]
    if "settings" in data or "secrets" in data:
        existing = secrets_of(src)
        result = _validated(src.kind, data.get("settings", src.settings), data.get("secrets"),
                            existing, app)
        changed = sorted(k for k in set(result.settings) | set(src.settings)
                         if result.settings.get(k) != src.settings.get(k))
        secrets_changed = sorted(k for k in set(result.secrets) | set(existing)
                                 if result.secrets.get(k) != existing.get(k))
        src.settings = result.settings
        _store_secrets(db, src, result.secrets)
        if changed:
            changes["settings"] = changed
        if secrets_changed:
            changes["credentials"] = secrets_changed
        src.imported = False
    if "enabled" in data and bool(data["enabled"]) != src.enabled:
        src.enabled = bool(data["enabled"])
        audit.record(db, "source_enabled" if src.enabled else "source_disabled",
                     actor_id=actor.id, ip=ip, detail={"source": src.name})
    src.updated_by = actor.id
    if changes:
        audit.record(db, "source_updated", actor_id=actor.id, ip=ip,
                     detail={"source": src.name, "changed": changes})
    db.flush()
    _invalidate_direct()
    return src


def delete(db: Session, actor: AppUser, src: DataSource, ip: str | None) -> None:
    # Feature 005 adds "in use by an applied integration" → 409 in_use.
    audit.record(db, "source_deleted", actor_id=actor.id, ip=ip,
                 detail={"source": src.name, "kind": src.kind})
    db.delete(src)
    _invalidate_direct()


def run_test(db: Session, actor: AppUser, src: DataSource, app: Settings,
             ip: str | None) -> TestResult:
    result = test_source(src.kind, src.settings, secrets_of(src), app)
    src.last_test_at = datetime.now(UTC)
    src.last_test_ok = result.ok
    src.last_test = {k: v for k, v in result.to_json().items() if k != "ok"}
    audit.record(db, "source_tested", actor_id=actor.id, ip=ip,
                 detail={"source": src.name, "ok": result.ok, "code": result.code})
    return result


def test_draft(data: dict, app: Settings, existing: DataSource | None = None) -> TestResult:
    kind = existing.kind if existing else data.get("kind")
    base = secrets_of(existing) if existing else {}
    result = _validated(kind, data.get("settings", existing.settings if existing else {}),
                        data.get("secrets"), base, app)
    return test_source(kind, result.settings, result.secrets, app)


# --- legacy DATABASE_URL_ORIGIN (research R10) ----------------------------------------------

LEGACY_NAME = "Origen (importado)"


def import_legacy_origin(db: Session, app: Settings) -> str:
    url = app.database_url_origin
    if not url:
        return "none"
    if db.scalar(select(func.count()).select_from(DataSource)):
        log.warning("DATABASE_URL_ORIGIN is no longer used; data sources already exist. "
                    "Remove the variable from .env.")
        return "skipped"
    u = urlsplit(url)
    if u.scheme not in ("postgresql", "postgres") or not u.hostname or not u.path.strip("/"):
        log.warning("DATABASE_URL_ORIGIN is not a PostgreSQL URL; not imported")
        return "invalid"
    query = {k: v[0] for k, v in parse_qs(u.query).items()}
    sslmode = query.get("sslmode", "require")
    if sslmode not in ("require", "verify-full", "prefer", "disable"):
        sslmode = "require"
    if sslmode in ("prefer", "disable") and not app.http_allowed:
        sslmode = "require"
    settings = {"host": u.hostname, "port": u.port or 5432, "database": u.path.strip("/"),
                "username": unquote(u.username or ""), "sslmode": sslmode,
                "timeout_seconds": 15}
    secrets = {"password": unquote(u.password or "")}
    result = schemas.validate("postgresql", settings, secrets, {}, app, check_addresses=False)
    if result.errors:
        log.warning("DATABASE_URL_ORIGIN could not be imported: %s", sorted(result.errors))
        return "invalid"
    src = DataSource(name=LEGACY_NAME, kind="postgresql", settings=result.settings,
                     secret_fields=[], imported=True,
                     description=t("sources.imported_description"))
    db.add(src)
    db.flush()
    _store_secrets(db, src, result.secrets)
    state = db.get(SecurityState, 1)
    if state is not None:
        state.legacy_origin_notice = True
    audit.record(db, "source_imported", detail={"source": LEGACY_NAME, "kind": "postgresql"})
    log.warning("DATABASE_URL_ORIGIN imported as data source %r; remove it from .env",
                LEGACY_NAME)
    return "imported"
