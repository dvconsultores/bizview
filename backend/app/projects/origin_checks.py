"""Origin inspection tools for the assistant: describe/profiling helpers and query checks.

Constitution VIII: these functions return structure and counts only, never row values.
"""
import hashlib
import json
import logging
import math
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import psycopg
import psycopg.errors
import yaml
from bizview_cli import sqlsafety
from bizview_cli import transform as transform_contract
from psycopg import sql as pgsql

from app.assistant.preview import CONNECT_TEXT, active_integrations, redact_values
from app.engine import direct, extract
from app.engine import report as engine
from app.engine.extract import ExtractError
from app.errors import ApiError
from app.i18n import t
from app.projects.personal import (
    personal_kind,
    query_columns,
    request_columns,
    shape_personal,
)
from app.projects.workview import real
from app.services.audit import record
from app.sources.service import by_name, secrets_of

log = logging.getLogger(__name__)

NOTE_CHARS = 300
MAX_NOTES_PER_SOURCE = 80
MAX_PROFILE_COLUMNS = 80
CHECK_WINDOW_DAYS = 7
WINDOW_PLACEHOLDER = re.compile(r"\{window_(start|end)(_date)?\}")
TIMEOUT_TEXT = "tiempo agotado; reduce la consulta"
QUERY_FILE = re.compile(r"^integrations/([^/]+)/queries/[^/]+\.sql$")
REQUEST_FILE = re.compile(r"^integrations/([^/]+)/requests/[^/]+\.yaml$")
REPORT_FILE = re.compile(r"^reports/([^/]+)/report\.yaml$")

DATE_TYPES = {"date", "timestamp without time zone", "timestamp with time zone"}
NO_DISTINCT = {
    "json", "jsonb", "bytea", "xml", "ARRAY", "USER-DEFINED",
    "tsvector", "tsquery", "point", "line", "lseg", "box", "path", "polygon", "circle",
}


