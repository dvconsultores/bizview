"""Feature 052 / US2: the structure chat — what it sends, what it refuses and what it flags.

The provider is a stand-in for `app.ai.get_provider` (the pattern `test_ai.py` already uses): the
product ships no `fake` provider, so the assertions are about the payload and the behaviour, not
about a test-only branch in the request path.
"""
import json

import pytest
from sqlalchemy import text

from app.ai import AIError, AIReply, chat
from app.sources import describe as describer
from tests.conftest import client, reauth, signed_in, sql

HOST = "203.0.113.9"
PASSWORD = "Origin-Secret-9f3k"
ROW_VALUE = "ACME-SECRET-CUSTOMER-9931"

PG = {"name": "ERP ventas", "kind": "postgresql", "settings": {
    "host": HOST, "port": 5432, "database": "erp", "username": "bi_ro"},
      "secrets": {"password": PASSWORD}}

STRUCTURE = {
    "kind": "postgresql", "truncated": False,
    "tables": [{"schema": "ventas", "name": "orders", "kind": "table", "estimated_rows": 1200,
                "primary_key": ["id"], "foreign_keys": [],
                "columns": [{"name": "id", "type": "integer", "nullable": False},
                            {"name": "created_at", "type": "timestamp with time zone",
                             "nullable": False},
                            {"name": "customer_email", "type": "text", "nullable": True}]}],
}


class FakeProvider:
    """Records what the chat sends and answers with a scripted text."""

    name, model = "openai_compatible", "fake-model"

    def __init__(self, answer="La tabla `orders` tiene `created_at`.", error: AIError | None = None,
                 tokens=(800, 120)):
        self.answer, self.error, self.tokens = answer, error, tokens
        self.calls: list[dict] = []

    def complete(self, prompt, *, system=None, max_tokens=1024, effort=None):
        self.calls.append({"prompt": prompt, "system": system, "max_tokens": max_tokens})
        if self.error is not None:
            raise self.error
        return AIReply(text=self.answer, model=self.model, tokens_in=self.tokens[0],
                       tokens_out=self.tokens[1])


@pytest.fixture
def su(superuser):
    return reauth(signed_in("root@example.com"))


@pytest.fixture
def ai_on(monkeypatch):
    """AI configured, with a fake key and the stand-in provider installed by the test."""
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "ai_provider", "openai_compatible")
    monkeypatch.setattr(settings, "ai_model", "fake-model")
    monkeypatch.setattr(settings, "ai_base_url", "http://ai.test/v1")
    monkeypatch.setattr(settings, "ai_structure_chat_daily_tokens", 100_000)
    monkeypatch.setattr(settings, "ai_structure_chat_store_questions", False)
    return settings


@pytest.fixture
def provider(monkeypatch):
    fake = FakeProvider()
    monkeypatch.setattr(chat, "get_provider", lambda settings: fake)
    return fake


@pytest.fixture
def source(su, monkeypatch):
    def fake(*_a, **_kw):
        return STRUCTURE

    monkeypatch.setattr(describer, "describe", fake)
    created = su.post("/api/sources", json=PG)
    assert created.status_code == 201, created.text
    return created.json()


def ask(su, question: str):
    return su.post("/api/sources/ERP ventas/chat", json={"question": question})


# --- what reaches the provider -------------------------------------------------------------

def test_payload_is_the_structure_the_question_and_the_turns(su, ai_on, provider, source):
    assert ask(su, "¿qué columnas tiene `orders`?").status_code == 200
    payload = provider.calls[-1]
    assert "orders" in payload["system"] and "customer_email" in payload["system"]
    assert "estructura" in payload["system"].lower()
    assert "Pregunta: ¿qué columnas tiene `orders`?" in payload["prompt"]
    for secret in (HOST, PASSWORD, "bi_ro", ROW_VALUE):
        assert secret not in json.dumps(payload, ensure_ascii=False)


def test_payload_carries_the_last_turns_and_no_more(su, ai_on, provider, source, monkeypatch):
    # Multi-turn context needs the stored texts: with storage off every question is standalone
    # (the installation decides, US2/AC6), and the test below proves that case.
    monkeypatch.setattr(ai_on, "ai_structure_chat_store_questions", True)
    for i in range(13):
        ask(su, f"¿qué columnas de `orders` son MARCA{i:02d}?")
    payload = provider.calls[-1]["prompt"]
    assert "Conversación anterior" in payload
    # at most the last 10 turns: 10 stored questions plus the one being asked
    assert payload.count("Pregunta:") == 11
    assert "MARCA12" in payload and "MARCA11" in payload
    assert "MARCA00" not in payload and "MARCA01" not in payload


