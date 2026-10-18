"""SQL rules shared by `bizview validate` and the backend (feature 005, research R3).

- Integration queries run on the ORIGIN in a read-only transaction with the source's account:
  exactly one SELECT/WITH statement; no DML/DDL/COPY/INTO/locking; no functions that read files,
  change settings, sleep, signal backends, or write (block-list).
- Report expressions run on the PRODUCT database: a single scalar/aggregate expression over the
  report's declared dataset aliases; no sub-queries; only allow-listed functions.
- Integration transforms run on the Polars SQL engine over a frame named `input`: a single
  SELECT/WITH statement; no sub-queries; no JOIN; no LIMIT/OFFSET; only allow-listed functions;
  the regenerated sqlglot text is the only input given to Polars.
"""
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.dialects.postgres import Postgres
from sqlglot.errors import ParseError, TokenError

from bizview_cli.i18n import t

DIALECT = "postgres"
PARAMS = ("window_start", "window_end")

BLOCKED_PREFIXES = ("pg_read", "pg_ls_", "pg_stat_file", "lo_", "dblink", "pg_terminate",
                    "pg_cancel", "pg_reload", "pg_rotate", "pg_sleep", "pg_advisory",
                    "pg_try_advisory", "pg_file", "pg_logdir", "pg_create", "pg_drop",
                    "pg_replication", "pg_switch", "pg_promote", "pg_backup", "pg_start",
                    "pg_stop", "copy")
BLOCKED_FUNCTIONS = {"set_config", "nextval", "setval", "query_to_xml", "query_to_json",
                     "xmlparse", "current_setting_set", "txid_current", "pg_notify",
                     "pg_import_system_collations", "pg_read_server_files"}

# Report expressions (product database): allow-list only (sqlglot function names).
ALLOWED_FUNCTIONS = {
    "sum", "count", "avg", "min", "max", "coalesce", "nullif", "round", "abs", "floor", "ceil",
    "greatest", "least", "lower", "upper", "trim", "concat", "length", "substring", "left",
    "right", "replace", "timestamp_trunc", "date_trunc", "extract", "cast", "try_cast", "case",
    "if", "time_to_str", "group_concat", "percentile_cont", "percentile_disc", "stddev",
    "variance", "logical_or", "logical_and", "mod", "pow", "sqrt", "current_date",
}

# Transform SQL (Polars engine): strict allow-list (sqlglot function names as returned by
# _function_name).
TRANSFORM_FUNCTIONS = frozenset({
    # math
    "abs", "ceil", "floor", "round", "sign", "sqrt", "power", "ln", "exp", "greatest",
    "least",
    # conditional
    "coalesce", "nullif", "if", "case",
    # text
    "lower", "upper", "trim", "length", "concat", "concat_ws", "left", "right", "substring",
    "replace", "split_part", "str_position", "starts_with", "ends_with", "initcap", "reverse",
    "regexp_like", "pad",
    # date/time
    "extract", "strftime", "strptime",
    # casts
    "cast", "try_cast",
    # aggregates
    "sum", "count", "avg", "min", "max",
    # window functions
    "row_number", "rank", "dense_rank", "lag", "lead", "first_value", "last_value",
})

# Functions that are deliberately not offered in transforms. The authoring guide uses this to tell
# users what was left out.
TRANSFORM_UNSUPPORTED = frozenset({
    "date_trunc", "timestamp_trunc", "current_date", "current_timestamp", "current_time",
    "random", "md5", "to_date", "str_to_time", "median", "percentile_cont",
    "percentile_disc", "group_concat", "array_agg", "first", "last",
})

# Window-only functions: these only make sense inside OVER (…).
WINDOW_ONLY_FUNCTIONS = frozenset({
    "row_number", "rank", "dense_rank", "lag", "lead", "first_value", "last_value",
})


class PolarsSQL(Postgres):
    """sqlglot dialect for the Polars SQL engine."""

    class Generator(Postgres.Generator):
        TRANSFORMS = {  # noqa: RUF012 (sqlglot convention)
            **Postgres.Generator.TRANSFORMS,
            exp.TryCast: lambda self, e: f"TRY_CAST({self.sql(e, 'this')} AS "
                                         f"{self.sql(e, 'to')})",
        }


@dataclass(frozen=True)
class SqlProblem:
    code: str
    message: str


