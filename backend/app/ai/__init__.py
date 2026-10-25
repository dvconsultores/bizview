"""Optional AI provider layer (constitution VIII).

Only strings composed by product code reach a provider: aggregates and metadata, never raw source
records, credentials, or users' personal data. Every feature that calls `complete()` documents
what it sends. `chat()` callers send only what the assistant tool layer composed (sanitised).
`context` is dynamic per-round text sent after the history (never stored); keep it out of
`system` so system+history remain a cacheable prefix.
Provider keys never leave this package: errors are redacted before they surface.
"""
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from app.config import Settings
from app.i18n import t

ERROR_CODES = ("not_configured", "invalid_key", "forbidden", "model_not_found", "no_credit",
               "rate_limited", "unreachable", "timeout", "refused", "context_too_long",
               "provider_error")

MESSAGES = {
    "not_configured": "La IA no está configurada.",
    "invalid_key": "La clave de API no es válida.",
    "forbidden": "La clave de API no tiene permiso para usar este modelo.",
    "model_not_found": "El modelo configurado no existe o no está disponible.",
    "no_credit": "La cuenta del proveedor de IA no tiene saldo; recárgala o cambia de clave.",
    "rate_limited": "El proveedor limitó las solicitudes. Intenta de nuevo en unos minutos.",
    "unreachable": "No se pudo conectar con el proveedor de IA.",
    "timeout": "El proveedor de IA no respondió a tiempo.",
    "refused": "El proveedor rechazó la solicitud.",
    "context_too_long": "La conversación superó el contexto máximo del modelo.",
    "provider_error": "El proveedor de IA devolvió un error; revisa la clave, el saldo y "
                      "el modelo en Administración → IA.",
}


class AIError(Exception):
    def __init__(self, code: str, detail: str | None = None):
        assert code in ERROR_CODES, code
        super().__init__(code)
        self.code = code
        self.detail = detail  # already redacted; for logs only

    @property
    def message(self) -> str:
        return t(f"ai.error.{self.code}")


@dataclass(frozen=True)
class AIReply:
    text: str
    model: str


ChatRole = Literal["user", "assistant", "tool"]
StopReason = Literal["end", "tool_use", "max_tokens"]


@dataclass(frozen=True)
class ToolSpec:            # a tool the model may call
    name: str
    description: str
    parameters: dict       # JSON Schema of the arguments (type: object)


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    args: dict
    args_error: str | None = None


def vision_enabled(settings: Settings) -> bool:
    """Whether the configured model can read images (feature 024, research R2).

    `AI_VISION=auto` (the default) trusts the Anthropic-style provider and distrusts an
    OpenAI-compatible endpoint, whose catalogue the product cannot know."""
    if settings.ai_vision == "true":
        return True
    if settings.ai_vision == "false":
        return False
    return settings.ai_provider == "anthropic"


@dataclass(frozen=True)
class ImagePart:           # an image attached to a user turn (feature 024)
    media_type: str
    data: bytes


@dataclass(frozen=True)
class ChatMessage:         # provider-neutral history entry
    role: ChatRole
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()   # assistant turns only
    tool_call_id: str | None = None         # tool results only (answers ToolCall.id)
    reasoning: str | None = None            # in memory only, never stored
    images: tuple[ImagePart, ...] = ()      # user turns only; never stored in the history


@dataclass(frozen=True)
class ChatUsage:
    input: int = 0
    output: int = 0
    cached: int = 0

    def __post_init__(self) -> None:
        # Clamp cached to a valid subset of input.
        object.__setattr__(self, "cached", max(0, min(self.cached, self.input)))

    @property
    def total(self) -> int:
        return self.input + self.output

    def weighted(self, weight: float) -> int:
        """Cost estimate where cached tokens cost `weight` (0..1) of normal tokens."""
        return round((self.input - self.cached) + self.output + weight * self.cached)


@dataclass(frozen=True)
class ChatReply:
    text: str
    tool_calls: tuple[ToolCall, ...]
    usage: ChatUsage
    model: str
    stop_reason: StopReason = "end"
    reasoning: str | None = None


class Provider(Protocol):
    name: str
    model: str

    def complete(self, prompt: str, *, system: str | None = None, max_tokens: int = 1024,
                 effort: str | None = None) -> AIReply: ...

    def chat(self, messages: Sequence[ChatMessage], *,
             tools: Sequence[ToolSpec] = (), system: str | None = None,
             max_tokens: int = 4096, context: str | None = None) -> ChatReply: ...


def redact(text: str, secret: str | None, limit: int = 200) -> str:
    """Truncate provider messages and remove the key, so they are safe to log or return."""
    if secret:
        text = text.replace(secret, "***")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def get_provider(settings: Settings) -> Provider:
    """The configured provider; raises AIError('not_configured') when AI is off or incomplete."""
    if not settings.ai_enabled:
        raise AIError("not_configured")
    if settings.ai_provider == "fake":  # test hooks only; re-checked at call time
        from app.ai import fake
        if not fake.enabled():
            raise AIError("not_configured")
        return fake.SHARED
    if settings.ai_provider == "anthropic":
        from app.ai.anthropic_provider import AnthropicProvider
        return AnthropicProvider(settings)
    from app.ai.openai_compatible import OpenAICompatibleProvider
    return OpenAICompatibleProvider(settings)
