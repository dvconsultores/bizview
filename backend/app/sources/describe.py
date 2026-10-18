"""Structure of a data source for spec authors (feature 005, research R8): never values.

- PostgreSQL: schemas, tables/views, columns (type, nullable), primary keys, estimated rows.
- REST: the JSON *shape* of one GET on a relative path (keys and value types; values dropped).
- SOAP: services, ports, operations and their input/output signatures from the WSDL.
"""
from urllib.parse import urljoin

import httpx

from app.config import Settings
from app.engine.extract import ExtractError, _pg_connect, same_origin
from app.i18n import t
from app.security import profile
from app.security.netguard import guarded_client, policy_from_settings
from app.sources.connectors import rest, soap
from app.sources.connectors.base import temp_pem

MAX_TABLES, MAX_COLUMNS, MAX_OPERATIONS, MAX_DEPTH = 500, 200, 200, 6


def postgresql(settings: dict, secrets: dict, app: Settings) -> dict:
    with _pg_connect(settings, secrets, app, timezone="UTC", time_limit_s=30) as conn:
        tables = conn.execute(
            "SELECT n.nspname, c.relname, c.relkind, greatest(c.reltuples, 0)::bigint "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE c.relkind IN ('r', 'v', 'm', 'p', 'f') "
            "AND n.nspname NOT IN ('pg_catalog', 'information_schema') "
            "AND n.nspname NOT LIKE 'pg_toast%%' AND n.nspname NOT LIKE 'pg_temp%%' "
            "AND has_table_privilege(c.oid, 'SELECT') "
            "ORDER BY 1, 2 LIMIT %s", (MAX_TABLES + 1,)).fetchall()
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
    cols: dict[tuple, list] = {}
    for schema, table, name, dtype, nullable in columns:
        cols.setdefault((schema, table), []).append(
            {"name": name, "type": dtype, "nullable": nullable})
    pks: dict[tuple, list] = {}
    for schema, table, name in keys:
        pks.setdefault((schema, table), []).append(name)
    kinds = {"r": "table", "p": "table", "v": "view", "m": "materialized_view",
             "f": "foreign_table"}
    out = [{"schema": s, "name": t, "kind": kinds[k], "estimated_rows": n,
            "primary_key": pks.get((s, t), []), "columns": cols.get((s, t), [])[:MAX_COLUMNS]}
           for s, t, k, n in tables[:MAX_TABLES]]
    return {"kind": "postgresql", "tables": out, "truncated": len(tables) > MAX_TABLES}


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
             path: str | None = None) -> dict:
    try:
        if kind == "postgresql":
            return postgresql(settings, secrets, app)
        if kind == "rest":
            return rest_shape(settings, secrets, app, path)
        if kind == "soap":
            return soap_operations(settings, secrets, app)
        if kind == "supabase":
            return supabase(settings, secrets, app, path)
    except httpx.HTTPError as e:
        raise ExtractError(f"error de red: {type(e).__name__}") from None
    raise ExtractError("tipo de fuente no soportado")
