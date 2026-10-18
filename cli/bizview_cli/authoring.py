"""Authoring contract for AI agents (feature 017, FR-001/FR-002).

Provides the stable contract summary, schema fragments, golden workspaces and template files
used by the authoring API/CLI prompts. Everything is generated from validate.SCHEMAS so the
contract and the validator cannot drift apart.
"""
from functools import cache
from importlib import resources
from typing import Any

from bizview_cli import layout, sqlsafety, validate

# Files of one project, relative to projects/<slug>/ (feature 020).
DRAFT_PATHS: tuple[str, ...] = tuple(p.strip() for p in layout.ALLOWED_TEXT.split(";"))

GOLDEN = {
    "example": "golden",
    "example-direct": "golden-direct",
    "example-supabase": "golden-supabase",
    "example-large": "golden-large",
}
GOLDEN_SOURCES = {
    "golden": "origen_ventas",
    "golden-direct": "bi",
    "golden-supabase": "origen_supabase",
    "golden-large": "origen_ventas",
}

RULES = """- Cada proyecto vive en `projects/<slug>/` con `project.yaml`.
- Las specs viven en `specs/NNN-<nombre>/` del proyecto con `spec.md`, `plan.md` y
  `tasks.md`.
- NNN = tres dígitos, consecutivos por proyecto, nunca se reutilizan.
- `spec.md` declara `**Tipo**: fuente | integracion | reporte | distribucion` (o
  `**Type**:` en inglés) y `**Status**: Approved` (o Implemented).
- La clave `spec:` de un artefacto es `specs/NNN-<nombre>` de su propio proyecto.
- Ids de integraciones, reportes y distribuciones son únicos entre todos los proyectos.
- Una spec `fuente` documenta una fuente con `**Fuente**: <nombre en Bizview>` y no
  tiene artefacto.
- `distributions/<id>.yaml` envía un reporte programado solo a roles (admin/user),
  nunca a direcciones de correo.
- attach_pdf requiere pdf.enabled en el reporte y el period debe estar permitido por
  el reporte.
- `tasks.md` debe tener todas las tareas marcadas como `- [X]`.
- El `id` del artefacto debe coincidir con el nombre de su carpeta.
- La clave `spec:` debe apuntar a la carpeta de spec existente.
- El SQL debe ser una única instrucción SELECT/WITH de solo lectura.
- Un dataset incremental debe filtrar con `:window_start` y `:window_end` y declararlos en
  `extract.params`.
- `date_column` debe ser una columna `date` o `timestamptz`.
- `date` de reporte debe ser `alias.columna` de tipo date/timestamptz.
- Métricas y dimensiones: `sql` usa `alias.columna` con funciones permitidas (sum, count,
  avg, min, max, coalesce, round, date_trunc).
- `formula` solo combina métricas que tienen `sql` con + - * / y paréntesis.
- Vistas, filtros y entradas de ai_narrative referencian métricas/dimensiones declaradas.
- Fuentes Supabase/REST: `extract: {request: requests/<x>.yaml}` con `method: GET`,
  `path: <tabla o vista>`, `params` de PostgREST (`select`, `order`,
  `and: "(fecha.gte.{window_start},fecha.lt.{window_end})"`), paginación
  `{type: offset, param: offset, size_param: limit, size: 1000}`, `records: "$"` y
  `fields` (columna -> "$.campo").
- Los checks `reconcile` solo se usan con PostgreSQL.
- Ningún archivo puede contener credenciales ni valores de filas.
- usa modo directo solo si el usuario indica que los datos ya están preparados por otro proceso; si no, crea una integración.
- el spec de un reporte directo debe incluir las cinco líneas `**Modo**: directo`,
  `**Fuente**:`, `**Tablas**:`, `**Mantenido por**:` y `**Volumen esperado**:` con texto
  en la misma línea.
- un reporte usa `uses` o `direct`, nunca ambos.
- si una tabla directa supera 5 millones de filas y no tiene un índice cuya columna
  principal sea la columna de fecha, propone una integración y un reporte con
  `materialize: daily` en lugar de modo directo.
- propon `materialize: daily` en reportes sobre conjuntos de más de 5 millones de filas
  (estimación de `profile_source` o del conjunto publicado).
- usa `transform` solo cuando la consulta de origen no puede dar la forma (fuentes
  REST/SOAP, limpieza)."""  # noqa: E501 (la regla de FR-012 va literal en una línea)


