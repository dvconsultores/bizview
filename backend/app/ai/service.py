"""AI status and connection test for the super user (FR-011, FR-012)."""
import logging
import time
from urllib.parse import urlsplit

from app.ai import AIError, ToolSpec, get_provider, state
from app.config import Settings
from app.i18n import t

log = logging.getLogger("app.ai")

TEST_PROMPT = "Responde únicamente con la palabra: OK"
# A second, tiny request: tools are where providers differ most, and a model that answers text but
# cannot call a tool leaves the assistant useless (feature 028 depends on tool calls).
TEST_TOOL = ToolSpec(name="ping",
                     description="Confirma que puedes llamar herramientas.",
                     parameters={"type": "object",
                                 "properties": {"ok": {"type": "boolean"}},
                                 "required": ["ok"]})


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
    """A real request and a real tool call, plus the models the endpoint reports.

    The super user cannot fix «the provider returned an error» without the provider's own words,
    so every failure keeps its code, its redacted detail and the action to take; the outcome is
    recorded in `ai_status`, which is what `/api/health` and the Auto refusal read.
    """
    result = {"ok": False, "provider": settings.ai_provider,
              "model": settings.ai_model_effective, "latency_ms": None, "reply": None,
              "error": None, "tool_call": None, "models": None}
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
        result["tool_call"] = _tool_round(provider, result)
        result["ok"] = bool(result["tool_call"]["ok"])
    result["latency_ms"] = int((time.monotonic() - started) * 1000)
    result["models"] = provider.list_models() if hasattr(provider, "list_models") else None
    return result


def _tool_round(provider, result: dict) -> dict:
    """One message with one tool offered: the model has to answer with a tool call."""
    from app.ai import ChatMessage

    round_result = {"ok": False, "name": None, "latency_ms": None}
    started = time.monotonic()
    try:
        reply = provider.chat([ChatMessage(role="user", content="Llama a la herramienta ping.")],
                              tools=[TEST_TOOL], max_tokens=64)
    except AIError as e:
        log.warning("AI tool test failed: %s (%s)", e.code, e.detail or "-")
        round_result["error"] = _error(e)
        state.record_error(e.code, e.detail, result["model"])
    else:
        call = reply.tool_calls[0] if reply.tool_calls else None
        round_result.update(ok=call is not None, name=call.name if call else None)
        if call is None:
            round_result["error"] = {"code": "invalid_tool_call", "message": t("ai.test.no_tool"),
                                     "detail": None, "action": None}
    round_result["latency_ms"] = int((time.monotonic() - started) * 1000)
    return round_result


def _error(e: AIError) -> dict:
    return {"code": e.code, "message": e.message, "detail": e.detail, "action": e.action}
