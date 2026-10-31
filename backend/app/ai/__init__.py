"""Optional AI provider layer (constitution VIII).

Only strings composed by product code reach a provider: aggregates and metadata, never raw source
records, credentials, or users' personal data. Every feature that calls `complete()` documents
what it sends: the optional help agent (feature 033) is the only caller left after 045 removed the
in-app authoring agent.
Provider keys never leave this package: errors are redacted before they surface.
"""
from dataclasses import dataclass
from typing import Protocol

from app.ai.errors import CODES as ERROR_CODES
from app.ai.errors import MESSAGES as MESSAGES
from app.ai.errors import action_for, transient
from app.config import Settings
from app.i18n import t


class AIError(Exception):
    """A provider failure with a code from `app.ai.errors` and the provider's own words."""

    def __init__(self, code: str, detail: str | None = None,
                 retry_after: float | None = None):
        assert code in ERROR_CODES, code
        super().__init__(code)
        self.code = code
        self.detail = detail            # already redacted; for logs and the admin page
        self.retry_after = retry_after  # seconds the provider asked for, when it said

    @property
    def message(self) -> str:
        return t(f"ai.error.{self.code}")

    @property
    def action(self) -> str | None:
        return action_for(self.code)

    @property
    def transitory(self) -> bool:
        return transient(self.code)



@dataclass(frozen=True)
class AIReply:
    text: str
    model: str


class Provider(Protocol):
    name: str
    model: str

    def complete(self, prompt: str, *, system: str | None = None, max_tokens: int = 1024,
                 effort: str | None = None) -> AIReply: ...


def redact(text: str, secret: str | None, limit: int = 200) -> str:
    """Truncate provider messages and remove the key, so they are safe to log or return."""
    if secret:
        text = text.replace(secret, "***")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def get_provider(settings: Settings) -> Provider:
    """The configured provider; raises AIError('not_configured') when AI is off or incomplete."""
    if not settings.ai_enabled:
        raise AIError("not_configured")
    if settings.ai_provider == "anthropic":
        from app.ai.anthropic_provider import AnthropicProvider
        return AnthropicProvider(settings)
    from app.ai.openai_compatible import OpenAICompatibleProvider
    return OpenAICompatibleProvider(settings)
