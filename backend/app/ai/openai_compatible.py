"""Any OpenAI-compatible chat endpoint (OpenAI, Ollama, vLLM, LM Studio, ...), over httpx.

Lets a customer keep all data on premises with a local model (constitution VIII).
"""
import time
from collections.abc import Callable

import httpx

from app.ai import (
    AIError,
    AIReply,
)
from app.ai.errors import (  # noqa: F401  (re-exported: the Anthropic provider imports them)
    CONTEXT_MARKERS,
    MODEL_MARKERS,
    STATUS_CODES,
    code_for_body,
    detail_of,
)
from app.config import Settings

RETRY_AFTER_MAX = 10.0
RETRY_AFTER_DEFAULT = 2.0


def retry_after_seconds(headers) -> float:
    """Seconds to wait before the single rate-limit retry: Retry-After (seconds) capped at
    10, else 2."""
    header = headers.get("Retry-After")
    if header is not None:
        try:
            value = float(header)
            if value >= 0:
                return min(value, RETRY_AFTER_MAX)
        except ValueError:
            pass
    return RETRY_AFTER_DEFAULT


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        assert settings.ai_base_url and settings.ai_model
        self.model = settings.ai_model
        self._key = settings.ai_api_key.get_secret_value() if settings.ai_api_key else None
        self._sleep = sleep
        headers = {"Authorization": f"Bearer {self._key}"} if self._key else {}
        self._client = httpx.Client(base_url=settings.ai_base_url, headers=headers,
                                    timeout=settings.ai_timeout_seconds, transport=transport)

    def complete(self, prompt: str, *, system: str | None = None, max_tokens: int = 1024,
                 effort: str | None = None) -> AIReply:
        messages = ([{"role": "system", "content": system}] if system else []) + \
            [{"role": "user", "content": prompt}]
        data = self._post({"model": self.model, "messages": messages, "max_tokens": max_tokens})
        try:
            choice = data["choices"][0]
            text = (choice.get("message") or {}).get("content") or ""
        except (KeyError, IndexError, TypeError, AttributeError):
            raise AIError("provider_error", "unexpected response shape") from None
        if choice.get("finish_reason") == "content_filter":
            raise AIError("refused", "content_filter")
        usage = data.get("usage") or {}
        return AIReply(text=text.strip(), model=data.get("model") or self.model,
                       tokens_in=int(usage.get("prompt_tokens") or 0),
                       tokens_out=int(usage.get("completion_tokens") or 0))




    def _post(self, body: dict, timeout: float | None = None) -> dict:
        attempt = 1
        while True:
            try:
                if timeout is not None:
                    r = self._client.post("/chat/completions", json=body, timeout=timeout)
                else:
                    r = self._client.post("/chat/completions", json=body)
            except httpx.TimeoutException as e:
                raise AIError("provider_down", self._safe(e)) from None
            except httpx.TransportError as e:
                raise AIError("provider_down", self._safe(e)) from None
            if r.status_code == 429 and attempt == 1:
                self._sleep(self._retry_after(r))
                attempt = 2
                continue
            if r.status_code >= 400:
                # 400 vs 404 depends on the provider: the body decides between a conversation that
                # is too long, a model that does not exist, and anything else.
                code = code_for_body(r.status_code, r.text) if r.status_code < 500 else \
                    code_for_body(r.status_code, "")
                raise AIError(code, self._safe(f"HTTP {r.status_code}: {r.text}"),
                              retry_after=(retry_after_seconds(r.headers)
                                           if r.status_code == 429 else None))
            try:
                return r.json()
            except ValueError:
                raise AIError("provider_error", "unexpected response shape") from None

    def _retry_after(self, response: httpx.Response) -> float:
        return retry_after_seconds(response.headers)

    def _safe(self, error: object) -> str:
        return detail_of(str(error), self._key)

    def list_models(self) -> list[str] | None:
        """Model ids the endpoint reports, or None when it has no `/models` (common in clones)."""
        try:
            r = self._client.get("/models", timeout=10)
            if r.status_code >= 400:
                return None
            data = r.json()
        except Exception:            # unreachable, no endpoint, unexpected shape: not an error
            return None
        rows = data.get("data") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return None
        ids = [row.get("id") for row in rows
               if isinstance(row, dict) and isinstance(row.get("id"), str)]
        return ids or None
