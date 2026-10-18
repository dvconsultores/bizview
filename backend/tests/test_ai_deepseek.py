"""Feature 017 / T004: recorded DeepSeek transports, never a live AI."""
import json
from pathlib import Path

import httpx
import httpx2
import pytest

from app.ai import AIError, ChatMessage, ChatReply, ChatUsage, ToolCall, fake
from app.ai.anthropic_provider import AnthropicProvider
from app.ai.openai_compatible import OpenAICompatibleProvider
from app.config import Settings

FIXTURES = Path(__file__).parent / "fixtures" / "deepseek"
KEY = "sk-test-SECRET-value-1234567890"


def settings(**kw) -> Settings:
    return Settings(database_url_bi="postgresql://x@localhost/x", **kw)


def ds(handler, sleeps: list[float] | None = None, key=KEY) -> OpenAICompatibleProvider:
    s = settings(ai_provider="openai_compatible", ai_model="deepseek-v4-pro",
                 ai_base_url="https://api.deepseek.test", ai_api_key=key)
    return OpenAICompatibleProvider(
        s, transport=httpx.MockTransport(handler),
        sleep=(sleeps.append if sleeps is not None else lambda _: None))


def recorder(responses):
    """Returns (handler, bodies); handler pops one (status, headers, payload) per request."""
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        status, headers, payload = responses.pop(0)
        bodies.append(json.loads(request.content))
        return httpx.Response(status, json=payload, headers=headers)

    return handler, bodies


def an(handler, model="claude-haiku-4-5") -> AnthropicProvider:
    s = settings(ai_provider="anthropic", ai_api_key=KEY, ai_model=model,
                 ai_base_url="http://anthropic.test")
    return AnthropicProvider(s, transport=httpx2.MockTransport(handler))


def message(content, stop_reason="end_turn", model="claude-haiku-4-5", usage=None) -> dict:
    usage = usage or {}
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": model,
            "content": content, "stop_reason": stop_reason, "stop_sequence": None, "usage": usage}


def test_deepseek_round_trip_and_reasoning_resend():
    call_1 = json.loads((FIXTURES / "tool_call.json").read_text())
    call_2 = json.loads((FIXTURES / "tool_call_followup.json").read_text())
    handler, bodies = recorder([(200, {}, call_1), (200, {}, call_2)])
    p = ds(handler)
    reply = p.chat([ChatMessage("user", "¿Qué fuentes hay?")])
    assert reply.reasoning == "Necesito ver las fuentes disponibles antes de responder."
    assert reply.usage == ChatUsage(128, 42, 96)
    assert reply.stop_reason == "tool_use"
    assert len(reply.tool_calls) == 1
    assert reply.tool_calls[0].name == "list_sources"

    history = [
        ChatMessage("user", "¿Qué fuentes hay?"),
        ChatMessage("assistant", "", tool_calls=reply.tool_calls, reasoning=reply.reasoning),
        ChatMessage("tool", "ERP, ventas, marketing", tool_call_id="call_list_sources_1"),
    ]
    final = p.chat(history)
    assert final.text == "Encontré 3 fuentes: ERP, ventas y marketing."
    assert final.reasoning == "Con la lista de fuentes ya puedo responder la pregunta original."
    assert bodies[-1]["messages"][1]["reasoning_content"] == reply.reasoning


def test_deepseek_reasoning_only_on_last_user_turn():
    reply = json.loads((FIXTURES / "tool_call.json").read_text())
    handler, bodies = recorder([(200, {}, reply)])
    p = ds(handler)
    history = [
        ChatMessage("user", "primera"),
        ChatMessage("assistant", "respuesta 1", reasoning="r1"),
        ChatMessage("user", "segunda"),
        ChatMessage("assistant", "", tool_calls=(ToolCall("id2", "list_sources", {}),),
                    reasoning="r2"),
        ChatMessage("tool", "ok", tool_call_id="id2"),
    ]
    p.chat(history)
    messages = bodies[0]["messages"]
    assert "reasoning_content" not in messages[1]
    assert messages[3]["reasoning_content"] == "r2"

    # Assistant without reasoning after the last user gets no reasoning_content key.
    history_no_reasoning = [
        ChatMessage("user", "primera"),
        ChatMessage("assistant", "respuesta 1", reasoning="r1"),
        ChatMessage("user", "segunda"),
        ChatMessage("assistant", "respuesta 2"),
    ]
    handler2, bodies2 = recorder([(200, {}, reply)])
    ds(handler2).chat(history_no_reasoning)
    messages2 = bodies2[0]["messages"]
    assert "reasoning_content" not in messages2[1]
    assert "reasoning_content" not in messages2[3]


