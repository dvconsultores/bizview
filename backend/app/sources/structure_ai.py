"""Turn a scan into the structure pack with one internal AI pass (052, converged 2026-11-03).

The pipeline is three steps and only the middle one involves a provider:

1. **scan** (`structure_scan`): describe output, sample shapes, a published OpenAPI document, the
   catalogue's foreign keys — structure and formats, never a row value;
2. **enrich** (this module): one `complete()` per chunk (at most `MAX_CHUNKS`), strict JSON back,
   one repair round when the answer does not parse, and a per-run token ceiling;
3. **verify** (this module): every table, field, path and relation the model returned is checked
   against the scan, and what does not exist is dropped and listed under `dropped`.

A run that fails changes nothing: the source keeps its previous pack, and the tab falls back to the
plain scan. Nothing here authors a project — the pack is what a person hands to the external AI.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from bizview_cli.structure import (
    ENRICHED_VERSION,
    enriched_markdown,
    enriched_schema,
    validate_enriched,
)
from sqlalchemy.orm import Session

from app.ai import AIError, get_provider, state
from app.config import Settings
from app.errors import ApiError
from app.i18n import M
from app.models import DataSource
from app.sources import structure_scan

log = logging.getLogger("app.structure_ai")

PROMPT_FILE = Path(__file__).parent.parent / "ai" / "prompts" / "structure_enrich.md"
MAX_CHUNKS = 6
#: Characters of one chunk's scan: small enough that a model answers in one go.
MAX_CHUNK_CHARS = 45_000

_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.M)


def prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8")


# --- chunking -----------------------------------------------------------------------------


def chunks(scan: dict) -> list[dict]:
    """The scan cut per schema or per endpoint, so one model call never sees everything."""
    head = {key: scan.get(key) for key in ("source", "kind", "generated_at", "notes", "bi_ready")}
    pieces: list[dict] = []
    if scan.get("tables"):
        by_schema: dict[str, list] = {}
        for table in scan["tables"]:
            by_schema.setdefault(str(table.get("schema") or "public"), []).append(table)
        for schema, tables in by_schema.items():
            pieces.append({"scope": f"esquema {schema}",
                           "tables": tables,
                           "relations": [r for r in scan.get("relations") or []
                                         if r["from"].startswith(f"{schema}.")]})
    for endpoint in scan.get("endpoints") or []:
        if endpoint.get("error") or not endpoint.get("shape"):
            continue
        pieces.append({"scope": f"endpoint {endpoint['path']}",
                       "endpoints": [endpoint], "relations": []})
    if scan.get("openapi"):
        pieces.append({"scope": "documento OpenAPI", "openapi": scan["openapi"]})
    if not pieces:
        pieces = [{"scope": "fuente", "operations": scan.get("operations") or []}]
    out: list[dict] = []
    for piece in pieces:
        body = json.dumps(piece, ensure_ascii=False)
        if len(body) > MAX_CHUNK_CHARS:            # cut by table, never mid-object
            for table in piece.get("tables") or []:
                single = {**piece, "tables": [table]}
                out.append({**head, **single})
            if not piece.get("tables"):
                out.append({**head, **piece})
        else:
            out.append({**head, **piece})
    return out[:MAX_CHUNKS]


# --- the model call -----------------------------------------------------------------------


def _ask(provider, chunk: dict, *, repair: str | None = None):
    body = json.dumps({k: v for k, v in chunk.items() if k != "scope"},
                      ensure_ascii=False, sort_keys=False)
    parts = [
        "Escaneo de la fuente (JSON):",
        body,
        "",
        f"Esquema que debe cumplir tu respuesta (JSON Schema):\n"
        f"{json.dumps(enriched_schema(), ensure_ascii=False)}",
        "",
        f"Alcance de este trozo: {chunk.get('scope')}. Devuelve solo las tablas de este trozo.",
        "Responde únicamente con el documento JSON.",
    ]
    if repair:
        parts += ["", "Tu respuesta anterior no se pudo usar:", repair[:1_500],
                  "", "Devuelve el documento JSON corregido, completo."]
    reply = provider.complete("\n".join(parts), system=prompt(), max_tokens=8000)
    return reply, _parse(reply.text)


def _parse(text: str) -> dict:
    """The JSON document of an answer; raises ValueError with the reason when there is none."""
    cleaned = _JSON_FENCE.sub("", (text or "").strip()).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("la respuesta no contiene un objeto JSON")
    try:
        data = json.loads(cleaned[start:end + 1])
    except ValueError as e:
        raise ValueError(f"JSON inválido: {e}") from None
    if not isinstance(data, dict):
        raise ValueError("la respuesta no es un objeto JSON")
    return data


# --- enrich -------------------------------------------------------------------------------


def enrich(scan: dict, settings: Settings) -> tuple[dict, dict]:
    """One call per chunk; returns the merged document and the usage of the run."""
    provider = get_provider(settings)
    doc: dict = {"source": scan["source"], "kind": scan["kind"],
                 "generated_at": scan["generated_at"],
                 "generator": {"mode": "ai", "model": settings.ai_model_effective,
                               "version": ENRICHED_VERSION, "tokens": 0},
                 "notes": scan.get("notes") or "", "tables": [], "relations": [],
                 "suggested_metrics": [], "dropped": []}
    usage = {"tokens": 0, "chunks": 0, "incomplete": []}
    seen_tables: set[str] = set()
    for chunk in chunks(scan):
        if usage["tokens"] >= settings.ai_structure_tokens:
            usage["incomplete"].append(str(chunk.get("scope")))
            continue
        reply, answer = _answer(chunk, provider)
        usage["tokens"] += (reply.tokens_in or 0) + (reply.tokens_out or 0)
        usage["chunks"] += 1
        for table in answer.get("tables") or []:
            name = str(table.get("id") or "")
            if name and name not in seen_tables:      # one entry per table, first chunk wins
                seen_tables.add(name)
                doc["tables"].append(table)
        for key in ("relations", "suggested_metrics", "dropped"):
            doc[key].extend(answer.get(key) or [])
        if answer.get("notes"):
            doc["notes"] = _merge_notes(doc.get("notes"), str(answer["notes"]))
    doc["generator"]["tokens"] = usage["tokens"]
    if usage["incomplete"]:
        doc["generator"]["incomplete"] = usage["incomplete"]
    return doc, usage


def _answer(chunk: dict, provider):
    """One chunk, with the repair round: a second attempt carries the parser's complaint."""
    try:
        return _ask(provider, chunk)
    except ValueError as e:
        log.info("structure answer unusable (%s): one repair round", e)
        try:
            return _ask(provider, chunk, repair=str(e))
        except ValueError as again:
            raise AIError("provider_error", f"respuesta no utilizable: {again}") from None


