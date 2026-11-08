"""Structure of a data source for spec authors (feature 005, research R8): never values.

- PostgreSQL: schemas, tables/views, columns (type, nullable), primary keys, estimated rows.
- REST: the JSON *shape* of one GET on a relative path (keys and value types; values dropped).
- SOAP: services, ports, operations and their input/output signatures from the WSDL.
"""
from urllib.parse import urljoin

import httpx

from app.config import Settings
from app.engine import source_slots
from app.engine.extract import ExtractError, _pg_connect, same_origin
from app.i18n import t
from app.security import profile
from app.security.netguard import guarded_client, policy_from_settings
from app.sources.connectors import rest, soap
from app.sources.connectors.base import temp_pem

MAX_TABLES, MAX_COLUMNS, MAX_OPERATIONS, MAX_DEPTH = 500, 200, 200, 6


def _slot_key(name: str | None, settings: dict) -> str:
    """The lane of this source: its catalogue name, the same key a run uses (feature 060)."""
    return str(name or settings.get("host") or "describe").lower()


class _PermitSource:
    """The two things `source_slots.limit_of` reads, from a settings dict (describe has no row)."""

    def __init__(self, kind: str, settings: dict) -> None:
        self.kind = kind
        self.settings = settings
#: Feature 052: how many date columns per table get a `min`/`max` in the structure pack.
MAX_DATE_COLUMNS = 3
DATE_TYPES = {"date", "timestamp without time zone", "timestamp with time zone"}


def postgresql(settings: dict, secrets: dict, app: Settings,
               write_probe: bool = False, date_ranges: bool = False,
               name: str | None = None) -> dict:
    """Structure of a PostgreSQL source; with `write_probe`, whether the credential can write.

    The probe (048) attempts one harmless write inside a transaction that is always rolled back: a
    credential that can create a temporary table can write, whatever its grants look like on paper.

    Feature 052: each table also carries its foreign keys and, with `date_ranges`, the `min`/`max`
    of up to `MAX_DATE_COLUMNS` date columns — the two aggregates the structure pack prints. A
    range that cannot be read (permission, timeout, an unaggregatable type) is skipped: a structure
    read never fails because one column could not be summarised.
    """
    with source_slots.turn(_slot_key(name, settings),
                           source_slots.limit_of(_PermitSource("postgresql", settings))), \
            _pg_connect(settings, secrets, app, timezone="UTC", time_limit_s=30,
                        integration="describe") as conn:
        tables_query = (
            "SELECT n.nspname, c.relname, c.relkind, greatest(c.reltuples, 0)::bigint "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE c.relkind IN ('r', 'v', 'm', 'p', 'f') "
            "AND n.nspname NOT IN ('pg_catalog', 'information_schema') "
            "AND n.nspname NOT LIKE 'pg_toast%%' AND n.nspname NOT LIKE 'pg_temp%%' "
            "AND has_table_privilege(c.oid, 'SELECT') "
            "ORDER BY 1, 2 LIMIT %s")
        tables = conn.execute(tables_query, (MAX_TABLES + 1,)).fetchall()
        columns = conn.execute(
            "SELECT table_schema, table_name, column_name, data_type, is_nullable = 'YES' "
            "FROM information_schema.columns "
            "WHERE table_schema NOT IN ('pg_catalog', 'information_schema') "
            "ORDER BY table_schema, table_name, ordinal_position").fetchall()
        keys = conn.execute(
            "SELECT tc.table_schema, tc.table_name, kcu.column_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "ON kcu.constraint_name = tc.constraint_name AND kcu.table_schema = tc.table_schema "
            "WHERE tc.constraint_type = 'PRIMARY KEY' ORDER BY kcu.ordinal_position").fetchall()
        foreign = conn.execute(
            "SELECT tc.table_schema, tc.table_name, kcu.column_name, "
            "ccu.table_name, ccu.column_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "ON kcu.constraint_name = tc.constraint_name AND kcu.table_schema = tc.table_schema "
            "JOIN information_schema.constraint_column_usage ccu "
            "ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema "
            "WHERE tc.constraint_type = 'FOREIGN KEY'").fetchall()
        cols: dict[tuple, list] = {}
        for schema, table, name, dtype, nullable in columns:
            cols.setdefault((schema, table), []).append(
                {"name": name, "type": dtype, "nullable": nullable})
        ranges = _date_ranges(conn, tables[:MAX_TABLES], cols) if date_ranges else {}
    pks: dict[tuple, list] = {}
    for schema, table, name in keys:
        pks.setdefault((schema, table), []).append(name)
    fks: dict[tuple, list] = {}
    for schema, table, column, ref_table, ref_column in foreign:
        fks.setdefault((schema, table), []).append(
            {"column": column, "references": f"{ref_table}.{ref_column}"})
    kinds = {"r": "table", "p": "table", "v": "view", "m": "materialized_view",
             "f": "foreign_table"}
    out = []
    for schema, table, relkind, rows in tables[:MAX_TABLES]:
        table_columns = [dict(c) for c in cols.get((schema, table), [])[:MAX_COLUMNS]]
        for column in table_columns:
            span = ranges.get((schema, table), {}).get(column["name"])
            if span:
                column["range"] = span
        out.append({"schema": schema, "name": table, "kind": kinds[relkind],
                    "estimated_rows": rows, "primary_key": pks.get((schema, table), []),
                    "foreign_keys": fks.get((schema, table), []), "columns": table_columns})
    report = {"kind": "postgresql", "tables": out, "truncated": len(tables) > MAX_TABLES}
    if write_probe:
        report["write_allowed"] = _write_probe(settings, secrets, app, name)
    return report