def _req_opt(schema: dict) -> tuple[list[str], list[str]]:
    """Split a schema into required and optional property names, in schema order."""
    required = schema.get("required", [])
    props = schema.get("properties", {})
    opt = [k for k in props if k not in required and k != "$schema"]
    return required, opt


def _one_of_values(schema: dict) -> list[Any] | None:
    """Enum or const values of a schema, or None when there are none."""
    if "enum" in schema:
        return schema["enum"]
    if "const" in schema:
        return [schema["const"]]
    return None


def _enum_line(schema: dict, name: str) -> str:
    values = _one_of_values(schema)
    if values is not None:
        return f"{name} en [{', '.join(map(str, values))}]"
    return name


def _dig(schema: dict, *keys: str) -> dict:
    """Walk nested schema dicts, returning {} for missing steps."""
    node = schema
    for key in keys:
        if not isinstance(node, dict):
            return {}
        node = node.get(key, {})
    return node if isinstance(node, dict) else {}


def _variant_text(branch: dict) -> str:
    """Compact human-readable rendering of a oneOf branch."""
    required = branch.get("required", [])
    props = branch.get("properties", {})
    type_prop = props.get("type", {}) if isinstance(props, dict) else {}
    const_type = None
    if isinstance(type_prop, dict) and "const" in type_prop:
        const_type = type_prop["const"]
    pieces: list[str] = []
    if const_type is not None:
        pieces.append(f"type: {const_type}")
    for key in props:
        if key == "type" and const_type is not None:
            continue
        values = _one_of_values(props[key])
        if key in required:
            if values is not None and len(values) == 1:
                pieces.append(f"{key}: {values[0]}")
            else:
                pieces.append(f"requiere {key}")
        elif values is not None:
            pieces.append(f"{key} en [{', '.join(map(str, values))}] opcional")
        else:
            pieces.append(f"{key} opcional")
    return ", ".join(pieces) if pieces else "(sin restricciones)"


def _variants(one_of: list[dict]) -> list[str]:
    return [_variant_text(b) for b in one_of]


TOPICS: dict[str, str] = {
    "index": "contrato resumido y lista de temas",
    "workspace": "esquema y reglas de bizview.yaml",
    "integration": "esquema y reglas de integrations/<id>/integration.yaml",
    "request": "esquema de integrations/<id>/requests/<x>.yaml",
    "report": "esquema y reglas de reports/<id>/report.yaml",
    "project": "esquema de project.yaml (nombre y slug del proyecto)",
    "distribution": "esquema y reglas de distributions/<id>.yaml (envíos programados por rol)",
    "spec": "reglas de spec/plan/tasks y plantillas",
    "transform": "transformación ETL en Polars: lista de funciones, modos, tipos y reglas",
    "example": "workspace golden completo (variante PostgreSQL)",
    "example-direct": "workspace golden-direct (variante reporte directo)",
    "example-supabase": "workspace golden-supabase (variante request)",
    "example-large": "workspace golden-large (transform por filas y materialize: daily)",
    "fragment:<schema>#<puntero>": "fragmento exacto de un esquema JSON (RFC 6901)",
}


TRANSFORM_AGGREGATES = frozenset({"sum", "count", "avg", "min", "max"})