def _merge_notes(current: str | None, extra: str) -> str:
    merged = [line for line in [str(current or "").strip(), extra.strip()] if line]
    return "\n".join(merged)[:4000]


# --- verify -------------------------------------------------------------------------------


def verify(doc: dict, scan: dict) -> dict:
    """Keep only what the scan proves: tables, fields, paths, relations, metrics."""
    dropped: list[str] = list(doc.get("dropped") or [])
    known = _known(scan)
    tables = []
    for table in doc.get("tables") or []:
        if not isinstance(table, dict):
            continue
        table_id = str(table.get("id") or "")
        if table_id not in known["tables"]:
            dropped.append(f"{table_id or '?'} (tabla que la fuente no tiene)")
            continue
        fields = []
        seen: set[str] = set()
        for field in table.get("fields") or []:
            if not isinstance(field, dict) or not field.get("name"):
                continue
            name = str(field["name"])
            if not _field_ok(name, field, known["tables"][table_id], scan):
                dropped.append(f"{table_id}.{name} (campo que la fuente no tiene)")
                continue
            if name.lower() in seen:
                continue
            seen.add(name.lower())
            fields.append(field)
        if not fields:
            dropped.append(f"{table_id} (ningún campo verificado)")
            continue
        tables.append({**table, "fields": fields,
                       "key": [k for k in table.get("key") or [] if str(k).lower() in seen],
                       "date_field": (table.get("date_field")
                                      if str(table.get("date_field") or "").lower() in seen
                                      else None)})
    doc["tables"] = tables

    # A table answers to the names a relation may use: its id, and `schema.id` when it has a schema.
    by_id: dict[str, set[str]] = {}
    for table in tables:
        fields = {str(f["name"]).lower() for f in table["fields"]}
        by_id[str(table["id"])] = fields
        if table.get("schema"):
            by_id.setdefault(f"{table['schema']}.{table['id']}", fields)
    relations = []
    for relation in doc.get("relations") or []:
        if not isinstance(relation, dict):
            continue
        if _relation_ok(relation, by_id):
            relations.append(relation)
        else:
            dropped.append(f"{relation.get('from')} → {relation.get('to')} "
                           "(relación con un campo que no existe)")
    # The catalogue's own foreign keys are a fact, not a suggestion: they are part of the pack even
    # when the model forgot them (only when both sides survived the check).
    known_pairs = {(r["from"], r["to"]) for r in relations}
    for relation in scan.get("relations") or []:
        if (relation["from"], relation["to"]) in known_pairs:
            continue
        if _relation_ok(relation, by_id):
            relations.append({key: relation[key] for key in ("from", "to", "kind", "confidence")
                              if key in relation})
            known_pairs.add((relation["from"], relation["to"]))
    doc["relations"] = relations

    metrics = []
    for metric in doc.get("suggested_metrics") or []:
        if isinstance(metric, dict) and str(metric.get("from")) in by_id \
                and metric.get("id") and metric.get("formula_words"):
            metrics.append(metric)
        else:
            dropped.append(f"{metric.get('id') if isinstance(metric, dict) else metric} "
                           "(métrica sin tabla o sin fórmula)")
    doc["suggested_metrics"] = metrics
    doc["dropped"] = dropped
    doc["generator"] = {**(doc.get("generator") or {}), "version": ENRICHED_VERSION}
    return doc