def test_deepseek_reasoning_kept_across_tool_rounds_with_context():
    reply = json.loads((FIXTURES / "tool_call.json").read_text())
    handler, bodies = recorder([(200, {"Content-Type": "application/json"}, reply)])

    history = [
        ChatMessage("user", "primera"),
        ChatMessage("assistant", "",
                    tool_calls=(ToolCall("id1", "list_sources", {}),),
                    reasoning="r1"),
        ChatMessage("tool", "ok", tool_call_id="id1"),
        ChatMessage("assistant", "",
                    tool_calls=(ToolCall("id2", "describe_source", {"name": "ERP"}),),
                    reasoning="r2"),
        ChatMessage("tool", "ok2", tool_call_id="id2"),
    ]

    provider = ds(handler)
    provider.chat(history, system="sys", context="## Estado\nX")

    messages = bodies[0]["messages"]

    user_messages = [m for m in messages if m["role"] == "user"]
    assert len(user_messages) == 1
    assert user_messages[0]["content"] == "primera"

    assistant_messages = [m for m in messages if m["role"] == "assistant"]
    assert assistant_messages[0]["reasoning_content"] == "r1"
    assert assistant_messages[1]["reasoning_content"] == "r2"

    assert messages[-1] == {"role": "tool", "tool_call_id": "id2",
                            "content": "ok2\n\n## Estado\nX"}

def test_deepseek_invalid_json_args_and_non_object_args():
    invalid = json.loads((FIXTURES / "invalid_arguments.json").read_text())
    handler, _ = recorder([(200, {}, invalid)])
    reply = ds(handler).chat([ChatMessage("user", "describe ERP")])
    assert reply.stop_reason == "tool_use"
    assert len(reply.tool_calls) == 1
    call = reply.tool_calls[0]
    assert call.args == {}
    assert call.args_error is not None
    assert call.args_error.startswith("Expecting")
    assert "columna" in call.args_error
    assert '{"name": "ERP"' not in call.args_error

    non_object = json.loads((FIXTURES / "invalid_arguments.json").read_text())
    non_object["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = "[1, 2]"
    handler, _ = recorder([(200, {}, non_object)])
    reply = ds(handler).chat([ChatMessage("user", "describe ERP")])
    assert reply.tool_calls[0].args == {}
    assert reply.tool_calls[0].args_error == "se esperaba un objeto JSON"


def test_deepseek_rate_limit_retry_and_sleep():
    ok = json.loads((FIXTURES / "tool_call.json").read_text())

    sleeps: list[float] = []
    handler, bodies = recorder([
        (429, {"Retry-After": "3"}, {"error": {"message": "slow down"}}),
        (200, {}, ok),
    ])
    reply = ds(handler, sleeps=sleeps).chat([ChatMessage("user", "hola")])
    assert reply.stop_reason == "tool_use"
    assert sleeps == [3.0]
    assert len(bodies) == 2

    sleeps = []
    handler, bodies = recorder([
        (429, {"Retry-After": "30"}, {"error": {"message": "slow down"}}),
        (200, {}, ok),
    ])
    ds(handler, sleeps=sleeps).chat([ChatMessage("user", "hola")])
    assert sleeps == [10.0]

    sleeps = []
    handler, bodies = recorder([
        (429, {}, {"error": {"message": "slow down"}}),
        (200, {}, ok),
    ])
    ds(handler, sleeps=sleeps).chat([ChatMessage("user", "hola")])
    assert sleeps == [2.0]

    sleeps = []
    handler, bodies = recorder([
        (429, {"Retry-After": "1"}, {"error": {"message": "slow down"}}),
        (429, {"Retry-After": "1"}, {"error": {"message": "slow down"}}),
    ])
    with pytest.raises(AIError) as err:
        ds(handler, sleeps=sleeps).chat([ChatMessage("user", "hola")])
    assert err.value.code == "rate_limited"
    assert len(bodies) == 2
    assert sleeps == [1.0]


def test_deepseek_context_too_long_detection():
    fixture = json.loads((FIXTURES / "context_too_long.json").read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={**fixture, "error": {
            **fixture["error"], "message": f"{KEY} {fixture['error']['message']}"}})

    p = ds(handler)
    with pytest.raises(AIError) as err:
        p.chat([ChatMessage("user", "hola")])
    assert err.value.code == "context_too_long"
    assert err.value.message == "La conversación superó el contexto máximo del modelo."
    assert KEY not in (err.value.detail or "")
    assert "context length" in (err.value.detail or "")


def test_deepseek_provider_400_without_context_marker_is_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "bad request"}})

    with pytest.raises(AIError) as err:
        ds(handler).chat([ChatMessage("user", "hola")])
    assert err.value.code == "provider_error"


