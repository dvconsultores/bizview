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
from pathlib import Path

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


#: Terms that make a table's rows people: a bare `name`/`nombre` is a person's name only there
#: (a coin, product or category name is data, not personal data).
_PEOPLE = {
    "customer", "customers", "client", "clients", "cliente", "clientes",
    "user", "users", "usuario", "usuarios", "person", "persons", "persona", "personas",
    "patient", "patients", "paciente", "pacientes", "contact", "contacts", "contacto",
    "contactos", "employee", "employees", "empleado", "empleados", "staff", "member",
    "members", "miembro", "miembros", "subscriber", "subscribers", "suscriptor",
    "suscriptores", "lead", "leads", "prospect", "prospects", "owner", "titular",
    "beneficiary", "beneficiario", "beneficiarios", "driver", "conductor",
    "student", "estudiante", "estudiantes", "citizen", "ciudadano", "afiliado", "afiliados",
    "associate", "socio", "socios", "supplier", "suppliers", "proveedor", "proveedores",
    "vendor", "vendedor", "vendedores", "agent", "agente", "agentes",
}
_AMBIGUOUS = {"name", "names", "nombre", "nombres"}


def is_personal(column: str, context: str | None = None) -> bool:
    """Whether a column name looks like personal data (heuristic, FR-001).

    `context` is the table or dataset the column belongs to; it decides `name`/`nombre`, personal
    only where the rows are people."""
    name = str(column or "").strip().lower()
    if not name:
        return False
    if re.search(r"chat[_-]?id", name) or "telegram" in name or "whatsapp" in name:
        return True
    tokens = [t for t in re.split(r"[^a-z0-9]+", name) if t]
    for token in tokens:
        if token in _EXACT:
            if token in _AMBIGUOUS and not (
                len(tokens) > 1 or _about_people(context)
            ):
                continue
            return True
        if len(token) > 4 and any(token.startswith(p) for p in _PREFIXES):
            return True
    return False


def _about_people(context: str | None) -> bool:
    if not context:
        return False
    return bool({t for t in re.split(r"[^a-z0-9]+", str(context).lower()) if t} & _PEOPLE)


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
    if out.get("kind") not in SQL_KINDS:
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


#: The dialects whose structure is tables and columns (feature 061 adds five). The renderer is one:
#: what differs between them is the heading, the default schema and the dialect notes.
SQL_KINDS = ("postgresql", "mysql", "mssql", "sqlite", "bigquery", "sheets")
SQL_HEADINGS = {"postgresql": "PostgreSQL", "mysql": "MySQL / MariaDB", "mssql": "SQL Server",
                "sqlite": "SQLite", "bigquery": "Google BigQuery", "sheets": "Google Sheets"}


def _sql_lines(body: dict, out: list[str], kind: str) -> None:
    out.append(f"## {SQL_HEADINGS.get(kind, kind)}")
    out.append("")
    dialect = body.get("dialect") or {}
    if dialect.get("notes"):
        out.append(f"Dialecto: {_cell(dialect['notes'])}")
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
    if kind in SQL_KINDS:
        _sql_lines(body, out, kind)
    elif kind in ("rest", "supabase"):
        _rest_lines(body, out)
    elif kind == "soap":
        _soap_lines(body, out)
    _observations(pack, out)
    return "\n".join(out).rstrip("\n") + "\n"


# --- the generated pack (feature 052, convergence 2026-11-03) ---------------------------------
#
# `structure.json` may be the *generated* document of `schemas/structure.schema.json`: the scan of
# the source, optionally enriched by an internal AI pass and always verified against that scan. One
# schema (shipped with this package and copied into the authoring pack) and one renderer, so the
# product, the CLI and the author's AI read the same contract.

ENRICHED_VERSION = 1
SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "structure.schema.json"


def enriched_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_enriched(doc) -> list[str]:
    """Problems of a generated pack, empty when it is valid (`file: message`)."""
    from jsonschema import Draft202012Validator

    problems: list[str] = []
    validator = Draft202012Validator(enriched_schema())
    for error in sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path)):
        where = "/".join(str(p) for p in error.absolute_path) or "structure"
        problems.append(f"{where}: {error.message}")
    return problems


def is_enriched(doc) -> bool:
    """Whether a `structure.json` is a generated pack (rather than the plain describe wrapper)."""
    return isinstance(doc, dict) and "generator" in doc and "tables" in doc \
        and not isinstance(doc.get("pack"), dict)


