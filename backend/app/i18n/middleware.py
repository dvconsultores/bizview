"""Locale middleware for ASGI apps."""
from app.config import get_settings
from app.i18n import _context, from_accept_language, open_box


class LocaleMiddleware:
    """Pure ASGI middleware that sets the locale context per request."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        accept_language = headers.get(b"accept-language", b"").decode("latin-1")
        locale = from_accept_language(accept_language) or get_settings().default_locale
        token = open_box(locale)
        try:
            await self.app(scope, receive, send)
        finally:
            _context.reset(token)