class OriginToolError(Exception):
    """A tool input error with a safe Spanish message."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def flag_personal(description: Any) -> Any:
    """Add a personal list to each table or shape with flagged columns."""
    if not isinstance(description, dict):
        return description
    if isinstance(description.get("tables"), list):
        tables = []
        for table in description["tables"]:
            if not isinstance(table, dict):
                tables.append(table)
                continue
            columns = table.get("columns")
            flagged = []
            if isinstance(columns, list):
                for col in columns:
                    if isinstance(col, dict) and col.get("name"):
                        kind = personal_kind(str(col["name"]), col.get("type"))
                        if kind:
                            flagged.append({"column": col["name"], "kind": kind})
            copy = dict(table)
            if flagged:
                copy["personal"] = flagged
            tables.append(copy)
        return {**description, "tables": tables}
    if isinstance(description.get("shape"), (dict, list)):
        flagged = shape_personal(description["shape"])
        if flagged:
            return {**description, "personal": flagged}
    return description


def _src_key(name: str) -> str:
    return name.strip().lower()


def _state(session) -> dict:
    return dict(session.working_state or {})


def remember(session, source: str, key: str, note: str, *, append: bool = False) -> None:
    """Store an inspected[src][key] note with size limits and no in-place mutation."""
    state = _state(session)
    inspected = dict(state.get("inspected") or {})
    src = _src_key(source)
    src_notes = dict(inspected.get(src) or {})
    if append and key in src_notes:
        note = f"{src_notes[key]} | {note}"
    note = note[:NOTE_CHARS]
    if key in src_notes or len(src_notes) < MAX_NOTES_PER_SOURCE:
        src_notes[key] = note
    inspected[src] = src_notes
    state["inspected"] = inspected
    session.working_state = state


def remember_personal(session, source: str, flags: dict[str, str]) -> None:
    """Merge personal column flags into state['personal'][src] without in-place mutation."""
    if not flags:
        return
    src = _src_key(source)
    state = _state(session)
    personal = dict(state.get("personal") or {})
    src_personal = dict(personal.get(src) or {})
    for col, kind in flags.items():
        src_personal[str(col)] = str(kind)
    personal[src] = src_personal
    state["personal"] = personal
    session.working_state = state


def remember_description(session, source: str, path: str | None, description: dict) -> None:
    """Remember a compacted description and flagged personal columns."""
    src = _src_key(source)
    state = _state(session)
    inspected = dict(state.get("inspected") or {})
    personal = dict(state.get("personal") or {})
    described = dict(state.get("described") or {})

    src_personal = dict(personal.get(src) or {})
    if isinstance(description.get("tables"), list):
        for table in description["tables"]:
            if not isinstance(table, dict) or not isinstance(table.get("name"), str):
                continue
            key = f"{table['schema']}.{table['name']}" if table.get("schema") else table["name"]
            note = ", ".join(str(c) for c in table.get("columns") or [])
            if table.get("personal"):
                note += " | personales: " + ", ".join(
                    f"{p['column']} ({p['kind']})" for p in table["personal"]
                    if isinstance(p, dict) and p.get("column") and p.get("kind")
                )
            note = note[:NOTE_CHARS]
            src_notes = dict(inspected.get(src) or {})
            if key in src_notes or len(src_notes) < MAX_NOTES_PER_SOURCE:
                src_notes[key] = note
            inspected[src] = src_notes
            for p in table.get("personal") or []:
                if isinstance(p, dict) and p.get("column") and p.get("kind"):
                    src_personal[str(p["column"])] = str(p["kind"])
    elif description.get("shape") is not None and description.get("path"):
        src_notes = dict(inspected.get(src) or {})
        key = str(description["path"])
        if key in src_notes or len(src_notes) < MAX_NOTES_PER_SOURCE:
            src_notes[key] = json.dumps(description["shape"], ensure_ascii=False)[:NOTE_CHARS]
        inspected[src] = src_notes
        if isinstance(description.get("personal"), list):
            for p in description["personal"]:
                if isinstance(p, dict) and p.get("column") and p.get("kind"):
                    leaf = str(p["column"]).split(".")[-1]
                    src_personal[leaf] = str(p["kind"])

    state["inspected"] = inspected
    if src_personal:
        personal[src] = src_personal
        state["personal"] = personal
    src_described = list(described.get(src) or [])
    entry = path or ""
    if entry not in src_described:
        src_described.append(entry)
    described[src] = src_described
    state["described"] = described
    session.working_state = state


def cached_description(session, source: str, path: str | None) -> dict | None:
    """Return the cached note when the path was already described this session."""
    src = _src_key(source)
    state = _state(session)
    if (path or "") not in (state.get("described") or {}).get(src, []):
        return None
    tables = [
        {"table": key, "note": note}
        for key, note in (state.get("inspected") or {}).get(src, {}).items()
        if not key.startswith("consulta ")
    ]
    personal = [
        {"column": c, "kind": k}
        for c, k in (state.get("personal") or {}).get(src, {}).items()
    ]
    return {
        "cached": True,
        "source": source,
        "path": path,
        "tables": tables,
        "personal": personal,
        "note": ("Estructura ya consultada en esta conversación; usa refresh: true para leerla "
                 "de nuevo."),
    }


def _error_text(e: Exception) -> str:
    if isinstance(e, psycopg.errors.QueryCanceled):
        return TIMEOUT_TEXT
    if isinstance(e, psycopg.errors.ConnectionTimeout):
        return TIMEOUT_TEXT
    if isinstance(e, psycopg.OperationalError):
        msg = str(e)
        if "timeout expired" in msg.lower() or "timed out" in msg.lower():
            return TIMEOUT_TEXT
        return CONNECT_TEXT
    if isinstance(e, extract.ExtractTimeout):
        return TIMEOUT_TEXT
    if isinstance(e, ExtractError):
        return str(e)
    if isinstance(e, httpx.TimeoutException):
        return TIMEOUT_TEXT
    if isinstance(e, psycopg.Error):
        return redact_values(str(e).splitlines()[0] if str(e) else "")
    if isinstance(e, httpx.HTTPError):
        return f"error de red: {type(e).__name__}"
    return "No se pudo completar la consulta."


def _split_table(table: str) -> tuple[str | None, str]:
    parts = table.split(".", 1)
    if len(parts) == 2:
        return parts[0].strip('"'), parts[1].strip('"')
    return None, parts[0].strip('"')


SOURCE_KIND_LABELS = {
    "supabase": "Supabase", "rest": "REST", "soap": "SOAP", "postgresql": "PostgreSQL",
}
PUBLIC_PREFIX = "public."
SQL_NOT_SUPPORTED = (
    "Esta fuente es {kind}: no admite SQL. Escribe "
    "integrations/<id>/requests/<nombre>.yaml en el borrador (ver "
    "get_authoring_guide('example-supabase')) y compruébalo con check_query usando path."
)
COUNT_ONLY_NOTE = (
    "Esta fuente solo permite contar filas; no hay nulos ni valores distintos. "
    "No repitas profile_source."
)


def normalise_table(kind: str | None, table: str) -> str:
    """Normalise a table name for REST/Supabase (strip, drop leading slashes and public schema)."""
    result = table.strip()
    if kind in ("supabase", "rest"):
        result = result.lstrip("/")
        if result.lower().startswith(PUBLIC_PREFIX.lower()):
            result = result[len(PUBLIC_PREFIX):]
    return result


def _profile_query(
    table_ident: pgsql.Composable, columns: list[tuple[str, str]]
) -> tuple[pgsql.Composed, list[dict]]:
    fields = [pgsql.SQL("count(*)")]
    column_positions = []
    for col, data_type in columns:
        col_ident = pgsql.Identifier(col)
        nonnull_pos = len(fields)
        fields.append(pgsql.SQL("count({})").format(col_ident))
        if data_type not in NO_DISTINCT:
            distinct_pos = len(fields)
            fields.append(pgsql.SQL("count(DISTINCT {})").format(col_ident))
        else:
            distinct_pos = None
        kind = personal_kind(col, data_type)
        if data_type in DATE_TYPES and kind is None:
            min_pos = len(fields)
            fields.append(pgsql.SQL("min({})").format(col_ident))
            max_pos = len(fields)
            fields.append(pgsql.SQL("max({})").format(col_ident))
        else:
            min_pos = max_pos = None
        column_positions.append(
            {"name": col, "type": data_type, "nonnull": nonnull_pos,
             "distinct": distinct_pos, "min": min_pos, "max": max_pos,
             "personal": kind}
        )
    query = pgsql.SQL("SELECT {} FROM {}").format(
        pgsql.SQL(", ").join(fields), table_ident
    )
    return query, column_positions


def _profile_columns(row, positions: list[dict]) -> list[dict]:
    total = row[0]
    result_columns = []
    for meta in positions:
        nonnull = row[meta["nonnull"]]
        null_ratio = round((total - nonnull) / total, 4) if total else None
        entry: dict[str, Any] = {
            "name": meta["name"],
            "type": meta["type"],
            "null_ratio": null_ratio,
            "distinct": row[meta["distinct"]] if meta["distinct"] is not None else None,
        }
        if meta["min"] is not None:
            min_val = row[meta["min"]]
            max_val = row[meta["max"]]
            entry["min"] = min_val.isoformat() if isinstance(min_val, date) else None
            entry["max"] = max_val.isoformat() if isinstance(max_val, date) else None
        if meta.get("personal"):
            entry["personal"] = meta["personal"]
        result_columns.append(entry)
    return result_columns


def _profile_pg(source, secrets: dict, app, table: str, timeout: int) -> dict:
    try:
        schema, rel = _split_table(table)
        with extract._pg_connect(source.settings, secrets, app, timezone="UTC",
                                 time_limit_s=timeout, connect_timeout_s=timeout) as conn:
            cur = conn.execute(
                """
                SELECT n.nspname, c.relname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind IN ('r', 'v', 'm', 'p', 'f')
                  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
                  AND has_table_privilege(c.oid, 'SELECT')
                  AND c.relname = %s
                  AND (%s::text IS NULL OR n.nspname = %s)
                """,
                (rel, schema, schema),
            )
            matches = cur.fetchall()
            if not matches:
                return {"error": ("La tabla no existe o no se puede leer; usa esquema.tabla "
                                  "como en describe_source.")}
            if len(matches) > 1:
                return {"error": "Hay varias tablas con ese nombre; indica esquema.tabla."}
            schema_name, rel_name = matches[0]

            cur = conn.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                (schema_name, rel_name),
            )
            all_columns = [(r[0], r[1]) for r in cur.fetchall()]
            truncated = len(all_columns) > MAX_PROFILE_COLUMNS
            columns = all_columns[:MAX_PROFILE_COLUMNS]

            table_ident = pgsql.Identifier(schema_name, rel_name)
            query, column_positions = _profile_query(table_ident, columns)
            cur = conn.execute(query)
            row = cur.fetchone()
            return {
                "table": f"{schema_name}.{rel_name}",
                "row_count": row[0],
                "columns": _profile_columns(row, column_positions),
                "truncated": truncated,
            }
    except Exception as e:
        return {"error": _error_text(e)}


def _profile_bi(app, table: str, timeout: int) -> dict:
    try:
        schema, rel = _split_table(table)
        schema = schema or "public"
        if direct.refusal(schema, rel, bi=True):
            return {"error": direct.PRODUCT_MESSAGE}
        runner = direct.DirectRunner(
            "bi",
            report_id="asistente-perfil",
            timeout_seconds=timeout,
            tables={"t": (schema, rel)},
        )
        with runner.session() as s:
            phys = direct.physical_schema(schema)
            rows = s.query(
                pgsql.SQL(
                    "SELECT column_name, data_type "
                    "FROM information_schema.columns "
                    "WHERE table_schema = {} AND table_name = {} "
                    "ORDER BY ordinal_position"
                ).format(pgsql.Literal(phys), pgsql.Literal(rel)),
                "UTC",
            )
            if not rows:
                return {
                    "error": (
                        "La tabla no existe o no se puede leer; usa esquema.tabla "
                        "como en describe_source."
                    )
                }
            all_columns = [(row[0], row[1]) for row in rows]
            truncated = len(all_columns) > MAX_PROFILE_COLUMNS
            columns = all_columns[:MAX_PROFILE_COLUMNS]

            estimate_rows = s.query(
                pgsql.SQL(
                    "SELECT greatest(c.reltuples, 0)::bigint "
                    "FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = {} AND c.relname = {}"
                ).format(pgsql.Literal(phys), pgsql.Literal(rel)),
                "UTC",
            )
            estimate = estimate_rows[0][0] if estimate_rows else 0
            if estimate > app.direct_report_warn_rows:
                return {
                    "table": f"{schema}.{rel}",
                    "row_count": estimate,
                    "estimado": True,
                    "columns": [
                        {
                            "name": col,
                            "type": data_type,
                            "personal": personal_kind(col, data_type),
                        }
                        for col, data_type in columns
                    ],
                    "truncated": truncated,
                    "note": (
                        "Tabla grande: total estimado por el catálogo, sin recorrerla; "
                        "no se calcularon nulos ni distintos."
                    ),
                }

            table_ident = pgsql.Identifier(phys, rel)
            query, column_positions = _profile_query(table_ident, columns)
            row = s.query(query, "UTC")[0]
            return {
                "table": f"{schema}.{rel}",
                "row_count": row[0],
                "columns": _profile_columns(row, column_positions),
                "truncated": truncated,
            }
    except direct.DirectError as e:
        return {"error": e.message}
    except Exception as e:
        return {"error": _error_text(e)}


def _profile_rest(source, secrets: dict, app, table: str, timeout: int) -> dict:
    if source.kind == "supabase":
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", table):
            return {"error": "El nombre de tabla no es válido para Supabase."}
        request = {"method": "GET", "path": table}
        extra = {"limit": "0"}
    else:
        path = table.strip()
        if path.startswith("/"):
            path = path[1:]
        if "://" in path or ".." in path:
            return {"error": "La ruta de la petición no es válida."}
        request = {"method": "GET", "path": path}
        extra = {}
    try:
        if source.kind == "supabase":
            _payload, headers = extract.supabase_once(
                source.settings, secrets, app, request, {},
                extra_params=extra, extra_headers={"Prefer": "count=exact"},
                time_limit_s=timeout,
            )
        else:
            _payload, headers = extract.rest_once(
                source.settings, secrets, app, request, {},
                extra_headers={"Prefer": "count=exact"}, time_limit_s=timeout,
            )
    except Exception as e:
        return {"error": _error_text(e)}
    content_range = headers.get("content-range", "")
    match = re.search(r"/(\d+)\s*$", content_range)
    result: dict[str, Any] = {
        "table": table,
        "row_count": int(match.group(1)) if match else None,
        "columns": [],
    }
    if not match:
        result["note"] = "la fuente no informó el total de filas"
    return result


def profile_source(db, actor, session, args: dict, app, ip) -> tuple[dict, str]:
    """Profile a table: row count, null ratios, distinct counts, date min/max."""
    name = args.get("name")
    table = args.get("table")
    if (not name or not isinstance(name, str) or not table or not isinstance(table, str)
            or len(table) > 200):
        raise OriginToolError("El nombre de la fuente y la tabla son obligatorios.")
    is_bi = name.strip().lower() == "bi" and bool(app.direct_reports_bi)
    source = None if is_bi else by_name(db, name)
    if source is None and not is_bi:
        return (
            {"error": "No existe una fuente con ese nombre."},
            t("assistant.summary.attempted_profile_on_missing_source", table=table),
        )
    if source is not None and source.kind in ("supabase", "rest"):
        table = normalise_table(source.kind, table)
        if not table:
            return (
                {"error": "El nombre de la tabla es obligatorio."},
                t("assistant.summary.profile_failed", table=args['table'], name=name),
            )
    record(db, "source_described", actor_id=getattr(actor, "id", None), ip=ip,
           detail={"source": "bi" if is_bi else name, "via": "assistant",
                   "session": session.id, "tool": "profile_source"})
    secrets = None if is_bi else secrets_of(source)
    timeout = max(1, math.ceil(app.ai_tool_timeout_seconds))
    if is_bi:
        result = _profile_bi(app, table, timeout)
    elif source.kind == "postgresql":
        result = _profile_pg(source, secrets, app, table, timeout)
    elif source.kind in ("supabase", "rest"):
        result = _profile_rest(source, secrets, app, table, timeout)
        if "error" not in result:
            result["solo_conteo"] = True
            result["note"] = COUNT_ONLY_NOTE
            if result.get("row_count") is None:
                result["note"] += " La fuente no informó el total de filas."
    elif source.kind == "soap":
        result = {"error": "El perfil no está disponible para fuentes SOAP."}
    else:
        result = {"error": "Tipo de fuente no soportado."}
    if "error" not in result:
        if (isinstance(result.get("row_count"), int)
                and result["row_count"] > app.direct_report_warn_rows):
            result["warning"] = (
                f"más de {app.direct_report_warn_rows} filas: un reporte directo "
                "necesita un índice en la columna de fecha; considera una integración "
                "con materialize: daily"
            )
        key = result.get("table", table)
        remember_source = "bi" if is_bi else name
        remember(session, remember_source, key,
                 f"perfil: {result.get('row_count')} filas", append=True)
        personal_flags = {}
        for col_entry in result.get("columns", []):
            if isinstance(col_entry, dict) and col_entry.get("personal"):
                personal_flags[str(col_entry["name"])] = str(col_entry["personal"])
        remember_personal(session, remember_source, personal_flags)
        db.add(real(session))
        db.flush()
        return result, t("assistant.summary.profile_succeeded", table=table, name=name)
    return result, t("assistant.summary.profile_failed", table=table, name=name)


def _bump(session, key: str) -> None:
    stats = dict(session.stats or {})
    stats[key] = int(stats.get(key) or 0) + 1
    session.stats = stats


def integration_spec(db, files: dict, iid: str) -> dict | None:
    """The draft's integration.yaml when present, otherwise the active version's definition."""
    try:
        spec = yaml.safe_load(files.get(f"integrations/{iid}/integration.yaml") or "")
    except Exception:
        return None
    if isinstance(spec, dict):
        return spec
    active = active_integrations(db).get(iid)
    if active:
        return active.get("definition") or {}
    return None


def _dataset_for(spec: dict | None, path: str) -> tuple[str | None, list[str] | None]:
    # Si el dataset declara transform, la consulta/petición se compara con
    # transform.input (C1); en caso contrario, contra las columnas publicadas.
    if not spec:
        return None, None
    match = QUERY_FILE.match(path) or REQUEST_FILE.match(path)
    if not match:
        return None, None
    iid = match.group(1)
    rel = path.split(f"integrations/{iid}/", 1)[1]
    datasets = spec.get("datasets") or {}
    if isinstance(datasets, dict):
        for ds_name, ds in datasets.items():
            if not isinstance(ds, dict):
                continue
            extract_cfg = ds.get("extract") or {}
            if extract_cfg.get("query") == rel or extract_cfg.get("request") == rel:
                tr = ds.get("transform")
                if isinstance(tr, dict):
                    tr_in = tr.get("input")
                    if isinstance(tr_in, dict) and tr_in:
                        return ds_name, list(tr_in.keys())
                cols = ds.get("columns") or {}
                return ds_name, list(cols.keys()) if isinstance(cols, dict) else None
    return None, None


def _transform_summary(
    spec: dict | None, dataset: str | None, tz_default: str
) -> dict | None:
    if not spec or not dataset:
        return None
    datasets = spec.get("datasets") or {}
    ds = datasets.get(dataset)
    if not isinstance(ds, dict):
        return None
    tr = ds.get("transform")
    if not isinstance(tr, dict):
        return None
    input_cols = tr.get("input")
    sql_text = tr.get("sql")
    columns = ds.get("columns")
    if (
        not isinstance(input_cols, dict)
        or not input_cols
        or not all(
            isinstance(d, dict) and isinstance(d.get("type"), str)
            for d in input_cols.values()
        )
        or not isinstance(sql_text, str)
        or not sql_text.strip()
        or not isinstance(columns, dict)
    ):
        return {
            "mode": None,
            "columns": [],
            "problems": [
                {
                    "code": "transform_invalid",
                    "level": "error",
                    "message": "transform incompleto: declara input (columna -> {type}) y sql",
                }
            ],
        }

    tz = spec.get("timezone") or tz_default
    if not isinstance(tz, str):
        tz = tz_default

    check = sqlsafety.check_transform(
        sql_text, {c: d["type"] for c, d in input_cols.items()}
    )
    problems = [
        {"code": p.code, "level": "error", "message": p.message}
        for p in check.problems
    ]

    out_columns: list[dict[str, str]] = []
    if not check.problems and transform_contract.available():
        try:
            inferred = transform_contract.infer(check, input_cols, tz)
            out_columns = [
                {"name": name, "type": transform_contract.dtype_name(dtype)}
                for name, dtype in inferred.items()
            ]
        except transform_contract.TransformError:
            out_columns = []
    if not check.problems:
        for problem in transform_contract.check_output(check, input_cols, columns, tz):
            item: dict[str, str] = {
                "code": problem.code,
                "level": problem.level,
                "message": problem.message,
            }
            if problem.fix is not None:
                item["fix"] = problem.fix
            problems.append(item)

    return {"mode": check.mode, "columns": out_columns, "problems": problems}


def _run_check_sql(source, secrets: dict, app, text: str,
                   columns_expected: list[str] | None) -> dict:
    if source.kind != "postgresql":
        return {"ok": False, "error": "Las consultas SQL solo se comprueban en fuentes PostgreSQL.",
                "columns": [], "missing": [], "extra": []}
    problems = sqlsafety.check_query(text)
    if problems:
        return {"ok": False, "error": "consulta no permitida: " + "; ".join(
            p.message for p in problems[:3]), "columns": [], "missing": [], "extra": []}
    q = extract.to_psycopg(text)
    wrapped = f"SELECT * FROM (\n{q}\n) AS q LIMIT 0"
    params_names = sqlsafety.query_params(text)
    end = datetime.now(UTC)
    start = end - timedelta(days=CHECK_WINDOW_DAYS)
    params = {k: {"window_start": start, "window_end": end}[k] for k in params_names
              if k in ("window_start", "window_end")}
    timeout = max(1, math.ceil(app.ai_tool_timeout_seconds))
    try:
        with extract._pg_connect(source.settings, secrets, app, timezone="UTC",
                                 time_limit_s=timeout, connect_timeout_s=timeout) as conn:
            cur = conn.execute(wrapped, params)
            desc = cur.description or []
            type_codes = list({d.type_code for d in desc})
            if type_codes:
                type_rows = conn.execute(
                    "SELECT oid::int, format_type(oid, NULL) FROM pg_type WHERE oid = ANY(%s)",
                    (type_codes,),
                ).fetchall()
                type_names = {int(r[0]): r[1] for r in type_rows}
            else:
                type_names = {}
            columns = [
                {"name": d.name, "type": type_names.get(d.type_code, "desconocido")}
                for d in desc
            ]
    except Exception as e:
        return {"ok": False, "error": _error_text(e), "columns": [], "missing": [], "extra": []}
    out_names = [c["name"] for c in columns]
    if columns_expected is None:
        missing: list[str] = []
        extra: list[str] = []
    else:
        missing = [c for c in columns_expected if c not in out_names]
        extra = [c for c in out_names if c not in columns_expected]
    return {"ok": not missing and not extra, "columns": columns, "missing": missing,
            "extra": extra, "error": None}


def _lookup(obj, path: str) -> tuple[bool, Any]:
    path = path.strip()
    if path in ("", "$"):
        return True, obj
    if path.startswith("$"):
        path = path[1:].lstrip(".")
    current = obj
    for name, index in extract._PATH_PART.findall(path):
        if name:
            if not isinstance(current, dict) or name not in current:
                return False, None
            current = current[name]
        else:
            i = int(index)
            if not isinstance(current, list) or i >= len(current):
                return False, None
            current = current[i]
    return True, current


def _json_type(v: Any) -> str:
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "number"
    if isinstance(v, str):
        return "string"
    if v is None:
        return "null"
    if isinstance(v, dict):
        return "object"
    if isinstance(v, list):
        return "array"
    return "desconocido"


def _without_window(request: dict) -> dict | None:
    """Request copy without window-holding params, or None when nothing changed."""
    params = request.get("params")
    if not isinstance(params, dict):
        return None
    new_params = dict(params)
    removed = False
    for key in list(new_params):
        value = new_params[key]
        candidates = value if isinstance(value, list) else [value]
        if any(isinstance(v, str) and WINDOW_PLACEHOLDER.search(v) for v in candidates):
            del new_params[key]
            removed = True
    if not removed:
        return None
    result = dict(request)
    result["params"] = new_params
    return result


_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}:\d{2}(\.\d+)?)?"
                       r"(?:Z|[+-]\d{2}:?\d{2})?$")
_UNIT_MIN = {"seconds": 631_152_000, "milliseconds": 631_152_000_000}   # 1990-01-01
_UNIT_MAX = {"seconds": 4_102_444_800, "milliseconds": 4_102_444_800_000}  # 2100-01-01


def timestamp_unit(value: Any) -> str | None:
    """The unit a mapped time value is in, from its magnitude or format (feature 040, FR-012).

    Postgres casts the value into a `timestamptz` column at load time, so a millisecond epoch sent
    as seconds (or the other way round) is not a mapping detail: it fails with «date/time field
    value out of range».
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        return "iso8601" if _ISO_DATE.match(value.strip()) else None
    if isinstance(value, (int, float)):
        for unit in ("seconds", "milliseconds"):
            low, high = _UNIT_MIN[unit], _UNIT_MAX[unit]
            if low <= float(value) <= high:
                return unit
    return None