TRANSFORM_RULES = """- con `transform`, `transform.input` declara las columnas que entrega la
  consulta o petición (columna -> tipo) y la consulta debe devolver exactamente esas; `columns`
  describe la salida (la tabla del dataset); primary_key, date_column y checks usan columnas
  de salida.
- la cláusula FROM debe ser `FROM input`; se rechazan JOIN, UNION/EXCEPT/INTERSECT,
  subconsultas, LIMIT/OFFSET, parámetros, nombres con esquema, funciones de tabla, FILTER en
  agregados y funciones fuera de la lista permitida; solo se ejecuta el SQL regenerado en
  Polars.
- modo rows: usa funciones por fila con WHERE; la memoria se acota con `batch_rows`
  (10000-1000000, por defecto 20000).
- modo whole: GROUP BY, HAVING, DISTINCT, ventanas, QUALIFY, ORDER BY o agregados; la ventana
  se derrama a archivos Arrow en la carpeta temporal y se procesa con el motor streaming de
  Polars; `TRANSFORM_MAX_ROWS` (por defecto 50 000 000) limita las filas de entrada.
- casting de un timestamptz a DATE se rechaza (usa la fecha UTC); usa
  `CAST(strftime(x, '%Y-%m-%d') AS DATE)` para la fecha local de la integración.
- numeric entra como DECIMAL(38, 9); más de 9 decimales se truncan, 29 o más dígitos enteros
  desbordan; ROUND de Polars difiere de PostgreSQL en mitades exactas -> redondea en las
  métricas del reporte; float en una columna numeric produce el aviso transform_float, usa
  CAST(x AS DECIMAL(38, 9)).
- usa `transform` solo cuando la consulta de origen no puede dar la forma (fuentes REST/SOAP,
  limpieza)."""

TRANSFORM_TYPES = {
    "text": {
        "entrada": "String",
        "salida": "String",
    },
    "integer": {
        "entrada": "Int32",
        "salida": "Int8/16/32, UInt8/16",
    },
    "bigint": {
        "entrada": "Int64",
        "salida": "Int8/16/32/64, UInt8/16/32",
    },
    "numeric": {
        "entrada": "Decimal(38, 9)",
        "salida": (
            "Decimal, Int*, UInt8/16/32"
            " (Float -> warning transform_float, usa CAST(x AS DECIMAL(38, 9)))"
        ),
    },
    "boolean": {
        "entrada": "Boolean",
        "salida": "Boolean",
    },
    "date": {
        "entrada": "Date",
        "salida": "Date",
    },
    "timestamptz": {
        "entrada": "Datetime(us, zona de la integración)",
        "salida": "Datetime con zona o sin zona (hora local de la integración)",
    },
}

_TRANSFORM_REPLACEMENT_SETS = {
    frozenset({"date_trunc", "timestamp_trunc"}): (
        "strftime(x, '%Y-%m-01') para mes o extract(...)"
    ),
    frozenset({"current_date", "current_timestamp", "current_time"}): (
        "no disponible; la ventana viene de :window_start/:window_end"
        " en la consulta de origen"
    ),
    frozenset({"to_date", "str_to_time"}): "strptime(x, '%Y-%m-%d') o CAST(x AS DATE)",
    frozenset({
        "median", "percentile_cont", "percentile_disc",
        "group_concat", "array_agg", "first", "last",
    }): "calcúlalo en las métricas del reporte o en la consulta de origen",
    frozenset({"random", "md5"}): "no disponible en el transform",
}
TRANSFORM_REPLACEMENTS = {
    name: replacement
    for names, replacement in sorted(
        _TRANSFORM_REPLACEMENT_SETS.items(), key=lambda item: sorted(item[0])[0]
    )
    for name in sorted(names)
}


def _transform_guide() -> dict:
    whole_only = sqlsafety.WINDOW_ONLY_FUNCTIONS | (
        sqlsafety.TRANSFORM_FUNCTIONS & TRANSFORM_AGGREGATES
    )
    schema = _dig(
        validate.SCHEMAS["integration"].schema,
        "properties",
        "datasets",
        "additionalProperties",
        "properties",
        "transform",
    )
    return {
        "topic": "transform",
        "schema": schema,
        "functions": {
            "rows": sorted(sqlsafety.TRANSFORM_FUNCTIONS - whole_only),
            "whole": sorted(whole_only),
        },
        "not_offered": sorted(sqlsafety.TRANSFORM_UNSUPPORTED),
        "replacements": TRANSFORM_REPLACEMENTS,
        "types": TRANSFORM_TYPES,
        "rules": TRANSFORM_RULES,
        "example": "example-large",
    }


