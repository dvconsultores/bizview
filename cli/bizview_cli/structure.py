"""The structure pack of a data source: `structure.md` + `structure.json` (feature 052).

One generator for the three callers — `bizview describe --pack`, `GET
/api/sources/{name}/structure?format=`, and the authoring pack — because two generators drift. The
reference format is `pack/bizview-starter-pack/bizview-starter/sources/<nombre>/structure.md`; when
this module and that template disagree, the template wins and this module is wrong.

Structure only: names, types, keys, counts, date ranges and the personal-data flag. Never a row
value, a host, a credential or a connection string.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import UTC, datetime

PACK_VERSION = 1

#: Column-name terms that make a column personal by heuristic (FR-001). The super user overrides
#: any of them per column, and the override travels here as `flags`.
_EXACT = {
    "email", "emails", "correo", "correos", "mail", "telefono", "telefonos", "celular",
    "celulares", "movil", "moviles", "documento", "documentos", "cedula", "cedulas", "dni",
    "rut", "pasaporte", "pasaportes", "apellido", "apellidos", "nombre", "nombres", "name",
    "names",
}
_PREFIXES = ("email", "correo", "telefono", "celular", "documento", "cedula", "pasaporte",
             "apellido", "nombre", "direccion", "address", "phone", "surname", "names")

_ISO = re.compile(
    r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?$")
_PAGINATION_KEYS = ("next", "next_page", "next_cursor", "cursor", "page", "offset", "total",
                    "total_count", "has_more", "pages", "count")


def is_personal(column: str) -> bool:
    """Whether a column name looks like personal data (heuristic, FR-001)."""
    name = str(column or "").strip().lower()
    if not name:
        return False
    if re.search(r"chat[_-]?id", name) or "telegram" in name or "whatsapp" in name:
        return True
    for token in (t for t in re.split(r"[^a-z0-9]+", name) if t):
        if token in _EXACT:
            return True
        if len(token) > 4 and any(token.startswith(p) for p in _PREFIXES):
            return True
    return False


def infer_timestamp_units(value) -> str | None:
    """`iso8601`, `epoch_s` or `epoch_ms` from one sample value; None when it is not a date.

    The *format* is what the pack carries: the value itself is a row value and never leaves.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if 1e9 <= value < 1e11:
            return "epoch_s"
        if 1e12 <= value < 1e14:
            return "epoch_ms"
        return None
    if isinstance(value, str) and _ISO.match(value.strip()):
        return "iso8601"
    return None


def _first_array_path(node, path: str = "$", depth: int = 0):
    """The path of the first array of objects in a shape, and the object's shape."""
    if depth > 8:
        return None
    if isinstance(node, dict):
        for key, value in node.items():
            found = _first_array_path(value, f"{path}.{key}", depth + 1)
            if found:
                return found
        return None
    if isinstance(node, list) and node and isinstance(node[0], dict):
        return path, node[0]
    return None


def _type_of(shape_value) -> str:
    if isinstance(shape_value, dict):
        return "object"
    if isinstance(shape_value, list):
        return "array"
    return str(shape_value)


def suggest(shape) -> dict:
    """`records`, `fields` and their types, from a response shape (FR-002).

    `fields` follows the request contract: column name → JSONPath *inside each record* (`$.id`),
    which is what `integrations/<id>/requests/*.yaml` expects. `types` keeps the shape's own types
    so the markdown table can print them.
    """
    found = _first_array_path(shape)
    if not found:
        if isinstance(shape, dict):
            return {"records": "$", "fields": {k: f"$.{k}" for k in shape},
                    "types": {k: _type_of(v) for k, v in shape.items()}}
        return {"records": None, "fields": {}, "types": {}}
    path, first = found
    return {"records": path, "fields": {k: f"$.{k}" for k in first},
            "types": {k: _type_of(v) for k, v in first.items()}}


def pagination_hint(shape) -> str | None:
    """The pagination key the response seems to use, from keys the product already knows."""
    if not isinstance(shape, dict):
        return None
    for key in shape:
        if str(key).lower() in _PAGINATION_KEYS:
            return str(key).lower()
    found = _first_array_path(shape)
    if found and isinstance(shape, dict):
        for value in shape.values():
            if isinstance(value, dict):
                hint = pagination_hint(value)
                if hint:
                    return hint
    return None


