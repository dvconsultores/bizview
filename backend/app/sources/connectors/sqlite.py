"""SQLite origin: a file the customer's export job drops in a mounted folder (feature 061).

The file is somebody else's data, so it is opened **read-only** (`mode=ro`), never created, never
migrated, and only if it lives inside `SOURCES_FILES_DIR` — a path with `..`, an absolute path
elsewhere, a symlink escaping the folder or the product's own database file cannot be saved
(spec US2, SC-007).
"""
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from app.config import Settings
from app.i18n import t
from app.sources.connectors import sql as sqlbase
from app.sources.connectors.base import TestResult, fail

kind = "sqlite"
label = "sources.kind.sqlite"
#: The folder the installation exposes; unset means the kind is not offered at all.
ENV_FOLDER = "SOURCES_FILES_DIR"
MAX_FILE_MB = 4_096


def folder(app: Settings | None = None) -> Path | None:
    raw = getattr(app, "sources_files_dir", None) if app is not None else None
    if not raw:
        raw = os.environ.get(ENV_FOLDER, "")
    return Path(raw).expanduser().resolve() if raw else None


def available(app: Settings | None = None) -> str | None:
    """The kind exists only where a folder of origin files is configured (spec US2)."""
    return None if folder(app) is not None else "sources.unavailable.folder"


def resolve(path: str, app: Settings | None = None) -> Path:
    """The file, proven to be inside the configured folder; raises `ValueError` with the reason."""
    base = folder(app)
    if base is None:
        raise ValueError("folder")
    candidate = Path(str(path or "").strip()).expanduser()
    candidate = (base / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if candidate != base and base not in candidate.parents:
        raise ValueError("outside")
    # A symlink inside the folder that points outside it resolves above and is already refused.
    if not candidate.is_file():
        raise ValueError("missing")
    if candidate.suffix.lower() not in (".sqlite", ".sqlite3", ".db", ".db3"):
        raise ValueError("extension")
    if candidate.stat().st_size > MAX_FILE_MB * 1024 * 1024:
        raise ValueError("too_large")
    return candidate


def list_files(app: Settings | None = None) -> list[dict]:
    """What the form's picker offers: the files under the folder, never the folder's path."""
    base = folder(app)
    if base is None or not base.is_dir():
        return []
    out = []
    for entry in sorted(base.iterdir()):
        try:
            resolved = resolve(entry.name, app)
        except ValueError:
            continue
        out.append({"name": entry.name, "size": resolved.stat().st_size})
    return out[:200]


def _connect(settings: dict, app: Settings | None) -> sqlite3.Connection:
    """The file, opened read-only and immutable when the customer replaces it wholesale."""
    path = resolve(settings.get("path", ""), app)
    timeout = int(settings.get("timeout_seconds") or 15)
    uri = f"file:{path}?mode=ro" + ("&immutable=1" if settings.get("immutable") else "")
    conn = sqlite3.connect(uri, uri=True, timeout=timeout, check_same_thread=False)
    conn.execute("PRAGMA query_only = ON")
    return conn


def classify(error: BaseException) -> str:
    text = str(error).lower()
    if "unable to open database file" in text or "no such file" in text:
        return "not_found"
    if "locked" in text or "busy" in text:
        return "busy"
    if "readonly" in text or "read-only" in text:
        return "not_read_only"
    return "error"


def is_busy(error: BaseException) -> bool:
    """060: a locked file is a pause (`database is locked`), never a defect."""
    return classify(error) == "busy"


def test(settings: dict, secrets: dict, app: Settings) -> TestResult:
    try:
        with closing(_connect(settings, app)) as conn:
            version = conn.execute("select sqlite_version()").fetchone()[0]
            tables = conn.execute(
                "select count(*) from sqlite_master where type in ('table','view') "
                "and name not like 'sqlite_%'").fetchone()[0]
    except ValueError as e:
        return TestResult(False, "not_found", message=t(f"sources.sqlite.{e.args[0]}"))
    except sqlite3.Error as e:
        return fail(classify(e), sqlbase.safe(e, secrets), secrets)
    return TestResult(True, details={"server_version": f"SQLite {version}", "tables": tables,
                                     "path": Path(settings.get("path", "")).name})


def describe(settings: dict, secrets: dict, app: Settings, *, path: str | None = None,
             write_probe: bool = False, date_ranges: bool = False,
             name: str | None = None) -> dict:
    """Tables, views and columns from `sqlite_master` + `PRAGMA table_info`, never a row."""
    try:
        with closing(_connect(settings, app)) as conn:
            objects = conn.execute(
                "select name, type from sqlite_master where type in ('table','view') "
                "and name not like 'sqlite_%' order by name").fetchall()
            tables = []
            for table_name, object_kind in objects:
                info = conn.execute(
                    f'PRAGMA table_info({sqlbase.quote("sqlite", table_name)})').fetchall()
                columns = [{"name": row[1], "type": (row[2] or "text"), "nullable": not row[3],
                            "primary_key": bool(row[5])} for row in info]
                tables.append({"schema": "main", "name": table_name,
                               "kind": "view" if object_kind == "view" else "table",
                               "columns": columns})
    except ValueError as e:
        raise _Refused(e.args[0]) from None
    except sqlite3.Error as e:
        raise _Refused(classify(e)) from None
    return {"kind": kind, "tables": tables, "truncated": False, "dialect": dialect_notes()}


class _Refused(Exception):
    """A structure read that cannot happen, with the reason a person can act on."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(t(f"sources.sqlite.{code}"))


def dialect_notes() -> dict:
    return {"kind": "sqlite", "quote": '"', "limit": "LIMIT", "identifier_case": "insensitive",
            "notes": "Dates are ISO-8601 text or Julian numbers; use date(col) and strftime."}


def session(settings: dict, secrets: dict, app: Settings, *, timezone: str, time_limit_s: int,
            integration: str | None = None):
    return sqlbase.session(lambda: _connect(settings, app), "sqlite", time_limit_s=time_limit_s)


def rows(conn, query: str, params: dict | None, *, check=None):
    return sqlbase.rows(conn, query, params, check=check)
