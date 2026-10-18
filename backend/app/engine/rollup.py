"""Motor de materialización diaria (rollups) para reportes de conjuntos.

Genera tablas mv_<report_id> con componentes agregados por día y
proporciona refrescos por ventana de días.
"""

import hashlib
import json
import logging
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import sqlglot
from bizview_cli import materialize
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlglot import exp

from app.config import get_settings
from app.db import get_engine, lock_key
from app.engine import datasets
from app.i18n import M
from app.models import WorkspaceVersion

log = logging.getLogger("app.engine")

ROLLUP_FORMAT = 1


class RollupError(Exception):
    """The report cannot be materialized (message in Spanish)."""


@dataclass(frozen=True)
class Definition:
    report_id: str
    ctx: Any
    base_alias: str
    base_integration: str
    base_dataset: str
    date_column: str
    date_type: str
    schema: str
    table: str
    integrations: tuple[str, ...]
    aliases: dict[str, tuple[str, str]]
    used_columns: dict[str, tuple[str, ...]]
    dimensions: tuple[str, ...]
    metrics: dict[str, materialize.Decomposition]
    components: tuple[materialize.Component, ...]
    timezone: str
    hash: str


def is_materialized(report_def: dict) -> bool:
    return (
        report_def.get("materialize") == "daily"
        and "direct" not in report_def
        and "uses" in report_def
    )