def enriched_json(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


_SEMANTIC_ES = {
    "identifier": "identificador", "reference": "referencia", "name": "nombre",
    "amount": "importe", "quantity": "cantidad", "percentage": "porcentaje",
    "timestamp": "fecha y hora", "date": "fecha", "category": "categoría", "flag": "indicador",
    "url": "URL", "image_url": "URL de imagen", "text": "texto", "unknown": "",
}


def enriched_markdown(doc: dict) -> str:
    """`structure.md` rendered from a generated pack — never written by the AI itself.

    Same sections and order as the pack template (`sources/<nombre>/structure.md`): the header line,
    then one block per table with its field table, then the relations, the suggested metrics and the
    observations. Sections that do not apply are omitted, as the template instructs.
    """
    notes = " ".join(str(doc.get("notes") or "").split()) or "—"
    generator = doc.get("generator") or {}
    how = "escaneo" if generator.get("mode") != "ai" else f"IA ({generator.get('model') or '—'})"
    out = [f"# Fuente «{doc.get('source')}» — estructura", "",
           f"Tipo: {doc.get('kind')} · Zona horaria de los datos: UTC · Notas: {notes}", "",
           f"Generado: {doc.get('generated_at')} · {how} · formato {generator.get('version', 1)}",
           ""]
    kind = doc.get("kind")
    tables = doc.get("tables") or []
    if kind == "soap":
        out.append("## SOAP")
        out.append("")
    elif kind in SQL_KINDS:
        out.append(f"## {SQL_HEADINGS.get(kind, kind)}")
        out.append("")
    else:
        out.append("## REST")
        out.append("")
        out.append("Base: configurada en Bizview (no se incluye) · Autenticación: gestionada por "
                   "Bizview")
        out.append("")

    schemas: dict[str, list] = {}
    for table in tables:
        schemas.setdefault(str(table.get("schema") or ("public" if kind == "postgresql" else "")),
                           []).append(table)
    for schema in sorted(schemas):
        if schema:
            out.append(f"### Esquema `{schema}`")
            out.append("")
        for table in schemas[schema]:
            heading = f"#### Tabla `{table.get('id')}`"
            if table.get("path"):
                heading += f" — GET `{table.get('path')}`"
            if table.get("row_count") is not None:
                heading += f" — ~{int(table['row_count'])} filas"
            if table.get("date_field"):
                heading += f" · fecha: `{table['date_field']}`"
            out.append(heading)
            out.append("")
            if table.get("row_is"):
                out.append(f"Una fila es {table['row_is']}.")
                out.append("")
            if table.get("params") or table.get("records") or table.get("pagination"):
                details = []
                if table.get("params"):
                    details.append("Params: " + ", ".join(
                        f"`{_cell(k)}={_cell(v)}`" for k, v in table["params"].items()))
                if table.get("records"):
                    details.append(f"`records: \"{_cell(table['records'])}\"`")
                pager = (table.get("pagination") or {}).get("type")
                if pager:
                    details.append(f"Paginación: {_cell(pager)}")
                out.append(" · ".join(details))
                out.append("")
            out.append("| Campo | Tipo | Clave | Personal | Nota |")
            out.append("|---|---|---|---|---|")
            keys = {str(k) for k in table.get("key") or []}
            personal = {str(p) for p in table.get("personal") or []
                        if isinstance(table.get("personal"), list)}
            for field in table.get("fields") or []:
                note = " · ".join(p for p in (
                    _SEMANTIC_ES.get(str(field.get("semantic") or ""), ""),
                    f"unidad {field['unit']}" if field.get("unit") else "",
                    str(field["units"]) if field.get("units") else "",
                    str(field.get("note") or "")) if p)
                is_personal = bool(field.get("personal")) or str(field.get("name")) in personal
                out.append("| " + " | ".join([
                    _cell(field.get("name")), _cell(field.get("type")),
                    "PK" if str(field.get("name")) in keys else "",
                    "**sí**" if is_personal else "", _cell(note)]) + " |")
            out.append("")
            for note in table.get("notes") or []:
                out.append(f"- {_cell(note)}")
            if table.get("notes"):
                out.append("")

    relations = doc.get("relations") or []
    if relations:
        out.append("## Relaciones")
        out.append("")
        for relation in relations:
            extra = f" ({relation['confidence']})" if relation.get("confidence") else ""
            out.append(f"- `{_cell(relation.get('from'))}` → `{_cell(relation.get('to'))}`: "
                       f"{_cell(relation.get('kind'))}{extra}")
        out.append("")

    metrics = doc.get("suggested_metrics") or []
    if metrics:
        out.append("## Métricas sugeridas")
        out.append("")
        out.append("Calculables con lo que esta estructura trae; son sugerencias, no un contrato.")
        out.append("")
        for metric in metrics:
            out.append(f"- `{_cell(metric.get('id'))}` (desde `{_cell(metric.get('from'))}`): "
                       f"{_cell(metric.get('formula_words'))}")
        out.append("")

    observations = [line.strip(" -") for line in str(doc.get("notes") or "").splitlines()
                   if line.strip()]
    generated = []
    if doc.get("bi_ready"):
        generated.append("Fuente declarada BI-ready: los reportes pueden leerla en vivo.")
    dropped = doc.get("dropped") or []
    if dropped:
        generated.append(f"La verificación descartó {len(dropped)} elemento(s) del resultado del "
                         "modelo: " + "; ".join(_cell(d) for d in dropped[:20]) +
                         ("" if len(dropped) <= 20 else "…"))
    incomplete = (generator.get("incomplete") or [])
    if incomplete:
        generated.append("No se examinaron por el tope de la corrida: " +
                         ", ".join(_cell(i) for i in incomplete[:20]) + ".")
    if not (observations or generated):
        generated.append("Sin observaciones.")
    out.append("## Observaciones")
    out.append("")
    for line in observations + generated:
        out.append(f"- {line}")
    out.append("")
    return "\n".join(out).rstrip("\n") + "\n"
