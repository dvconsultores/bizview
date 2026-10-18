"""Feature 014 / T002: provider chat() with tool calls (mocked transports only, never a live
AI)."""
import dataclasses
import json

import httpx
import httpx2
import pytest

from app.ai import (
    AIError,
    ChatMessage,
    ChatReply,
    ChatUsage,
    ToolCall,
    ToolSpec,
    fake,
    get_provider,
)
from app.ai.anthropic_provider import FALLBACK_BETA, FALLBACK_MODELS, AnthropicProvider
from app.ai.openai_compatible import OpenAICompatibleProvider
from app.config import Settings

KEY = "sk-test-SECRET-value-1234567890"

HISTORY = [
    ChatMessage("user", "Quiero ventas por marca"),
    ChatMessage("assistant", "Miro las fuentes",
                tool_calls=(ToolCall("call_1", "list_sources", {}),)),
    ChatMessage("tool", '[{"name": "ERP", "kind": "postgresql"}]', tool_call_id="call_1"),
    ChatMessage("user", "Usa ERP"),
]
TOOLS = (
    ToolSpec("list_sources", "Lista las fuentes",
             {"type": "object", "properties": {}}),
    ToolSpec("describe_source", "Estructura",
             {"type": "object", "properties": {"name": {"type": "string"}},
              "required": ["name"]}),
)


def settings(**kw) -> Settings:
    return Settings(database_url_bi="postgresql://x@localhost/x", **kw)


def oc(handler, key=KEY) -> OpenAICompatibleProvider:
    s = settings(ai_provider="openai_compatible", ai_model="llama3",
                 ai_base_url="http://ollama:11434/v1", ai_api_key=key)
    return OpenAICompatibleProvider(s, transport=httpx.MockTransport(handler))


def an(handler, model="claude-haiku-4-5") -> AnthropicProvider:
    s = settings(ai_provider="anthropic", ai_api_key=KEY, ai_model=model,
                 ai_base_url="http://anthropic.test")
    return AnthropicProvider(s, transport=httpx2.MockTransport(handler))


def message(content, stop_reason="end_turn", model="claude-haiku-4-5", usage=None) -> dict:
    usage = usage or {}
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": usage,
    }


def handler_not_called():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("handler should not be called")

    return handler


# --- OpenAI-compatible provider -----------------------------------------------------------

def test_openai_chat_request_mapping():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["raw"] = request.content.decode()
        captured["auth"] = request.headers.get("authorization", "")
        return httpx.Response(200, json={
            "id": "chatcmpl-1", "object": "chat.completion", "created": 1,
            "model": "llama3",
            "choices": [{"index": 0, "message": {
                "role": "assistant", "content": "",
                "tool_calls": [{"id": "c9", "type": "function",
                                "function": {"name": "describe_source",
                                             "arguments": '{"name": "ERP"}'}}]},
                "finish_reason": "tool_calls"}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30},
        })

    reply = oc(handler).chat(HISTORY, tools=TOOLS, system="sys", max_tokens=900)

    body = captured["body"]
    assert body["messages"][0] == {"role": "system", "content": "sys"}
    assert body["messages"][2]["content"] == "Miro las fuentes"
    assert body["messages"][2]["tool_calls"][0] == {
        "id": "call_1", "type": "function",
        "function": {"name": "list_sources", "arguments": "{}"}}
    assert body["messages"][3] == {"role": "tool", "tool_call_id": "call_1",
                                   "content": '[{"name": "ERP", "kind": "postgresql"}]'}
    assert body["tools"][1]["function"]["parameters"]["required"] == ["name"]
    assert body["max_tokens"] == 900
    assert KEY not in captured["raw"]
    assert captured["auth"] == f"Bearer {KEY}"
    assert reply == ChatReply(
        "", (ToolCall("c9", "describe_source", {"name": "ERP"}),),
        ChatUsage(120, 30), "llama3", "tool_use")


