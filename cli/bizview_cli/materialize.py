"""Descomposición de métricas SQL para materialización diaria.

Propósito: verificar si una métrica/dimensión es elegible para materialización
`daily` y, cuando sí lo es, descomponer la expresión en componentes agregados
sobre filas crudas más un template recomponible sobre el rollup diario.
"""

import hashlib
from dataclasses import dataclass

import sqlglot
from sqlglot import exp

DIALECT = "postgres"
SLOT_PREFIX = "__slot_"
DISTINCT_FIX = ("si la columna es la clave primaria del conjunto base y las uniones no repiten "
                "filas, usa count(*); si no, quita materialize")

INELIGIBLE_AGG_CLASSES = (
    exp.Stddev,
    exp.StddevPop,
    exp.StddevSamp,
    exp.Variance,
    exp.VariancePop,
    exp.GroupConcat,
    exp.LogicalOr,
    exp.LogicalAnd,
    exp.PercentileCont,
    exp.PercentileDisc,
)


@dataclass(frozen=True)
class Component:
    name: str        # "c_" + sha1(sql)[:12]
    kind: str        # "sum" | "count" | "min" | "max"
    sql: str         # canonical postgres text of the aggregate over raw rows (FILTER included)


@dataclass(frozen=True)
class Slot:
    kind: str                    # "sum" | "count" | "min" | "max" | "avg"
    components: tuple[str, ...]  # one component name; (sum name, count name) for avg


@dataclass(frozen=True)
class Decomposition:
    components: tuple[Component, ...]   # deduplicated, first-appearance order
    slots: tuple[Slot, ...]
    template: str   # canonical postgres text of the metric where aggregate i (the AggFunc
                    # or the Filter wrapping it) is replaced by an unqualified column named
                    # f"{SLOT_PREFIX}{i}"


@dataclass(frozen=True)
class Reason:
    message: str
    fix: str


@dataclass(frozen=True)
class Problem:
    path: str       # "/metrics/<id>/sql" or "/dimensions/<id>/sql"
    message: str
    fix: str


def _canonical(node: exp.Expression | None) -> str:
    if node is None:
        return ""
    return node.sql(dialect=DIALECT, identify=True)


def _component_name(sql: str) -> str:
    return "c_" + hashlib.sha1(sql.encode("utf-8")).hexdigest()[:12]


def _agg_kind(node: exp.AggFunc) -> str | None:
    if isinstance(node, exp.Sum):
        return "sum"
    if isinstance(node, exp.Count):
        return "count"
    if isinstance(node, exp.Min):
        return "min"
    if isinstance(node, exp.Max):
        return "max"
    if isinstance(node, exp.Avg):
        return "avg"
    return None


def _has_current_time(node: exp.Expression) -> bool:
    for n in node.walk():
        if isinstance(n, (exp.CurrentDate, exp.CurrentTimestamp, exp.CurrentTime)):
            return True
    return False


def _has_window(node: exp.Expression) -> bool:
    for n in node.walk():
        if isinstance(n, exp.Window):
            return True
    return False


def _has_nested_aggregate(node: exp.AggFunc) -> bool:
    for n in node.iter_expressions():
        if any(isinstance(x, exp.AggFunc) for x in n.walk()):
            return True
    return False


def _has_bare_column(node: exp.Expression) -> bool:
    """True si hay una columna fuera de cualquier agregado (o Filter que lo envuelva)."""
    if isinstance(node, exp.AggFunc):
        return False
    if isinstance(node, exp.Filter) and isinstance(node.this, exp.AggFunc):
        return False
    if isinstance(node, exp.Column):
        return True
    for child in node.iter_expressions():
        if _has_bare_column(child):
            return True
    return False


def _parse(expr_text: str) -> exp.Expression | None:
    try:
        return sqlglot.parse_one(f"SELECT {expr_text}", read=DIALECT).expressions[0]
    except Exception:
        return None


def _collect_units(node: exp.Expression) -> list[tuple[exp.AggFunc, exp.Filter | None]]:
    """Recolecta unidades agregadas en pre-order (izquierda a derecha, afuera primero)."""
    units: list[tuple[exp.AggFunc, exp.Filter | None]] = []

    def visit(n: exp.Expression) -> None:
        if isinstance(n, exp.Filter) and isinstance(n.this, exp.AggFunc):
            units.append((n.this, n))
            return
        if isinstance(n, exp.AggFunc):
            units.append((n, None))
            return
        for child in n.iter_expressions():
            visit(child)

    visit(node)
    return units


def _has_distinct_argument(agg: exp.AggFunc) -> bool:
    return any(isinstance(x, exp.Distinct) for x in agg.iter_expressions())


def _reason_list(reasons: list[Reason]) -> list[Reason]:
    """Deduplica por message manteniendo el orden."""
    seen: set[str] = set()
    out: list[Reason] = []
    for r in reasons:
        if r.message not in seen:
            seen.add(r.message)
            out.append(r)
    return out


