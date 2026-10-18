"""AI status and connection test for the super user (FR-011, FR-012)."""
import logging
import time
from urllib.parse import urlsplit

from app.ai import AIError, get_provider
from app.config import Settings
from app.i18n import t

log = logging.getLogger("app.ai")

TEST_PROMPT = "Responde únicamente con la palabra: OK"


def public_base_url(url: str | None) -> str | None:
    """scheme://host[:port]/path — never credentials, query, or fragment."""
    if not url:
        return None
    u = urlsplit(url)
    host = u.hostname or ""
    port = f":{u.port}" if u.port else ""
    return f"{u.scheme}://{host}{port}{u.path}"


def status(settings: Settings) -> dict:
    return {
        "enabled": settings.ai_enabled,
        "provider": settings.ai_provider,
        "model": settings.ai_model_effective,
        "base_url": public_base_url(settings.ai_base_url),
        "key_configured": settings.ai_api_key is not None,
        "timeout_seconds": settings.ai_timeout_seconds,
        "missing": settings.ai_missing,
    }


def test_connection(settings: Settings) -> dict:
    result = {"ok": False, "provider": settings.ai_provider,
              "model": settings.ai_model_effective, "latency_ms": None, "reply": None,
              "error": None}
    started = time.monotonic()
    try:
        provider = get_provider(settings)
        reply = provider.complete(TEST_PROMPT, max_tokens=1024, effort="low")
    except AIError as e:
        if e.detail:
            log.warning("AI connection test failed: %s (%s)", e.code, e.detail)
        result["error"] = {"code": e.code, "message": e.message}
    else:
        result.update(ok=True, model=reply.model, reply=reply.text[:200] or t("ai.empty_reply"))
    result["latency_ms"] = int((time.monotonic() - started) * 1000)
    return result