@dataclass(frozen=True)
class TransformCheck:
    problems: list[SqlProblem]
    mode: str | None  # "rows" | "whole" | None when problems
    sql: str | None  # regenerated text, None when problems


def _function_name(node: exp.Expression) -> str:
    """The callable's bare name: unquoted, schema-less, lowercase.

    sqlglot yields an `exp.Identifier` for a quoted name (`"pg_read_file"`), so `str()` kept the
    quotes and slipped past the block-list; unwrap the identifier and keep the last part of a
    qualified name (`pg_catalog."pg_read_file"`)."""
    if isinstance(node, exp.Anonymous):
        this = node.this
        while isinstance(this, exp.Dot):
            this = this.expression
        name = this.name if isinstance(this, exp.Identifier) else str(this)
    else:
        name = node.sql_name()
    return name.strip('"`[]').lower()


def _blocked(name: str) -> bool:
    return name in BLOCKED_FUNCTIONS or any(name.startswith(p) for p in BLOCKED_PREFIXES)


def check_query(sql: str) -> list[SqlProblem]:
    """Rules for an integration extraction query (runs on the origin)."""
    try:
        statements = [s for s in sqlglot.parse(sql, read=DIALECT) if s is not None]
    except ParseError as e:
        return [SqlProblem("unsafe_sql", t("sql.parse_failed", error=str(e)[:200]))]
    if len(statements) != 1:
        return [SqlProblem("unsafe_sql", t("sql.exactly_one_statement"))]
    tree = statements[0]
    problems: list[SqlProblem] = []
    if not isinstance(tree, exp.Query):
        problems.append(SqlProblem("unsafe_sql", t("sql.only_select_or_with_select")))
    for node in tree.walk():
        if isinstance(node, exp.Insert | exp.Update | exp.Delete | exp.Merge | exp.Create |
                      exp.Drop | exp.Alter | exp.Command | exp.Copy | exp.TruncateTable |
                      exp.Grant | exp.Set | exp.Transaction | exp.Commit | exp.Rollback):
            problems.append(SqlProblem("unsafe_sql", t("sql.statement_not_allowed", key=node.key)))
        elif isinstance(node, exp.Into):
            problems.append(SqlProblem("unsafe_sql", t("sql.select_into_not_allowed")))
        elif isinstance(node, exp.Lock):
            problems.append(SqlProblem("unsafe_sql", t("sql.for_update_share_not_allowed")))
        elif isinstance(node, exp.Func):
            name = _function_name(node)
            if _blocked(name):
                problems.append(SqlProblem("unsafe_sql", t("sql.function_not_allowed", name=name)))
        elif isinstance(node, exp.Placeholder):
            if node.name and node.name not in PARAMS:
                problems.append(SqlProblem("unsafe_sql",
                                           t("sql.unknown_parameter", name=node.name)))
    return _dedupe(problems)


def query_params(sql: str) -> set[str]:
    tree = sqlglot.parse_one(sql, read=DIALECT)
    return {n.name for n in tree.find_all(exp.Placeholder) if n.name}


def check_expression(sql: str, aliases: dict[str, set[str]]) -> list[SqlProblem]:
    """Rules for a report metric/dimension expression. `aliases` maps alias → its columns."""
    try:
        statements = [s for s in sqlglot.parse(f"SELECT {sql}", read=DIALECT) if s is not None]
    except ParseError as e:
        return [SqlProblem("invalid_reference", t("sql.invalid_expression", error=str(e)[:160]))]
    select = statements[0] if len(statements) == 1 else None
    # Only "SELECT <one expression>": any other clause (FROM, WHERE, JOIN, …) is refused, whatever
    # name the parser gives it.
    if not isinstance(select, exp.Select) or len(select.expressions) != 1 or any(
            v for k, v in select.args.items() if k != "expressions"):
        return [SqlProblem("invalid_reference", t("sql.single_expression_required"))]
    tree = select.expressions[0]
    problems: list[SqlProblem] = []
    for node in tree.walk():
        if isinstance(node, exp.Query | exp.Subquery):
            problems.append(SqlProblem("unsafe_sql", t("sql.subqueries_not_allowed")))
        elif isinstance(node, exp.Func):
            name = _function_name(node)
            if name not in ALLOWED_FUNCTIONS:
                problems.append(SqlProblem("unsafe_sql", t("sql.function_not_allowed", name=name)))
        elif isinstance(node, exp.Column):
            table, column = node.table, node.name
            if not table:
                problems.append(SqlProblem("invalid_reference",
                                           t("sql.column_alias_required", column=column)))
            elif table not in aliases:
                problems.append(SqlProblem("invalid_reference",
                                           t("sql.unknown_alias", table=table)))
            elif column not in aliases[table]:
                problems.append(SqlProblem("invalid_reference",
                                           t("sql.column_not_in_dataset", table=table,
                                             column=column)))
    return _dedupe(problems)