def _build_definition(
    report_id: str,
    report_def: dict,
    integrations: dict,
    version=None,
    *,
    timezone: str | None = None,
) -> Definition:
    from app.engine import report as engine_report

    if not is_materialized(report_def):
        raise RollupError("El reporte no tiene materialize: daily")

    tz = timezone or get_settings().timezone

    ctx = engine_report._build_context(
        report_id, report_def, version, integrations, datasets.schema_name
    )

    date_alias, date_col = report_def["date"].split(".", 1)
    if date_alias not in ctx.tables:
        raise RollupError("La fecha del reporte no pertenece a un conjunto del reporte")
    date_contract = ctx.columns[date_alias].get(date_col)
    if date_contract is None:
        raise RollupError("La columna de fecha no existe en el conjunto")
    date_type = date_contract["type"]
    if date_type not in ("date", "timestamptz"):
        raise RollupError("La columna de fecha debe ser date o timestamptz")

    base_alias = date_alias
    base_integration = report_def["uses"][date_alias].split(".", 1)[0]
    base_dataset = ctx.tables[base_alias][1]

    aliases: dict[str, tuple[str, str]] = {}
    for alias, ref in report_def["uses"].items():
        iid, name = ref.split(".", 1)
        aliases[alias] = (iid, name)

    def _collect_columns(expr_text: str) -> set[tuple[str, str]]:
        try:
            parsed = sqlglot.parse_one(f"SELECT {expr_text}", read="postgres").expressions[0]
        except Exception:
            return set()
        return {
            (n.table, n.name)
            for n in parsed.walk()
            if isinstance(n, exp.Column) and n.table and n.name
        }

    used_cols: dict[str, set[str]] = {alias: set() for alias in aliases}

    # Date column
    cols = _collect_columns(report_def["date"])
    for table, col in cols:
        if table in used_cols:
            used_cols[table].add(col)

    # Join columns
    for join in report_def.get("joins", []):
        for side in ("left", "right"):
            if side in join:
                alias_part, col_part = join[side].split(".", 1)
                if alias_part in used_cols:
                    used_cols[alias_part].add(col_part)

    # Metric columns
    for mid in materialize.sql_metric_ids(report_def):
        metric_sql_text = report_def["metrics"][mid]["sql"]
        cols = _collect_columns(metric_sql_text)
        for table, col in cols:
            if table in used_cols:
                used_cols[table].add(col)

    # Dimension columns
    dims = materialize.used_dimensions(report_def)
    for did in dims:
        dim_sql_text = report_def["dimensions"][did]["sql"]
        cols = _collect_columns(dim_sql_text)
        for table, col in cols:
            if table in used_cols:
                used_cols[table].add(col)

    # Metrics decomposition
    metrics: dict[str, materialize.Decomposition] = {}
    for mid in materialize.sql_metric_ids(report_def):
        metric_sql_text = report_def["metrics"][mid]["sql"]
        result = materialize.decompose(metric_sql_text)
        if isinstance(result, list):
            raise RollupError(f"/metrics/{mid}/sql: {result[0].message}")
        metrics[mid] = result

    # Dimension eligibility
    for did in dims:
        reasons = materialize.dimension_reasons(report_def["dimensions"][did]["sql"])
        if reasons:
            raise RollupError(f"/dimensions/{did}/sql: {reasons[0].message}")

    # Deduplicated components
    component_map: dict[str, materialize.Component] = {}
    for dcomp in metrics.values():
        for comp in dcomp.components:
            component_map[comp.name] = comp
    components = tuple(
        sorted(component_map.values(), key=lambda c: c.name)
    )

    used_columns = {
        alias: tuple(sorted(cols)) for alias, cols in used_cols.items()
    }

    hash_data = {
        "format": ROLLUP_FORMAT,
        "uses": report_def["uses"],
        "joins": report_def.get("joins", []),
        "date": report_def["date"],
        "metrics": {
            mid: report_def["metrics"][mid]["sql"]
            for mid in materialize.sql_metric_ids(report_def)
        },
        "dimensions": {
            did: report_def["dimensions"][did]["sql"] for did in dims
        },
        "columns": ctx.columns,
        "timezone": tz,
    }
    hash_str = hashlib.sha256(
        json.dumps(hash_data, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()

    return Definition(
        report_id=report_id,
        ctx=ctx,
        base_alias=base_alias,
        base_integration=base_integration,
        base_dataset=base_dataset,
        date_column=date_col,
        date_type=date_type,
        schema=datasets.schema_name(base_integration),
        table="mv_" + report_id.replace("-", "_"),
        integrations=tuple(ctx.integrations),
        aliases=aliases,
        used_columns=used_columns,
        dimensions=tuple(dims),
        metrics=metrics,
        components=components,
        timezone=tz,
        hash=hash_str,
    )


def definition(
    report_id: str,
    report_def: dict,
    integrations: dict,
    version=None,
    *,
    timezone: str | None = None,
) -> Definition:
    return _build_definition(
        report_id, report_def, integrations, version, timezone=timezone
    )


def definitions(
    artifacts: dict,
    *,
    integration_id: str | None = None,
    timezone: str | None = None,
) -> list[Definition]:
    from app.engine import report as engine_report

    result: list[Definition] = []
    reports = artifacts.get("reports", {})
    integrations = artifacts.get("integrations", {})
    for rid in sorted(reports.keys()):
        report_def = reports[rid]["definition"]
        if not is_materialized(report_def):
            continue
        try:
            d = definition(rid, report_def, integrations, timezone=timezone)
        except (RollupError, engine_report.ReportError) as e:
            log.warning("rollup %s: %s", rid, e)
            continue
        if integration_id is not None and integration_id not in d.integrations:
            continue
        result.append(d)
    return result


def table_sql(d: Definition) -> sql.Composed:
    return sql.SQL("{}").format(
        sql.Identifier(d.schema, d.table)
    )


def day_sql(
    column: sql.Composable, column_type: str, timezone: str
) -> sql.Composed:
    if column_type == "timestamptz":
        return sql.SQL("({} AT TIME ZONE {})::date").format(
            column, sql.Literal(timezone)
        )
    return sql.SQL("({})").format(column)


def _dim_column_name(dim_id: str) -> str:
    return "k_" + dim_id


def select_sql(d: Definition, *, window: bool) -> sql.Composed:
    from app.engine import report as engine_report

    parts: list[sql.Composable] = []

    date_col = engine_report.date_expression(d.ctx)
    parts.append(sql.SQL("{} AS {}").format(date_col, sql.Identifier("day")))

    for did in d.dimensions:
        dim_expr = engine_report.expression(d.ctx, d.ctx.dimensions[did]["sql"])
        parts.append(
            sql.SQL("{} AS {}").format(
                dim_expr, sql.Identifier(_dim_column_name(did))
            )
        )

    for comp in d.components:
        comp_expr = engine_report.expression(d.ctx, comp.sql)
        parts.append(
            sql.SQL("{} AS {}").format(comp_expr, sql.Identifier(comp.name))
        )

    from_clause = engine_report.from_clause(d.ctx)

    where_conditions: list[sql.Composable] = []
    where_conditions.append(
        sql.SQL("{} IS NOT NULL").format(engine_report.date_expression(d.ctx))
    )

    if window:
        where_conditions.append(
            sql.SQL("{} = ANY(%(days)s)").format(
                engine_report.date_expression(d.ctx)
            )
        )
        base_col = sql.SQL("{}.{}").format(
            sql.Identifier(d.base_alias), sql.Identifier(d.date_column)
        )
        if d.date_type == "timestamptz":
            where_conditions.append(
                sql.SQL("{} >= %(lo)s AND {} < %(hi)s").format(base_col, base_col)
            )
        else:
            where_conditions.append(
                sql.SQL("{} BETWEEN %(lo)s AND %(hi)s").format(base_col)
            )

    group_by = sql.SQL(", ").join(
        sql.SQL(str(i)) for i in range(1, 2 + len(d.dimensions))
    )

    query = sql.SQL("SELECT {} FROM {} WHERE {} GROUP BY {}").format(
        sql.SQL(", ").join(parts),
        from_clause,
        sql.SQL(" AND ").join(where_conditions),
        group_by,
    )
    return query


def column_names(d: Definition) -> list[str]:
    return (
        ["day"]
        + [_dim_column_name(did) for did in d.dimensions]
        + [comp.name for comp in d.components]
    )


def table_exists(pg, d: Definition) -> bool:
    row = pg.execute(
        "SELECT to_regclass(quote_ident(%s) || '.' || quote_ident(%s)) IS NOT NULL",
        (d.schema, d.table),
    ).fetchone()
    return bool(row[0])


def column_types(pg, d: Definition) -> dict[str, str]:
    rows = pg.execute(
        """
        SELECT a.attname, format_type(a.atttypid, a.atttypmod)
        FROM pg_attribute a
        WHERE a.attrelid = to_regclass(quote_ident(%s) || '.' || quote_ident(%s))
          AND a.attnum > 0
          AND NOT a.attisdropped
        """,
        (d.schema, d.table),
    ).fetchall()
    return {name: typ for name, typ in rows if name.startswith("c_")}


def _base_index_name(d: Definition) -> str:
    return ("ix_" + d.base_dataset + "_" + d.date_column)[:63]


def build_full(pg, d: Definition) -> tuple[int, dict[str, str]]:
    tmp_table = d.table + "__new"
    tmp_index = d.table + "__new_day"

    pg.execute(
        sql.SQL("DROP TABLE IF EXISTS {}.{}").format(
            sql.Identifier(d.schema), sql.Identifier(tmp_table)
        )
    )

    select = select_sql(d, window=False)
    rows = pg.execute(
        sql.SQL("CREATE TABLE {}.{} AS {}").format(
            sql.Identifier(d.schema),
            sql.Identifier(tmp_table),
            select,
        )
    ).rowcount

    pg.execute(
        sql.SQL("CREATE INDEX {} ON {}.{} ({})").format(
            sql.Identifier(tmp_index),
            sql.Identifier(d.schema),
            sql.Identifier(tmp_table),
            sql.Identifier("day"),
        )
    )

    base_schema, base_table = d.ctx.tables[d.base_alias]
    pg.execute(
        sql.SQL(
            "CREATE INDEX IF NOT EXISTS {} ON {}.{} ({})"
        ).format(
            sql.Identifier(_base_index_name(d)),
            sql.Identifier(base_schema),
            sql.Identifier(base_table),
            sql.Identifier(d.date_column),
        )
    )

    pg.execute(
        sql.SQL("DROP TABLE IF EXISTS {}.{}").format(
            sql.Identifier(d.schema), sql.Identifier(d.table)
        )
    )
    pg.execute(
        sql.SQL("ALTER TABLE {}.{} RENAME TO {}").format(
            sql.Identifier(d.schema),
            sql.Identifier(tmp_table),
            sql.Identifier(d.table),
        )
    )
    pg.execute(
        sql.SQL("ALTER INDEX {}.{} RENAME TO {}").format(
            sql.Identifier(d.schema),
            sql.Identifier(tmp_index),
            sql.Identifier(d.table + "_day"),
        )
    )

    return rows, column_types(pg, d)


def window_bounds(
    d: Definition, days: Iterable[date]
) -> tuple[date | datetime, date | datetime]:
    days_list = sorted(days)
    if not days_list:
        raise ValueError("days must not be empty")
    if d.date_type == "date":
        return days_list[0], days_list[-1]
    tz = ZoneInfo(d.timezone)
    lo = datetime(days_list[0].year, days_list[0].month, days_list[0].day,
                  tzinfo=tz)
    last = days_list[-1]
    hi = datetime(last.year, last.month, last.day, tzinfo=tz) + timedelta(days=1)
    return lo, hi


def refresh_days(
    pg, d: Definition, days: Iterable[date]
) -> tuple[int, int]:
    days_list = sorted(days)
    if not days_list:
        return 0, 0

    lo, hi = window_bounds(d, days_list)

    deleted = pg.execute(
        sql.SQL("DELETE FROM {} WHERE {} = ANY(%(days)s)").format(
            table_sql(d),
            sql.Identifier("day"),
        ),
        {"days": days_list},
    ).rowcount

    select = select_sql(d, window=True)
    params = {
        "days": days_list,
        "lo": lo,
        "hi": hi,
    }
    insert_sql = sql.SQL("INSERT INTO {} ({}) {}").format(
        table_sql(d),
        sql.SQL(", ").join(sql.Identifier(c) for c in column_names(d)),
        select,
    )
    inserted = pg.execute(insert_sql, params).rowcount

    return deleted, inserted


def metric_sql(
    d: Definition, metric_id: str, column_types: dict[str, str], alias: str = "r"
) -> sql.SQL:
    recomposed = materialize.recompose(d.metrics[metric_id], column_types, alias)
    return sql.SQL(recomposed)


def lock(pg, report_id: str) -> None:
    pg.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (lock_key("rollup", report_id),),
    )


def read_state(pg, report_id: str) -> dict | None:
    row = pg.execute(
        """
        SELECT definition_hash, status, source_runs, columns, rows,
               schema_name, table_name, error
        FROM report_rollup
        WHERE report_id = %(report_id)s
        """,
        {"report_id": report_id},
    ).fetchone()
    if row is None:
        return None
    return {
        "definition_hash": row[0],
        "status": row[1],
        "source_runs": row[2] if isinstance(row[2], dict) else dict(row[2] or {}),
        "columns": row[3] if isinstance(row[3], dict) else dict(row[3] or {}),
        "rows": row[4],
        "schema_name": row[5],
        "table_name": row[6],
        "error": row[7],
    }


def mark_ready(
    pg,
    d: Definition,
    *,
    source_runs: dict,
    rows: int | None,
    refresh_ms: int,
    columns: dict | None = None,
    built: bool = False,
) -> None:
    pg.execute(
        """
        INSERT INTO report_rollup
            (report_id, schema_name, table_name, definition_hash, status,
             source_runs, columns, rows, built_at, refreshed_at, refresh_ms,
             error, updated_at)
        VALUES
            (%(report_id)s, %(schema_name)s, %(table_name)s, %(definition_hash)s,
             'ready', %(source_runs)s, %(columns)s, %(rows)s,
             CASE WHEN %(built)s THEN now() END, now(), %(refresh_ms)s,
             NULL, now())
        ON CONFLICT (report_id) DO UPDATE SET
            schema_name = EXCLUDED.schema_name,
            table_name = EXCLUDED.table_name,
            definition_hash = EXCLUDED.definition_hash,
            status = 'ready',
            error = NULL,
            source_runs = EXCLUDED.source_runs,
            rows = EXCLUDED.rows,
            refreshed_at = now(),
            refresh_ms = EXCLUDED.refresh_ms,
            updated_at = now(),
            columns = CASE WHEN %(has_columns)s
                           THEN EXCLUDED.columns
                           ELSE report_rollup.columns END,
            built_at = CASE WHEN %(built)s
                            THEN now()
                            ELSE report_rollup.built_at END
        """,
        {
            "report_id": d.report_id,
            "schema_name": d.schema,
            "table_name": d.table,
            "definition_hash": d.hash,
            "source_runs": Jsonb(source_runs),
            "columns": Jsonb(columns if columns is not None else {}),
            "rows": rows,
            "built": built,
            "refresh_ms": refresh_ms,
            "has_columns": columns is not None,
        },
    )


def mark_status(
    pg, d: Definition, status: str, error: str | None
) -> None:
    pg.execute(
        """
        INSERT INTO report_rollup
            (report_id, schema_name, table_name, definition_hash, status,
             error, updated_at)
        VALUES
            (%(report_id)s, %(schema_name)s, %(table_name)s, %(definition_hash)s,
             %(status)s, %(error)s, now())
        ON CONFLICT (report_id) DO UPDATE SET
            status = EXCLUDED.status,
            error = EXCLUDED.error,
            updated_at = now()
        """,
        {
            "report_id": d.report_id,
            "schema_name": d.schema,
            "table_name": d.table,
            "definition_hash": d.hash,
            "status": status,
            "error": error,
        },
    )


def drop_table(pg, schema: str, table: str) -> None:
    pg.execute(
        sql.SQL("DROP TABLE IF EXISTS {}.{}").format(
            sql.Identifier(schema), sql.Identifier(table)
        )
    )


# --- Refresh inside a run (T038) -----------------------------------------------------------------

_defs_cache: dict[tuple, list[Definition]] = {}
_defs_cache_lock = threading.Lock()


def active_definitions(db, version_id: int | None, integration_id: str) -> list[Definition]:
    """Materialized report definitions of a version that use the integration (cached: versions
    are immutable)."""
    if version_id is None:
        return []
    version = db.get(WorkspaceVersion, version_id)
    if version is None:
        return []
    key = (version_id, version.checksum, integration_id, datasets.schema_name("x"),
           get_settings().timezone)
    with _defs_cache_lock:
        if key in _defs_cache:
            return _defs_cache[key]
        defs = definitions(version.artifacts, integration_id=integration_id)
        if len(_defs_cache) > 64:
            _defs_cache.clear()
        _defs_cache[key] = defs
        return defs


@dataclass
class Capture:
    integration_id: str
    defs: list[Definition]
    days: dict[str, set[date]]                       # report id -> touched base days
    full: set[str]                                   # report ids needing a full rebuild
    before: dict[tuple[str, str], str | None]        # (report id, alias) -> fingerprint


def new_capture(integration_id: str, defs: list[Definition]) -> Capture | None:
    """State captured by the loads of a run; None when no materialized report applies."""
    if not defs:
        return None
    return Capture(integration_id=integration_id, defs=defs, days={}, full=set(), before={})


def fingerprint(pg, schema: str, table: str, columns: Iterable[str]) -> str | None:
    """Cheap content fingerprint of a table; None (= unknown, treat as changed) when large."""
    columns = sorted(columns)
    table_ident = sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(table))
    row = pg.execute(
        "SELECT reltuples::bigint FROM pg_class WHERE oid = to_regclass(%s)",
        (table_ident.as_string(pg),),
    ).fetchone()
    if row is None or row[0] > 1_000_000:
        return None
    if columns:
        cols_expr = sql.SQL("row({})::text").format(
            sql.SQL(", ").join(sql.Identifier(c) for c in columns))
        query = sql.SQL(
            "SELECT count(*), coalesce(sum(hashtextextended({}, 0)::numeric), 0) FROM {}"
        ).format(cols_expr, table_ident)
    else:
        query = sql.SQL("SELECT count(*), 0 FROM {}").format(table_ident)
    row = pg.execute(query).fetchone()
    return f"{row[0]}:{row[1]}"