def golden_root(name: str = GOLDEN["example"]):
    """Traversable root of a bundled golden workspace."""
    return resources.files("bizview_cli") / name


def golden_files(name: str = GOLDEN["example"]) -> dict[str, str]:
    """Every regular file of a golden workspace, keyed by posix path relative to its root."""
    root = golden_root(name)
    out: dict[str, str] = {}

    def walk(node, prefix: str) -> None:
        for child in sorted(node.iterdir(), key=lambda c: c.name):
            if child.name.startswith(".") or child.name == "__pycache__":
                continue
            rel = f"{prefix}/{child.name}" if prefix else child.name
            if child.is_dir():
                walk(child, rel)
            elif child.is_file():
                out[rel] = child.read_text(encoding="utf-8")

    walk(root, "")
    prefix = "projects/ejemplo/"
    if any(path.startswith(prefix) for path in out):
        # Feature 020: examples are the files of the project, relative to projects/<slug>/.
        out = {path.removeprefix(prefix): text for path, text in out.items()
               if path.startswith(prefix)}
    return out


def _workspace_summary() -> str:
    s = validate.SCHEMAS["workspace"].schema
    req, opt = _req_opt(s)
    name_schema = _dig(s, "properties", "name")
    currency = _dig(s, "properties", "currency")
    pattern = name_schema.get("pattern", "")
    currency_pattern = currency.get("pattern", "")
    return (f"- requerido: {', '.join(req)}\n"
            f"- opcional: {', '.join(opt)}\n"
            f"- name: patrón `{pattern}` (ej. facturas-dia)\n"
            "- timezone: zona IANA (ej. America/Caracas)\n"
            f"- currency: código ISO 4217, patrón `{currency_pattern}` (ej. USD)")


def _opt_part(opt: list[str], sep: str = "; ") -> str:
    """Optional-properties suffix: '' when empty, otherwise '; optional ...'."""
    return f"{sep}opcional {', '.join(opt)}" if opt else ""


def _integration_summary() -> str:
    s = validate.SCHEMAS["integration"].schema
    req, opt = _req_opt(s)
    schedule = _dig(s, "properties", "schedule")
    line = [f"- requerido: {', '.join(req)}", f"- opcional: {', '.join(opt)}"]
    line.append("- schedule.pattern: cron de 5 campos, patrón "
                f"`{schedule.get('pattern', '')}` (ej. 0 * * * *)")
    datasets = _dig(s, "properties", "datasets")
    ds_extra = datasets.get("additionalProperties", {})
    ds_req, ds_opt = _req_opt(ds_extra)
    line.append("- datasets:<id>: id con patrón "
                f"`{datasets.get('propertyNames', {}).get('pattern', '')}`; "
                f"requerido {', '.join(ds_req)}{_opt_part(ds_opt)}")
    line.append("- date_column: columna date o timestamptz (obligatoria para incremental)")
    cols = _dig(ds_extra, "properties", "columns")
    col_extra = cols.get("additionalProperties", {})
    _col_req, col_opt = _req_opt(col_extra)
    col_type = _dig(col_extra, "properties", "type")
    line.append("- columns:<columna>: requerido type; "
                f"{_enum_line(col_type, 'type')}{_opt_part(col_opt)}")
    extract = _dig(ds_extra, "properties", "extract")
    extract_variants = _variants(extract.get("oneOf", []))
    line.append("- extract: " + " | ".join(extract_variants))
    incremental = _dig(ds_extra, "properties", "incremental")
    incremental_variants = _variants(incremental.get("oneOf", []))
    line.append("- incremental: " + " | ".join(incremental_variants))
    checks = _dig(ds_extra, "properties", "checks")
    check_variants = _variants(checks.get("items", {}).get("oneOf", []))
    line.append("- checks: " + " | ".join(check_variants))
    t = _dig(ds_extra, "properties", "transform")
    treq, topt = _req_opt(t)
    batch = _dig(t, "properties", "batch_rows")
    brange = f"{batch['minimum']}-{batch['maximum']}, por defecto {batch['default']}"
    line.append(
        f"- transform: requiere {', '.join(treq)}{_opt_part(topt)} ({brange});"
        " input = columnas de la consulta/petición (columna -> {type});"
        " columns = salida; SELECT … FROM input;"
        " detalles: get_authoring_guide('transform')"
    )
    return "\n".join(line)