def test_history_is_not_stored_unless_the_installation_asks(su, ai_on, provider, source):
    ask(su, "¿qué es `orders`?")
    ask(su, "¿y `customer_email`?")
    assert "Conversación anterior" not in provider.calls[-1]["prompt"]
    rows = sql("SELECT role, body FROM source_chat_message ORDER BY id")
    assert [row[0] for row in rows] == ["question", "answer", "question", "answer"]
    assert all(row[1] is None for row in rows)
    history = su.get("/api/sources/ERP ventas/chat").json()
    assert [t["role"] for t in history["turns"]] == ["question", "answer", "question", "answer"]
    assert all(t["text"] is None for t in history["turns"])


def test_questions_can_be_stored_when_enabled(su, ai_on, provider, source, monkeypatch):
    monkeypatch.setattr(ai_on, "ai_structure_chat_store_questions", True)
    ask(su, "¿qué es `orders`?")
    history = su.get("/api/sources/ERP ventas/chat").json()
    assert history["turns"][0]["text"] == "¿qué es `orders`?"


# --- refusals: product code, before the provider ------------------------------------------

@pytest.mark.parametrize("question", [
    "dame 5 filas de orders",
    "muéstrame los registros de ayer",
    "¿cuánto vendimos ayer?",
    "show me the rows of orders",
    "give me 10 records",
    "borra la tabla orders",
    "ejecuta este select",
    "delete from orders",
    "truncate orders",
    "inserta un registro",
])
def test_data_and_action_requests_are_refused_without_a_call(su, ai_on, provider, source,
                                                             question):
    r = ask(su, question)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["refused"] is True and body["unknown"] == []
    assert body["usage"]["spent_today"] == 0 and body["tokens_in"] == 0
    assert provider.calls == []
    assert "estructura" in body["answer"].lower()


@pytest.mark.parametrize("question", [
    "¿cuántas tablas tiene la fuente?",
    "¿qué campos trae el endpoint de listados y cuál es la fecha?",
    "resume esta fuente para el REQUEST.md",
    "redacta las observaciones de structure.md",
])
def test_structure_questions_are_not_refused(su, ai_on, provider, source, question):
    r = ask(su, question)
    assert r.status_code == 200 and r.json()["refused"] is False
    assert len(provider.calls) == 1


# --- object validation --------------------------------------------------------------------

def test_an_object_absent_from_the_structure_is_flagged(su, ai_on, provider, source):
    provider.answer = "La tabla `ventas_fantasma` guarda los pagos; usa `paid_at`."
    body = ask(su, "¿dónde están los pagos?").json()
    names = {item["name"] for item in body["unknown"]}
    assert names == {"ventas_fantasma", "paid_at"}
    assert all(item["kind"] in ("table", "column", "unknown") for item in body["unknown"])


def test_known_objects_are_not_flagged(su, ai_on, provider, source):
    provider.answer = "Usa `ventas.orders` y su columna `created_at`; `customer_email` es personal."
    body = ask(su, "¿qué columnas tiene orders?").json()
    assert body["unknown"] == []


def test_a_file_name_in_the_answer_is_not_an_object(su, ai_on, provider, source):
    provider.answer = "Escríbelo en structure.md bajo «Observaciones»."
    assert ask(su, "redacta las observaciones").json()["unknown"] == []


# --- the budget ---------------------------------------------------------------------------

def test_the_daily_cap_stops_the_chat_and_rolls_over(su, ai_on, provider, source, monkeypatch):
    monkeypatch.setattr(ai_on, "ai_structure_chat_daily_tokens", 900)
    assert ask(su, "¿qué es `orders`?").json()["usage"]["spent_today"] == 920
    r = ask(su, "¿y `customer_email`?")
    assert r.status_code == 429 and r.json()["error"]["code"] == "ai_chat_cap"
    assert r.json()["error"]["ai"]["cap"] == 900
    assert len(provider.calls) == 1
    # a new day starts from zero: the cap reads the UTC date of the stored turns
    sql("UPDATE source_chat_message SET created_at = now() - interval '1 day'")
    assert ask(su, "¿y `customer_email`?").status_code == 200