def capture(pg, cap: Capture, *, dataset: str, ds: dict,
            window: tuple[sql.Composable, tuple] | None, schema: str, staging: str) -> None:
    """Record touched days / pre-load fingerprints; called before the load changes the table."""
    for d in cap.defs:
        for alias, (iid, name) in d.aliases.items():
            if iid != cap.integration_id or name != dataset:
                continue
            if alias != d.base_alias:
                cap.before[(d.report_id, alias)] = fingerprint(
                    pg, schema, dataset, d.used_columns[alias])
                continue
            if window is None:
                cap.full.add(d.report_id)
                continue
            window_cond, window_params = window
            day = day_sql(sql.Identifier(d.date_column), d.date_type, d.timezone)
            target = sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(dataset))
            stg = sql.Identifier(staging)
            branches = [sql.SQL("SELECT {} AS day FROM {} WHERE {}").format(
                day, target, window_cond)]
            pk = ds.get("primary_key")
            if pk:
                join_cond = sql.SQL(" AND ").join(
                    sql.SQL("s.{0} = t.{0}").format(sql.Identifier(c)) for c in pk)
                branches.append(sql.SQL(
                    "SELECT {} AS day FROM {} t WHERE EXISTS (SELECT 1 FROM {} s WHERE {})"
                ).format(day, target, stg, join_cond))
            branches.append(sql.SQL("SELECT {} AS day FROM {}").format(day, stg))
            query = sql.SQL("SELECT DISTINCT day FROM ({}) q WHERE day IS NOT NULL").format(
                sql.SQL(" UNION ").join(branches))
            days = {r[0] for r in pg.execute(query, window_params).fetchall() if r[0] is not None}
            if days:
                cap.days.setdefault(d.report_id, set()).update(days)