def _ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _date_ranges(conn, tables, cols: dict[tuple, list]) -> dict[tuple, dict[str, dict]]:
    """`min`/`max` of the date columns of each table, at most `MAX_DATE_COLUMNS` of them."""
    out: dict[tuple, dict[str, dict]] = {}
    for schema, table, _kind, _rows in tables:
        picks = [c for c in cols.get((schema, table), [])
                 if str(c["type"]).lower() in DATE_TYPES][:MAX_DATE_COLUMNS]
        for column in picks:
            ident = _ident(column["name"])
            try:
                with conn.transaction():
                    row = conn.execute(
                        f"SELECT min({ident})::text, max({ident})::text "
                        f"FROM {_ident(schema)}.{_ident(table)}").fetchone()
            except Exception:
                continue
            if row and (row[0] or row[1]):
                out.setdefault((schema, table), {})[column["name"]] = {"min": row[0],
                                                                      "max": row[1]}
    return out


def _write_probe(settings: dict, secrets: dict, app: Settings,
                 name: str | None = None) -> bool:
    """True when the credential managed to write. The table is never created: always rolled back."""
    with source_slots.turn(_slot_key(name, settings),
                           source_slots.limit_of(_PermitSource("postgresql", settings))), \
            _pg_connect(settings, secrets, app, timezone="UTC", time_limit_s=30,
                        integration="describe") as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                cur.execute("CREATE TEMP TABLE bizview_write_probe (id int)")
            return True
        except Exception:
            return False
        finally:
            try:
                conn.rollback()
            except Exception:
                pass


def shape(value, depth: int = 0):
    """Keys and types of a JSON value; list items merged; no values kept."""
    if depth >= MAX_DEPTH:
        return "…"
    if isinstance(value, dict):
        return {k: shape(v, depth + 1) for k, v in list(value.items())[:100]}
    if isinstance(value, list):
        merged: dict | str | None = None
        for item in value[:20]:
            s = shape(item, depth + 1)
            merged = {**merged, **s} if isinstance(merged, dict) and isinstance(s, dict) else s
        return [merged] if merged is not None else []
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if value is None:
        return "null"
    return "string"


def rest_shape(settings: dict, secrets: dict, app: Settings, path: str | None) -> dict:
    rel, data = _rest_json(settings, secrets, app, path)
    return {"kind": "rest", "path": "/" + rel, "shape": shape(data)}


def supabase(settings: dict, secrets: dict, app: Settings, path: str | None) -> dict:
    """Supabase (feature 016): tables and columns from the API's own description (structure
    only); with `path`, the shape of that endpoint's response like a REST source."""
    from app.sources.connectors import supabase as sb
    rest_settings, rest_secrets = sb.rest_settings(settings), sb.rest_secrets(secrets)
    if path:
        rel, data = _rest_json(rest_settings, rest_secrets, app, path)
        return {"kind": "supabase", "path": "/" + rel, "shape": shape(data)}
    _rel, spec = _rest_json(rest_settings, rest_secrets, app, None)
    return {"kind": "supabase", **openapi_tables(spec)}