def test_openai_chat_plain_and_stop_reasons():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hola"},
                         "finish_reason": "stop"}],
        })

    reply = oc(handler).chat(HISTORY)
    assert reply.text == "Hola"
    assert reply.tool_calls == ()
    assert reply.usage == ChatUsage(0, 0)
    assert reply.stop_reason == "end"

    def length_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"index": 0, "message": {"role": "assistant", "content": ""},
                         "finish_reason": "length"}],
        })

    assert oc(length_handler).chat(HISTORY).stop_reason == "max_tokens"


@pytest.mark.parametrize("arguments", ["{not json", "[1, 2]"])
def test_openai_chat_invalid_tool_arguments(arguments):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"index": 0, "message": {
                "role": "assistant", "content": "",
                "tool_calls": [{"id": "c1", "type": "function",
                                "function": {"name": "x", "arguments": arguments}}]},
                "finish_reason": "tool_calls"}],
        })

    reply = oc(handler).chat(HISTORY)
    assert reply.stop_reason == "tool_use"
    assert len(reply.tool_calls) == 1
    call = reply.tool_calls[0]
    assert call.id == "c1"
    assert call.name == "x"
    assert call.args == {}
    if arguments == "[1, 2]":
        assert call.args_error == "se esperaba un objeto JSON"
    else:
        assert call.args_error is not None
        assert call.args_error.startswith("Expecting")
        assert "columna" in call.args_error
        assert "{not json" not in call.args_error


def test_openai_chat_content_filter_refused():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"index": 0, "message": {"role": "assistant", "content": ""},
                         "finish_reason": "content_filter"}],
        })

    with pytest.raises(AIError) as err:
        oc(handler).chat(HISTORY)
    assert err.value.code == "refused"


def test_openai_chat_401_redacts_key():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": f"bad key {KEY}"}})

    with pytest.raises(AIError) as err:
        oc(handler).chat(HISTORY)
    assert err.value.code == "invalid_key"
    assert KEY not in (err.value.detail or "")


@pytest.mark.parametrize("body", [{}, []])
def test_openai_chat_bad_shape(body):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    with pytest.raises(AIError) as err:
        oc(handler).chat(HISTORY)
    assert err.value.code == "provider_error"


def test_openai_chat_tool_message_without_id():
    provider = oc(handler_not_called())
    with pytest.raises(ValueError):
        provider.chat([ChatMessage("tool", "x")])


def test_openai_complete_bad_shape_list():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    with pytest.raises(AIError) as err:
        oc(handler).complete("hola")
    assert err.value.code == "provider_error"


def test_openai_chat_context_joins_last_message():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"},
                         "finish_reason": "stop"}]
        })

    provider = oc(handler)

    # history ending in tool -> context joins the tool message
    provider.chat(HISTORY[:3], system="sys", context="## Estado\nX")
    messages = captured["body"]["messages"]
    assert len(messages) == 4
    assert messages[0] == {"role": "system", "content": "sys"}
    assert messages[-1] == {"role": "tool", "tool_call_id": "call_1",
                            "content": '[{"name": "ERP", "kind": "postgresql"}]\n\n## Estado\nX'}

    # history ending in user -> context joins the user message
    provider.chat(HISTORY, system="sys", context="## Estado\nX")
    messages = captured["body"]["messages"]
    assert len(messages) == 5
    assert messages[-1] == {"role": "user", "content": "Usa ERP\n\n## Estado\nX"}

    # history ending in assistant -> separate trailing user message
    provider.chat(HISTORY[:2], system="sys", context="## Estado\nX")
    messages = captured["body"]["messages"]
    assert len(messages) == 4
    assert messages[-1] == {"role": "user", "content": "## Estado\nX"}
    assert messages[-2]["role"] == "assistant"

    # empty history with system -> [system, {user: context}]
    provider.chat([], system="sys", context="## Estado\nX")
    messages = captured["body"]["messages"]
    assert len(messages) == 2
    assert messages[0] == {"role": "system", "content": "sys"}
    assert messages[1] == {"role": "user", "content": "## Estado\nX"}

    # without context -> unchanged
    provider.chat(HISTORY[:3], system="sys")
    messages = captured["body"]["messages"]
    assert len(messages) == 4
    assert messages[-1]["role"] == "tool"