def _shape_result(request: dict, first, columns_expected: list[str] | None) -> dict:
    """Field-check result shape for a single record (or None)."""
    fields = []
    missing = []
    units: dict[str, str] = {}
    mismatched: list[dict[str, str]] = []
    raw_units = request.get("timestamp_units")
    declared = raw_units if isinstance(raw_units, dict) else {}
    for col, fpath in request["fields"].items():
        if first is None:
            found, json_type = None, None
        else:
            found, value = _lookup(first, fpath)
            json_type = _json_type(value) if found else None
            unit = timestamp_unit(value) if found else None
            if unit is not None:
                units[col] = unit
                if col in declared and declared[col] != unit:
                    mismatched.append({"column": col, "declared": str(declared[col]),
                                       "suggested": unit})
        fields.append({"column": col, "found": found, "json_type": json_type,
                       "timestamp_unit": units.get(col)})
        if first is not None and not found:
            missing.append(col)
    missing_columns = [c for c in columns_expected or [] if c not in request["fields"]]
    # 040 (E): the keys the response actually carries, so a `fields` entry the shape does not have
    # is named with the real ones instead of «columnas o campos que no coinciden».
    keys = sorted(first) if isinstance(first, dict) else []
    return {
        "ok": not missing and not missing_columns and not mismatched,
        "records": 0 if first is None else 1,
        "fields": fields,
        "keys": keys,
        "timestamp_units": units,
        "unit_mismatch": mismatched,
        "missing": missing,
        "missing_columns": missing_columns,
        "error": None,
    }


