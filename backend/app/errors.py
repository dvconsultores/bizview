"""API error envelope: {"error": {"code", "message", "fields"?}} (contracts/api.md)."""
import logging
import re
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.i18n import M

log = logging.getLogger("app")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: 'M | str',
                 fields: dict[str, str] | None = None, extra: dict[str, Any] | None = None):
        self.status, self.code, self.message = status, code, message
        self.fields, self.extra = fields, extra or {}

    def __str__(self) -> str:
        return str(self.message)

    @property
    def text(self) -> str:
        return str(self.message)


def error_body(code: str, message: 'M | str', fields=None, extra=None) -> dict:
    err: dict[str, Any] = {"code": code, "message": str(message)}
    if isinstance(message, M):
        err["key"] = message.key
        err["params"] = message.params
    if fields:
        err["fields"] = fields
    err.update(extra or {})
    return {"error": err}


class StateConflict(Exception):
    """A write the database refused because the run's state moved under it (feature 040).

    An `IntegrityError` in the middle of a `/speckit-all` turn used to end the conversation with
    «Ocurrió un error inesperado (IntegrityError)»: the constraint name is the only thing that says
    *what* conflicted, so it is carried out instead of the exception type (Step 0 of 040).
    """

    def __init__(self, constraint: str | None, detail: str = "") -> None:
        self.constraint = constraint or "unknown"
        self.detail = detail
        super().__init__(f"loop_state_conflict:{self.constraint}")

    @property
    def stop_reason(self) -> str:
        return f"blocked:loop_state_conflict:{self.constraint}"[:120]


_CONSTRAINT = re.compile(r'(?:constraint|index) "([^"]+)"')


def constraint_of(exc: BaseException | None) -> str | None:
    """The database constraint an `IntegrityError` violated, from psycopg's diagnostics."""
    if exc is None:
        return None
    orig = getattr(exc, "orig", None)
    name = getattr(getattr(orig, "diag", None), "constraint_name", None)
    if name:
        return str(name)
    match = _CONSTRAINT.search(str(orig or exc))
    return match.group(1) if match else None


def unauthenticated() -> ApiError:
    return ApiError(401, "unauthenticated", M("auth.session_ended"))


def forbidden(message: 'M | str | None' = None) -> ApiError:
    return ApiError(403, "forbidden", message or M("common.forbidden"))


def not_found(message: 'M | str | None' = None) -> ApiError:
    return ApiError(404, "not_found", message or M("common.not_found"))


def validation(fields: dict[str, str], message: 'M | str | None' = None) -> ApiError:
    return ApiError(422, "validation_error", message or M("common.validation"), fields=fields)


_STATUS_CODES = {401: "unauthenticated", 403: "forbidden", 404: "not_found",
                 405: "method_not_allowed", 409: "conflict"}


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return JSONResponse(error_body(exc.code, exc.message, exc.fields, exc.extra),
                            status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        fields: dict[str, str] = {}
        for e in exc.errors():
            loc = [str(p) for p in e.get("loc", ()) if p not in ("body", "query", "path")]
            fields[".".join(loc) or "_"] = e.get("type", "invalid")
        return JSONResponse(error_body("validation_error", M("common.validation"),
                                       fields), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = _STATUS_CODES.get(exc.status_code, "error")
        msg: M | str
        if exc.status_code == 404:
            msg = M("common.not_found")
        elif exc.status_code == 405:
            msg = M("http.method_not_allowed")
        elif exc.status_code == 429:
            msg = M("http.too_many_requests")
        elif exc.status_code == 413:
            msg = M("http.payload_too_large")
        else:
            msg = str(exc.detail)
        return JSONResponse(error_body(code, msg), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _internal(request: Request, exc: Exception):
        # A correlation id ties the "Ocurrió un error inesperado" on screen to the traceback in the
        # server log: without it the report is impossible to act on (owner, 2026-10-22: the button
        # said only "unexpected error"). The id is not a secret and carries no data.
        request_id = uuid.uuid4().hex[:12]
        log.exception("unhandled error on %s %s [%s]", request.method, request.url.path,
                      request_id)
        return JSONResponse(
            error_body("internal", M("common.unexpected_id", request_id=request_id)),
            status_code=500)
