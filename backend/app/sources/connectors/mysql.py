"""MySQL / MariaDB origin (feature 061).

`PyMySQL` is pure Python, so the published image needs no system package. The session is made
read-only where the engine allows it, the statement rule refuses anything that is not a read, and
the credential verdict reports whether the user may write (`SHOW GRANTS`), which is what a DBA can
act on.
"""
import re
from contextlib import closing

from app.config import Settings
from app.security import profile
from app.sources.connectors import sql as sqlbase
from app.sources.connectors.base import TestResult, fail

kind = "mysql"
label = "sources.kind.mysql"
SSL_MODES = {"require": {"ssl": {}}, "verify-full": {"ssl_verify_cert": True},
             "prefer": {"ssl_disabled": False}, "disable": {"ssl_disabled": True}}
#: What MySQL answers when the origin has no free connection slot (060 semantics).
#: The engine's own "no more slots" codes: 1040 Too many connections, 1203 the user's own
#: limit, 1129 the host blocked after too many failures. 2002/2003 are "cannot connect"
#: and stay unreachable — a server that is down is not a busy one.
BUSY_CODES = {1040, 1203, 1129}
AUTH_CODES = {1044, 1045, 1698, 1251}
NOT_FOUND_CODES = {1049, 1146}


def _driver():
    import pymysql

    return pymysql


def connect_kwargs(settings: dict, secrets: dict, app: Settings) -> dict:
    from app.security.netguard import policy_from_settings, resolve_checked

    host = settings["host"]
    port = int(settings.get("port") or 3306)
    ip = resolve_checked(host, port, policy_from_settings(app))[0]
    sslmode = settings.get("sslmode") or "require"
    kwargs = {
        "host": ip, "port": port, "user": settings["username"],
        "password": secrets.get("password", ""), "database": settings["database"],
        "connect_timeout": sqlbase.CONNECT_TIMEOUT_S,
        "read_timeout": int(settings.get("timeout_seconds") or 15),
        "charset": "utf8mb4", "autocommit": True,
        "program_name": "bizview-engine",
        "init_command": "SET SESSION TRANSACTION READ ONLY",
    }
    if sslmode in ("require", "verify-full"):
        kwargs.update(SSL_MODES[sslmode] or {})
        ca = settings.get("ca_certificate")
        if ca:
            kwargs["ssl_ca"] = ca
    elif sslmode == "disable":
        kwargs["ssl_disabled"] = True
    return kwargs


def _connect(settings: dict, secrets: dict, app: Settings):
    if profile.sslmode_problem(settings.get("sslmode") or "require", app):
        raise sqlbase.NotAllowed(profile.NOT_ALLOWED)
    pymysql = _driver()
    kwargs = connect_kwargs(settings, secrets, app)
    conn = pymysql.connect(**kwargs)
    try:
        cur = conn.cursor()
        cur.execute("SET SESSION MAX_EXECUTION_TIME = %s", (int(settings.get("timeout_seconds")
                                                             or 15) * 1000,))
        cur.close()
    except Exception:
        pass                    # an older MariaDB has no such variable; the read timeout remains
    return conn


def classify(error: BaseException) -> str:
    args = getattr(error, "args", ()) or ()
    code = args[0] if args and isinstance(args[0], int) else None
    text = str(error)
    if code is None:                    # a wrapped error keeps its code only in the message
        found = re.match(r"\(?(\d{4})\b", text)
        code = int(found.group(1)) if found else None
    text = text.lower()
    if isinstance(code, int) and code in BUSY_CODES:
        return "busy"
    if isinstance(code, int) and code in AUTH_CODES:
        return "auth_failed"
    if isinstance(code, int) and code in NOT_FOUND_CODES:
        return "not_found"
    if "too many connections" in text:
        return "busy"
    if "access denied" in text:
        return "auth_failed"
    if "unknown database" in text:
        return "not_found"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    if "ssl" in text or "certificate" in text or "tls" in text:
        return "tls_error"
    return "unreachable"


def is_busy(error: BaseException) -> bool:
    """060: the origin has no slot — a pause, never a defect."""
    return classify(error) == "busy"


def _can_write(conn) -> tuple[list[str], dict]:
    warnings: list[str] = []
    try:
        cur = conn.cursor()
        cur.execute("SHOW GRANTS")
        grants = " ".join(str(row[0]) for row in cur.fetchall()).upper()
        cur.close()
    except Exception:
        return warnings, {}
    writes = ("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "ALL PRIVILEGES")
    if any(f" {word} " in f"{grants} " for word in writes):
        warnings.append("not_read_only")
    return warnings, {"grants_visible": True}


def test(settings: dict, secrets: dict, app: Settings) -> TestResult:
    try:
        with closing(_connect(settings, secrets, app)) as conn:
            return sqlbase.test_connection(
                kind, lambda: conn, version_query="SELECT VERSION()",
                read_only_query_sql="SELECT @@SESSION.transaction_read_only",
                extra=_can_write, secrets=secrets, app=app)
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
            tables_sql=("SELECT table_schema, table_name, table_type"
                        " FROM information_schema.tables WHERE table_schema NOT IN"
                        " ('mysql','information_schema','performance_schema','sys')"
                        " ORDER BY 1, 2"),
            columns_sql=("SELECT table_schema, table_name, column_name, data_type,"
                         " is_nullable = 'YES' FROM information_schema.columns"
                         " WHERE table_schema NOT IN ('mysql','information_schema',"
                         "'performance_schema','sys') ORDER BY 1, 2, ordinal_position"),
            quote=lambda name: sqlbase.quote(kind, name))


def dialect_notes() -> dict:
    return {"kind": "mysql", "quote": "`", "limit": "LIMIT", "identifier_case": "platform",
            "notes": "Quote with backticks; dates: DATE(col), DATE_FORMAT, NOW(), INTERVAL n DAY."}


def session(settings: dict, secrets: dict, app: Settings, *, timezone: str, time_limit_s: int,
            integration: str | None = None):
    return sqlbase.session(lambda: _connect(settings, secrets, app), kind,
                           time_limit_s=time_limit_s)


def rows(conn, query: str, params: dict | None, *, check=None):
    return sqlbase.rows(conn, query, params, check=check)