def openapi_tables(spec) -> dict:
    """Tables/views and their columns from a PostgREST OpenAPI description: names, types,
    nullability and primary keys only (no defaults, comments or examples)."""
    definitions = spec.get("definitions") if isinstance(spec, dict) else None
    if not isinstance(definitions, dict):
        raise ExtractError(t("sources.no_table_description"))
    tables = []
    for name in sorted(definitions)[:MAX_TABLES]:
        d = definitions[name] if isinstance(definitions[name], dict) else {}
        props = d.get("properties") if isinstance(d.get("properties"), dict) else {}
        required = set(d.get("required") or [])
        columns, pk = [], []
        for col, p in list(props.items())[:MAX_COLUMNS]:
            p = p if isinstance(p, dict) else {}
            columns.append({"name": col, "type": p.get("format") or p.get("type") or "unknown",
                            "nullable": col not in required})
            if "<pk/>" in str(p.get("description") or ""):
                pk.append(col)
        tables.append({"name": name, "primary_key": pk, "columns": columns})
    return {"tables": tables, "truncated": len(definitions) > MAX_TABLES}


def _rest_json(settings: dict, secrets: dict, app: Settings, path: str | None):
    if profile.url_problem(settings["base_url"], app):
        raise ExtractError("la fuente requiere HTTPS en el perfil de seguridad actual")
    rel = (path or settings.get("test_path") or "/").lstrip("/")
    if "://" in rel or rel.startswith("/"):
        raise ExtractError("la ruta debe ser relativa a la URL base de la fuente")
    base = settings["base_url"].rstrip("/") + "/"
    url = same_origin(base, urljoin(base, rel))
    with guarded_client(policy=policy_from_settings(app), timeout=30,
                        verify=rest._verify(settings)) as client:
        headers, params, auth = rest.build_request(settings, secrets, client)
        with client.stream("GET", url, headers=headers, params=params, auth=auth) as r:
            body = rest._read_limited(r)
            status = r.status_code
    if status >= 300:
        raise ExtractError(t("sources.http_status", status=status))
    try:
        import json
        data = json.loads(body)
    except ValueError:
        raise ExtractError("la respuesta no es JSON (o supera 1 MB)") from None
    return rel, data


def soap_operations(settings: dict, secrets: dict, app: Settings) -> dict:
    if profile.url_problem(settings["wsdl_url"], app):
        raise ExtractError("la fuente requiere HTTPS en el perfil de seguridad actual")
    with temp_pem(settings.get("client_certificate")) as cert_path, \
            temp_pem(secrets.get("client_key")) as key_path:
        cert = (cert_path, key_path) if cert_path and key_path else None
        http_client = guarded_client(policy=policy_from_settings(app), timeout=30,
                                     verify=rest._verify(settings), cert=cert)
    with http_client:
        client = soap.build_client(settings, secrets, app, http_client)
        services, count = [], 0
        for service in client.wsdl.services.values():
            ports = []
            for port in service.ports.values():
                ops = []
                for name, op in sorted(port.binding._operations.items()):
                    if count >= MAX_OPERATIONS:
                        break
                    count += 1
                    ops.append({"name": name,
                                "input": op.input.signature() if op.input else None,
                                "output": op.output.signature(as_output=True)
                                if op.output else None})
                ports.append({"name": port.name, "operations": ops})
            services.append({"name": service.name, "ports": ports})
    return {"kind": "soap", "services": services}


def describe(kind: str, settings: dict, secrets: dict, app: Settings,
             path: str | None = None, write_probe: bool = False,
             date_ranges: bool = False, name: str | None = None) -> dict:
    """The structure of any kind; which module answers is the registry's business (feature 061)."""
    from app.sources.connectors import registry

    if kind not in registry.BY_KIND:
        raise ExtractError("tipo de fuente no soportado")
    try:
        return registry.describe(kind, settings, secrets, app, path=path,
                                 write_probe=write_probe, date_ranges=date_ranges, name=name)
    except httpx.HTTPError as e:
        raise ExtractError(f"error de red: {type(e).__name__}") from None