def _flag_key(table: dict, column: str) -> str:
    prefix = f"{table.get('schema')}.{table.get('name')}" if table.get("schema") else \
        str(table.get("name"))
    return f"{prefix}.{column}".lower()


def _apply_personal(structure: dict, flags: dict[str, bool]) -> dict:
    """Stamp `personal` on every column: the override when there is one, the heuristic otherwise."""
    out = copy.deepcopy(structure)
    if out.get("kind") != "postgresql":
        return out
    for table in out.get("tables") or []:
        for column in table.get("columns") or []:
            name = str(column.get("name", ""))
            override = flags.get(_flag_key(table, name))
            column["personal"] = bool(override) if override is not None else is_personal(name)
    return out


def build_pack(structure: dict, *, source: str, kind: str, notes: str = "",
               bi_ready: dict | None = None, timezone: str = "UTC",
               flags: dict[str, bool] | None = None, samples: list[dict] | None = None,
               generated_at: datetime | None = None) -> dict:
    """The two files' content, as one object: a `pack` header and the describe `structure`."""
    body = _apply_personal(structure, flags or {})
    if samples is not None and body.get("kind") in ("rest", "supabase"):
        body["samples"] = copy.deepcopy(samples)
    return {
        "pack": {
            "version": PACK_VERSION,
            "source": source,
            "kind": kind,
            "generated_at": (generated_at or datetime.now(UTC)).isoformat(),
            "timezone": timezone or "UTC",
            "bi_ready": bool((bi_ready or {}).get("enabled")),
            "bi_ready_scopes": list((bi_ready or {}).get("schemas") or []),
            "notes": notes or "",
            "truncated": bool(body.get("truncated")),
        },
        "structure": body,
    }


def structure_json(pack: dict) -> str:
    return json.dumps(pack, indent=2, ensure_ascii=False) + "\n"


def _cell(text) -> str:
    return str(text if text is not None else "").replace("|", r"\|").replace("\n", " ").strip()


def _params(sample: dict) -> str:
    params = sample.get("params") or {}
    if not params:
        return "ninguno"
    return ", ".join(f"`{_cell(k)}={_cell(v)}`" for k, v in list(params.items())[:20])


def _postgresql_lines(body: dict, out: list[str]) -> None:
    out.append("## PostgreSQL")
    out.append("")
    schemas: dict[str, list] = {}
    for table in body.get("tables") or []:
        schemas.setdefault(str(table.get("schema") or "public"), []).append(table)
    for schema in sorted(schemas):
        out.append(f"### Esquema `{_cell(schema)}`")
        out.append("")
        for table in schemas[schema]:
            rows = int(table.get("estimated_rows") or 0)
            heading = f"#### Tabla `{_cell(table.get('name'))}` — ~{rows} filas"
            dated = [c for c in table.get("columns") or [] if c.get("range")]
            if dated:
                first = dated[0]
                span = first["range"]
                heading += (f" · fecha: `{_cell(first.get('name'))}` "
                            f"({_cell(span.get('min'))} → {_cell(span.get('max'))})")
            out.append(heading)
            out.append("")
            out.append("| Columna | Tipo | Nulo | Clave | Personal | Nota |")
            out.append("|---|---|---|---|---|---|")
            fks = {str(fk.get("column")): str(fk.get("references"))
                   for fk in table.get("foreign_keys") or []}
            pks = [str(k) for k in table.get("primary_key") or []]
            for column in table.get("columns") or []:
                name = str(column.get("name"))
                key = "PK" if name in pks else (f"FK → {fks[name]}" if name in fks else "")
                unit = ""
                if column.get("range"):
                    unit = "fecha"
                out.append("| " + " | ".join([
                    _cell(name), _cell(column.get("type")),
                    "sí" if column.get("nullable") else "no", _cell(key),
                    "**sí**" if column.get("personal") else "", _cell(unit)]) + " |")
            out.append("")


