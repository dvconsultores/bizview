"""Browser-test database helpers (DB_SCHEMA must be app_test_*):

    python -m tests.e2e_schema drop            # the schema, its engine dataset and preview schemas
                                               # plus the __public direct-report mapping
    python -m tests.e2e_schema seed <folder>   # feature 005: origin table, source, workspace in
                                               # <folder>, applied version, one integration run;
                                               # feature 017: reference invoice table
"""
import hashlib
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


def seed_image_cache() -> list[str]:
    """Feature 044: the pictures a `column:` image set resolves to, written before the run.

    The addresses in the workspace point at `cdn.example`, which this harness never contacts: the
    rows are recorded as already `ok`, so the worker's cache pass has nothing to fetch and still
    rewrites the loaded column to the file name. That is what lets the browser spec assert that a
    viewer opens no third-party connection without needing an internet connection of its own.

    Two addresses share one PNG on purpose: identical bytes must land in one file.
    """
    import io

    from PIL import Image as Pillow
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.images import cache
    from app.models import ImageCache

    buffer = io.BytesIO()
    Pillow.new("RGB", (16, 16), (30, 120, 90)).save(buffer, format="PNG")
    data = buffer.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    folder = Path(get_settings().image_cache_dir)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{digest}.png").write_bytes(data)

    names = []
    with get_sessionmaker().begin() as db:
        for product in ("Alimento-premium", "Vacuna-triple"):
            url = f"https://cdn.example/{product}.png"
            db.execute(pg_insert(ImageCache).values(
                url=url, sha256=digest, ext="png", bytes=len(data),
                fetched_at=datetime.now(UTC), status="ok", error=None).on_conflict_do_update(
                    index_elements=[ImageCache.url],
                    set_={"sha256": digest, "ext": "png", "bytes": len(data),
                          "status": "ok", "error": None}))
            names.append(cache.name_of(db.scalar(
                select(ImageCache).where(ImageCache.url == url))))
    return names


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
    seed_image_cache()
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