def _run_check_request(source, secrets: dict, app, text: str,
                       columns_expected: list[str] | None) -> dict:
    shape = {"ok": False, "error": None, "records": 0, "fields": [], "missing": [],
             "missing_columns": [], "keys": [], "timestamp_units": {}, "unit_mismatch": []}
    if source.kind == "soap":
        return {**shape, "ok": True,
                "skipped": "no comprobable (fuente SOAP)",
                "note": ("Las peticiones SOAP no se comprueban; "
                         "se validarán al ejecutar la integración.")}
    if source.kind not in ("rest", "supabase"):
        return {**shape, "error": "Las peticiones solo se comprueban en fuentes REST o Supabase."}
    try:
        request = yaml.safe_load(text)
    except Exception as e:
        first_line = str(e).splitlines()[0][:200] if str(e) else ""
        return {**shape, "error": f"YAML no válido: {first_line}"}
    if (not isinstance(request, dict) or not isinstance(request.get("records"), str)
            or not isinstance(request.get("fields"), dict)):
        return {**shape, "error": "La petición debe definir records y fields."}
    if str(request.get("method") or "GET").upper() != "GET":
        return {**shape, "ok": True,
                "skipped": "no comprobable (petición POST)",
                "note": ("Solo se comprueban peticiones GET; "
                         "esta se validará al ejecutar la integración.")}
    extra: dict[str, Any] = {}
    page = request.get("pagination") or {}
    if isinstance(page, dict):
        if page.get("size_param"):
            extra[str(page["size_param"])] = 1
        if page.get("type") == "page":
            extra[str(page.get("param") or "page")] = 1
        elif page.get("type") == "offset":
            extra[str(page.get("param") or "offset")] = 0
        if not page.get("size_param") and source.kind == "supabase":
            extra["limit"] = 1
    end = datetime.now(UTC)
    start = end - timedelta(days=CHECK_WINDOW_DAYS)
    params = {"window_start": start, "window_end": end}
    timeout = max(1, math.ceil(app.ai_tool_timeout_seconds))

    def _fetch(req: dict, req_params: dict) -> tuple[Any, dict]:
        if source.kind == "supabase":
            return extract.supabase_once(
                source.settings, secrets, app, req, req_params, extra_params=extra,
                time_limit_s=timeout,
            )
        return extract.rest_once(
            source.settings, secrets, app, req, req_params, extra_params=extra,
            time_limit_s=timeout,
        )

    try:
        payload, _headers = _fetch(request, params)
    except Exception as e:
        return {**shape, "error": _error_text(e)}
    records = extract.json_path(payload, request["records"])
    if records is None:
        records = []
    # 041: un objeto en la ruta de registros es un único registro.
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list):
        return {**shape, "error": f"'{request['records']}' no es una lista en la respuesta"}

    first = records[0] if records else None
    result = _shape_result(request, first, columns_expected)
    if first is None:
        result["note"] = (
            f"sin registros en los últimos {CHECK_WINDOW_DAYS} días; no se comprobaron los campos"
        )
        request_no_window = _without_window(request)
        if request_no_window is not None:
            try:
                payload2, _headers2 = _fetch(request_no_window, params)
            except Exception:
                return result
            records2 = extract.json_path(payload2, request_no_window["records"])
            if records2 is None:
                records2 = []
            if isinstance(records2, dict):
                records2 = [records2]
            if not isinstance(records2, list):
                return {**shape, "error": f"'{request['records']}' no es una lista en la respuesta"}
            first2 = records2[0] if records2 else None
            if first2 is None:
                return {
                    **result,
                    "sin_ventana": True,
                    "note": (
                        f"sin registros en los últimos {CHECK_WINDOW_DAYS} días ni sin filtro "
                        "de fechas; no se comprobaron los campos"
                    ),
                }
            result2 = _shape_result(request_no_window, first2, columns_expected)
            return {
                **result2,
                "sin_ventana": True,
                "note": (
                    "No hubo filas en la ventana; se comprobó la forma con la fila más "
                    "reciente sin filtro de fechas."
                ),
            }
    return result