def _latest_succeeded(pg, integration_id: str, before_run: int | None = None) -> int | None:
    if before_run is None:
        row = pg.execute(
            "SELECT max(id) FROM integration_run "
            "WHERE integration_id = %s AND status = 'succeeded'", (integration_id,)).fetchone()
    else:
        row = pg.execute(
            "SELECT max(id) FROM integration_run "
            "WHERE integration_id = %s AND status = 'succeeded' AND id < %s",
            (integration_id, before_run)).fetchone()
    return row[0]


def _decide(pg, d: Definition, cap: Capture, run_id: int, integration_id: str, schema: str,
            state: dict | None) -> tuple[str, set[date]]:
    """'full' or 'window' (with the days to refresh)."""
    if (state is None or state["status"] != "ready" or state["definition_hash"] != d.hash
            or not table_exists(pg, d) or d.report_id in cap.full):
        return "full", set()
    prev = _latest_succeeded(pg, integration_id, run_id)
    if prev is None or state["source_runs"].get(integration_id) != prev:
        return "full", set()
    for (rid, alias), before in cap.before.items():
        if rid != d.report_id:
            continue
        after = fingerprint(pg, schema, d.aliases[alias][1], d.used_columns[alias])
        if before is None or after is None or before != after:
            return "full", set()
    return "window", cap.days.get(d.report_id, set())