def test_fake_provider_reasoning_and_args_error_flow_through():
    reply = ChatReply(
        text="",
        tool_calls=(
            ToolCall("call_1", "list_sources", {}, args_error="se esperaba un objeto JSON"),
        ),
        usage=ChatUsage(),
        model="fake",
        stop_reason="tool_use",
        reasoning="pensando",
    )
    p = fake.FakeProvider([reply])
    out = p.chat([ChatMessage("user", "hola")])
    assert out.reasoning == "pensando"
    assert out.tool_calls[0].args_error == "se esperaba un objeto JSON"
    assert out.stop_reason == "tool_use"
    assert out.usage.output > 0


def test_anthropic_provider_ignores_reasoning():
    captured: dict = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["raw"] = request.content.decode()
        return httpx2.Response(200, json=message(
            [{"type": "text", "text": "Hola"}],
            usage={"input_tokens": 10, "output_tokens": 5}))

    p = an(handler)
    reply = p.chat([ChatMessage("user", "primera"),
                    ChatMessage("assistant", "respuesta 1", reasoning="secreto-razonamiento")])
    assert reply.text == "Hola"
    assert "secreto-razonamiento" not in captured["raw"]
    content_blocks = json.loads(captured["raw"])["messages"][1]["content"]
    for block in content_blocks:
        block.pop("cache_control", None)
    assert content_blocks == [{"type": "text", "text": "respuesta 1"}]


def test_usage_deepseek_cached_prompt():
    handler, _ = recorder(
        [
            (
                200,
                {},
                {
                    "id": "chatcmpl-1",
                    "object": "chat.completion",
                    "model": "deepseek-v4-pro",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "Hola"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 10000,
                        "completion_tokens": 200,
                        "total_tokens": 10200,
                        "prompt_cache_hit_tokens": 9000,
                        "prompt_cache_miss_tokens": 1000,
                    },
                },
            )
        ]
    )
    provider = ds(handler)
    reply = provider.chat([ChatMessage(role="user", content="hola")])
    assert reply.usage == ChatUsage(10000, 200, 9000)
    assert reply.usage.weighted(0.1) == 2100
    assert reply.usage.weighted(1.0) == 10200
    assert reply.usage.weighted(0) == 1200


def test_usage_openai_style_cached():
    handler, _ = recorder(
        [
            (
                200,
                {},
                {
                    "id": "chatcmpl-2",
                    "object": "chat.completion",
                    "model": "deepseek-v4-pro",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "Hola"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 500,
                        "completion_tokens": 50,
                        "prompt_tokens_details": {"cached_tokens": 400},
                    },
                },
            ),
            (
                200,
                {},
                {
                    "id": "chatcmpl-3",
                    "object": "chat.completion",
                    "model": "deepseek-v4-pro",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "Hola"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 500,
                        "completion_tokens": 50,
                        "prompt_tokens_details": None,
                    },
                },
            ),
        ]
    )
    provider = ds(handler)
    reply = provider.chat([ChatMessage(role="user", content="hola")])
    assert reply.usage.cached == 400
    reply = provider.chat([ChatMessage(role="user", content="hola")])
    assert reply.usage.cached == 0


def test_usage_anthropic_cached():
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json=message(
                [{"type": "text", "text": "Hola"}],
                usage={
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "cache_read_input_tokens": 800,
                    "cache_creation_input_tokens": 50,
                },
            ),
        )

    provider = an(handler)
    reply = provider.chat([ChatMessage(role="user", content="hola")])
    assert reply.usage == ChatUsage(950, 20, 800)
    assert reply.usage.weighted(0.1) == 250


def test_usage_weighted_clamps_cached():
    usage = ChatUsage(input=10, output=1, cached=50)
    assert usage.cached == 10
    assert usage.weighted(0.1) == 2


def test_usage_both_cache_fields_not_double_counted():
    handler, _ = recorder([
        (
            200,
            {},
            {
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "model": "deepseek-v4-pro",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hola"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10000,
                    "completion_tokens": 300,
                    "total_tokens": 10300,
                    "prompt_cache_hit_tokens": 9000,
                    "prompt_cache_miss_tokens": 1000,
                    "prompt_tokens_details": {"cached_tokens": 9000},
                },
            },
        )
    ])
    provider = ds(handler)
    reply = provider.chat([ChatMessage(role="user", content="hola")])
    assert reply.usage == ChatUsage(10000, 300, 9000)
    assert reply.usage.weighted(0.1) == 2200