def _known(scan: dict) -> dict:
    """Every object name the scan proves, per table."""
    tables: dict[str, dict] = {}
    for table in scan.get("tables") or []:
        key = str(table.get("name"))
        tables[key] = {"columns": {str(c.get("name")).lower() for c in table.get("columns") or []},
                       "kind": "postgresql"}
        if table.get("schema"):
            tables.setdefault(f"{table['schema']}.{key}", tables[key])
    for endpoint in scan.get("endpoints") or []:
        if not endpoint.get("shape") and not endpoint.get("error"):
            continue
        tables[str(endpoint["path"])] = {"paths": _leaf_paths(endpoint.get("shape")),
                                         "records": endpoint.get("records") or "$",
                                         "kind": "rest", "endpoint": endpoint}
        if endpoint.get("name"):
            tables[str(endpoint["name"])] = tables[str(endpoint["path"])]
    for published in (scan.get("openapi") or {}).get("tables") or []:
        tables[str(published["name"])] = {
            "columns": {str(f["name"]).lower() for f in published.get("fields") or []},
            "kind": "openapi"}
    return {"tables": tables}


def _leaf_paths(shape, prefix: str = "$", depth: int = 0, out: set[str] | None = None) -> set[str]:
    """Every JSONPath a shape proves, including the intermediate objects."""
    paths = out if out is not None else set()
    if depth > 8:
        return paths
    if isinstance(shape, dict):
        for key, value in shape.items():
            path = f"{prefix}.{key}"
            paths.add(path)
            _leaf_paths(value, path, depth + 1, paths)
    elif isinstance(shape, list):
        for item in shape:
            _leaf_paths(item, prefix, depth + 1, paths)
    return paths


def _field_ok(name: str, field: dict, table: dict | None, scan: dict) -> bool:
    """Whether the scan proves this field: a column the catalogue lists, or a path a shape has.

    A REST field's `path` is written *inside a record* (`$.quote.USD.price`), as the request
    contract expects; the shape's paths are absolute, so the endpoint's `records` is the prefix
    that joins the two."""
    if table is None:
        return False
    if table.get("kind") in ("postgresql", "openapi"):
        return name.lower() in table["columns"]
    path = str(field.get("path") or "")
    if not path.startswith("$"):
        return False
    paths = table["paths"]
    if path in paths:
        return True
    base = str(table.get("records") or "$")
    return base.rstrip("$") + path.lstrip("$") in paths


def _relation_ok(relation: dict, by_id: dict[str, set[str]]) -> bool:
    def side(value) -> bool:
        text = str(value or "")
        for table, fields in by_id.items():
            prefix = f"{table}."
            if text.lower().startswith(prefix.lower()):
                return text[len(prefix):].lower() in fields
        return False

    return side(relation.get("from")) and side(relation.get("to"))


# --- the run ------------------------------------------------------------------------------


def generate(db: Session, source: DataSource, app: Settings) -> dict:
    """Scan → enrich → verify → save, returning the pack. Raises the typed error of a failed run."""
    if source.kind == "soap":
        raise ApiError(422, "validation", M("sourceStructure.ai_unsupported"),
                       fields={"kind": "unsupported"})
    if app.ai_structure_tokens <= 0:
        raise ApiError(429, "ai_structure_ceiling", M("sourceStructure.ai_ceiling"),
                       extra={"ai": {"cap": app.ai_structure_tokens}})
    scan = structure_scan.scan(db, source, app)
    try:
        doc, usage = enrich(scan, app)
    except AIError as e:
        log.warning("structure generation failed: %s (%s)", e.code, e.detail or "-")
        state.record_error(e.code, e.detail, app.ai_model_effective)
        raise ApiError(502, f"ai_{e.code}", M(f"ai.error.{e.code}"),
                       extra={"ai": {"code": e.code, "action": e.action}}) from None
    state.record_ok(doc["generator"].get("model"))
    verified = verify(doc, scan)
    if not verified["tables"]:
        # Nothing survived the check: an empty pack would look like "this source has nothing".
        raise ApiError(502, "ai_provider_error", M("sourceStructure.ai_empty"),
                       extra={"ai": {"code": "provider_error", "action": None,
                                     "dropped": verified.get("dropped", [])[:20]}})
    verified["notes"] = _merge_notes(source.notes, str(doc.get("notes") or ""))
    problems = validate_enriched(verified)
    if problems:
        log.warning("generated pack invalid: %s", "; ".join(problems[:5]))
        raise ApiError(502, "ai_provider_error", M("sourceStructure.ai_invalid"),
                       extra={"ai": {"code": "provider_error", "action": None,
                                     "problems": problems[:20]}}) from None
    source.structure_pack_prev = dict(source.structure_pack or {})
    source.structure_pack = verified
    return {"pack": verified, "usage": usage, "markdown": enriched_markdown(verified)}
