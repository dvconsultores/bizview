"""PostgreSQL origins: pinned address, TLS policy, read-only session (feature 004)."""
import psycopg

from app.config import Settings
from app.db import TCP_LIVENESS
from app.security import profile
from app.security.netguard import BlockedAddress, policy_from_settings, resolve_checked
from app.sources.connectors.base import TestResult, fail, temp_pem


def connect_kwargs(settings: dict, secrets: dict, app: Settings, ca_path: str | None) -> dict:
    ip = resolve_checked(settings["host"], int(settings.get("port") or 5432),
                         policy_from_settings(app))[0]
    timeout = int(settings.get("timeout_seconds") or 15)
    sslmode = settings.get("sslmode") or "require"
    kwargs = {
        "host": settings["host"],          # used for TLS verification (verify-full)
        "hostaddr": ip,                    # the checked address is what we dial
        "port": int(settings.get("port") or 5432),
        "dbname": settings["database"],
        "user": settings["username"],
        "password": secrets.get("password", ""),
        "sslmode": sslmode,
        "connect_timeout": timeout,
        "application_name": "bizview",
        "options": f"-c default_transaction_read_only=on -c statement_timeout={timeout * 1000}",
        **TCP_LIVENESS,
    }
    if sslmode == "verify-full":
        kwargs["sslrootcert"] = ca_path or "system"
    return kwargs


# Server messages are localised (e.g. Spanish at Customer B) and connection failures carry no
# SQLSTATE, so classification matches the common languages explicitly.
AUTH_WORDS = ("password authentication failed", "autentificación", "autenticación",
              "authentification", "authentifizierung", "pg_hba.conf")
MISSING = ("does not exist", "no existe", "n'existe pas", "existiert nicht", "não existe")
ROLE_WORDS = ("role", "rol ", "rôle", "rolle", "papel")
DB_WORDS = ("database", "base de datos", "base de données", "datenbank", "banco de dados")


def _classify(error: Exception) -> str:
    text = str(error).lower()
    if any(w in text for w in AUTH_WORDS):
        return "auth_failed"
    if any(w in text for w in MISSING):
        if any(w in text for w in ROLE_WORDS):
            return "auth_failed"
        if any(w in text for w in DB_WORDS):
            return "not_found"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "ssl" in text or "certificate" in text or "tls" in text:
        return "tls_error"
    return "unreachable"


def test(settings: dict, secrets: dict, app: Settings) -> TestResult:
    if profile.sslmode_problem(settings.get("sslmode") or "require", app):
        return TestResult(False, profile.NOT_ALLOWED)
    try:
        with temp_pem(settings.get("ca_certificate")) as ca_path:
            kwargs = connect_kwargs(settings, secrets, app, ca_path)
            conn = psycopg.connect(**kwargs)
    except BlockedAddress as e:
        return fail("blocked_address", str(e.reason))
    except psycopg.Error as e:
        return fail(_classify(e), str(e).splitlines()[0] if str(e) else "", secrets)
    warnings: list[str] = []
    try:
        with conn:
            version = conn.execute("select version()").fetchone()[0]
            superuser = conn.execute(
                "select rolsuper from pg_roles where rolname = current_user").fetchone()[0]
            can_write = conn.execute(
                "select has_database_privilege(current_database(), 'CREATE') or exists ("
                " select 1 from information_schema.table_privileges"
                " where grantee = current_user and privilege_type in"
                " ('INSERT','UPDATE','DELETE','TRUNCATE'))").fetchone()[0]
            ssl_used = conn.execute(
                "select coalesce((select ssl from pg_stat_ssl where pid = pg_backend_pid()),"
                " false)").fetchone()[0]
    except psycopg.Error as e:
        return fail("error", str(e).splitlines()[0], secrets)
    if superuser:
        warnings.append("superuser_account")
    elif can_write:
        warnings.append("not_read_only")
    return TestResult(True, warnings=warnings,
                      details={"server_version": version.split(",")[0], "tls": bool(ssl_used)})