def test_openai_prefix_stable_across_rounds():
    captured = []

    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"},
                         "finish_reason": "stop"}]
        })

    provider = oc(handler)
    provider.chat(HISTORY[:1], system="sys", context="estado 1")
    provider.chat(HISTORY[:3], system="sys", context="estado 2")
    body1, body2 = captured

    assert body1["messages"][0] == body2["messages"][0]  # system identical
    assert body2["messages"][1] == {"role": "user", "content": "Quiero ventas por marca"}
    assert body2["messages"][-1]["content"].endswith("estado 2")
    assert body1["messages"][-1]["content"].endswith("estado 1")
    for msg in body2["messages"][:-1]:
        assert "estado" not in json.dumps(msg)


# --- Anthropic provider -------------------------------------------------------------------

def test_anthropic_chat_request_mapping():
    captured = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["body"] = json.loads(request.content)
        captured["raw"] = request.content.decode()
        captured["x_api_key"] = request.headers.get("x-api-key", "")
        return httpx2.Response(200, json=message(
            [{"type": "text", "text": "Veamos"},
             {"type": "tool_use", "id": "toolu_1", "name": "describe_source",
              "input": {"name": "ERP"}}],
            stop_reason="tool_use",
            usage={"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 5},
        ))

    reply = an(handler).chat(HISTORY, tools=TOOLS, system="sys", max_tokens=800)

    body = captured["body"]
    assert body["system"] == [{"type": "text", "text": "sys",
                               "cache_control": {"type": "ephemeral"}}]
    assert body["tools"][0] == {"name": "list_sources", "description": "Lista las fuentes",
                                "input_schema": {"type": "object", "properties": {}}}
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user"]
    assert body["messages"][1]["content"] == [
        {"type": "text", "text": "Miro las fuentes"},
        {"type": "tool_use", "id": "call_1", "name": "list_sources", "input": {}}]
    assert body["messages"][2]["content"][0]["type"] == "tool_result"
    assert body["messages"][2]["content"][0]["tool_use_id"] == "call_1"
    assert body["messages"][2]["content"][-1] == {
        "type": "text",
        "text": "Usa ERP",
        "cache_control": {"type": "ephemeral"},
    }
    assert body["max_tokens"] == 800
    assert KEY not in captured["raw"]
    assert captured["x_api_key"] == KEY
    assert reply == ChatReply(
        "Veamos", (ToolCall("toolu_1", "describe_source", {"name": "ERP"}),),
        ChatUsage(105, 20, 5), "claude-haiku-4-5", "tool_use")


def test_anthropic_fallback_model_uses_beta():
    captured = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["url"] = str(request.url)
        captured["beta"] = request.headers.get("anthropic-beta", "")
        return httpx2.Response(200, json=message(
            [{"type": "text", "text": ""}], stop_reason="max_tokens"))

    provider = an(handler, model="claude-opus-5-5")
    assert provider.model in FALLBACK_MODELS
    reply = provider.chat(HISTORY)
    assert "/v1/messages" in captured["url"]
    assert "beta=true" in captured["url"]
    assert FALLBACK_BETA in captured["beta"]
    assert reply.stop_reason == "max_tokens"


@pytest.mark.parametrize("method", ["chat", "complete"])
def test_anthropic_refusal(method):
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=message(
            [{"type": "text", "text": "No puedo"}], stop_reason="refusal"))

    p = an(handler)
    with pytest.raises(AIError) as err:
        p.chat(HISTORY) if method == "chat" else p.complete("x")
    assert err.value.code == "refused"


def test_anthropic_401_redacts_key_and_error():
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(401, json={
            "type": "error",
            "error": {"type": "authentication_error",
                      "message": f"invalid x-api-key {KEY}"}})

    with pytest.raises(AIError) as err:
        an(handler).chat(HISTORY)
    assert err.value.code == "invalid_key"
    assert KEY not in (err.value.detail or "")


