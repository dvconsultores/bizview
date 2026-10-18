"""Dataset tables owned by the engine (feature 005, research R4).

Each integration gets schema `ds_<id>`; each dataset of its contract is one table with the
contract's columns, primary key and NOT NULLs, plus `_run_id` and `_loaded_at`. Tables are created
and extended from the validated contract; an incompatible change rebuilds the table, and the run
then loads it in full. All statements run in the caller's transaction, so a failed run leaves the
previous data untouched.
"""
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from psycopg import Connection, sql

from app.config import get_settings

PG_TYPES = {"text": "text", "integer": "integer", "bigint": "bigint", "numeric": "numeric",
            "boolean": "boolean", "date": "date", "timestamptz": "timestamp with time zone"}
SYSTEM_COLUMNS = ("_run_id", "_loaded_at")


PREVIEW_PREFIX: ContextVar[str | None] = ContextVar("bizview_preview_prefix", default=None)


@contextmanager
def preview_schemas(prefix: str):
    """Within this block schema_name() points at the assistant preview schemas (feature 014)."""
    if not re.match(r"^preview_[0-9]{1,18}$", prefix):
        raise ValueError(f"Prefijo de vista previa inválido: {prefix!r}")
    token = PREVIEW_PREFIX.set(prefix)
    try:
        yield
    finally:
        PREVIEW_PREFIX.reset(token)


def preview_prefix(session_id: int) -> str:
    return f"preview_{session_id}"


def schema_name(integration_id: str) -> str:
    """`ds_<id>`; under tests, prefixed with the test schema so the run stays isolated."""
    base = "ds_" + integration_id.replace("-", "_")
    preview = PREVIEW_PREFIX.get()
    if preview is not None:
        base = f"{preview}__{base}"
    settings = get_settings()
    if settings.db_schema != "public":
        return f"{settings.db_schema}__{base}"
    return base


@dataclass
class TableState:
    created: bool = False
    rebuilt: bool = False
    added: tuple[str, ...] = ()

    @property
    def needs_full(self) -> bool:
        return self.created or self.rebuilt


def _existing(conn: Connection, schema: str, table: str) -> dict[str, tuple[str, bool]] | None:
    rows = conn.execute(
        "SELECT column_name, data_type, is_nullable = 'YES' FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s", (schema, table)).fetchall()
    return {name: (dtype, nullable) for name, dtype, nullable in rows} if rows else None


def _primary_key(conn: Connection, schema: str, table: str) -> list[str]:
    rows = conn.execute(
        "SELECT a.attname FROM pg_index i "
        "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
        "WHERE i.indrelid = (quote_ident(%s) || '.' || quote_ident(%s))::regclass "
        "AND i.indisprimary ORDER BY array_position(i.indkey, a.attnum)",
        (schema, table)).fetchall()
    return [r[0] for r in rows]


def _create(conn: Connection, schema: str, table: str, ds: dict) -> None:
    cols = [sql.SQL("{} {}{}").format(
        sql.Identifier(name), sql.SQL(PG_TYPES[c["type"]]),
        sql.SQL("" if c.get("nullable", True) else " NOT NULL"))
        for name, c in ds["columns"].items()]
    cols += [sql.SQL("_run_id bigint NOT NULL"),
             sql.SQL("_loaded_at timestamptz NOT NULL DEFAULT now()")]
    if ds.get("primary_key"):
        cols.append(sql.SQL("PRIMARY KEY ({})").format(
            sql.SQL(", ").join(map(sql.Identifier, ds["primary_key"]))))
    conn.execute(sql.SQL("CREATE TABLE {}.{} ({})").format(
        sql.Identifier(schema), sql.Identifier(table), sql.SQL(", ").join(cols)))
    if ds.get("date_column"):
        conn.execute(sql.SQL("CREATE INDEX {} ON {}.{} ({})").format(
            sql.Identifier(f"ix_{table}_{ds['date_column']}"[:63]), sql.Identifier(schema),
            sql.Identifier(table), sql.Identifier(ds["date_column"])))


def ensure_table(conn: Connection, integration_id: str, table: str, ds: dict) -> TableState:
    """Create or evolve one dataset table to match its contract."""
    schema = schema_name(integration_id)
    conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
    current = _existing(conn, schema, table)
    if current is None:
        _create(conn, schema, table, ds)
        return TableState(created=True)
    wanted = ds["columns"]
    compatible = (
        _primary_key(conn, schema, table) == list(ds.get("primary_key") or [])
        and all(name in wanted or name in SYSTEM_COLUMNS or nullable
                for name, (_, nullable) in current.items())
        and all(current[name][0] == PG_TYPES[c["type"]]
                and (current[name][1] or not c.get("nullable", True))
                for name, c in wanted.items() if name in current)
    )
    if not compatible:
        conn.execute(sql.SQL("DROP TABLE {}.{}").format(sql.Identifier(schema),
                                                        sql.Identifier(table)))
        _create(conn, schema, table, ds)
        return TableState(rebuilt=True)
    added = tuple(name for name in wanted if name not in current)
    for name in added:
        # Added columns are nullable in existing rows; the next full run fills them.
        conn.execute(sql.SQL("ALTER TABLE {}.{} ADD COLUMN {} {}").format(
            sql.Identifier(schema), sql.Identifier(table), sql.Identifier(name),
            sql.SQL(PG_TYPES[wanted[name]["type"]])))
    return TableState(added=added)


def drop_integration(conn: Connection, integration_id: str) -> None:
    conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
        sql.Identifier(schema_name(integration_id))))