class _Captured(Exception):
    def __init__(self, statement: pgsql.Composable) -> None:
        super().__init__("captured")
        self.statement = statement


class _CaptureSession:
    def query(self, statement, _tz: str):
        raise _Captured(statement)


def _captured_statement(ctx, metric_ids: list[str], rng, tz: str) -> pgsql.Composed:
    try:
        engine.aggregate(ctx, metric_ids, rng, {}, tz, session=_CaptureSession())
    except _Captured as captured:
        return captured.statement
    raise RuntimeError("no statement")


def _check_metric_ids(doc: dict) -> list[str]:
    for view in doc.get("views", []):
        if isinstance(view, dict) and view.get("type") == "kpis":
            metrics = view.get("metrics")
            if isinstance(metrics, list):
                return [str(item) for item in metrics if isinstance(item, str)]
            break
    return [
        str(metric_id)
        for metric_id, definition in doc.get("metrics", {}).items()
        if isinstance(definition, dict) and "sql" in definition
    ]


def _run_check_direct(session, path: str, text: str, app) -> dict:
    rid = REPORT_FILE.match(path).group(1)
    base = {
        "ok": False,
        "columns": [],
        "missing": [],
        "extra": [],
        "error": None,
        "report": rid,
    }
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError:
        doc = None
    if not isinstance(doc, dict) or not isinstance(doc.get("direct"), dict):
        return {**base, "error": "YAML no válido o sin bloque direct."}
    try:
        version = engine.PreviewVersion(
            id=None,
            artifacts={"workspace": {}, "integrations": {}, "reports": {}},
        )
        ctx = engine.preview_context(version, rid, doc, {}, set(), session.id)
        metric_ids = _check_metric_ids(doc)
        if not metric_ids:
            return {**base, "error": "El reporte no tiene métricas con sql para comprobar."}
        tz = app.timezone
        today = datetime.now(ZoneInfo(tz)).date()
        sel, _ = engine.selection(ctx, {}, today)
        stmt = _captured_statement(ctx, metric_ids, sel.current, tz)
        wrapped = pgsql.SQL("SELECT * FROM ({}) AS q LIMIT 0").format(stmt)
        runner = ctx.runner
        runner.timeout_seconds = max(
            1, min(int(runner.timeout_seconds), math.ceil(app.ai_tool_timeout_seconds))
        )
        with runner.session() as direct_session:
            direct_session.query(wrapped, tz)
            desc = list(direct_session.description)
            type_names: dict[int, str] = {}
            if desc:
                type_rows = direct_session.query(
                    pgsql.SQL(
                        "SELECT oid::int, format_type(oid, NULL) "
                        "FROM pg_type WHERE oid = ANY({})"
                    ).format(pgsql.Literal(sorted({oid for _, oid in desc}))),
                    tz,
                )
                type_names = {int(oid): str(name) for oid, name in type_rows}
        columns = [
            {"name": name, "type": type_names.get(oid, "desconocido")}
            for name, oid in desc
        ]
        return {**base, "ok": True, "columns": columns, "metrics": metric_ids}
    except direct.DirectError as e:
        return {**base, "error": e.message}
    except ApiError as e:
        return {**base, "error": redact_values(e.message)}
    except Exception as e:
        log.warning("direct check failed (%s)", type(e).__name__)
        return {**base, "error": "No se pudo comprobar el reporte; revisa el borrador."}


