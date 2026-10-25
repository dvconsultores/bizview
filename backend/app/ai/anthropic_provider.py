"""Claude through the official Anthropic SDK (research R6)."""
import base64
import time
from collections.abc import Callable, Sequence

import anthropic
import httpx2  # the SDK's HTTP client since anthropic 1.9 (httpx clients are rejected)

from app.ai import (
    AIError,
    AIReply,
    ChatMessage,
    ChatReply,
    ChatUsage,
    ToolCall,
    ToolSpec,
    redact,
)
from app.ai.openai_compatible import CONTEXT_MARKERS, MODEL_MARKERS, retry_after_seconds
from app.config import Settings

# Models that accept server-side refusal fallback ("default" routing, beta 2026-07-01).
FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"
CACHE_CONTROL = {"type": "ephemeral"}


def _tokens(usage, name: str) -> int:
    return getattr(usage, name, 0) or 0



# Statuses the SDK classes above do not cover. 402 is the balance of an Anthropic-compatible
# provider (DeepSeek answers it when the account runs out, mid-run).
STATUS_CODES = {402: "no_credit", 404: "model_not_found", 429: "rate_limited"}


def code_for_status(status: int | None) -> str:
    """A provider's HTTP status as one of our AI error codes."""
    return STATUS_CODES.get(status, "provider_error")


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, settings: Settings, transport: httpx2.BaseTransport | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        assert settings.ai_api_key is not None and settings.ai_model_effective
        self.model = settings.ai_model_effective
        self._key = settings.ai_api_key.get_secret_value()
        self._chat_timeout = settings.ai_chat_timeout_seconds
        self._sleep = sleep
        client_kwargs: dict = {
            "api_key": self._key,
            "base_url": settings.ai_base_url,  # None → the SDK default (api.anthropic.com)
            "timeout": settings.ai_timeout_seconds,
            "max_retries": 1,
        }
        if transport is not None:  # tests: a mocked transport, never the network
            client_kwargs["http_client"] = httpx2.Client(
                transport=transport, timeout=settings.ai_timeout_seconds)
        self._client = anthropic.Anthropic(**client_kwargs)

    def complete(self, prompt: str, *, system: str | None = None, max_tokens: int = 1024,
                 effort: str | None = None) -> AIReply:
        params: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            params["system"] = system
        if effort:
            params["output_config"] = {"effort": effort}
        response = self._create(params)
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        return AIReply(text=text, model=response.model)

    def chat(self, messages: Sequence[ChatMessage], *,
             tools: Sequence[ToolSpec] = (), system: str | None = None,
             max_tokens: int = 4096, context: str | None = None) -> ChatReply:
        turns = self._messages(messages)
        if system:
            params: dict = {
                "model": self.model,
                "max_tokens": max_tokens,
                "system": [{
                    "type": "text",
                    "text": system,
                    "cache_control": dict(CACHE_CONTROL),
                }],
                "messages": self._with_context(turns, context),
            }
        else:
            params = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": self._with_context(turns, context),
            }
        if tools:
            params["tools"] = [{"name": t.name, "description": t.description,
                                "input_schema": t.parameters} for t in tools]
        response = self._create(params, timeout=self._chat_timeout, max_retries=0)

        text = "".join(b.text for b in response.content if b.type == "text").strip()
        tool_calls = tuple(ToolCall(b.id, b.name, dict(b.input))
                           for b in response.content if b.type == "tool_use")
        u = response.usage
        input_tokens = (
            _tokens(u, "input_tokens")
            + _tokens(u, "cache_creation_input_tokens")
            + _tokens(u, "cache_read_input_tokens")
        )
        usage = ChatUsage(
            input=input_tokens,
            output=_tokens(u, "output_tokens"),
            cached=_tokens(u, "cache_read_input_tokens"),
        )
        stop = response.stop_reason
        stop_reason = "tool_use" if stop == "tool_use" else \
            "max_tokens" if stop == "max_tokens" else "end"
        return ChatReply(text=text, tool_calls=tool_calls, usage=usage,
                         model=response.model, stop_reason=stop_reason)

    def _with_context(self, turns: list[dict], context: str | None) -> list[dict]:
        """Add cache_control to stable end and last history block, then append context.

        Compaction of the last round means the very last block is re-written next turn;
        mark the block before the last assist tool round so the provider can re-read
        the already-compacted prefix. Context is never marked.
        """
        if not turns:
            if context:
                return [{"role": "user", "content": [{"type": "text", "text": context}]}]
            return []

        result = [dict(turn) for turn in turns]
        for turn in result:
            turn["content"] = [dict(block) for block in turn["content"]]

        last_idx = len(result) - 1
        last_block = result[last_idx]["content"][-1]
        last_block.setdefault("cache_control", dict(CACHE_CONTROL))

        # Find last assistant turn that contains tool_use blocks
        last_tool_assistant = -1
        for i, turn in enumerate(result):
            if turn["role"] != "assistant":
                continue
            if any(block.get("type") == "tool_use" for block in turn["content"]):
                last_tool_assistant = i
        if last_tool_assistant > 0:
            stable = result[last_tool_assistant - 1]
            stable["content"][-1].setdefault("cache_control", dict(CACHE_CONTROL))

        if context:
            if result[-1]["role"] == "user":
                result[-1]["content"].append({"type": "text", "text": context})
            else:
                result.append({"role": "user", "content": [{"type": "text", "text": context}]})
        return result

    def _messages(self, messages: Sequence[ChatMessage]) -> list[dict]:
        """Neutral history → Messages API turns; consecutive same-role turns are merged so all
        tool results answering one assistant turn travel in the next user message."""
        merged: list[dict] = []
        for msg in messages:
            if msg.role == "user":
                content: list[dict] = [{"type": "text", "text": msg.content}]
                content.extend(
                    {"type": "image",
                     "source": {"type": "base64", "media_type": img.media_type,
                                "data": base64.b64encode(img.data).decode("ascii")}}
                    for img in msg.images
                )
                block: dict = {"role": "user", "content": content}
            elif msg.role == "assistant":
                content: list[dict] = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for call in msg.tool_calls:
                    content.append({"type": "tool_use", "id": call.id, "name": call.name,
                                    "input": call.args})
                if not content:
                    continue
                block = {"role": "assistant", "content": content}
            else:  # tool
                if msg.tool_call_id is None:
                    raise ValueError("tool message requires tool_call_id")
                block = {"role": "user",
                         "content": [{"type": "tool_result", "tool_use_id": msg.tool_call_id,
                                      "content": msg.content}]}
            if merged and merged[-1]["role"] == block["role"]:
                merged[-1]["content"].extend(block["content"])
            else:
                merged.append(block)
        return merged

    def _create(
        self, params: dict, timeout: float | None = None, max_retries: int | None = None
    ):
        client = (
            self._client
            if max_retries is None
            else self._client.with_options(max_retries=max_retries)
        )
        manual_retry = max_retries == 0
        attempts = 0

        while True:
            attempts += 1
            try:
                response = self._send(client, params, timeout)
                break
            except anthropic.RateLimitError as e:
                if manual_retry and attempts == 1:
                    self._sleep(retry_after_seconds(e.response.headers))
                    continue
                raise AIError("rate_limited", self._safe(e)) from None
            except anthropic.AuthenticationError as e:
                raise AIError("invalid_key", self._safe(e)) from None
            except anthropic.PermissionDeniedError as e:
                raise AIError("forbidden", self._safe(e)) from None
            except anthropic.NotFoundError as e:
                raise AIError("model_not_found", self._safe(e)) from None
            except anthropic.BadRequestError as e:
                detail = self._safe(e)
                lowered = str(e).lower()
                if any(marker in lowered for marker in CONTEXT_MARKERS):
                    raise AIError("context_too_long", detail) from None
                if any(marker in lowered for marker in MODEL_MARKERS):
                    raise AIError("model_not_found", detail) from None
                raise AIError("provider_error", detail) from None
            except anthropic.APITimeoutError as e:  # subclass of APIConnectionError: check first
                raise AIError("timeout", self._safe(e)) from None
            except anthropic.APIConnectionError as e:
                raise AIError("unreachable", self._safe(e)) from None
            except anthropic.APIStatusError as e:
                # The SDK has no class for every status: an exhausted balance is a 402 on the
                # Anthropic-compatible endpoints (DeepSeek), and it read as an unknown error.
                raise AIError(code_for_status(getattr(e, "status_code", None)),
                              self._safe(e)) from None

        if response.stop_reason == "refusal":
            category = getattr(getattr(response, "stop_details", None), "category", None)
            raise AIError("refused", f"category={category}")
        return response

    def _send(self, client, params: dict, timeout: float | None):
        if self.model in FALLBACK_MODELS:
            if timeout is not None:
                return client.beta.messages.create(
                    **params, betas=[FALLBACK_BETA], fallbacks="default", timeout=timeout)
            return client.beta.messages.create(
                **params, betas=[FALLBACK_BETA], fallbacks="default")
        if timeout is not None:
            return client.messages.create(**params, timeout=timeout)
        return client.messages.create(**params)

    def _safe(self, error: Exception) -> str:
        return redact(f"{type(error).__name__}: {error}", self._key)