def decompose(metric_sql: str) -> Decomposition | list[Reason]:
    """Descompone una métrica SQL en componentes y template, o devuelve razones."""
    expr = _parse(metric_sql)
    if expr is None:
        return [Reason("la expresión no se pudo analizar", "revisa la sintaxis SQL de la métrica")]
    reasons: list[Reason] = []

    if _has_current_time(expr):
        reasons.append(Reason(
            "current_date no se puede sumar por día",
            "usa una columna de fecha o quita materialize: daily",
        ))
    if _has_window(expr):
        reasons.append(Reason(
            "las funciones de ventana no se pueden materializar por día",
            "quita materialize: daily o reescribe la métrica sin OVER",
        ))
    if _has_bare_column(expr):
        reasons.append(Reason(
            "las columnas fuera de un agregado no se pueden materializar por día",
            "envuelve la columna en sum, count, min, max o avg; o quita materialize: daily",
        ))

    units = _collect_units(expr)
    for agg, _filt in units:
        if _has_distinct_argument(agg):
            reasons.append(Reason(
                "DISTINCT dentro de un agregado no se puede materializar por día",
                DISTINCT_FIX,
            ))
            continue
        kind = _agg_kind(agg)
        if kind is None:
            if isinstance(agg, INELIGIBLE_AGG_CLASSES):
                if isinstance(agg, (exp.PercentileCont, exp.PercentileDisc)):
                    reasons.append(Reason(
                        "percentiles no se pueden sumar por día",
                        "quita materialize: daily o usa sum, count, min, max o avg",
                    ))
                elif isinstance(agg, (exp.Stddev, exp.StddevPop, exp.StddevSamp,
                                      exp.Variance, exp.VariancePop)):
                    reasons.append(Reason(
                        "stddev y variance no se pueden sumar por día",
                        "quita materialize: daily o usa sum, count, min, max o avg",
                    ))
                elif isinstance(agg, exp.GroupConcat):
                    reasons.append(Reason(
                        "string_agg no se puede materializar por día",
                        "quita materialize: daily o usa sum, count, min, max o avg",
                    ))
                elif isinstance(agg, (exp.LogicalOr, exp.LogicalAnd)):
                    reasons.append(Reason(
                        "bool_or/bool_and no se pueden materializar por día",
                        "quita materialize: daily o usa sum, count, min, max o avg",
                    ))
            else:
                reasons.append(Reason(
                    f"la función agregada {agg.__class__.__name__} no se puede materializar "
                    "por día",
                    "quita materialize: daily o usa sum, count, min, max o avg",
                ))
            continue
        if _has_nested_aggregate(agg):
            reasons.append(Reason(
                "los agregados anidados no se pueden materializar por día",
                "separa la métrica en pasos o quita materialize: daily",
            ))
            continue

    reasons = _reason_list(reasons)
    if reasons:
        return reasons

    canonical_expr = expr.copy()
    collected_units = _collect_units(canonical_expr)

    components: list[Component] = []
    component_index: dict[str, Component] = {}
    slots: list[Slot] = []

    def get_or_add_component(kind: str, sql: str) -> Component:
        if sql in component_index:
            return component_index[sql]
        comp = Component(name=_component_name(sql), kind=kind, sql=sql)
        components.append(comp)
        component_index[sql] = comp
        return comp

    for agg, filt in collected_units:
        kind = _agg_kind(agg)
        assert kind is not None

        if kind == "avg":
            expressions = agg.args.get("expressions")
            arg = expressions[0] if expressions else agg.this
            where = filt.expression.copy() if filt is not None else None

            sum_agg = exp.Sum(this=arg.copy())
            count_agg = exp.Count(this=arg.copy())
            if where is not None:
                sum_agg = exp.Filter(this=sum_agg, expression=where.copy())
                count_agg = exp.Filter(this=count_agg, expression=where.copy())

            sum_sql = _canonical(sum_agg)
            count_sql = _canonical(count_agg)
            sum_comp = get_or_add_component("sum", sum_sql)
            count_comp = get_or_add_component("count", count_sql)
            slots.append(Slot(kind="avg", components=(sum_comp.name, count_comp.name)))
        else:
            unit_node = filt.copy() if filt is not None else agg.copy()
            unit_sql = _canonical(unit_node)
            comp = get_or_add_component(kind, unit_sql)
            slots.append(Slot(kind=kind, components=(comp.name,)))

    template_expr = expr.copy()
    collected_units = _collect_units(template_expr)
    for i, (agg, filt) in enumerate(collected_units):
        replacement = exp.column(f"{SLOT_PREFIX}{i}")
        node = filt if filt is not None else agg
        if node is template_expr or node.parent is None:
            template_expr = replacement
        else:
            node.replace(replacement)

    template = _canonical(template_expr)

    return Decomposition(
        components=tuple(components),
        slots=tuple(slots),
        template=template,
    )


