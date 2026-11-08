"""Google BigQuery origin (feature 061).

A service account, an allow-list of datasets and a **cost ceiling**: every query is dry-run
first and refused before it runs when the estimate exceeds `max_bytes_billed`, so a wrong query
costs nothing (spec US3, SC-006). The run detail keeps the bytes processed and the slot time.
"""
import json
from datetime import date, datetime
from decimal import Decimal

from app.config import Settings
from app.i18n import t
from app.sources.connectors import sql as sqlbase
from app.sources.connectors.base import TestResult, fail

kind = "bigquery"
label = "sources.kind.bigquery"
SCOPES = ("https://www.googleapis.com/auth/bigquery.readonly",)


def _sdk():
    from google.cloud import bigquery
    from google.oauth2 import service_account

    return bigquery, service_account


def service_account_info(secrets: dict) -> dict:
    """The JSON as a dict, or `ValueError` with a key a person can act on."""
    raw = (secrets or {}).get("service_account") or ""
    try:
        info = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except ValueError:
        raise ValueError("sources.bigquery.bad_json") from None
    if not info.get("client_email") or not info.get("private_key"):
        raise ValueError("sources.bigquery.missing_keys")
    return info


def credentials(secrets: dict):
    """The service account's credentials and its info."""
    info = service_account_info(secrets)
    _, service_account = _sdk()
    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES), info


def service_account_email(secrets: dict) -> str | None:
    """Shown in the form: the address to grant the roles to, read without the SDK."""
    try:
        return service_account_info(secrets).get("client_email")
    except ValueError:
        return None


def client(settings: dict, secrets: dict):
    bigquery, _ = _sdk()
    creds, _info = credentials(secrets)
    return bigquery.Client(project=settings["project"], credentials=creds,
                           location=settings.get("location") or None)


def datasets(settings: dict) -> list[str]:
    raw = str(settings.get("datasets") or "")
    return [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()]


def max_bytes(settings: dict) -> int:
    return int(settings.get("max_bytes_billed") or 1_000_000_000)


def classify(error: BaseException) -> str:
    text = str(error).lower()
    if "403" in text and ("access denied" in text or "permission" in text):
        return "auth_failed"
    if "404" in text and "not found" in text:
        return "not_found"
    if "quota" in text or "rate limit" in text or "too many" in text:
        return "busy"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "401" in text or "invalid_grant" in text or "credentials" in text \
            or "pem file" in text:
        return "auth_failed"
    return "unreachable"


def is_busy(error: BaseException) -> bool:
    return classify(error) == "busy"


def test(settings: dict, secrets: dict, app: Settings) -> TestResult:
    try:
        info = service_account_info(secrets)
    except ValueError as e:          # the JSON itself: a key a person can act on
        return TestResult(False, "auth_failed", message=t(e.args[0]))
    try:
        bigquery, _ = _sdk()
        creds, _info = credentials(secrets)
        client = bigquery.Client(project=settings["project"], credentials=creds)
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False,
                                             maximum_bytes_billed=max_bytes(settings))
        job = client.query("SELECT 1", job_config=job_config)
        details = {"project": settings["project"], "service_account": info.get("client_email", ""),
                   "max_bytes_billed": max_bytes(settings)}
        warnings: list[str] = []
        roles = _roles(client, info.get("client_email", ""))
        if roles:
            details["roles"] = roles
            if any(role in ("roles/bigquery.dataEditor", "roles/bigquery.dataOwner",
                            "roles/bigquery.admin", "roles/owner", "roles/editor")
                   for role in roles):
                warnings.append("not_read_only")
        _ = job          # the dry run's cost is zero by definition
        return TestResult(True, warnings=warnings, details=details)
    except Exception as e:
        return fail(classify(e), sqlbase.safe(e, secrets), secrets)


def _roles(client, email: str) -> list[str]:
    """The project roles of the service account, when the caller may read the policy."""
    try:
        policy = client.get_iam_policy(request={"requested_policy_version": 3})
    except Exception:
        return []
    roles = []
    for binding in policy.bindings:
        members = getattr(binding, "members", None) or ()
        if f"serviceAccount:{email}" in members:
            roles.append(binding.role)
    return sorted(roles)