def test_zero_tokens_turns_the_chat_off(su, ai_on, provider, source, monkeypatch):
    monkeypatch.setattr(ai_on, "ai_structure_chat_daily_tokens", 0)
    r = ask(su, "¿qué es `orders`?")
    assert r.status_code == 429 and r.json()["error"]["code"] == "ai_chat_cap"
    assert provider.calls == []


def test_ai_off_is_a_typed_error_and_the_tab_still_works(superuser, source):
    authed = reauth(signed_in("root@example.com"))
    r = authed.post("/api/sources/ERP ventas/chat", json={"question": "¿qué es `orders`?"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "ai_not_configured"
    assert r.json()["error"]["ai"]["action"] == "admin_ai"
    assert authed.get("/api/sources/ERP ventas/structure").status_code == 200


@pytest.mark.parametrize("code", ["no_credit", "bad_key", "model_not_found", "rate_limited"])
def test_provider_errors_keep_the_035_vocabulary(su, ai_on, provider, source, code):
    provider.error = AIError(code, "detalle del proveedor")
    r = ask(su, "¿qué es `orders`?")
    assert r.status_code == 502 and r.json()["error"]["code"] == f"ai_{code}"
    assert r.json()["error"]["ai"]["code"] == code
    assert r.json()["error"]["message"]


def test_a_failed_call_stores_no_turn(su, ai_on, provider, source):
    provider.error = AIError("provider_down")
    ask(su, "¿qué es `orders`?")
    assert sql("SELECT count(*) FROM source_chat_message")[0][0] == 0


# --- audit and permissions ----------------------------------------------------------------

def test_counts_are_audited_and_the_question_is_not(su, ai_on, provider, source):
    ask(su, "¿qué columnas tiene `customer_email`?")
    detail = str(sql("SELECT detail FROM audit_event WHERE kind = 'source_chat_asked'"))
    assert "usage" in detail and "'in'" in detail
    assert "customer_email" not in detail


def test_the_chat_is_super_user_only(admin, user, source):
    for who in (admin, user):
        c = signed_in(who.email)
        assert c.get("/api/sources/ERP ventas/chat").status_code == 403
        assert c.post("/api/sources/ERP ventas/chat",
                      json={"question": "hola"}).status_code == 403
    assert client().post("/api/sources/ERP ventas/chat", json={"question": "x"}).status_code == 401


def test_clearing_removes_only_my_turns(su, ai_on, provider, source):
    ask(su, "¿qué es `orders`?")
    assert su.delete("/api/sources/ERP ventas/chat").status_code == 204
    assert sql("SELECT count(*) FROM source_chat_message")[0][0] == 0
    detail = str(sql("SELECT detail FROM audit_event WHERE kind = 'source_chat_cleared'"))
    assert "turns" in detail


def test_old_turns_are_purged(su, ai_on, provider, source, db):
    ask(su, "¿qué es `orders`?")
    db.execute(text("UPDATE source_chat_message SET created_at = now() - interval '40 days'"))
    db.commit()
    removed = chat.purge_older_than(db)
    db.commit()
    assert removed == 2


# --- the context window -------------------------------------------------------------------

def test_a_huge_structure_is_sent_as_an_index_plus_what_the_question_names():
    tables = [{"schema": "s", "name": f"t{i}", "kind": "table", "estimated_rows": i,
               "primary_key": [], "foreign_keys": [],
               "columns": [{"name": f"c{j}", "type": "text", "nullable": True}
                           for j in range(40)]} for i in range(400)]
    pack = {"pack": {"source": "big", "kind": "postgresql", "notes": ""},
            "structure": {"kind": "postgresql", "tables": tables, "truncated": False}}
    text_out = chat.context(pack, "¿qué columnas tiene t17?")
    assert len(text_out) <= chat.MAX_CONTEXT_CHARS + 2_000
    assert '"detalle": {"schema": "s", "name": "t17"' in text_out
    assert "se envía el índice" in text_out
    assert "c39" not in text_out.split('"detalle"')[0]   # the index keeps counts, not columns