def run_check(db, session, source, secrets: dict, app, *, path: str | None = None,
              sql_text: str | None = None) -> dict:
    """Run a query/request check and store the result in session.query_checks."""
    files = (session.draft or {}).get("files") if session.draft else None
    text = None
    if path:
        text = (files or {}).get(path)
    elif sql_text is not None:
        text = sql_text
    if text is None:
        result = {"ok": False, "error": "No hay texto para comprobar.", "columns": [],
                  "missing": [], "extra": [], "path": path, "dataset": None}
        if path:
            checks = dict(session.query_checks or {})
            checks[path] = {
                "sha256": None,
                "ok": False,
                "columns": [],
                "error": result["error"],
                "at": datetime.now(UTC).isoformat(),
            }
            session.query_checks = checks
        return result
    dataset = None
    columns_expected = None
    spec = None
    if path and REPORT_FILE.match(path):
        result = _run_check_direct(session, path, text, app)
    else:
        if path:
            match = QUERY_FILE.match(path) or REQUEST_FILE.match(path)
            if match:
                spec = integration_spec(db, files or {}, match.group(1))
                dataset, columns_expected = _dataset_for(spec, path)
        if path and REQUEST_FILE.match(path):
            result = _run_check_request(source, secrets, app, text, columns_expected)
        else:
            result = _run_check_sql(source, secrets, app, text, columns_expected)
    result["path"] = path
    result["dataset"] = dataset
    if path and (QUERY_FILE.match(path) or REQUEST_FILE.match(path)):
        transform_summary = _transform_summary(spec, dataset, app.timezone)
        if transform_summary is not None:
            result["transform"] = transform_summary
            if any(p["level"] == "error" for p in transform_summary["problems"]):
                result["ok"] = False
    if path:
        checks = dict(session.query_checks or {})
        entry = {
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "ok": result["ok"],
            "columns": result.get("fields") if REQUEST_FILE.match(path) else result.get("columns"),
            "error": result.get("error"),
            "at": datetime.now(UTC).isoformat(),
        }
        if REQUEST_FILE.match(path):
            # 041: `recheck_draft` replaced the entry and wiped the keys the wrapper had stored.
            entry["keys"] = [str(key) for key in result.get("keys") or []]
        if result.get("skipped"):
            entry["skipped"] = result["skipped"]
        checks[path] = entry
        session.query_checks = checks
    return result


