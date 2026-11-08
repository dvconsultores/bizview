"""Origin checks for a project's queries and requests (feature 020, re-homed from the assistant).

Every call returns structure and counts only, never row values (constitution VIII), and error texts
are redacted before they leave this module.
"""
import hashlib
import logging
import math
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import psycopg
import psycopg.errors
import yaml
from bizview_cli import sqlsafety
from bizview_cli import transform as transform_contract
from psycopg import sql as pgsql

from app.engine import direct, extract
from app.engine import report as engine
from app.engine.extract import ExtractError
from app.errors import ApiError
from app.i18n import t
from app.projects.personal import (
    personal_kind,
    shape_personal,
)
from app.sources.connectors import registry
from app.sources.service import by_name, secrets_of


def active_integrations(db) -> dict:
    """The integrations of the active workspace version: {id: entry}."""
    from app.workspace import service as workspace_service

    active = workspace_service.active(db)
    if not active:
        return {}
    return (active.artifacts or {}).get("integrations") or {}


def redact_values(text: str, limit: int = 300) -> str:
    """Database error texts can quote row values: strip quoted literals and key groups."""
    text = re.sub(r"'[^']*'", "«…»", text)
    text = re.sub(r'"[^"]*"', "«…»", text)
    text = re.sub(r"=\([^)]*\)", "=(…)", text)
    text = re.sub(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://\S+", "«…»", text)
    for key in ("host", "hostaddr", "port", "user", "dbname", "database", "password", "sslmode"):
        text = re.sub(rf"\b{key}=[^\s,]+", f"{key}=«…»", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "«…»", text)
    return text[:limit]


CONNECT_TEXT = "no se pudo conectar; revisa host, puerto y credenciales"

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
    if not registry.is_sql(source.kind):
        return {"ok": False, "error": "Las consultas SQL solo se comprueban en fuentes SQL.",
                "columns": [], "missing": [], "extra": []}
    problems = sqlsafety.check_query(text)
    if problems:
        return {"ok": False, "error": "consulta no permitida: " + "; ".join(
            p.message for p in problems[:3]), "columns": [], "missing": [], "extra": []}
    if source.kind != registry.POSTGRESQL:
        return _probe_sql(source, secrets, app, text, columns_expected)
    q = extract.to_psycopg(text)
    wrapped = f"SELECT * FROM (\n{q}\n) AS q LIMIT 0"
    params_names = sqlsafety.query_params(text)
    end = datetime.now(UTC)
    start = end - timedelta(days=CHECK_WINDOW_DAYS)
    params = {k: {"window_start": start, "window_end": end}[k] for k in params_names
              if k in ("window_start", "window_end")}
    timeout = max(1, math.ceil(app.origin_check_timeout_seconds))
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


def _probe_sql(source, secrets: dict, app, text: str,
               columns_expected: list[str] | None) -> dict:
    """Run the query once with `LIMIT 0` on a kind that is not PostgreSQL (feature 061).

    Same question as the PostgreSQL probe — does it parse, and which columns does it return — with
    whatever the driver says about the types. A driver error is reported as it came."""
    params = {"window_start": datetime.now(UTC) - timedelta(days=CHECK_WINDOW_DAYS),
              "window_end": datetime.now(UTC)}
    timeout = max(1, math.ceil(app.origin_check_timeout_seconds))
    wrapped = f"SELECT * FROM (\n{text}\n) AS q LIMIT 0"
    try:
        columns, _rows = extract.sql_all(source.kind, source.settings, secrets, app, wrapped,
                                        params, timezone="UTC", time_limit_s=timeout)
    except Exception as e:
        detail = str(e).splitlines()[0][:200] if str(e) else type(e).__name__
        return {"ok": False, "error": detail, "columns": [], "missing": [], "extra": []}
    out = [{"name": name, "type": ""} for name in columns]
    expected = list(columns_expected or [])
    return {"ok": True, "error": None, "columns": out,
            "missing": [c for c in expected if c not in columns],
            "extra": [c for c in columns if c not in expected]}


def _run_check_request(source, secrets: dict, app, text: str,
                       columns_expected: list[str] | None) -> dict:
    shape = {"ok": False, "error": None, "records": 0, "fields": [], "missing": [],
             "missing_columns": [], "keys": [], "timestamp_units": {}, "unit_mismatch": []}
    if source.kind == registry.SOAP:
        return {**shape, "ok": True,
                "skipped": "no comprobable (fuente SOAP)",
                "note": ("Las peticiones SOAP no se comprueban; "
                         "se validarán al ejecutar la integración.")}
    if registry.request_rows(source.kind) is None or not source.settings.get("base_url"):
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
        if not page.get("size_param") and source.kind == registry.SUPABASE:
            extra["limit"] = 1
    end = datetime.now(UTC)
    start = end - timedelta(days=CHECK_WINDOW_DAYS)
    params = {"window_start": start, "window_end": end}
    timeout = max(1, math.ceil(app.origin_check_timeout_seconds))

    def _fetch(req: dict, req_params: dict) -> tuple[Any, dict]:
        if source.kind == registry.SUPABASE:
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
        ctx = engine.direct_context(rid, doc)
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
            1, min(int(runner.timeout_seconds), math.ceil(app.origin_check_timeout_seconds))
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