def test_anthropic_400_prompt_too_long_maps_to_context_too_long():
    calls = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(request)
        return httpx2.Response(400, json={
            "type": "error",
            "error": {
                "type": "invalid_request_error",
                "message": "prompt is too long: 215000 tokens > 200000 maximum",
            },
        })

    with pytest.raises(AIError) as err:
        an(handler).chat(HISTORY)

    assert err.value.code == "context_too_long"
    assert KEY not in (err.value.detail or "")
    assert len(calls) == 1


def test_anthropic_other_400_is_provider_error():
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(400, json={
            "type": "error",
            "error": {
                "type": "invalid_request_error",
                "message": "messages: roles must alternate",
            },
        })

    with pytest.raises(AIError) as err:
        an(handler).chat(HISTORY)

    assert err.value.code == "provider_error"


def test_anthropic_cache_breakpoints_and_context_tail():
    captured = {}

    def handler(request):
        captured["raw"] = request.content.decode()
        captured["body"] = json.loads(request.content)
        return httpx2.Response(200, json=message([{"type": "text", "text": "ok"}]))

    provider = an(handler)
    provider.chat(HISTORY[:3], tools=TOOLS, system="sys", context="## Estado\nX")
    body = captured["body"]
    assert body["system"] == [{"type": "text", "text": "sys",
                               "cache_control": {"type": "ephemeral"}}]
    assert all("cache_control" not in tool for tool in body["tools"])
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user"]
    assert body["messages"][0]["content"][-1]["cache_control"] == {"type": "ephemeral"}
    assert body["messages"][2]["content"][0]["type"] == "tool_result"
    assert body["messages"][2]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert body["messages"][2]["content"][-1] == {"type": "text", "text": "## Estado\nX"}
    assert all("cache_control" not in block
               for block in body["messages"][1]["content"])
    assert captured["raw"].count('"cache_control"') == 3


def test_anthropic_context_after_assistant_turn():
    captured = []

    def handler(request):
        captured.append(json.loads(request.content))
        return httpx2.Response(200, json=message([{"type": "text", "text": "ok"}]))

    provider = an(handler)
    provider.chat(HISTORY[:2], context="ctx")
    body = captured[-1]
    assert body["messages"][-1] == {"role": "user", "content": [{"type": "text", "text": "ctx"}]}
    assert body["messages"][-2]["content"][-1]["type"] == "tool_use"
    assert body["messages"][-2]["content"][-1]["cache_control"] == {"type": "ephemeral"}

    provider.chat([], context="ctx")
    assert captured[-1]["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": "ctx"}]}
    ]


def test_anthropic_prefix_stable_across_rounds():
    captured = []

    def handler(request):
        captured.append(request.content.decode())
        return httpx2.Response(200, json=message([{"type": "text", "text": "ok"}]))

    def strip(obj):
        if isinstance(obj, dict):
            return {k: strip(v) for k, v in obj.items() if k != "cache_control"}
        if isinstance(obj, list):
            return [strip(v) for v in obj]
        return obj

    provider = an(handler)
    provider.chat(HISTORY[:1], system="sys", context="estado 1")
    provider.chat(HISTORY[:3], system="sys", context="estado 2")
    body1, body2 = (json.loads(raw) for raw in captured)
    assert body1["system"] == body2["system"]
    assert strip(body1["messages"][0]["content"][:-1]) == \
        strip(body2["messages"][0]["content"])
    assert "estado 1" not in captured[1]


# --- Fake provider (tests and e2e only) ---------------------------------------------------

def test_fake_scripted_chat():
    provider = fake.FakeProvider()
    first = ChatReply("Primero", (ToolCall("t1", "list_sources", {}),),
                      ChatUsage(5, 5), "fake")
    provider.queue(first)
    provider.queue(lambda messages, tools, system:
                   ChatReply(f"sys={system};tools={len(tools)}",
                             (ToolCall("t2", "describe_source", {"name": "ERP"}),),
                             ChatUsage(0, 0), "fake"))

    r1 = provider.chat(HISTORY[:1], tools=TOOLS, system="sys")
    assert r1 == dataclasses.replace(first, stop_reason="tool_use")  # tool calls imply tool_use
    r2 = provider.chat(HISTORY, tools=TOOLS, system="sys")
    assert r2.text == "sys=sys;tools=2"
    assert r2.tool_calls == (ToolCall("t2", "describe_source", {"name": "ERP"}),)
    assert r2.usage.total > 0
    r3 = provider.chat([ChatMessage("user", "hola")])
    assert r3.text == "Respuesta de prueba."
    assert r3.usage.total > 0
    assert provider.requests[0]["kind"] == "chat"
    assert provider.requests[1]["tools"][0]["name"] == "list_sources"
    assert "Quiero ventas" in provider.payloads()[0]


