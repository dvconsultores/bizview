"""Browser-test database helpers (DB_SCHEMA must be app_test_*):

    python -m tests.e2e_schema drop            # the schema, its engine dataset and preview schemas
                                               # plus the __public direct-report mapping
    python -m tests.e2e_schema seed <folder>   # feature 005: origin table, source, workspace in
                                               # <folder>, applied version, one integration run;
                                               # feature 017: reference invoice table
"""
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.engine import make_url

from app.config import get_settings
from app.db import get_engine, get_sessionmaker
from tests.safety import assert_test_schema

NOW = datetime(2026, 9, 29, 15, 0, tzinfo=UTC)
REFERENCE_TABLE = "origin_invoices"
REFERENCE_SOURCE = "Origen e2e"


def drop(schema: str) -> None:
    with get_engine().begin() as c:
        c.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        prefix = schema.replace("_", r"\_")
        for pattern, start in (
            (prefix + r"\_\_ds\_%", f"{schema}__ds_"),
            (prefix + r"\_\_preview\_%", f"{schema}__preview_"),
            (prefix + r"\_\_public", f"{schema}__public"),
        ):
            for (name,) in c.execute(
                text("SELECT nspname FROM pg_namespace WHERE nspname LIKE :p"),
                {"p": pattern},
            ).all():
                assert name.startswith(start)
                c.execute(text(f'DROP SCHEMA "{name}" CASCADE'))


def seed_reference(conn, schema: str, now: datetime | None = None) -> str:
    """Create the reference invoice table used by the agent e2e (feature 017) and the SC-001
    live eval. `cliente_email` is deliberately personal data the agent must exclude."""
    if now is None:
        now = datetime.now(UTC)
    table = f'"{schema}".{REFERENCE_TABLE}'
    conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
    conn.execute(text(f"CREATE TABLE {table} (numero text, emitida_en timestamptz, "
                      f"estado text, moneda text, monto_total numeric, impuesto numeric, "
                      f"cliente_email text)"))
    rows = [
        ("F-1001", now - timedelta(hours=10), "emitida", "USD", 120.0, 19.2,
         "cliente1@example.com"),
        ("F-1002", now - timedelta(hours=22), "pagada", "USD", 80.5, 12.9,
         "cliente2@example.com"),
        ("F-1003", now - timedelta(days=1, hours=4), "pagada", "USD", 200.0, 32.0,
         "cliente3@example.com"),
        ("F-1004", now - timedelta(days=1, hours=16), "anulada", "USD", 45.0, 7.2,
         "cliente4@example.com"),
        ("F-1005", now - timedelta(days=2, hours=2), "emitida", "USD", 150.25, 24.04,
         "cliente5@example.com"),
        ("F-1006", now - timedelta(days=2, hours=14), "pagada", "VES", 3500.0, 560.0,
         "cliente6@example.com"),
        ("F-1007", now - timedelta(days=3, hours=6), "pagada", "USD", 95.0, 15.2,
         "cliente7@example.com"),
        ("F-1008", now - timedelta(days=3, hours=18), "emitida", "USD", 300.0, 48.0,
         "cliente8@example.com"),
    ]
    for r in rows:
        conn.execute(
            text(f"INSERT INTO {table} VALUES (:n, :e, :s, :m, :t, :i, :c)"),
            dict(zip("nesmtic", r, strict=True)),
        )
    return table


def seed(schema: str, folder: Path) -> None:
    from bizview_cli import validate as wsv

    from app.engine import runner
    from app.models import AppUser
    from app.sources import service as sources
    from app.workspace import service as workspace
    from tests.workspace_fixture import build

    origin = f'"{schema}".origin_sales'
    with get_engine().begin() as c:
        c.execute(text(f"DROP TABLE IF EXISTS {origin}"))
        c.execute(text(f"CREATE TABLE {origin} (doc text, line int, kind text, "
                       f"completed_at timestamptz, amount numeric, product text)"))
        rows = [("A1", 1, "sale", NOW - timedelta(days=1), 10.5, "Alimento premium"),
                ("A1", 2, "sale", NOW - timedelta(days=1), 4.25, "Vacuna triple"),
                ("A2", 1, "return", NOW - timedelta(days=2), 3, "Alimento premium")]
        for r in rows:
            c.execute(text(f"INSERT INTO {origin} VALUES (:d, :l, :k, :t, :a, :p)"),
                      dict(zip("dlktap", r, strict=True)))
        seed_reference(c, schema)
    build(folder, origin, source="Origen e2e")
    result = wsv.validate(folder)
    assert result.ok, [str(i) for i in result.issues]
    wsv.write_lock(folder, result.lock)
    settings = get_settings()
    url = make_url(settings.database_url_bi)
    settings.workspace_path = str(folder)
    with get_sessionmaker().begin() as db:
        actor = db.scalar(select(AppUser).where(AppUser.is_superuser))
        if sources.by_name(db, REFERENCE_SOURCE) is None:
            sources.create(db, actor, {
                "name": REFERENCE_SOURCE, "kind": "postgresql",
                "settings": {"host": url.host, "port": url.port or 5432, "database": url.database,
                             "username": url.username, "sslmode": "prefer"},
                "secrets": {"password": url.password}}, settings, None)
    with get_sessionmaker().begin() as db:
        actor = db.scalar(select(AppUser).where(AppUser.is_superuser))
        version = workspace.apply(db, actor, None)
        version_id, item = version.id, version.artifacts["integrations"]["ventas-prueba"]
    run = runner.run_integration(item["definition"], item["files"], version_id=version_id,
                                 kind="full", now=NOW)
    assert run.status == "succeeded", run.message


if __name__ == "__main__":
    target = assert_test_schema(get_settings().db_schema)
    if sys.argv[1:] == ["drop"]:
        drop(target)
    elif sys.argv[1:2] == ["seed"] and len(sys.argv) == 3:
        seed(target, Path(sys.argv[2]))
    else:
        sys.exit("usage: python -m tests.e2e_schema drop | seed <folder>")
