"""The structure pack of one source, on the server side (feature 052, FR-001/FR-003).

Glue only: read the structure (the describe of 005), stamp the BI-ready flag, the notes, the
personal flags and the samples, then hand it to the one generator in `bizview_cli.structure` so the
API, the UI and `bizview describe --pack` produce the same bytes.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import DataSource, SourceSampleRequest, SourceStructureFlag
from app.sources import describe as describer
from app.sources import service

SAMPLE_KINDS = ("rest", "supabase")


def flags(db: Session, source: DataSource) -> dict[str, bool]:
    """The overrides the super user made, keyed `schema.table.column` (or `table.column`)."""
    rows = db.scalars(select(SourceStructureFlag)
                      .where(SourceStructureFlag.source_id == source.id))
    return {_flag_key(row.schema_name, row.table_name, row.column_name): row.personal
            for row in rows}


def _flag_key(schema: str, table: str, column: str) -> str:
    prefix = f"{schema}.{table}" if schema else table
    return f"{prefix}.{column}".lower()


def set_flag(db: Session, source: DataSource, *, schema: str, table: str, column: str,
             personal: bool) -> None:
    key = (source.id, schema or "", table, column)
    row = db.get(SourceStructureFlag, key)
    if row is None:
        row = SourceStructureFlag(source_id=source.id, schema_name=schema or "", table_name=table,
                                  column_name=column, personal=personal)
        db.add(row)
    else:
        row.personal = personal


def sample_payload(sample: SourceSampleRequest) -> dict:
    """What an author needs to know about one saved sample, without a value."""
    return {"name": sample.name, "method": sample.method, "path": sample.path,
            "params": sample.params or {}, "notes": sample.notes,
            "shape": sample.last_shape, "records": (sample.last_suggestions or {}).get("records"),
            "fields": (sample.last_suggestions or {}).get("fields") or {},
            "types": (sample.last_suggestions or {}).get("types") or {},
            "timestamp_units": (sample.last_suggestions or {}).get("timestamp_units"),
            "pagination": (sample.last_suggestions or {}).get("pagination"),
            "error": sample.last_error}


def build(db: Session, source: DataSource, app: Settings, *, path: str | None = None) -> dict:
    """The pack this source produces right now (structure only: no credential leaves here)."""
    from bizview_cli.structure import build_pack

    secrets = service.secrets_of(source)
    structure = describer.describe(source.kind, source.settings, secrets, app, path,
                                   date_ranges=True, name=source.name)
    saved = list(db.scalars(select(SourceSampleRequest)
                            .where(SourceSampleRequest.source_id == source.id)
                            .order_by(func.lower(SourceSampleRequest.name))))
    bi_ready = dict(source.bi_ready or {})
    return build_pack(
        structure, source=source.name, kind=source.kind, notes=source.notes or "",
        bi_ready=bi_ready, timezone=str(bi_ready.get("timezone") or "UTC"),
        flags=flags(db, source),
        samples=[sample_payload(s) for s in saved] if source.kind in SAMPLE_KINDS else None)


def suggestions_for(shape: dict, values: dict) -> dict:
    """`records`, `fields`, `types` and the timestamp unit, inferred by product code (FR-002)."""
    from bizview_cli.structure import infer_timestamp_units, pagination_hint, suggest

    found = suggest(shape)
    units = {}
    for column, path in found["fields"].items():
        unit = infer_timestamp_units(_dig(values, path))
        if unit:
            units[column] = unit
    found["timestamp_units"] = _uniform(units)
    found["pagination"] = pagination_hint(shape)
    return found


def _dig(value, path: str):
    """`$.a.b` → the value at that path of one record, when the record is a dict."""
    if not isinstance(value, dict):
        return None
    node = value
    for part in [p for p in str(path).lstrip("$.").split(".") if p]:
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _uniform(units: dict[str, str]) -> str | None:
    distinct = set(units.values())
    return distinct.pop() if len(distinct) == 1 else None
