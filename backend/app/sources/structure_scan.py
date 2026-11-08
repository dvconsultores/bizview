"""The scan of a source: everything the structure pass may look at, and nothing else (052).

Two rules hold this module together:

* it reads **structure** — describe output, response shapes, the OpenAPI document a source
  publishes, the catalogue's own foreign keys — and never a row value;
* what it does keep of a response is *format*, not data: the unit of a date field, and the values of
  a field only when the same short token repeats across records (an enum, which the pack template
  prints as `valores: draft, paid, cancelled`). A name, an address or an identifier repeats by
  accident at most, and the pattern keeps those out.

The scan is what the AI sees and what every name in the AI's answer is checked against.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime

from bizview_cli.structure import suggest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import DataSource, SourceSampleRequest
from app.sources import describe as describer
from app.sources import samples as sample_service
from app.sources.connectors import registry

#: Endpoints tried when a source may publish its own description. First one that answers wins.
OPENAPI_PATHS = ("openapi.json", "swagger.json", "v1/openapi.json")
#: The shape of a published document is read this deep and no deeper.
MAX_OPENAPI_PATHS = 200
#: A short token that repeats is an enum; anything else never leaves the source.
ENUM_TOKEN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,23}$")
MAX_ENUM_VALUES = 5
#: A field whose name says it is a date is asked for its format, never its value.
DATE_NAME = re.compile(r"(date|time|updated|created|at|fecha|hora)", re.I)


def scan(db: Session, source: DataSource, app: Settings, *, run_samples: bool = True) -> dict:
    """The source as the AI may see it: names, types, shapes and formats."""
    out: dict = {"source": source.name, "kind": source.kind,
                 "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                 "notes": source.notes or "",
                 "bi_ready": bool((source.bi_ready or {}).get("enabled")),
                 "truncated": False, "tables": [], "endpoints": [], "relations": [],
                 "operations": [], "openapi": None}
    secrets = _secrets(source)
    if registry.is_sql(source.kind):
        structure = describer.describe(source.kind, source.settings, secrets, app,
                                       date_ranges=True, name=source.name)
        out["tables"] = structure.get("tables") or []
        out["truncated"] = bool(structure.get("truncated"))
        out["relations"] = _foreign_key_relations(out["tables"])
        return out
    if source.kind == registry.SOAP:
        structure = describer.describe(source.kind, source.settings, secrets, app)
        out["operations"] = [
            {"service": service.get("name"), "port": port.get("name"), **operation}
            for service in structure.get("services") or []
            for port in service.get("ports") or []
            for operation in port.get("operations") or []]
        return out

    if registry.capabilities(source.kind).tables:      # Google Sheets: a worksheet is a table
        structure = describer.describe(source.kind, source.settings, secrets, app)
        out["tables"] = structure.get("tables") or []
        out["truncated"] = bool(structure.get("truncated"))
        return out

    settings, http_secrets = sample_service.rest_of(source, secrets)
    out["endpoints"] = _endpoints(db, source, settings, http_secrets, app,
                                  run_samples=run_samples)
    out["openapi"] = _openapi(settings, http_secrets, app)
    return out


def _secrets(source: DataSource) -> dict:
    from app.sources import service as source_service

    try:
        return source_service.secrets_of(source)
    except Exception:                      # no key, no cipher: the scan then has no credential
        return {}


def _foreign_key_relations(tables: list[dict]) -> list[dict]:
    """Relations the catalogue already states: no guessing needed when a foreign key exists."""
    known = {(str(t.get("schema")), str(t.get("name"))) for t in tables}
    out = []
    for table in tables:
        schema = str(table.get("schema"))
        owner = f"{schema}.{table.get('name')}"
        for fk in table.get("foreign_keys") or []:
            target = str(fk.get("references") or "")
            target_table = target.rsplit(".", 1)[0] if "." in target else target
            if (schema, target_table) in known or any(
                    (str(t.get("schema")), str(t.get("name"))) == (schema, target_table)
                    for t in tables):
                out.append({"from": f"{owner}.{fk.get('column')}", "to": target,
                            "kind": "many_to_one", "confidence": "high"})
    return out


def _endpoints(db: Session, source: DataSource, settings: dict, secrets: dict, app: Settings,
               *, run_samples: bool) -> list[dict]:
    """One entry per endpoint worth describing: the test path and every saved sample."""
    seen: dict[str, dict] = {}
    test_path = str(settings.get("test_path") or "").strip()
    candidates = []
    if test_path:
        candidates.append({"path": test_path.lstrip("/"), "params": {}, "name": None})
    saved = db.scalars(select(SourceSampleRequest)
                       .where(SourceSampleRequest.source_id == source.id)
                       .order_by(SourceSampleRequest.name)).all()
    for sample in saved:
        candidates.append({"path": sample.path, "params": sample.params or {},
                           "name": sample.name})
    for item in candidates:
        if item["path"] in seen:
            continue
        entry = {"path": item["path"], "params": item["params"], "name": item["name"],
                 "shape": None, "records": None, "formats": {}, "error": None}
        stored = next((s for s in saved if s.name == item["name"]), None) if item["name"] else None
        if stored is not None and stored.last_shape and not run_samples:
            entry["shape"] = stored.last_shape
            entry["records"] = (stored.last_suggestions or {}).get("records")
        else:
            try:
                _status, data = sample_service.get_json(settings, secrets, app, item["path"],
                                                        item["params"])
            except Exception as e:                     # one failing endpoint must not stop a scan
                entry["error"] = type(e).__name__
            else:
                entry["shape"] = describer.shape(data)
                entry["records"] = suggest(data)["records"]
                entry["formats"] = {**formats_of(_record_of(data)),
                                    **enums_of(_records_of(data))}
        seen[item["path"]] = entry
    return list(seen.values())


def _openapi(settings: dict, secrets: dict, app: Settings) -> dict | None:
    """Names and types of what the source says it publishes, when it publishes a description."""
    for path in OPENAPI_PATHS:
        try:
            _status, data = sample_service.get_json(settings, secrets, app, path, timeout=8)
        except Exception:
            continue
        if isinstance(data, dict) and isinstance(data.get("paths"), dict):
            return {"path": path, "paths": _openapi_paths(data), "tables": _openapi_tables(data)}
    return None


def _openapi_paths(spec: dict) -> list[dict]:
    out = []
    for path, item in list((spec.get("paths") or {}).items())[:MAX_OPENAPI_PATHS]:
        methods = [m.upper() for m in (item or {}) if m.lower() in ("get", "post")]
        out.append({"path": str(path)[:300], "methods": methods})
    return out


def _openapi_tables(spec: dict) -> list[dict]:
    """Parameters and definitions, reduced to names and types (never examples or defaults)."""
    out = []
    for name, schema in list((spec.get("components") or {}).get("schemas", {}).items())[:200]:
        props = (schema or {}).get("properties") or {}
        out.append({"name": str(name)[:200],
                    "fields": [{"name": str(field)[:200],
                                "type": _schema_type(definition)}
                               for field, definition in list(props.items())[:200]]})
    return out


def _schema_type(definition) -> str:
    if not isinstance(definition, dict):
        return "unknown"
    if definition.get("type") == "array":
        return f"{_schema_type(definition.get('items') or {})}[]"
    return str(definition.get("format") or definition.get("type") or "unknown")[:60]


def _record_of(data):
    """The first object of a response: only its *format* is read, and only by `formats_of`."""
    node = data
    for _depth in range(8):
        if isinstance(node, list):
            return node[0] if node and isinstance(node[0], dict) else None
        if not isinstance(node, dict):
            return None
        deeper = next((v for v in node.values() if isinstance(v, (list, dict)) and v), None)
        if deeper is None:
            return node
        node = deeper
    return None


def _records_of(data) -> list[dict]:
    """Up to 20 records of a response — read for repetition only, never copied."""
    node = data
    for _depth in range(8):
        if isinstance(node, list):
            return [r for r in node[:20] if isinstance(r, dict)]
        if not isinstance(node, dict):
            return []
        deeper = next((v for v in node.values() if isinstance(v, (list, dict)) and v), None)
        if deeper is None:
            return [node]
        node = deeper
    return []


def formats_of(record) -> dict:
    """`{field: {"format": "iso8601"}}` for a date field, `{field: {"enum": [...]}}` for an enum.

    One record is enough for the format; the enum needs repetition, which is why `_records_of`
    exists. Nothing else of a value is ever kept."""
    if not isinstance(record, dict):
        return {}
    out: dict = {}
    for name, value in list(record.items())[:200]:
        unit = describer_shape_units(value, name)
        if unit:
            out[str(name)[:200]] = {"format": unit}
    return out


def describer_shape_units(value, name: str) -> str | None:
    """The time unit of a field when its value or its name says it is a date."""
    from bizview_cli.structure import infer_timestamp_units

    unit = infer_timestamp_units(value)
    if unit:
        return unit
    if isinstance(value, str) and DATE_NAME.search(name or "") and len(value) <= 40:
        return "iso8601" if re.search(r"\d{4}-\d{2}-\d{2}", value) else None
    return None


def enums_of(records: list[dict]) -> dict:
    """Values of a field that repeat: an enum a reader needs, and free text never repeats."""
    counts: dict[str, dict[str, int]] = {}
    for record in records:
        for name, value in list(record.items())[:200]:
            if not isinstance(value, str) or not ENUM_TOKEN.match(value):
                continue
            bucket = counts.setdefault(str(name)[:200], {})
            bucket[value] = bucket.get(value, 0) + 1
    out: dict = {}
    for name, values in counts.items():
        repeated = [v for v, times in sorted(values.items()) if times >= 2]
        if repeated:
            out[name] = {"enum": repeated[:MAX_ENUM_VALUES]}
    return out