def dimension_reasons(dimension_sql: str) -> list[Reason]:
    """Razones por las que una dimensión no es elegible para materialización."""
    expr = _parse(dimension_sql)
    if expr is None:
        return []
    reasons: list[Reason] = []
    if _has_current_time(expr):
        reasons.append(Reason(
            "current_date no se puede usar en una dimensión materializada",
            "usa una columna de fecha o quita materialize: daily",
        ))
    if _has_window(expr):
        reasons.append(Reason(
            "las funciones de ventana no se pueden usar en una dimensión materializada",
            "quita materialize: daily o reescribe la dimensión sin OVER",
        ))
    for n in expr.walk():
        if isinstance(n, exp.AggFunc):
            reasons.append(Reason(
                "las funciones agregadas no se pueden usar en una dimensión materializada",
                "quita materialize: daily o mueve el agregado a una métrica",
            ))
    return _reason_list(reasons)


def used_dimensions(report: dict) -> list[str]:
    """Ids de dimensiones usadas por vistas y filtros, ordenados y únicos."""
    dims = report.get("dimensions", {})
    used: set[str] = set()
    for view in report.get("views", []):
        for key in ("dimension", "dimensions"):
            val = view.get(key)
            if isinstance(val, str):
                if val in dims:
                    used.add(val)
            elif isinstance(val, list):
                for v in val:
                    if v in dims:
                        used.add(v)
    for fid in report.get("filters", []):
        if fid in dims:
            used.add(fid)
    return sorted(used)


def sql_metric_ids(report: dict) -> list[str]:
    """Ids de métricas con SQL, ordenados."""
    return sorted(k for k, v in report.get("metrics", {}).items() if "sql" in v)


def check_report(report: dict) -> list[Problem]:
    """Problemas de materialización: métricas SQL (ordenadas) y dimensiones usadas."""
    problems: list[Problem] = []
    metrics = report.get("metrics", {})
    for mid in sql_metric_ids(report):
        sql_text = metrics[mid]["sql"]
        result = decompose(sql_text)
        if isinstance(result, list):
            for reason in result:
                problems.append(Problem(
                    path=f"/metrics/{mid}/sql",
                    message=reason.message,
                    fix=reason.fix,
                ))
    dims = report.get("dimensions", {})
    for did in used_dimensions(report):
        sql_text = dims[did]["sql"]
        for reason in dimension_reasons(sql_text):
            problems.append(Problem(
                path=f"/dimensions/{did}/sql",
                message=reason.message,
                fix=reason.fix,
            ))
    return problems


def _col(name: str, alias: str) -> exp.Column:
    return exp.column(name, table=alias, quoted=True)


def recompose(d: Decomposition, column_types: dict[str, str], alias: str = "r") -> str:
    """Recompone la expresión a partir de las columnas del rollup."""
    parsed = sqlglot.parse_one(f"SELECT {d.template}", read=DIALECT).expressions[0]

    slot_by_index: dict[int, Slot] = dict(enumerate(d.slots))

    def build_slot_expr(slot: Slot) -> exp.Expression:
        if slot.kind == "avg":
            sum_name, count_name = slot.components
            return exp.Div(
                this=exp.Cast(
                    this=exp.Sum(this=_col(sum_name, alias)),
                    to=exp.DataType.build("numeric", dialect=DIALECT),
                ),
                expression=exp.Nullif(
                    this=exp.Sum(this=_col(count_name, alias)),
                    expression=exp.Literal.number(0),
                ),
            )
        if slot.kind == "sum":
            comp_name = slot.components[0]
            comp_type = column_types.get(comp_name)
            if comp_type is None:
                raise KeyError(f"Missing type for component {comp_name}")
            return exp.Cast(
                this=exp.Sum(this=_col(comp_name, alias)),
                to=exp.DataType.build(comp_type, dialect=DIALECT),
            )
        if slot.kind == "count":
            comp_name = slot.components[0]
            return exp.Cast(
                this=exp.Coalesce(
                    this=exp.Sum(this=_col(comp_name, alias)),
                    expressions=[exp.Literal.number(0)],
                ),
                to=exp.DataType.build("bigint", dialect=DIALECT),
            )
        if slot.kind == "min":
            comp_name = slot.components[0]
            return exp.Min(this=_col(comp_name, alias))
        if slot.kind == "max":
            comp_name = slot.components[0]
            return exp.Max(this=_col(comp_name, alias))
        raise ValueError(f"Unknown slot kind: {slot.kind}")

    def transform_node(node: exp.Expression) -> exp.Expression:
        if isinstance(node, exp.Column) and not node.table:
            name = node.name
            if name.startswith(SLOT_PREFIX):
                idx_str = name[len(SLOT_PREFIX):]
                try:
                    idx = int(idx_str)
                except ValueError:
                    return node
                slot = slot_by_index.get(idx)
                if slot is not None:
                    return build_slot_expr(slot)
        return node

    transformed = parsed.transform(transform_node)
    return transformed.sql(dialect=DIALECT, identify=True)