def _request_summary() -> str:
    s = validate.SCHEMAS["request"].schema
    req, opt = _req_opt(s)
    method = _dig(s, "properties", "method")
    pagination = _dig(s, "properties", "pagination")
    pag_req, pag_opt = _req_opt(pagination)
    pag_type = _dig(pagination, "properties", "type")
    return (f"- requerido: {', '.join(req)}\n"
            f"- opcional: {', '.join(opt)}\n"
            f"- {_enum_line(method, 'method')}\n"
            f"- pagination: requerido {', '.join(pag_req)}; type en "
            f"[{', '.join(map(str, _one_of_values(pag_type) or []))}]"
            f"{_opt_part(pag_opt)}\n"
            '- fields: columna -> ruta JSON ("$.campo")')


def _metric_summary(metric: dict) -> str:
    req, opt = _req_opt(metric)
    variant_keys = [" | ".join(branch.get("required", []))
                    for branch in metric.get("oneOf", [])]
    fmt = _dig(metric, "properties", "format")
    better = _dig(metric, "properties", "better")
    fmt_line = _enum_line(fmt, "format")
    better_line = _enum_line(better, "better")
    return (f"- métrica requerida: {', '.join(req)}; "
            f"exactamente una de: {' | '.join(variant_keys)}"
            f"{_opt_part(opt)}; {fmt_line}; {better_line}")


def _view_summary(branch: dict) -> str:
    const_type = _dig(branch, "properties", "type").get("const")
    required = branch.get("required", [])
    props = branch.get("properties", {})
    opt = [p for p in props if p != "type" and p not in required]
    req_names = [r for r in required if r != "type"]
    text = f"- vista `{const_type}`: requiere {', '.join(req_names)}"
    if opt:
        text += f"; opcional: {', '.join(opt)}"
    if "grain" in props:
        text += f"; grain en [{', '.join(map(str, _one_of_values(props['grain']) or []))}]"
    return text


def _pdf_summary(pdf: dict) -> str:
    req, opt = _req_opt(pdf)
    props = pdf.get("properties", {})
    descriptions = {
        "enabled": "enabled (booleano)",
        "orientation": None,
        "views": "views (índices de views, sin repetir, mínimo 1)",
    }
    parts = []
    for name in req + opt:
        desc = descriptions.get(name, name)
        if desc is None:
            values = _one_of_values(props.get(name, {}))
            if values is not None:
                desc = f"{name} en [{', '.join(map(str, values))}]"
            else:
                desc = name
        parts.append(desc)
    return "- pdf: " + ", ".join(parts)


def _project_summary() -> str:
    required, optional = _req_opt(validate.SCHEMAS["project"].schema)
    lines = [f"- requerido: {', '.join(required)}", f"- opcional: {', '.join(optional)}"]
    pattern = _dig(validate.SCHEMAS["project"].schema, "properties", "slug", "pattern")
    lines.append(f"- slug: patrón `{pattern}` (igual al nombre de la carpeta)")
    return "\n".join(lines)


def _distribution_summary() -> str:
    schema = validate.SCHEMAS["distribution"].schema
    required, optional = _req_opt(schema)
    lines = [f"- requerido: {', '.join(required)}", f"- opcional: {', '.join(optional)}"]
    item = _dig(schema, "properties", "subscriptions", "items")
    if item:
        req, opt = _req_opt(item)
        lines.append(f"- subscriptions[]: requerido {', '.join(req)}; opcional {', '.join(opt)}")
        freq = ", ".join(_dig(item, "properties", "frequency", "enum") or [])
        period = ", ".join(_dig(item, "properties", "period", "enum") or [])
        lines.append(f"- frequency en [{freq}]; period en [{period}]")
        lines.append("- recipients.roles en [admin, user] (nunca direcciones de correo)")
        lines.append("- weekday solo con weekly (0 = lunes); monthday solo con monthly (1-28)")
    return "\n".join(lines)