def _rest_lines(body: dict, out: list[str]) -> None:
    out.append("## REST")
    out.append("")
    out.append("Base: configurada en Bizview (no se incluye) · Autenticación: gestionada por "
               "Bizview")
    out.append("")
    samples = body.get("samples") or []
    if not samples and body.get("path"):
        samples = [{"name": body.get("path"), "method": "GET", "path": body.get("path"),
                    "shape": body.get("shape")}]
    for sample in samples:
        out.append(f"### Petición `{_cell(sample.get('name'))}` — "
                   f"{_cell(sample.get('method') or 'GET')} `{_cell(sample.get('path'))}`")
        out.append("")
        units = sample.get("timestamp_units")
        pagination = sample.get("pagination")
        out.append(f"Params: {_params(sample)}. Paginación: "
                   f"{_cell(pagination) if pagination else 'ninguna'}.")
        records = sample.get("records")
        out.append(f"`records: \"{_cell(records)}\"`." if records else "`records`: no detectado.")
        fields = sample.get("fields") or {}
        types = sample.get("types") or {}
        if fields:
            out.append("Campos por elemento:")
            out.append("")
            out.append("| JSONPath | Tipo | Nota |")
            out.append("|---|---|---|")
            for column, path in fields.items():
                ftype = types.get(column, "")
                note = ""
                if units and str(path).lower().endswith(
                        ("date", "time", "updated", "created", "at", "timestamp")):
                    note = f"fecha ({units})"
                out.append(f"| `{_cell(path)}` | {_cell(ftype)} | {_cell(note)} |")
            out.append("")
        if sample.get("error"):
            out.append(f"La petición falló al generarse: {_cell(sample['error'])}.")
            out.append("")


def _soap_lines(body: dict, out: list[str]) -> None:
    out.append("## SOAP")
    out.append("")
    for service in body.get("services") or []:
        for port in service.get("ports") or []:
            for operation in port.get("operations") or []:
                out.append(f"Operación `{_cell(operation.get('name'))}`: "
                           f"entrada `{_cell(operation.get('input') or '—')}`, "
                           f"salida `{_cell(operation.get('output') or '—')}`.")
    out.append("")


def _observations(pack: dict, out: list[str]) -> None:
    header, body = pack["pack"], pack["structure"]
    notes = [line.strip(" -") for line in str(header.get("notes") or "").splitlines()
             if line.strip()]
    generated = []
    if header.get("truncated"):
        generated.append("El catálogo se truncó: no caben todas las tablas de la fuente.")
    personal = [f"`{_cell(t.get('name'))}.{_cell(c.get('name'))}`"
                for t in body.get("tables") or []
                for c in t.get("columns") or [] if c.get("personal")]
    if personal:
        generated.append("Datos personales: " + ", ".join(personal[:50]) +
                         ("" if len(personal) <= 50 else f" y {len(personal) - 50} más") + ".")
    if header.get("bi_ready"):
        scopes = ", ".join(str(s) for s in header.get("bi_ready_scopes") or []) or "sin esquemas"
        generated.append(f"Fuente declarada BI-ready; los reportes pueden leer: {scopes}.")
    if not (notes or generated):
        generated.append("Sin observaciones.")
    out.append("## Observaciones")
    out.append("")
    for line in notes + generated:
        out.append(f"- {line}")
    out.append("")


def structure_markdown(pack: dict) -> str:
    """`structure.md`, following the pack template's sections and order."""
    header, body = pack["pack"], pack["structure"]
    notes = " ".join(str(header.get("notes") or "").split()) or "—"
    out = [f"# Fuente «{header.get('source')}» — estructura", "",
           f"Tipo: {header.get('kind')} · Zona horaria de los datos: "
           f"{header.get('timezone') or 'UTC'} · Notas: {notes}", ""]
    kind = body.get("kind")
    if kind == "postgresql":
        _postgresql_lines(body, out)
    elif kind in ("rest", "supabase"):
        _rest_lines(body, out)
    elif kind == "soap":
        _soap_lines(body, out)
    _observations(pack, out)
    return "\n".join(out).rstrip("\n") + "\n"