def test_fake_tool_calls_default_stop_reason():
    provider = fake.FakeProvider()
    provider.queue(ChatReply("", (ToolCall("x", "list_sources", {}),),
                             ChatUsage(1, 1), "fake"))
    reply = provider.chat([ChatMessage("user", "x")])
    assert reply.stop_reason == "tool_use"


def test_fake_complete_and_reset():
    provider = fake.FakeProvider()
    assert provider.complete("hola").text == "OK"
    assert provider.requests[0]["kind"] == "complete"
    provider.reset()
    assert provider.requests == []


def test_fake_settings_require_test_hooks(monkeypatch):
    monkeypatch.delenv("BIZVIEW_TEST_HOOKS", raising=False)
    with pytest.raises(ValueError):
        settings(ai_provider="fake")
    monkeypatch.setenv("BIZVIEW_TEST_HOOKS", "1")
    s = settings(ai_provider="fake")
    assert s.ai_enabled
    assert s.ai_model_effective == "fake"
    assert get_provider(s) is fake.SHARED
    monkeypatch.delenv("BIZVIEW_TEST_HOOKS")
    with pytest.raises(AIError) as err:
        get_provider(s)
    assert err.value.code == "not_configured"


def test_fake_records_context():
    provider = fake.FakeProvider()
    provider.chat([ChatMessage("user", "x")], system="s", context="ctx")
    request = provider.requests[-1]
    assert request["context"] == "ctx"
    assert request["system"] == "s"
    assert "ctx" in provider.payloads()[-1]

    provider.chat([ChatMessage("user", "x")], system="s")
    assert provider.requests[-1]["context"] is None


def test_chat_timeout_is_separate_from_complete_openai():
    reads: list[float | None] = []

    def handler(request):
        reads.append(request.extensions["timeout"]["read"])
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hola"},
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    provider = oc(handler)
    provider.chat(HISTORY)
    provider.complete("hola")
    assert reads == [180.0, 30.0]


def test_chat_timeout_is_separate_from_complete_anthropic():
    reads: list[float | None] = []

    def handler(request):
        reads.append(request.extensions["timeout"]["read"])
        return httpx2.Response(200, json=message([{"type": "text", "text": "Hola"}]))

    provider = an(handler)
    provider.chat(HISTORY)
    provider.complete("hola")
    assert reads == [180.0, 30.0]


def test_custom_chat_timeout_openai():
    reads: list[float | None] = []

    def handler(request):
        reads.append(request.extensions["timeout"]["read"])
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hola"},
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    s = settings(ai_provider="openai_compatible", ai_model="llama3",
                 ai_base_url="http://ollama:11434/v1", ai_api_key=KEY,
                 ai_chat_timeout_seconds=45)
    provider = OpenAICompatibleProvider(s, transport=httpx.MockTransport(handler))
    provider.chat(HISTORY)
    assert reads == [45.0]


def test_openai_chat_timeout_maps_to_timeout_error():
    def handler(request):
        raise httpx.ReadTimeout("lento", request=request)

    provider = oc(handler)
    with pytest.raises(AIError) as err:
        provider.chat(HISTORY)
    assert err.value.code == "timeout"


def test_chat_timeout_setting_bounds():
    from pydantic import ValidationError

    assert Settings(database_url_bi="postgresql://x@localhost/x").ai_chat_timeout_seconds == 180
    assert Settings(database_url_bi="postgresql://x@localhost/x").ai_agent_discovery_limit == 15
    with pytest.raises(ValidationError):
        settings(ai_chat_timeout_seconds=5)
    with pytest.raises(ValidationError):
        settings(ai_chat_timeout_seconds=601)
    with pytest.raises(ValidationError):
        settings(ai_agent_discovery_limit=2)
    with pytest.raises(ValidationError):
        settings(ai_agent_discovery_limit=101)