def _check_direct_report(
    db, actor, session, source_name: str, path: str, app, ip
) -> tuple[dict, str] | None:
    files = (session.draft or {}).get("files") if session.draft else {}
    text = files.get(path, "")
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError:
        doc = None
    if not isinstance(doc, dict) or not isinstance(doc.get("direct"), dict):
        raise OriginToolError(
            "check_query con reports/<id>/report.yaml solo comprueba reportes "
            "directos (bloque direct)."
        )
    declared = str(doc["direct"].get("source") or "").strip()
    rid = REPORT_FILE.match(path).group(1)
    if declared.lower() != source_name.strip().lower():
        result = {
            "ok": False,
            "error": f"El reporte usa la fuente «{declared}»; indica source: {declared}.",
            "columns": [],
            "missing": [],
            "extra": [],
            "path": path,
            "report": rid,
        }
        return result, t("assistant.summary.attempted_check_with_other_source", path=path)
    record(
        db,
        "source_described",
        actor_id=getattr(actor, "id", None),
        ip=ip,
        detail={"source": declared, "via": "assistant", "session": session.id,
                "tool": "check_query"},
    )
    result = run_check(db, session, None, {}, app, path=path)
    _bump(session, "query_checks")
    if result.get("ok"):
        names = ", ".join(str(item["name"]) for item in result.get("columns", []))
        note = f"correcta; columnas: {names or 'ninguna'}"
        status = t("assistant.summary.status_ok")
    else:
        note = f"error: {result.get('error') or 'desconocido'}"
        status = t("assistant.summary.status_error")
    remember(session, declared, f"consulta {path}", note)
    db.add(real(session))
    db.flush()
    return result, t("assistant.summary.checked_metric", path=path,
                     declared=declared, status=status)