def after_load(pg, run_id: int, integration_id: str, cap: Capture, *, schema: str,
               restore_timezone: str, deadline: float, stop: Callable[[], None],
               safe_message: Callable[[Exception], str]) -> dict[str, dict]:
    """Refresh the rollups of the reports using the integration inside the publish transaction
    (C4): one SAVEPOINT per report; on failure ROLLBACK TO SAVEPOINT keeps the previous rollup,
    which is marked stale. Never commits or rolls back the transaction itself."""
    previous_timeout = pg.execute("SHOW statement_timeout").fetchone()[0]
    results: dict[str, dict] = {}
    for d in sorted(cap.defs, key=lambda x: x.report_id):
        stop()
        lock(pg, d.report_id)
        pg.execute("SAVEPOINT rollup_sp")
        t0 = time.monotonic()
        mode = "full"
        try:
            remaining = deadline - t0
            if remaining <= 0:
                raise RollupError(M("rollup.timeout"))
            pg.execute("SELECT set_config('statement_timeout', %s, true)",
                       (f"{max(int(remaining * 1000), 1)}ms",))
            pg.execute("SELECT set_config('TimeZone', %s, true)", (d.timezone,))
            state = read_state(pg, d.report_id)
            mode, days = _decide(pg, d, cap, run_id, integration_id, schema, state)
            if mode == "full":
                rows, types = build_full(pg, d)
                source_runs = {}
                for other in d.integrations:
                    if other != integration_id:
                        latest = _latest_succeeded(pg, other)
                        if latest is not None:
                            source_runs[other] = latest
                source_runs[integration_id] = run_id
                ms = int((time.monotonic() - t0) * 1000)
                mark_ready(pg, d, source_runs=source_runs, rows=rows, refresh_ms=ms,
                           columns=types, built=True)
                results[d.report_id] = {"ok": True, "mode": "full", "days": 0,
                                        "rows": rows, "ms": ms}
            else:
                if days:
                    deleted, inserted = refresh_days(pg, d, days)
                    rows = (state["rows"] or 0) - deleted + inserted
                else:
                    rows = state["rows"]
                source_runs = {**state["source_runs"], integration_id: run_id}
                ms = int((time.monotonic() - t0) * 1000)
                mark_ready(pg, d, source_runs=source_runs, rows=rows, refresh_ms=ms)
                results[d.report_id] = {"ok": True, "mode": "window", "days": len(days),
                                        "rows": rows, "ms": ms}
            pg.execute("RELEASE SAVEPOINT rollup_sp")
        except Exception as e:
            pg.execute("ROLLBACK TO SAVEPOINT rollup_sp")
            stop()      # a stop request (or the cancel it caused) ends the whole run
            msg = safe_message(e)
            log.warning("rollup %s failed: %s", d.report_id, type(e).__name__)
            mark_status(pg, d, "stale", msg)
            results[d.report_id] = {"ok": False, "mode": mode, "error": msg,
                                    "ms": int((time.monotonic() - t0) * 1000)}
        finally:
            pg.execute("SELECT set_config('TimeZone', %s, true)", (restore_timezone,))
            pg.execute("SELECT set_config('statement_timeout', %s, true)", (previous_timeout,))
    return results


