"""The structure of a SQL origin, in the shape PostgreSQL's reader produces (feature 061).

Every SQL kind answers the same two questions — which tables, and which columns with which types —
from its own `information_schema`, and hands them here. The pack (048/052/057) and the AI prompt
therefore need no per-kind branch beyond the dialect notes.
"""
from collections.abc import Callable

MAX_TABLES, MAX_COLUMNS = 500, 200


def describe_sql(conn, kind: str, *, tables_sql: str, columns_sql: str,
                 quote: Callable[[str], str]) -> dict:
    """`{tables: [...], truncated: bool, dialect: {...}}`; a row is never read."""
    cur = conn.cursor()
    try:
        cur.execute(tables_sql)
        table_rows = cur.fetchall()
    finally:
        cur.close()
    truncated = len(table_rows) > MAX_TABLES
    by_name: dict[tuple[str, str], dict] = {}
    for row in table_rows[:MAX_TABLES]:
        schema, name, table_type = ([*list(row), None, None, None])[:3]
        if schema is None:
            continue
        by_name[(str(schema), str(name))] = {
            "schema": str(schema), "name": str(name),
            "kind": "view" if str(table_type or "").upper().endswith("VIEW") else "table",
            "columns": [],
        }
    cur = conn.cursor()
    try:
        cur.execute(columns_sql)
        for row in cur.fetchall():
            if len(row) < 4:
                continue
            schema, table, column, data_type = (str(row[0]), str(row[1]), str(row[2]),
                                                str(row[3]))
            nullable = bool(row[4]) if len(row) > 4 else True
            target = by_name.get((schema, table))
            if target is None or len(target["columns"]) >= MAX_COLUMNS:
                continue
            target["columns"].append({"name": column, "type": data_type,
                                      "nullable": nullable})
    finally:
        cur.close()
    from app.sources.connectors import registry

    module = registry.module(kind) if kind in registry.BY_KIND else None
    return {
        "kind": kind,
        "tables": list(by_name.values()),
        "truncated": truncated,
        "dialect": module.dialect_notes() if module is not None else {},
        "quote": quote("x")[:1],
    }