def check_query(db, actor, session, args: dict, app, ip) -> tuple[dict, str]:
    """Tool entry: validate one draft file or ad-hoc SQL for a source."""
    source_name = args.get("source")
    path = args.get("path")
    sql = args.get("sql")
    if not source_name or not isinstance(source_name, str):
        raise OriginToolError("Indica la fuente y una de path (archivo del borrador) o sql.")
    if not ((path and isinstance(path, str) and not sql)
            or (sql and isinstance(sql, str) and not path)):
        raise OriginToolError("Indica la fuente y una de path (archivo del borrador) o sql.")
    if path:
        draft_files = (session.draft or {}).get("files") if session.draft else None
        if not draft_files:
            raise OriginToolError("No hay un borrador; usa propose_draft primero.")
        if path not in draft_files or not (
            QUERY_FILE.match(path)
            or REQUEST_FILE.match(path)
            or REPORT_FILE.match(path)
        ):
            raise OriginToolError(
                "La ruta debe ser un archivo del borrador integrations/<id>/queries/*.sql, "
                "integrations/<id>/requests/*.yaml o reports/<id>/report.yaml "
                "(reporte directo)."
            )
        if REPORT_FILE.match(path):
            report_result = _check_direct_report(
                db, actor, session, source_name, path, app, ip
            )
            if report_result is not None:
                return report_result
    if sql and len(sql) > 20_000:
        raise OriginToolError("La consulta SQL es demasiado larga (máximo 20000 caracteres).")
    source = by_name(db, source_name)
    if source is None:
        return (
            {"error": "No existe una fuente con ese nombre."},
            t("assistant.summary.attempted_query_on_missing_source"),
        )
    if sql and source.kind != "postgresql":
        return (
            {"ok": False,
             "error": SQL_NOT_SUPPORTED.format(
                 kind=SOURCE_KIND_LABELS.get(source.kind, source.kind)),
             "columns": [], "missing": [], "extra": [], "path": None, "dataset": None},
            t("assistant.summary.sql_not_supported", source_name=source_name),
        )
    record(db, "source_described", actor_id=getattr(actor, "id", None), ip=ip,
           detail={"source": source_name, "via": "assistant", "session": session.id,
                   "tool": "check_query"})
    secrets = secrets_of(source)
    result = run_check(db, session, source, secrets, app, path=path, sql_text=sql)
    _bump(session, "query_checks")

    if path:
        text = (session.draft or {}).get("files", {}).get(path)
    else:
        text = sql
    if text is not None:
        if path and REQUEST_FILE.match(path):
            try:
                request_doc = yaml.safe_load(text)
            except Exception:
                request_doc = None
            names = request_columns(request_doc)
        else:
            names = {c["name"] for c in result.get("columns", [])}
            names.update(query_columns(text))
        flags = {n: kind for n in names if (kind := personal_kind(n))}
        if flags:
            result["personal"] = [{"column": c, "kind": flags[c]} for c in sorted(flags)]
            remember_personal(session, source_name, flags)

    if result.get("skipped"):
        note = f"no comprobada: {result['skipped']}"
    elif path and REQUEST_FILE.match(path):
        cols = [f["column"] for f in result.get("fields", [])]
        note = (f"correcta; campos: {', '.join(cols)}" if result["ok"]
                else f"error: {result.get('error')}")
    else:
        cols = [c["name"] for c in result.get("columns", [])]
        note = (f"correcta; columnas: {', '.join(cols)}" if result["ok"]
                else f"error: {result.get('error')}")
    remember(session, source_name, f"consulta {path or 'ad hoc'}", note)
    db.add(real(session))
    db.flush()
    status = (t("assistant.summary.status_ok") if result["ok"]
              else t("assistant.summary.status_errors"))
    return result, t("assistant.summary.checked_query", path=path or 'ad hoc',
                     source_name=source_name, status=status)


def recheck_draft(db, session, app) -> list[dict]:
    """Re-check every draft query/request; return failures. Empty list = all good."""
    files = (session.draft or {}).get("files") if session.draft else {}
    failures = []
    for path in sorted(files):
        if REPORT_FILE.match(path):
            try:
                doc = yaml.safe_load(files[path])
            except yaml.YAMLError:
                doc = None
            if not isinstance(doc, dict) or not isinstance(doc.get("direct"), dict):
                continue
            result = run_check(db, session, None, {}, app, path=path)
            if not result.get("ok"):
                failures.append(
                    {
                        "path": path,
                        "error": result.get("error")
                        or t("origin.check_metric_failed"),
                    }
                )
            continue
        if not (QUERY_FILE.match(path) or REQUEST_FILE.match(path)):
            continue
        match = QUERY_FILE.match(path) or REQUEST_FILE.match(path)
        iid = match.group(1)
        spec = integration_spec(db, files, iid)
        if spec is None:
            failures.append({"path": path, "error": t("origin.invalid_source_declared")})
            continue
        source_name = spec.get("source") if isinstance(spec, dict) else None
        if not source_name or not isinstance(source_name, str):
            failures.append({"path": path, "error": t("origin.invalid_source_declared")})
            continue
        source = by_name(db, source_name)
        if source is None:
            failures.append({"path": path,
                              "error": t("origin.missing_source",
                                          source_name=source_name)})
            continue
        result = run_check(db, session, source, secrets_of(source), app, path=path)
        if not result["ok"]:
            if result.get("error"):
                failures.append({"path": path, "error": result["error"]})
            else:
                parts = []
                if result.get("missing"):
                    parts.append(t("origin.missing_columns",
                                    columns=", ".join(result["missing"])))
                if result.get("extra"):
                    parts.append(t("origin.extra_columns", columns=", ".join(result["extra"])))
                if result.get("missing_columns"):
                    parts.append(t("origin.undefined_contract_fields",
                                    columns=", ".join(result["missing_columns"])))
                failures.append({"path": path, "error": "; ".join(parts)})
    return failures