def failed_reports(results: dict[str, dict]) -> list[str]:
    return sorted(rid for rid, r in results.items() if not r.get("ok", False))


def ensure_version(version_id: int, *, retry_failed: bool = False) -> bool:
    """Build missing/outdated rollups of a version outside any run (worker pool thread) and drop
    the ones no longer materialized. True when some rollup is still pending (busy or stale)."""
    settings = get_settings()
    still_pending = False
    with get_engine().connect() as conn:
        pg = conn.connection.driver_connection
        row = pg.execute("SELECT artifacts FROM workspace_version WHERE id = %s",
                         (version_id,)).fetchone()
        pg.commit()
        if row is None:
            return False
        artifacts = row[0]
        keep = {rid for rid, rdef in artifacts.get("reports", {}).items()
                if is_materialized(rdef.get("definition", {}))}
        try:
            for rid, schema_name, table_name in pg.execute(
                    "SELECT report_id, schema_name, table_name FROM report_rollup").fetchall():
                if rid not in keep:
                    lock(pg, rid)
                    drop_table(pg, schema_name, table_name)
                    pg.execute("DELETE FROM report_rollup WHERE report_id = %s", (rid,))
            pg.commit()
        except Exception as e:
            pg.rollback()
            log.warning("rollup drop of removed reports failed: %s", type(e).__name__)
        for d in definitions(artifacts):
            row = pg.execute("SELECT definition_hash, status FROM report_rollup "
                             "WHERE report_id = %s", (d.report_id,)).fetchone()
            pending = (row is None or row[0] != d.hash or not table_exists(pg, d)
                       or row[1] == "stale" or (row[1] == "failed" and retry_failed))
            pg.commit()
            if not pending:
                continue
            acquired: list[str] = []
            try:
                for iid in d.integrations:
                    key = lock_key("integration", iid)
                    got = pg.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 0))",
                                     (key,)).fetchone()[0]
                    if not got:
                        break
                    acquired.append(key)
                if len(acquired) != len(d.integrations):
                    still_pending = True        # an integration is running: retry later
                    continue
                try:
                    pg.execute("SELECT set_config('statement_timeout', %s, true)",
                               (f"{settings.rollup_timeout_seconds * 1000}ms",))
                    pg.execute("SELECT set_config('TimeZone', %s, true)", (d.timezone,))
                    lock(pg, d.report_id)
                    t0 = time.monotonic()
                    rows, types = build_full(pg, d)
                    source_runs = {}
                    for iid in d.integrations:
                        latest = _latest_succeeded(pg, iid)
                        if latest is not None:
                            source_runs[iid] = latest
                    mark_ready(pg, d, source_runs=source_runs, rows=rows,
                               refresh_ms=int((time.monotonic() - t0) * 1000),
                               columns=types, built=True)
                    pg.commit()
                except Exception as e:
                    pg.rollback()
                    first = (str(e).splitlines() or [""])[0][:300]
                    mark_status(pg, d, "failed", f"{type(e).__name__}: {first}")
                    pg.commit()
                    log.warning("rollup %s build failed: %s", d.report_id, type(e).__name__)
            finally:
                for key in acquired:
                    pg.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", (key,))
                pg.commit()
    return still_pending