def describe(settings: dict, secrets: dict, app: Settings, *, path: str | None = None,
             write_probe: bool = False, date_ranges: bool = False,
             name: str | None = None) -> dict:
    """Datasets as schemas, tables and columns from `INFORMATION_SCHEMA`, never a row."""
    allowed = datasets(settings)
    scope = ""
    if allowed:
        quoted = ", ".join(f"'{d}'" for d in allowed)
        scope = f" WHERE table_schema IN ({quoted})"
    query = ("SELECT table_schema, table_name, table_type FROM "
             f"`{settings['project']}.region-{settings.get('location') or 'EU'}`"
             ".INFORMATION_SCHEMA.TABLES" + scope + " ORDER BY 1, 2 LIMIT 500")
    columns = ("SELECT table_schema, table_name, column_name, data_type, "
               "is_nullable = 'YES' FROM "
               f"`{settings['project']}.region-{settings.get('location') or 'EU'}`"
               ".INFORMATION_SCHEMA.COLUMNS" + scope + " ORDER BY 1, 2, ordinal_position")
    with session(settings, secrets, app, timezone="UTC", time_limit_s=60) as conn:
        from app.sources.connectors import structure_sql

        return structure_sql.describe_sql(conn, kind, tables_sql=query, columns_sql=columns,
                                          quote=lambda n: sqlbase.quote(kind, n))


def dialect_notes() -> dict:
    return {"kind": "bigquery", "quote": "`", "limit": "LIMIT", "identifier_case": "insensitive",
            "notes": "Standard SQL; backticks around project.dataset.table; dates: DATE(col), "
                     "DATE_TRUNC, CURRENT_DATE(), TIMESTAMP_SUB."}


class _Cursor:
    """The DB-API shape the shared reader expects, over a BigQuery result."""

    def __init__(self, job) -> None:
        rows = job.result()
        self._rows = iter(rows)
        # The result carries the schema; the job's own copy is the fallback for an older client.
        columns = getattr(rows, "schema", None) or getattr(job, "schema", None) or []
        self.description = [(field.name,) for field in columns]

    def fetchmany(self, size: int) -> list:
        out = []
        for _ in range(size):
            try:
                out.append(_tuple(self._rows.__next__()))
            except StopIteration:
                break
        return out

    def fetchone(self):
        rows = self.fetchmany(1)
        return rows[0] if rows else None

    def fetchall(self) -> list:
        return [_tuple(row) for row in self._rows]

    def close(self) -> None:
        self._rows = iter(())


def _tuple(row) -> tuple:
    values = []
    for value in row.values():
        if isinstance(value, Decimal | int | float | str | bool | date | datetime) or value is None:
            values.append(value)
        else:
            values.append(str(value))
    return tuple(values)


class _Connection:
    """A BigQuery client dressed as a DB-API connection for the shared reader."""

    def __init__(self, client, settings: dict, *, time_limit_s: int) -> None:
        self._client = client
        self._settings = settings
        self._time_limit = time_limit_s

    def cursor(self):
        return _ClientCursor(self._client, self._settings, self._time_limit)

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass


class _ClientCursor:
    def __init__(self, client, settings: dict, time_limit_s: int) -> None:
        self._client = client
        self._settings = settings
        self._time_limit = time_limit_s
        self._cursor: _Cursor | None = None
        self.description: list = []

    def execute(self, query: str, params=None) -> None:
        bigquery, _ = _sdk()
        sqlbase.read_only_query(query)
        dry = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False,
                                      maximum_bytes_billed=max_bytes(self._settings))
        estimate = self._client.query(query, job_config=dry)
        billed = max_bytes(self._settings)
        if int(getattr(estimate, "total_bytes_processed", 0) or 0) > billed:
            raise RuntimeError(
                f"the query would scan {estimate.total_bytes_processed} bytes, "
                f"over the {billed} this source allows")
        config = bigquery.QueryJobConfig(maximum_bytes_billed=billed,
                                         use_query_cache=True)
        job = self._client.query(query, job_config=config)
        job.result(timeout=self._time_limit)
        self._cursor = _Cursor(job)
        self.description = self._cursor.description

    def fetchmany(self, size: int) -> list:
        assert self._cursor is not None
        return self._cursor.fetchmany(size)

    def fetchone(self):
        assert self._cursor is not None
        return self._cursor.fetchone()

    def fetchall(self) -> list:
        assert self._cursor is not None
        return self._cursor.fetchall()

    def close(self) -> None:
        if self._cursor is not None:
            self._cursor.close()


def session(settings: dict, secrets: dict, app: Settings, *, timezone: str, time_limit_s: int,
            integration: str | None = None):
    from contextlib import contextmanager

    @contextmanager
    def open_session():
        conn = _Connection(client(settings, secrets), settings, time_limit_s=time_limit_s)
        try:
            yield conn
        finally:
            conn.close()

    return open_session()


def rows(conn, query: str, params: dict | None, *, check=None):
    return sqlbase.rows(conn, query, params, check=check)
