"""Any OpenAI-compatible chat endpoint (OpenAI, Ollama, vLLM, LM Studio, ...), over httpx.

Lets a customer keep all data on premises with a local model (constitution VIII).
"""
import base64
import json
import time
from collections.abc import Callable, Sequence

import httpx

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
from app.ai.errors import (  # noqa: F401  (re-exported: the Anthropic provider imports them)
    CONTEXT_MARKERS,
    MODEL_MARKERS,
    STATUS_CODES,
    code_for_body,
    detail_of,
)
from app.config import Settings
from app.i18n import t


def _usage(usage_data: dict) -> ChatUsage:
    """Extract ChatUsage from an OpenAI-compatible usage dict defensively."""
    input_tokens = usage_data.get("prompt_tokens") or 0
    output_tokens = usage_data.get("completion_tokens") or 0
    cached = usage_data.get("prompt_cache_hit_tokens")
    if cached is None:
        details = usage_data.get("prompt_tokens_details")
        cached = details.get("cached_tokens") if isinstance(details, dict) else None
    cached = int(cached or 0)
    return ChatUsage(input=input_tokens, output=output_tokens, cached=cached)


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
        self._chat_timeout = settings.ai_chat_timeout_seconds
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
        return AIReply(text=text.strip(), model=data.get("model") or self.model)

    def chat(self, messages: Sequence[ChatMessage], *,
             tools: Sequence[ToolSpec] = (), system: str | None = None,
             max_tokens: int = 4096, context: str | None = None) -> ChatReply:
        base_messages = self._with_context(self._messages(messages, system), context)
        body: dict = {"model": self.model, "max_tokens": max_tokens,
                      "messages": base_messages}
        if tools:
            body["tools"] = [{"type": "function",
                              "function": {"name": t.name, "description": t.description,
                                           "parameters": t.parameters}} for t in tools]
        data = self._post(body, timeout=self._chat_timeout)
        try:
            choice = data["choices"][0]
            finish = choice.get("finish_reason")
            if finish == "content_filter":
                raise AIError("refused", "content_filter")
            message = choice.get("message") or {}
            reasoning = (message.get("reasoning_content") or "").strip() or None
            tool_calls: list[ToolCall] = []
            for index, raw in enumerate(message.get("tool_calls") or []):
                function = raw.get("function") or {}
                args_text = function.get("arguments") or "{}"
                args_error: str | None = None
                try:
                    args = json.loads(args_text)
                except json.JSONDecodeError as e:
                    args = {}
                    short = t("ai.json_position", msg=e.msg, line=e.lineno, column=e.colno)
                    args_error = redact(short, self._key, limit=120)
                if args_error is None and not isinstance(args, dict):
                    args = {}
                    args_error = "se esperaba un objeto JSON"
                tool_calls.append(ToolCall(id=raw.get("id") or f"call_{index}",
                                           name=function.get("name") or "", args=args,
                                           args_error=args_error))
            text = (message.get("content") or "").strip()
            usage_data = data.get("usage") or {}
            usage = _usage(usage_data)
            stop_reason = "tool_use" if finish == "tool_calls" or tool_calls else \
                "max_tokens" if finish == "length" else "end"
            return ChatReply(text=text, tool_calls=tuple(tool_calls), usage=usage,
                             model=data.get("model") or self.model, stop_reason=stop_reason,
                             reasoning=reasoning)
        except AIError:
            raise
        except (KeyError, IndexError, TypeError, AttributeError):
            raise AIError("provider_error", "unexpected response shape") from None

    def _with_context(self, base: list[dict], context: str | None) -> list[dict]:
        if not context:
            return base
        if not base or base[-1]["role"] not in ("user", "tool"):
            return [*base, {"role": "user", "content": context}]
        last = dict(base[-1])
        if isinstance(last["content"], list):          # content parts: append a text part
            last["content"] = [*last["content"], {"type": "text", "text": context}]
        else:
            last["content"] = f"{last['content']}\n\n{context}"
        return [*base[:-1], last]

    def _messages(self, messages: Sequence[ChatMessage], system: str | None) -> list[dict]:
        result: list[dict] = []
        if system:
            result.append({"role": "system", "content": system})
        last_user_index = -1
        for index, msg in enumerate(messages):
            if msg.role == "user":
                last_user_index = index
        for index, msg in enumerate(messages):
            if msg.role == "user":
                if msg.images:
                    parts: list[dict] = [{"type": "text", "text": msg.content}]
                    parts += [
                        {"type": "image_url",
                         "image_url": {"url": "data:{};base64,{}".format(
                             img.media_type, base64.b64encode(img.data).decode("ascii"))}}
                        for img in msg.images
                    ]
                    result.append({"role": "user", "content": parts})
                else:
                    result.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                item: dict = {"role": "assistant", "content": msg.content or None}
                if msg.tool_calls:
                    item["tool_calls"] = [
                        {"id": c.id, "type": "function",
                         "function": {"name": c.name,
                                      "arguments": json.dumps(c.args, ensure_ascii=False)}}
                        for c in msg.tool_calls]
                if msg.reasoning and (last_user_index == -1 or index > last_user_index):
                    item["reasoning_content"] = msg.reasoning
                result.append(item)
            else:  # tool
                if msg.tool_call_id is None:
                    raise ValueError("tool message requires tool_call_id")
                result.append({"role": "tool", "tool_call_id": msg.tool_call_id,
                               "content": msg.content})
        return result

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