def _report_summary() -> str:
    s = validate.SCHEMAS["report"].schema
    req, opt = _req_opt(s)
    line = [f"- requerido: {', '.join(req)}", f"- opcional: {', '.join(opt)}"]
    one_of_required = [option.get("required", []) for option in s.get("oneOf", [])]
    if one_of_required:
        alternatives = " | ".join(
            ", ".join(required) for required in one_of_required
        )
        line.append(f"- exactamente uno de: {alternatives}")
    direct = _dig(s, "properties", "direct")
    direct_req, direct_opt = _req_opt(direct)
    direct_keys = ", ".join(direct_req)
    opt_parts = []
    for key in direct_opt:
        node = _dig(direct, "properties", key)
        if "minimum" in node and "maximum" in node:
            opt_parts.append(f"{key} ({node['minimum']}-{node['maximum']})")
        else:
            opt_parts.append(key)
    line.append(f"- direct: requerido {direct_keys}"
                f"{_opt_part(opt_parts)}")
    tables = _dig(direct, "properties", "tables")
    max_props = tables.get("maxProperties")
    entry = _dig(tables, "additionalProperties")
    table_req, table_opt = _req_opt(entry)
    required_text = ", ".join(table_req)
    line.append(f"- direct.tables:<alias>: máx. {max_props}; requerido {required_text}"
                f"{_opt_part(table_opt)}; table = esquema.tabla")
    metrics = _dig(s, "properties", "metrics")
    metric = metrics.get("additionalProperties", {})
    line.append(_metric_summary(metric))
    line.append("- textos en inglés opcionales: title_en, description_en, metrics.*.label_en, "
                "metrics.*.description_en, dimensions.*.label_en, views[].title_en (la interfaz "
                "en inglés los usa; si faltan muestra el texto en español)")
    views = _dig(s, "properties", "views")
    view_lines = [_view_summary(b) for b in views.get("items", {}).get("oneOf", [])]
    line.extend(view_lines)
    joins = _dig(s, "properties", "joins")
    join_type = _dig(joins, "items", "properties", "type")
    line.append(f"- {_enum_line(join_type, 'joins.type')}")
    dims = _dig(s, "properties", "dimensions")
    dim = dims.get("additionalProperties", {})
    dim_req, dim_opt = _req_opt(dim)
    line.append(f"- dimensions:<id>: requerido {', '.join(dim_req)}"
                f"{_opt_part(dim_opt)}")
    for key in ("periods", "compare"):
        node = _dig(s, "properties", key)
        default = _dig(node, "properties", "default")
        values = _one_of_values(default)
        if values is not None:
            line.append(f"- {key}: default y allowed en "
                        f"[{', '.join(map(str, values))}]")
        else:
            line.append(f"- {key}: default y allowed")
    pdf = _dig(s, "properties", "pdf")
    line.append(_pdf_summary(pdf))
    materialize = _dig(s, "properties", "materialize")
    line.append(
        "- " + _enum_line(materialize, "materialize")
        + ": daily mantiene agregados diarios (métricas sum, count, min, max, avg)"
    )
    return "\n".join(line)


@cache
def summary() -> str:
    """Compact authoring contract generated from the live schemas and workspace rules."""
    blocks = [
        "# Contrato de autoría BizView",
        "",
        "## Archivos permitidos (relativos a projects/<slug>/)",
        *(f"- `{p}`" for p in DRAFT_PATHS),
        "",
        "## project.yaml",
        _project_summary(),
        "",
        "## bizview.yaml",
        _workspace_summary(),
        "",
        "## integrations/<id>/integration.yaml",
        _integration_summary(),
        "",
        "## integrations/<id>/requests/<x>.yaml",
        _request_summary(),
        "",
        "## reports/<id>/report.yaml",
        _report_summary(),
        "",
        "## distributions/<id>.yaml",
        _distribution_summary(),
        "",
        "## Reglas del workspace",
        RULES,
        "",
        "Detalles: `get_authoring_guide(topic)` con topic en: "
        + ", ".join(TOPICS),
    ]
    return "\n".join(blocks)


