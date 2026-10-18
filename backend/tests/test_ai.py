"""Feature 003 / US3: AI settings, status, connection test, providers (FR-008 - FR-013)."""
import base64
import json
import os

import httpx
import pytest
from pydantic import SecretStr

from app.ai import AIError, AIReply, ChatMessage, ImagePart, get_provider, redact, service
from app.ai.anthropic_provider import AnthropicProvider
from app.ai.openai_compatible import OpenAICompatibleProvider
from app.config import Settings, get_settings
from tests.conftest import client, signed_in

KEY = "sk-test-SECRET-value-1234567890"


def settings(**kw) -> Settings:
    return Settings(database_url_bi="postgresql://x@localhost/x", **kw)


@pytest.fixture
def ai_settings(monkeypatch):
    """Patch the cached settings used by the endpoints."""
    s = get_settings()

    def apply(**kw):
        for k, v in kw.items():
            monkeypatch.setattr(s, k, v)
        return s
    return apply


# --- settings -----------------------------------------------------------------------------

def test_ai_is_off_by_default():
    s = settings()
    assert (s.ai_provider, s.ai_enabled, s.ai_missing) == ("none", False, [])
    with pytest.raises(AIError) as e:
        get_provider(s)
    assert e.value.code == "not_configured"


def test_missing_settings_are_reported():
    assert settings(ai_provider="anthropic").ai_missing == ["AI_API_KEY"]
    assert settings(ai_provider="openai_compatible").ai_missing == ["AI_MODEL", "AI_BASE_URL"]
    s = settings(ai_provider="anthropic", ai_api_key=KEY)
    assert s.ai_enabled and s.ai_model_effective == "claude-opus-5-5"


def test_invalid_base_url_is_rejected():
    with pytest.raises(ValueError):
        settings(ai_base_url="ftp://nope")


def test_redact_removes_key_and_truncates():
    assert redact(f"bad key {KEY} here", KEY) == "bad key *** here"
    assert len(redact("x" * 500, None)) == 200


# --- endpoints ----------------------------------------------------------------------------

def test_public_config_reports_version_license_and_ai(ai_settings):
    body = client().get("/api/config").json()
    assert body["version"] and body["license"] == "AGPL-3.0-or-later"
    assert body["ai_enabled"] is False
    ai_settings(ai_provider="anthropic", ai_api_key=SecretStr(KEY))
    assert client().get("/api/config").json()["ai_enabled"] is True
    assert client().get("/api/health").json()["version"] == body["version"]


def test_ai_endpoints_are_super_user_only(superuser, admin, user):
    for who in (admin, user):
        c = signed_in(who.email)
        assert c.get("/api/admin/ai").status_code == 403
        assert c.post("/api/admin/ai/test").status_code == 403
    assert client().get("/api/admin/ai").status_code == 401
    r = signed_in(superuser.email).get("/api/admin/ai")
    assert r.status_code == 200 and r.json()["provider"] == "none"


def test_status_never_contains_the_key(superuser, ai_settings):
    ai_settings(ai_provider="openai_compatible", ai_api_key=SecretStr(KEY), ai_model="llama3",
                ai_base_url="http://user:pw@ollama:11434/v1?token=abc")
    r = signed_in(superuser.email).get("/api/admin/ai")
    assert KEY not in r.text and "pw@" not in r.text and "token" not in r.text
    assert r.json() == {"enabled": True, "provider": "openai_compatible", "model": "llama3",
                        "base_url": "http://ollama:11434/v1", "key_configured": True,
                        "timeout_seconds": 30, "missing": []}


def test_connection_test_not_configured(superuser):
    body = signed_in(superuser.email).post("/api/admin/ai/test").json()
    assert body["ok"] is False and body["error"]["code"] == "not_configured"


class FakeProvider:
    name, model = "anthropic", "claude-opus-5-5"

    def __init__(self, outcome):
        self.outcome = outcome

    def complete(self, prompt, **kw):
        if isinstance(self.outcome, AIError):
            raise self.outcome
        return AIReply(text=self.outcome, model=self.model)


@pytest.mark.parametrize("outcome,code", [
    ("OK", None),
    (AIError("invalid_key", "401 ***"), "invalid_key"),
    (AIError("model_not_found"), "model_not_found"),
    (AIError("refused", "category=cyber"), "refused"),
    (AIError("timeout"), "timeout"),
])
def test_connection_test_outcomes(superuser, monkeypatch, outcome, code):
    monkeypatch.setattr(service, "get_provider", lambda s: FakeProvider(outcome))
    r = signed_in(superuser.email).post("/api/admin/ai/test")
    body = r.json()
    assert r.status_code == 200 and body["latency_ms"] is not None
    if code is None:
        assert body["ok"] is True and body["reply"] == "OK" and body["error"] is None
    else:
        assert body["ok"] is False and body["error"]["code"] == code
        assert body["error"]["message"]


# --- OpenAI-compatible provider -----------------------------------------------------------

