"""AI status and connection test for the super user (FR-011, FR-012)."""
import logging
import time
from urllib.parse import urlsplit

from app.ai import AIError, get_provider, state
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
    recorded = state.read()
    return {
        "enabled": settings.ai_enabled,
        "provider": settings.ai_provider,
        "model": settings.ai_model_effective,
        "base_url": public_base_url(settings.ai_base_url),
        "key_configured": settings.ai_api_key is not None,
        "timeout_seconds": settings.ai_timeout_seconds,
        "missing": settings.ai_missing,
        # 035: how the last call went, so the page can say «funcionando» or «error no_credit».
        "last_ok_at": recorded["last_ok_at"],
        "last_error_code": recorded["last_error_code"],
        "last_error_at": recorded["last_error_at"],
        "last_error_detail": recorded["last_error_detail"],
        "last_model": recorded["last_model"],
        "healthy": state.healthy(),
        "blocking_code": state.blocked_reason(),
    }


def test_connection(settings: Settings) -> dict:
    """A real request, plus the models the endpoint reports.

    The super user cannot fix «the provider returned an error» without the provider's own words,
    so every failure keeps its code, its redacted detail and the action to take; the outcome is
    recorded in `ai_status`, which `/api/health` reads.
    """
    result = {"ok": False, "provider": settings.ai_provider,
              "model": settings.ai_model_effective, "latency_ms": None, "reply": None,
              "error": None, "models": None}
    started = time.monotonic()
    provider = None
    try:
        provider = get_provider(settings)
    except AIError as e:
        result["error"] = _error(e)
        state.record_error(e.code, e.detail, settings.ai_model_effective)
        result["latency_ms"] = int((time.monotonic() - started) * 1000)
        return result

    try:
        reply = provider.complete(TEST_PROMPT, max_tokens=64, effort="low")
    except AIError as e:
        log.warning("AI connection test failed: %s (%s)", e.code, e.detail or "-")
        result["error"] = _error(e)
        state.record_error(e.code, e.detail, result["model"])
    else:
        result.update(ok=True, model=reply.model, reply=reply.text[:200] or t("ai.empty_reply"))
        state.record_ok(reply.model)
    result["latency_ms"] = int((time.monotonic() - started) * 1000)
    result["models"] = provider.list_models() if hasattr(provider, "list_models") else None
    return result




def _error(e: AIError) -> dict:
    return {"code": e.code, "message": e.message, "detail": e.detail, "action": e.action}
