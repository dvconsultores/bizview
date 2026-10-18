"""Common result type and helpers for connectors."""
import os
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field

from app.ai import redact
from app.i18n import t

MESSAGES = {
    None: "Conexión correcta.",
    "unreachable": "No se pudo conectar con la fuente.",
    "timeout": "La fuente no respondió a tiempo.",
    "tls_error": "El certificado o la conexión cifrada no son válidos.",
    "auth_failed": "Las credenciales fueron rechazadas.",
    "not_found": "No se encontró el recurso (base de datos, ruta o servicio).",
    "blocked_address": "La dirección de la fuente no está permitida.",
    "not_allowed_in_profile": "La configuración no está permitida en el perfil de seguridad "
                              "actual (se requiere HTTPS/TLS).",
    "invalid_response": "La fuente respondió de forma inesperada.",
    "error": "Error al conectar con la fuente.",
}
WARNINGS = {
    "superuser_account": "La cuenta es administradora del servidor; use una de solo lectura.",
    "not_read_only": "La cuenta puede modificar datos; use una de solo lectura.",
}


def test_message(code: str | None) -> str:
    """Connection-test message in the request language (ids sources.test.*, feature 022)."""
    key = "ok" if code is None else (code if code in MESSAGES else "error")
    return t(f"sources.test.{key}")


@dataclass
class TestResult:
    ok: bool
    code: str | None = None
    message: str = ""
    latency_ms: int | None = None
    warnings: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.message:
            self.message = test_message(self.code)

    def to_json(self) -> dict:
        d = asdict(self)
        d["warning_messages"] = [t(f"sources.warning.{w}") for w in self.warnings if w in WARNINGS]
        return d


def fail(code: str, detail: str = "", secrets: dict | None = None) -> TestResult:
    """Failure with a safe, short detail (all secret values redacted)."""
    text = detail
    for value in (secrets or {}).values():
        if isinstance(value, str) and len(value) >= 4:
            text = redact(text, value, limit=10_000)
    text = redact(text, None, limit=200)
    message = test_message(code)
    return TestResult(False, code, f"{message} ({text})" if text else message)


def timed(fn: Callable[[], TestResult]) -> TestResult:
    started = time.monotonic()
    result = fn()
    result.latency_ms = int((time.monotonic() - started) * 1000)
    return result


@contextmanager
def temp_pem(content: str | None) -> Iterator[str | None]:
    """Write PEM text to a private temporary file only for the duration of a connection setup."""
    if not content:
        yield None
        return
    fd, path = tempfile.mkstemp(prefix="bizview-", suffix=".pem")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(content)
        yield path
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
