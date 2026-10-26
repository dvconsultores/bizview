"""What a provider failure means, in one closed vocabulary (feature 035).

Every provider — the Anthropic SDK, an OpenAI-compatible endpoint, or an Anthropic-compatible
third party such as DeepSeek — maps its failures here, and everything downstream (the chat bubble,
`/api/health`, the Administración page, Auto mode) reads only these codes. Adding a code means
adding its text to `app/i18n/{es,en}.py` and to `MESSAGES`: a test walks the list.
"""
from __future__ import annotations

from typing import Literal

Code = Literal["not_configured", "no_credit", "bad_key", "model_not_found", "rate_limited",
               "context_too_long", "provider_down", "invalid_tool_call", "refused",
               "history_invalid", "provider_error"]

CODES: tuple[str, ...] = ("not_configured", "no_credit", "bad_key", "model_not_found",
                          "rate_limited", "context_too_long", "provider_down",
                          "invalid_tool_call", "refused", "history_invalid", "provider_error")

# Text of each code, in the default language, kept next to the catalogue for the docstring tests.
MESSAGES: dict[str, str] = {
    "not_configured": "La IA no está configurada.",
    "no_credit": "La cuenta del proveedor de IA no tiene saldo; recárgala o cambia de clave.",
    "bad_key": "La clave de API no es válida o no tiene permiso para este modelo.",
    "model_not_found": "El modelo configurado no existe o no está disponible.",
    "rate_limited": "El proveedor limitó las solicitudes. Intenta de nuevo en unos minutos.",
    "context_too_long": "La conversación superó el contexto máximo del modelo.",
    "provider_down": "No se pudo hablar con el proveedor de IA: no responde, no se llega a él "
                     "o devuelve un error del servidor.",
    "invalid_tool_call": "El modelo devolvió una llamada a herramienta mal formada.",
    "refused": "El proveedor rechazó la solicitud.",
    # 036: the conversation itself cannot be replayed (a result whose tool_use is gone). Sending it
    # again would fail identically: the reader repairs it, and nothing is retried automatically.
    "history_invalid": "La conversación guardada no se puede reenviar al proveedor; "
                       "repárala y vuelve a intentarlo.",
    "provider_error": "El proveedor de IA devolvió un error; revisa la clave, el saldo y "
                      "el modelo en Administración → IA.",
}

# Codes a person fixes in Administración → IA; the bubble offers that link and Auto refuses to run.
ADMIN_CODES: frozenset[str] = frozenset({"not_configured", "no_credit", "bad_key",
                                        "model_not_found"})
# Codes worth one automatic retry: the same request may well work in a minute.
TRANSIENT_CODES: frozenset[str] = frozenset({"rate_limited", "provider_down"})
# Non-transient codes that make every run pointless until somebody fixes the installation.
BLOCKING_CODES: frozenset[str] = frozenset({"no_credit", "bad_key", "model_not_found"})

Action = Literal["admin_ai", "retry"]


def action_for(code: str) -> Action | None:
    """The one thing the reader can do about `code`, or None when there is nothing to press."""
    if code in ADMIN_CODES:
        return "admin_ai"
    if code in TRANSIENT_CODES:
        return "retry"
    return None


def transient(code: str) -> bool:
    return code in TRANSIENT_CODES


def blocking(code: str | None) -> bool:
    return code in BLOCKING_CODES


# Body markers, checked in this order: a conversation that is too long is the reader's to shorten,
# so it wins over a body that happens to mention the model too.
CONTEXT_MARKERS = ("maximum context length", "context_length_exceeded", "context length",
                   "too many tokens", "prompt is too long")
MODEL_MARKERS = ("model not exist", "model_not_found", "no such model", "unknown model",
                 "invalid model", "model does not exist")

# HTTP statuses whose meaning does not depend on the body.
STATUS_CODES: dict[int, str] = {401: "bad_key", 402: "no_credit", 403: "bad_key",
                                404: "model_not_found", 429: "rate_limited"}

MAX_DETAIL = 300


def code_for_status(status: int | None) -> str:
    """The code for a bare HTTP status: what the SDK classes above do not already name."""
    if status is None:
        return "provider_error"
    if status >= 500:
        return "provider_down"
    return STATUS_CODES.get(status, "provider_error")


def code_for_body(status: int | None, body: str) -> str:
    """Refine a status with what the body says (providers disagree on 400 vs 404 for a model)."""
    lowered = body.lower()
    if any(marker in lowered for marker in CONTEXT_MARKERS):
        return "context_too_long"
    if any(marker in lowered for marker in MODEL_MARKERS):
        return "model_not_found"
    return code_for_status(status)


def detail_of(text: str, secret: str | None = None, limit: int = MAX_DETAIL) -> str:
    """The provider's own words, safe to store and show: key out, capped, one line.

    Newlines are collapsed so a JSON body stays readable in a bubble, and the key is removed even
    when a provider echoes the request back.
    """
    flat = " ".join(str(text).split())
    if secret:
        flat = flat.replace(secret, "***")
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"