def expression_columns(sql: str) -> set[tuple[str, str]]:
    select = sqlglot.parse_one(f"SELECT {sql}", read=DIALECT)
    return {(c.table, c.name) for c in select.expressions[0].find_all(exp.Column)}


_ALLOWED_TABLE_ARGS = {"this", "alias"}
_ALLOWED_SELECT_ARGS = {
    "with_", "expressions", "distinct", "from_", "where", "group", "having", "qualify", "order",
}
_ALLOWED_TYPES = {
    exp.DataType.Type.TEXT, exp.DataType.Type.VARCHAR, exp.DataType.Type.CHAR,
    exp.DataType.Type.SMALLINT, exp.DataType.Type.INT, exp.DataType.Type.BIGINT,
    exp.DataType.Type.DECIMAL, exp.DataType.Type.DOUBLE, exp.DataType.Type.FLOAT,
    exp.DataType.Type.BOOLEAN, exp.DataType.Type.DATE, exp.DataType.Type.TIMESTAMP,
    exp.DataType.Type.TIMESTAMPTZ,
}

# Simple node classes that are always allowed in transforms. exp.And and exp.Or are exp.Func
# subclasses in sqlglot 30, so this tuple is checked before the function branches. Nodes with
# their own dedicated validation branches (Column, Star, Table, TableAlias, Select, With, In,
# Var, DataType, Distinct, Window) are intentionally NOT in this tuple.
_SIMPLE_ALLOWED = (
    exp.Identifier, exp.Alias, exp.Literal, exp.Boolean, exp.Null, exp.Paren, exp.Neg, exp.Not,
    exp.And, exp.Or, exp.Add, exp.Sub, exp.Mul, exp.Div, exp.Mod, exp.DPipe, exp.EQ, exp.NEQ,
    exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Is, exp.Between, exp.Like, exp.ILike, exp.Interval,
    exp.Group, exp.Having, exp.Order, exp.Ordered, exp.Qualify, exp.From, exp.Where, exp.CTE,
    exp.DataTypeParam,
)


def _cte_names(tree: exp.Select) -> dict[int, list[str]]:
    """Map each Select node id → names of CTEs visible at that point (excluding `input`)."""
    visible: dict[int, list[str]] = {}
    with_ = tree.args.get("with_")
    if isinstance(with_, exp.With):
        names: list[str] = []
        for cte in with_.expressions:
            if isinstance(cte.this, exp.Select):
                visible[id(cte.this)] = list(names)  # only earlier CTEs
            names.append(cte.alias)
        visible[id(tree)] = list(names)
    return visible


def _allowed_in_literal(node: exp.Expression) -> bool:
    if isinstance(node, exp.Literal | exp.Boolean | exp.Null):
        return True
    if isinstance(node, exp.Neg):
        return isinstance(node.this, exp.Literal)
    return False


def _check_select_args(node: exp.Select, problems: list[SqlProblem]) -> None:
    for arg, value in node.args.items():
        if arg not in _ALLOWED_SELECT_ARGS and value:
            problems.append(SqlProblem("unsafe_sql", t("sql.construction_not_allowed", arg=arg)))
    if not node.args.get("from_"):
        problems.append(SqlProblem("unsafe_sql", t("sql.select_must_read_from_input")))


