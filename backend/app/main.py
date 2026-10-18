"""FastAPI application: JSON API under /api, served behind Caddy on the same origin."""
import json
import logging
import os
import sys
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import errors
from app.api import (
    admin,
    ai,
    assistant,
    auth,
    dashboards,
    guide,
    health,
    me,
    projects,
    reports,
    security,
    shared,
    sharing,
    sources,
    telegram,
    tokens,
    workspace,
)
from app.config import get_settings
from app.i18n import M
from app.i18n import middleware as i18n_middleware
from app.security import profile
from app.security.crypto import CryptoError
from app.security.middleware import admin_networks

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False)


def _configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("app")
    root.handlers[:] = [handler]
    root.setLevel(level)


def create_app() -> FastAPI:
    settings = get_settings()
    _configure_logging(settings.log_level)
    if settings.db_pool_warm:
        import threading

        from app.db import warm_pool
        threading.Thread(target=warm_pool, args=(settings.db_pool_warm,), daemon=True,
                         name="db-warm").start()
    profile.enforce_at_start(settings)  # refuse to serve an insecure internet installation
    docs = settings.docs_enabled
    app = FastAPI(title=settings.product_name, docs_url="/api/docs" if docs else None,
                  redoc_url=None, openapi_url="/api/openapi.json" if docs else None)
    errors.install(app)

    @app.exception_handler(CryptoError)
    async def _crypto(_: Request, exc: CryptoError):
        logging.getLogger("app.security").error("encryption unavailable: %s", exc)
        return JSONResponse(errors.error_body(
            "encryption_unavailable",
            M("security.encryption_unavailable")), status_code=503)

    app.add_middleware(i18n_middleware.LocaleMiddleware)
    app.middleware("http")(admin_networks)

    @app.middleware("http")
    async def csrf_and_cache(request: Request, call_next):
        # CSRF (research R3): a cross-site page can neither set this header without a CORS
        # preflight (never approved) nor send an Origin that matches our Host.
        if request.method in UNSAFE_METHODS and request.url.path.startswith("/api/"):
            origin = request.headers.get("origin")
            same_origin = origin is None or urlsplit(origin).netloc == request.headers.get("host")
            if request.headers.get("x-requested-with") != "fetch" or not same_origin:
                return JSONResponse(errors.error_body("csrf_failed", M("security.csrf_failed")),
                                    status_code=403)
        response = await call_next(request)
        if request.url.path.startswith(shared.router.prefix + "/"):
            for key, value in shared.PUBLIC_HEADERS.items():
                response.headers[key] = value
        elif request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    for module in (health, auth, me, dashboards, admin, ai, sources, security, workspace,
                   reports, tokens, telegram, assistant, projects, shared, sharing, guide):
        app.include_router(module.router)
    if os.environ.get("BIZVIEW_TEST_HOOKS") == "1":   # e2e only (feature 007); never in images
        from app.api import testhooks
        app.include_router(testhooks.router)
        logging.getLogger("app").warning("test hooks enabled")
    return app


app = create_app()
