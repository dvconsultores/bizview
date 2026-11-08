"""SQL Server origin (feature 061).

`pymssql` speaks TDS directly, so the published image needs no ODBC manager and no Microsoft
package (research R2). SQL Server has no session read-only switch: the read-only rule is the
statement classifier plus the credential verdict — `IS_MEMBER('db_datawriter')` and the role list —
which the test card shows as a warning when the login can write.
"""
from contextlib import closing

from app.config import Settings
from app.security import profile
from app.sources.connectors import sql as sqlbase
from app.sources.connectors.base import TestResult, fail

kind = "mssql"
label = "sources.kind.mssql"
#: The origin has no free connection slot, or the pool is exhausted (060 semantics).
BUSY_TEXT = ("too many connections", "server is unavailable", "login failed for user",
             "connection limit", "max pool size", "resource limit")
AUTH_TEXT = ("login failed", "password", "not associated with a trusted")
NOT_FOUND_TEXT = ("cannot open database", "invalid object name")


def _driver():
    import pymssql

    return pymssql


def connect_kwargs(settings: dict, secrets: dict, app: Settings) -> dict:
    from app.security.netguard import policy_from_settings, resolve_checked

    host = settings["host"]
    port = int(settings.get("port") or 1433)
    ip = resolve_checked(host, port, policy_from_settings(app))[0]
    encrypt = settings.get("encrypt") or "yes"
    kwargs = {
        "server": ip, "port": port, "user": settings["username"],
        "password": secrets.get("password", ""), "database": settings["database"],
        "login_timeout": sqlbase.CONNECT_TIMEOUT_S,
        "timeout": int(settings.get("timeout_seconds") or 15),
        "appname": "bizview-engine",
        "autocommit": True,
    }
    # pymssql has no `strict`; a CA is honoured when FreeTDS has it configured. Encryption is
    # requested on the connection and the verdict says whether the session is actually encrypted.
    kwargs["encryption"] = "require" if encrypt == "yes" else "off"
    return kwargs


def _connect(settings: dict, secrets: dict, app: Settings):
    if profile.sslmode_problem("disable" if (settings.get("encrypt") or "yes") == "optional"
                               else "require", app):
        raise sqlbase.NotAllowed(profile.NOT_ALLOWED)
    return _driver().connect(**connect_kwargs(settings, secrets, app))


def classify(error: BaseException) -> str:
    text = str(error).lower()
    if any(word in text for word in BUSY_TEXT[:1]) or "17809" in text:
        return "busy"
    if any(word in text for word in AUTH_TEXT):
        return "auth_failed"
    if any(word in text for word in NOT_FOUND_TEXT):
        return "not_found"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "ssl" in text or "tls" in text or "certificate" in text:
        return "tls_error"
    return "unreachable"


def is_busy(error: BaseException) -> bool:
    return classify(error) == "busy"


def _write_verdict(conn) -> tuple[list[str], dict]:
    warnings: list[str] = []
    details: dict = {}
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT IS_MEMBER('db_datawriter'), "
                        "IS_SRVROLEMEMBER('sysadmin'), SUSER_NAME()")
            writer, sysadmin, login = cur.fetchone()
        finally:
            cur.close()
    except Exception:
        return warnings, details
    if writer or sysadmin:
        warnings.append("not_read_only")
    details["login"] = str(login or "")
    details["encrypted"] = _encrypted(conn)
    return warnings, details


def _encrypted(conn) -> bool | None:
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT encrypt_option FROM sys.dm_exec_connections "
                        "WHERE session_id = @@SPID")
            row = cur.fetchone()
        finally:
            cur.close()
    except Exception:
        return None
    return bool(row and str(row[0]).upper() == "TRUE")


def test(settings: dict, secrets: dict, app: Settings) -> TestResult:
    try:
        with closing(_connect(settings, secrets, app)) as conn:
            return sqlbase.test_connection(
                kind, lambda: conn, version_query="SELECT @@VERSION",
                read_only_query_sql=None, extra=_write_verdict, secrets=secrets, app=app)
    except sqlbase.NotAllowed:
        return TestResult(False, profile.NOT_ALLOWED)
    except Exception as e:
        return fail(classify(e), sqlbase.safe(e, secrets), secrets)


def describe(settings: dict, secrets: dict, app: Settings, *, path: str | None = None,
             write_probe: bool = False, date_ranges: bool = False,
             name: str | None = None) -> dict:
    from app.sources.connectors import structure_sql

    with closing(_connect(settings, secrets, app)) as conn:
        return structure_sql.describe_sql(
            conn, kind,
            tables_sql=("SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES"
                        " WHERE TABLE_SCHEMA NOT IN ('sys','INFORMATION_SCHEMA')"
                        " ORDER BY 1, 2"),
            columns_sql=("SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE,"
                        " CASE WHEN IS_NULLABLE = 'YES' THEN 1 ELSE 0 END"
                        " FROM INFORMATION_SCHEMA.COLUMNS"
                        " WHERE TABLE_SCHEMA NOT IN ('sys','INFORMATION_SCHEMA')"
                        " ORDER BY 1, 2, ORDINAL_POSITION"),
            quote=lambda name: sqlbase.quote(kind, name))


def dialect_notes() -> dict:
    return {"kind": "mssql", "quote": "[]", "limit": "TOP", "identifier_case": "insensitive",
            "notes": "Bracket identifiers; LIMIT does not exist — use SELECT TOP (n). "
                     "Dates: CAST(col AS date), DATEADD, FORMAT."}


def session(settings: dict, secrets: dict, app: Settings, *, timezone: str, time_limit_s: int,
            integration: str | None = None):
    return sqlbase.session(lambda: _connect(settings, secrets, app), kind,
                           time_limit_s=time_limit_s)


def rows(conn, query: str, params: dict | None, *, check=None):
    return sqlbase.rows(conn, query, params, check=check)