def _check_table(node: exp.Table, visible_ctes: list[str], problems: list[SqlProblem]) -> None:
    if not isinstance(node.this, exp.Identifier):
        problems.append(SqlProblem("unsafe_sql", t("sql.table_functions_not_allowed")))
        return
    if node.args.get("db") or node.args.get("catalog"):
        problems.append(SqlProblem(
            "unsafe_sql",
            t("sql.qualified_names_not_allowed", sql=node.sql(comments=False))))
        return
    for arg, value in node.args.items():
        if arg not in _ALLOWED_TABLE_ARGS and value:
            problems.append(SqlProblem("unsafe_sql", t("sql.construction_not_allowed", arg=arg)))
    if node.name != "input" and node.name not in visible_ctes:
        problems.append(SqlProblem("unsafe_sql", t("sql.unknown_table", name=node.name)))


def check_transform(sql: str, input_types: dict[str, str] | None = None) -> TransformCheck:
    """Rules for an integration transform SQL over `input`, executed by Polars."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except (ParseError, TokenError) as e:
        return TransformCheck(
            [SqlProblem("unsafe_sql",
                        t("sql.parse_transform_failed", error=str(e)[:200]))],
            None, None)
    if len(statements) != 1:
        return TransformCheck([SqlProblem("unsafe_sql", t("sql.exactly_one_statement"))],
                              None, None)
    tree = statements[0]
    problems: list[SqlProblem] = []
    if not isinstance(tree, exp.Select):
        problems.append(SqlProblem("unsafe_sql",
                                   t("sql.only_select_from_input_with_optional_with")))
        return TransformCheck(_dedupe(problems), None, None)

    cte_map = _cte_names(tree)
    alias_names = {a.alias for a in tree.find_all(exp.Alias) if a.alias}

    def _visible_for(node: exp.Expression) -> list[str]:
        ancestor = node
        while ancestor is not None and not isinstance(ancestor, exp.Select):
            ancestor = ancestor.parent
        if ancestor is None:
            return []
        return cte_map.get(id(ancestor), [])

    for node in tree.walk():
        parent = node.parent

        # Simple always-allowed node classes (checked before Func because And/Or are Funcs).
        if isinstance(node, _SIMPLE_ALLOWED):
            continue

        # Explicit refusals with specific messages.
        if isinstance(node, exp.Join):
            problems.append(SqlProblem("unsafe_sql", t("sql.joins_not_allowed")))
        elif isinstance(node, exp.SetOperation):
            problems.append(SqlProblem("unsafe_sql", t("sql.set_operations_not_allowed")))
        elif isinstance(node, (exp.Subquery, exp.Exists)):
            problems.append(SqlProblem("unsafe_sql", t("sql.subqueries_not_allowed")))
        elif isinstance(node, exp.Select) and node is not tree and not (
                isinstance(parent, exp.CTE) and parent.args.get("this") is node):
            problems.append(SqlProblem("unsafe_sql", t("sql.subqueries_not_allowed")))
        elif isinstance(node, exp.Limit | exp.Offset | exp.Fetch):
            problems.append(SqlProblem("unsafe_sql", t("sql.limit_offset_fetch_not_allowed")))
        elif isinstance(node, exp.Into):
            problems.append(SqlProblem("unsafe_sql", t("sql.select_into_not_allowed")))
        elif isinstance(node, exp.Placeholder | exp.Parameter):
            problems.append(SqlProblem("unsafe_sql", t("sql.parameters_not_allowed")))
        elif isinstance(node, exp.Lateral):
            problems.append(SqlProblem("unsafe_sql", t("sql.lateral_subqueries_not_allowed")))
        elif isinstance(node, exp.Values):
            problems.append(SqlProblem("unsafe_sql", t("sql.values_not_allowed")))
        elif isinstance(node, exp.Filter):
            problems.append(SqlProblem("unsafe_sql", t("sql.filter_on_aggregates_not_allowed")))
        elif isinstance(node, exp.WindowSpec):
            problems.append(SqlProblem("unsafe_sql",
                                       t("sql.window_frames_not_allowed")))
        elif isinstance(node, exp.Anonymous):
            name = _function_name(node)
            if name in TRANSFORM_UNSUPPORTED:
                problems.append(SqlProblem(
                    "unsafe_sql",
                    t("sql.function_not_allowed_transform_engine", name=name)))
            elif name not in TRANSFORM_FUNCTIONS:
                problems.append(SqlProblem("unsafe_sql", t("sql.function_not_allowed", name=name)))
        elif isinstance(node, exp.Func):
            name = _function_name(node)
            if name in TRANSFORM_UNSUPPORTED:
                problems.append(SqlProblem(
                    "unsafe_sql",
                    t("sql.function_not_allowed_transform_engine", name=name)))
            elif name not in TRANSFORM_FUNCTIONS:
                problems.append(SqlProblem("unsafe_sql", t("sql.function_not_allowed", name=name)))
            if name in WINDOW_ONLY_FUNCTIONS and not isinstance(parent, exp.Window):
                problems.append(SqlProblem("unsafe_sql", t("sql.requires_over", name=name)))
        elif isinstance(node, exp.Table):
            _check_table(node, _visible_for(node), problems)
        elif isinstance(node, exp.TableAlias):
            if node.args.get("columns"):
                problems.append(SqlProblem(
                    "unsafe_sql", t("sql.column_lists_in_table_aliases_not_allowed")))
        elif isinstance(node, exp.Column):
            if node.args.get("db") or node.args.get("catalog"):
                problems.append(SqlProblem(
                    "unsafe_sql",
                    t("sql.qualified_names_not_allowed", sql=node.sql(comments=False))))
            if input_types is not None and isinstance(node.this, exp.Identifier):
                if node.name not in input_types and node.name not in alias_names:
                    problems.append(SqlProblem("invalid_reference",
                                               t("sql.unknown_column", name=node.name)))
        elif isinstance(node, exp.Select):
            _check_select_args(node, problems)
        elif isinstance(node, exp.With):
            if node.args.get("recursive"):
                problems.append(SqlProblem("unsafe_sql", t("sql.with_recursive_not_allowed")))
            for cte in node.expressions:
                if not isinstance(cte.this, exp.Select):
                    problems.append(SqlProblem("unsafe_sql", t("sql.cte_must_be_select")))
                if cte.args.get("materialized"):
                    problems.append(SqlProblem("unsafe_sql", t("sql.materialized_cte_not_allowed")))
        elif isinstance(node, exp.In):
            if node.args.get("query") or node.args.get("unnest") or node.args.get("field"):
                problems.append(SqlProblem("unsafe_sql", t("sql.in_requires_literal_list")))
            for item in node.expressions:
                if not _allowed_in_literal(item):
                    problems.append(SqlProblem("unsafe_sql",
                                               t("sql.in_requires_literal_list")))
                    break
        elif isinstance(node, exp.Var):
            if not (isinstance(parent, exp.Extract) and node.arg_key == "this") and not (
                    isinstance(parent, exp.Interval) and node.arg_key == "unit"):
                problems.append(SqlProblem("unsafe_sql",
                                           t("sql.construction_not_allowed", arg="var")))
        elif isinstance(node, exp.DataType):
            if node.this not in _ALLOWED_TYPES or node.args.get("nested"):
                problems.append(SqlProblem(
                    "unsafe_sql",
                    t("sql.cast_type_not_allowed", sql=node.sql(comments=False))))
        elif isinstance(node, exp.Distinct):
            if node.args.get("on"):
                problems.append(SqlProblem("unsafe_sql", t("sql.distinct_on_not_allowed")))
        elif isinstance(node, exp.Star):
            for arg in ("except_", "replace", "rename", "ilike"):
                if node.args.get(arg):
                    problems.append(SqlProblem("unsafe_sql",
                                               t("sql.construction_not_allowed", arg=arg)))
        elif isinstance(node, exp.Window):
            if node.args.get("alias"):
                problems.append(SqlProblem("unsafe_sql", t("sql.named_windows_not_allowed")))
        else:
            problems.append(SqlProblem("unsafe_sql",
                                       t("sql.construction_not_allowed", arg=node.key)))

    if problems:
        return TransformCheck(_dedupe(problems), None, None)

    has_whole = any(isinstance(n, exp.Group | exp.Having | exp.Distinct | exp.Window |
                               exp.Qualify | exp.Order | exp.AggFunc) for n in tree.walk())
    mode = "whole" if has_whole else "rows"
    regenerated = tree.sql(dialect=PolarsSQL, identify=True)
    return TransformCheck([], mode, regenerated)


def _dedupe(problems: list[SqlProblem]) -> list[SqlProblem]:
    seen, out = set(), []
    for p in problems:
        if (p.code, p.message) not in seen:
            seen.add((p.code, p.message))
            out.append(p)
    return out