def _template(name: str) -> str:
    path = (
        resources.files("bizview_cli")
        / "workspace_template"
        / "preset"
        / "templates"
        / name
    )
    return path.read_text(encoding="utf-8")


def _pointer_parts(pointer: str) -> list[str]:
    """Decode an RFC 6901 JSON pointer into path parts."""
    if pointer == "":
        return []
    return [p.replace("~1", "/").replace("~0", "~") for p in pointer[1:].split("/")]


def _resolve_fragment(schema: dict, pointer: str):
    node = schema
    for part in _pointer_parts(pointer):
        if isinstance(node, dict):
            node = node.get(part, ...)
        elif isinstance(node, list):
            try:
                idx = int(part)
            except ValueError:
                return ...
            if 0 <= idx < len(node):
                node = node[idx]
            else:
                return ...
        else:
            return ...
        if node is ...:
            return ...
    return node


def _fragment_notes(topic: str) -> str:
    if topic == "integration":
        return ("El id debe coincidir con la carpeta; SQL de solo lectura; params de window "
                "obligatorios en extractos incrementales; date_column date/timestamptz; "
                "checks reconcile solo con PostgreSQL.")
    if topic == "report":
        return ("Las columnas se referencian como alias.columna; date debe ser date/timestamptz; "
                "toda vista/filtro/ai_narrative.inputs referencia ids declarados. "
                "Un reporte directo usa el bloque `direct` en lugar de `uses` y su spec "
                "declara las cinco líneas de modo directo.")
    if topic == "distribution":
        return (
            "Solo roles admin/user como destinatarios; weekday solo con weekly "
            "(0 = lunes) y monthday solo con monthly (1-28); period debe estar en "
            "periods.allowed del reporte; attach_pdf requiere pdf.enabled; sin PDF "
            "hace falta link_days; link_days ≤ share.max_days."
        )
    if topic == "request":
        return ("Usa method GET, path relativo a la fuente, paginación offset con size 1000, "
                "records \"$\" y mapeo fields columna -> \"$.campo\" para Supabase/PostgREST.")
    return ""


def guide(topic: str | None = None) -> dict:
    """Return a topic guide for the authoring contract."""
    topic = (topic or "").strip()
    if topic in ("", "index"):
        return {"topic": "index", "topics": TOPICS, "summary": summary()}
    if topic in ("workspace", "integration", "request", "report", "project", "distribution"):
        out = {
            "topic": topic,
            "schema": validate.SCHEMAS[topic].schema,
            "notes": _fragment_notes(topic),
        }
        if topic == "workspace":
            out["paths"] = list(DRAFT_PATHS)
            out["rules"] = RULES
        return out
    if topic == "spec":
        return {
            "topic": "spec",
            "rules": RULES,
            "templates": {
                "spec-template.md": _template("spec-template.md"),
                "plan-template.md": _template("plan-template.md"),
                "tasks-template.md": _template("tasks-template.md"),
            },
        }
    if topic == "transform":
        return _transform_guide()
    if topic in GOLDEN:
        return {
            "topic": topic,
            "source": GOLDEN_SOURCES[GOLDEN[topic]],
            "files": golden_files(GOLDEN[topic]),
        }
    if topic.startswith("fragment:"):
        rest = topic.removeprefix("fragment:")
        schema_name, _, pointer = rest.partition("#")
        if schema_name not in validate.SCHEMAS:
            return {"topic": topic, "error": f"esquema desconocido: {schema_name}"}
        target = validate.SCHEMAS[schema_name].schema
        node = _resolve_fragment(target, pointer)
        if node is ...:
            return {"topic": topic, "error": f"puntero no resoluble: {pointer}"}
        return {
            "topic": topic,
            "schema": schema_name,
            "pointer": pointer,
            "fragment": node,
        }
    return {"topic": topic, "error": f"tema desconocido: {topic}", "topics": TOPICS}