def test_anthropic_chat_timeout_not_retried_by_sdk():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        raise httpx2.ReadTimeout("lento", request=request)

    provider = an(handler)
    with pytest.raises(AIError) as exc_info:
        provider.chat(HISTORY)
    assert exc_info.value.code == "timeout"
    assert calls == 1


def test_busy_stale_must_cover_chat_timeout():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        settings(ai_chat_timeout_seconds=600)
    settings(ai_chat_timeout_seconds=600, ai_chat_busy_stale_seconds=1300)
    with pytest.raises(ValidationError):
        settings(ai_chat_timeout_seconds=440, ai_tool_timeout_seconds=20)


RATE_LIMIT_BODY = {
    "type": "error",
    "error": {"type": "rate_limit_error", "message": "rate limited"},
}


def an_sleep(handler, sleeps: list[float], model="claude-haiku-4-5") -> AnthropicProvider:
    s = settings(ai_provider="anthropic", ai_api_key=KEY, ai_model=model,
                 ai_base_url="http://anthropic.test")
    return AnthropicProvider(s, transport=httpx2.MockTransport(handler), sleep=sleeps.append)


def test_anthropic_chat_rate_limit_retried_once_with_retry_after():
    calls = 0
    sleeps = []

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx2.Response(429, json=RATE_LIMIT_BODY, headers={"Retry-After": "3"})
        return httpx2.Response(200, json=message([{"type": "text", "text": "Hola"}]))

    provider = an_sleep(handler, sleeps)
    reply = provider.chat(HISTORY)
    assert reply.text == "Hola"
    assert calls == 2
    assert sleeps == [3.0]


@pytest.mark.parametrize("headers,expected", [
    ({"Retry-After": "120"}, 10.0),
    ({}, 2.0),
    ({"Retry-After": "abc"}, 2.0),
])
def test_anthropic_chat_rate_limit_retry_after_capped(headers, expected):
    calls = 0
    sleeps = []

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx2.Response(429, json=RATE_LIMIT_BODY, headers=headers)
        return httpx2.Response(200, json=message([{"type": "text", "text": "Hola"}]))

    provider = an_sleep(handler, sleeps)
    reply = provider.chat(HISTORY)
    assert reply.text == "Hola"
    assert calls == 2
    assert sleeps == [expected]


def test_anthropic_chat_rate_limit_twice_raises():
    calls = 0
    sleeps = []

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx2.Response(429, json=RATE_LIMIT_BODY, headers={"Retry-After": "1"})

    provider = an_sleep(handler, sleeps)
    with pytest.raises(AIError) as exc_info:
        provider.chat(HISTORY)
    assert exc_info.value.code == "rate_limited"
    assert KEY not in (exc_info.value.detail or "")
    assert calls == 2
    assert sleeps == [1.0]


def test_anthropic_chat_timeout_after_rate_limit_not_retried():
    calls = 0
    sleeps = []

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx2.Response(429, json=RATE_LIMIT_BODY, headers={"Retry-After": "0"})
        raise httpx2.ReadTimeout("lento", request=request)

    provider = an_sleep(handler, sleeps)
    with pytest.raises(AIError) as exc_info:
        provider.chat(HISTORY)
    assert exc_info.value.code == "timeout"
    assert calls == 2
    assert sleeps == [0.0]


def test_openai_retry_after_seconds_helper():
    from app.ai.openai_compatible import retry_after_seconds

    assert retry_after_seconds(httpx.Headers({"Retry-After": "5"})) == 5.0
    assert retry_after_seconds(httpx.Headers({"Retry-After": "60"})) == 10.0
    assert retry_after_seconds(httpx.Headers({"Retry-After": "-1"})) == 2.0
    assert retry_after_seconds(httpx.Headers({})) == 2.0
    assert retry_after_seconds(httpx.Headers({"retry-after": "5"})) == 5.0
