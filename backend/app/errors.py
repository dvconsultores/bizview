"""API error envelope: {"error": {"code", "message", "fields"?}} (contracts/api.md)."""
import logging
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
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(error_body("internal", M("common.unexpected")),
                            status_code=500)