def oc(handler, key=KEY) -> OpenAICompatibleProvider:
    s = settings(ai_provider="openai_compatible", ai_model="llama3",
                 ai_base_url="http://ollama:11434/v1", ai_api_key=key)
    return OpenAICompatibleProvider(s, transport=httpx.MockTransport(handler))


def test_openai_compatible_success_sends_expected_request():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"model": "llama3", "choices": [
            {"message": {"role": "assistant", "content": " OK "}, "finish_reason": "stop"}]})

    reply = oc(handler).complete("hola", system="sys", max_tokens=50)
    assert reply == AIReply(text="OK", model="llama3")
    assert seen["url"] == "http://ollama:11434/v1/chat/completions"
    assert seen["auth"] == f"Bearer {KEY}"
    assert seen["body"]["messages"][0] == {"role": "system", "content": "sys"}
    assert seen["body"]["max_tokens"] == 50


def test_openai_compatible_without_key_sends_no_auth():
    def handler(request):
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})
    assert oc(handler, key=None).complete("x").text == "OK"


@pytest.mark.parametrize("status,code", [(401, "invalid_key"), (403, "forbidden"),
                                         (404, "model_not_found"), (429, "rate_limited"),
                                         (500, "provider_error")])
def test_openai_compatible_http_errors(status, code):
    p = oc(lambda r: httpx.Response(status, text=f"error with {KEY}"))
    p._sleep = lambda s: None
    with pytest.raises(AIError) as e:
        p.complete("x")
    assert e.value.code == code and KEY not in (e.value.detail or "")


@pytest.mark.parametrize("exc,code", [(httpx.ReadTimeout("slow"), "timeout"),
                                      (httpx.ConnectError("refused"), "unreachable")])
def test_openai_compatible_transport_errors(exc, code):
    def handler(request):
        raise exc
    with pytest.raises(AIError) as e:
        oc(handler).complete("x")
    assert e.value.code == code


def test_openai_compatible_content_filter_is_refused():
    p = oc(lambda r: httpx.Response(200, json={"choices": [
        {"message": {"content": ""}, "finish_reason": "content_filter"}]}))
    with pytest.raises(AIError) as e:
        p.complete("x")
    assert e.value.code == "refused"


# --- Anthropic provider -------------------------------------------------------------------

def test_anthropic_unreachable_endpoint():
    """Local closed port: exercises the SDK error mapping without contacting Anthropic."""
    s = settings(ai_provider="anthropic", ai_api_key=KEY, ai_base_url="http://127.0.0.1:9",
                 ai_timeout_seconds=3)
    with pytest.raises(AIError) as e:
        AnthropicProvider(s).complete("x", max_tokens=16)
    assert e.value.code in ("unreachable", "timeout")
    assert KEY not in (e.value.detail or "")


@pytest.mark.skipif(os.environ.get("AI_LIVE_TESTS") != "1",
                    reason="contacts api.anthropic.com; set AI_LIVE_TESTS=1")
def test_anthropic_live_invalid_key():
    s = settings(ai_provider="anthropic", ai_api_key="sk-ant-invalid-key-for-test")
    result = service.test_connection(s)
    assert result["ok"] is False and result["error"]["code"] == "invalid_key"


# --- image parts on the wire (feature 024, T006/T029) --------------------------------------

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8


def test_openai_compatible_body_carries_the_images_with_the_text_first():
    seen = {}

    def handler(request: httpx.Request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    message = ChatMessage("user", "un reporte como este",
                          images=(ImagePart("image/png", PNG_BYTES),))
    oc(handler).chat([message], system="sys", max_tokens=64)

    content = seen["body"]["messages"][1]["content"]
    assert content[0] == {"type": "text", "text": "un reporte como este"}
    assert content[1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64," + base64.b64encode(PNG_BYTES).decode()},
    }


def test_openai_compatible_body_without_images_is_unchanged():
    seen = {}

    def handler(request: httpx.Request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    oc(handler).chat([ChatMessage("user", "hola")], system="sys", max_tokens=64)
    assert seen["body"]["messages"][1] == {"role": "user", "content": "hola"}


def test_anthropic_messages_carry_the_label_before_the_image():
    """The text block (the untrusted-data label) is read before the picture."""
    s = settings(ai_provider="anthropic", ai_api_key=KEY)
    provider = AnthropicProvider(s)
    parts = provider._messages([ChatMessage("user", "datos no confiables\nun reporte como este",
                                            images=(ImagePart("image/jpeg", PNG_BYTES),))])
    content = parts[0]["content"]
    assert [block["type"] for block in content] == ["text", "image"]
    assert content[0]["text"].startswith("datos no confiables")
    assert content[1]["source"] == {
        "type": "base64", "media_type": "image/jpeg",
        "data": base64.b64encode(PNG_BYTES).decode()}


def test_anthropic_messages_without_images_are_unchanged():
    s = settings(ai_provider="anthropic", ai_api_key=KEY)
    provider = AnthropicProvider(s)
    assert provider._messages([ChatMessage("user", "hola")]) == [
        {"role": "user", "content": [{"type": "text", "text": "hola"}]}]
