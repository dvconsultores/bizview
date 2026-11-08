"""The one list of source kinds (feature 061).

Before this module the kind was a string compared in nine places — the connection test, the
structure reader, the extractor, the BI-ready check, the sample requests, the AI structure prompt,
the worker's "does this hold a session?" and two more — and every new kind had to be added to each
one. Here a kind is declared once: its label, its form fields (from `schemas`), what it can do, and
how to ask whether its driver is installed. Everything else asks the registry.

A module is the connector: it exposes `kind`, `label` (an i18n key under `sources.kind.`), `test()`,
`describe()` and, when it holds a session on the origin, `session()`; the rest of the capabilities
are declared here so a caller never has to guess.
"""
import importlib
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache

from app.config import Settings
from app.i18n import t
from app.sources.connectors.base import TestResult


@dataclass(frozen=True)
class Capabilities:
    """What a kind can do, so callers stop asking `kind == …`.

    `sql` — an integration's query is SQL this kind runs (the DB-API streaming path).
    `tables` — it has schemas/tables/columns the structure reader can list.
    `files` — it reads a local file instead of a network address.
    `api` — it answers HTTP requests rather than SQL (REST, SOAP, Supabase, Sheets).
    `session` — it opens a real session on the origin, so the 060 ceiling applies to it.
    `native_copy` — it can stream `COPY (query) TO STDOUT` (PostgreSQL only; the runner falls back
    to the row path for every other SQL kind).
    """

    sql: bool = False
    tables: bool = False
    files: bool = False
    api: bool = False
    session: bool = False
    native_copy: bool = False


@dataclass(frozen=True)
class Spec:
    kind: str
    module: str                     # `app.sources.connectors.<module>`
    capabilities: Capabilities
    fields: Callable[[], tuple]     # the form fields, from `schemas` (lazy: no import cycle)
    #: Extra driver modules whose absence makes the kind unavailable (`sqlite3` is stdlib).
    drivers: tuple[str, ...] = field(default_factory=tuple)


def _fields(name: str) -> Callable[[], tuple]:
    def load() -> tuple:
        from app.sources import schemas

        return schemas.FIELDS[name]

    return load


SPECS: tuple[Spec, ...] = (
    Spec("postgresql", "postgresql", Capabilities(sql=True, tables=True, session=True,
                                                  native_copy=True), _fields("postgresql"),
         ("psycopg",)),
    Spec("supabase", "supabase", Capabilities(api=True), _fields("supabase")),
    Spec("rest", "rest", Capabilities(api=True), _fields("rest")),
    Spec("soap", "soap", Capabilities(api=True), _fields("soap")),
    Spec("sqlite", "sqlite", Capabilities(sql=True, tables=True, files=True, session=True),
         _fields("sqlite"), ("sqlite3",)),
    Spec("mysql", "mysql", Capabilities(sql=True, tables=True, session=True), _fields("mysql"),
         ("pymysql",)),
    Spec("mssql", "mssql", Capabilities(sql=True, tables=True, session=True), _fields("mssql"),
         ("pymssql",)),
    Spec("bigquery", "bigquery", Capabilities(sql=True, tables=True), _fields("bigquery"),
         ("google.cloud.bigquery",)),
    Spec("sheets", "sheets", Capabilities(api=True, tables=True), _fields("sheets"),
         ("googleapiclient", "google.oauth2.service_account")),
)

BY_KIND: dict[str, Spec] = {spec.kind: spec for spec in SPECS}
#: The kinds other modules still name in a sentence rather than through a capability: PostgreSQL
#: has COPY and direct reports, SOAP has no tables or paths, Supabase borrows REST's reader.
#: Named here so no module compares a kind to a string literal (feature 061, SC-005).
POSTGRESQL = "postgresql"
SOAP = "soap"
REST = "rest"
SUPABASE = "supabase"
SQLITE = "sqlite"
KINDS: tuple[str, ...] = tuple(spec.kind for spec in SPECS)


@cache
def module(kind: str):
    """The connector module of a kind (imported on demand: a missing driver fails here only)."""
    spec = BY_KIND.get(kind)
    if spec is None:
        raise KeyError(kind)
    return importlib.import_module(f"app.sources.connectors.{spec.module}")


def capabilities(kind: str) -> Capabilities:
    spec = BY_KIND.get(kind)
    return spec.capabilities if spec is not None else Capabilities()


def is_sql(kind: str) -> bool:
    return capabilities(kind).sql


def holds_session(kind: str) -> bool:
    return capabilities(kind).session


def has_native_copy(kind: str) -> bool:
    return capabilities(kind).native_copy


def missing_drivers(kind: str) -> tuple[str, ...]:
    """The imports this kind needs and the installation does not have."""
    spec = BY_KIND.get(kind)
    if spec is None:
        return ()
    missing = []
    for name in spec.drivers:
        try:
            importlib.import_module(name)
        except Exception:
            missing.append(name)
    return tuple(missing)


def available(kind: str, app: Settings | None = None) -> str | None:
    """`None` when the kind can be used here, else the i18n key of the reason.

    A kind whose driver is not installed is *listed as unavailable with the reason*, never a 500
    (spec edge case, FR-017); a kind that needs a folder that is not configured says so too.
    """
    spec = BY_KIND.get(kind)
    if spec is None:
        return "sources.unavailable.unknown"
    if missing_drivers(kind):
        return "sources.unavailable.driver"
    connector = module(kind)
    check = getattr(connector, "available", None)
    if check is not None:
        return check(app)          # a kind with its own rule (SQLite's folder)
    return None


def test_source(kind: str, settings: dict, secrets: dict, app: Settings) -> TestResult:
    """The connection test of any kind, with the timer and the driver check around it."""
    from app.sources.connectors.base import timed

    reason = available(kind, app)
    if reason is not None:
        result = TestResult(False, "unavailable")
        result.message = t(reason)
        return result
    return timed(lambda: module(kind).test(settings, secrets, app))


def describe(kind: str, settings: dict, secrets: dict, app: Settings,
             path: str | None = None, write_probe: bool = False, date_ranges: bool = False,
             name: str | None = None) -> dict:
    """The structure of any kind; only PostgreSQL takes the write probe (a rolled-back write)."""
    connector = module(kind)
    if write_probe and not capabilities(kind).sql:
        write_probe = False
    return connector.describe(settings, secrets, app, path=path, write_probe=write_probe,
                              date_ranges=date_ranges, name=name)


def request_rows(kind: str):
    """The kind's HTTP request reader, or `None` when the kind does not read with a request.

    REST, SOAP, Supabase and Google Sheets all answer a request rather than a query; PostgreSQL,
    MySQL, SQL Server, SQLite and BigQuery stream rows (feature 061).
    """
    spec = BY_KIND.get(kind)
    if spec is None or not spec.capabilities.api:
        return None
    return getattr(module(kind), "request_rows", None)
