"""Feature 036: a conversation always replays as a payload both providers accept.

The report that opened this feature: `tool_use_id call_00_g9JN… found in tool_result blocks` on
every turn, because a tool's own note had been written between the `tool_use` and its result and
the old loader paired results by adjacency.
"""
import random

import pytest

from app.ai import ChatMessage, ToolCall
from app.ai.anthropic_provider import AnthropicProvider
from app.ai.history_rules import check_payload, validate_messages
from app.ai.openai_compatible import OpenAICompatibleProvider
from app.assistant import history
from app.config import Settings

KEY = "sk-test-SECRET-value-1234567890"
G9JN = "call_00_g9JNBifdtD02Zjv7EV6i7946"
DATA = '<datos origen="herramienta:apply_draft">{"ok": true}</datos>'


def settings(**kw) -> Settings:
    return Settings(database_url_bi="postgresql://x@localhost/x", **kw)


_CACHE: dict[str, object] = {}


def oc() -> OpenAICompatibleProvider:
    if "oc" not in _CACHE:
        _CACHE["oc"] = OpenAICompatibleProvider(
            settings(ai_provider="openai_compatible", ai_model="llama3",
                     ai_base_url="http://ollama:11434/v1", ai_api_key=KEY))
    return _CACHE["oc"]          # type: ignore[return-value]


def anthropic() -> AnthropicProvider:
    if "anthropic" not in _CACHE:
        _CACHE["anthropic"] = AnthropicProvider(
            settings(ai_provider="anthropic", ai_model="claude-opus-5-5", ai_api_key=KEY))
    return _CACHE["anthropic"]   # type: ignore[return-value]


def payload_for(messages, provider: str):
    """The exact body each provider would send (no network: only the converters run)."""
    if provider == "openai_compatible":
        return oc()._messages(messages, None)
    return anthropic()._messages(messages)


def call(call_id: str, name: str = "apply_draft") -> ToolCall:
    return ToolCall(id=call_id, name=name, args={})


def row(id: int, role: str, content: str = "", *, calls=(), call_id: str | None = None,
        owner_id: int | None = None, data: str = "", tool_name: str = "apply_draft",
        orphan: bool = False) -> history.StoredMessage:
    return history.StoredMessage(id=id, role=role, content=content, calls=tuple(calls),
                                 call_id=call_id, owner_id=owner_id, data=data,
                                 tool_name=tool_name if role == "tool" else None,
                                 orphan=orphan)


def session_23() -> list[history.StoredMessage]:
    """The production shape: the tool wrote its own note between the call and its result."""
    return [
        row(3660, "user", "continua"),
        row(3661, "assistant", "", calls=(call(G9JN),)),
        row(3662, "assistant", "Contrato del run autorizado: draft, preview, apply."),
        row(3663, "tool", "Aplicó la versión 12.", call_id=G9JN, data=DATA),
        row(3664, "assistant", "Proyecto cerrado y aplicado."),
        row(3670, "user", "continua"),
        row(3671, "assistant", "El proveedor de IA devolvió un error."),
    ]


# --- the incident ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", ["anthropic", "openai_compatible"])
def test_the_incident_replays_as_a_valid_payload(provider):
    built = history.for_provider(session_23(), provider, session_id=23)
    assert validate_messages(built.messages, provider) == []
    assert check_payload(payload_for(built.messages, provider), provider) == []

    # The result answers its own assistant turn, immediately, and the note follows the exchange.
    roles = [message.role for message in built.messages]
    assert roles[:4] == ["user", "assistant", "tool", "assistant"]
    assert built.messages[1].tool_calls[0].id == G9JN
    assert built.messages[2].tool_call_id == G9JN
    assert "Contrato del run autorizado" in built.messages[3].content
    assert built.messages[2].content == DATA          # the newest exchange keeps its data


def test_the_result_is_grouped_with_its_owner_and_never_orphaned():
    built = history.for_provider(session_23(), "anthropic", session_id=23)
    assert built.dropped == [] and built.noted == []
    payload = payload_for(built.messages, "anthropic")
    assert payload[2]["content"][0]["type"] == "tool_result"     # results lead the user turn
    assert payload[2]["content"][0]["tool_use_id"] == G9JN


# --- orphans, notes, empties ----------------------------------------------------------------


def test_a_result_without_its_call_is_dropped_and_reported():
    rows = [
        row(1, "user", "hola"),
        row(2, "assistant", "sin herramientas"),
        row(3, "tool", "residuo", call_id="call_zzz", data=DATA),
        row(4, "user", "otra"),
    ]
    built = history.build(rows)
    assert [m.role for m in built.messages] == ["user", "assistant", "user"]
    assert built.dropped == ["tool:3:call_zzz"]


def test_a_call_without_a_result_becomes_a_note():
    rows = [row(1, "user", "aplica"), row(2, "assistant", "", calls=(call(G9JN),)),
            row(3, "user", "sigue")]
    built = history.build(rows)
    assert built.noted == [G9JN]
    assistant = built.messages[1]
    assert assistant.tool_calls == ()
    assert "sin resultado" in assistant.content and "apply_draft" in assistant.content


def test_preview_notices_and_empty_assistant_rows_are_never_sent():
    rows = [row(1, "user", "hola"),
            row(2, "tool", "Vista previa lista.", tool_name="preview", data=DATA),
            row(3, "assistant", "")]
    built = history.build(rows)
    assert [m.role for m in built.messages] == ["user"]


def test_an_explicitly_flagged_orphan_is_not_replayed_even_with_a_matching_id():
    rows = [row(1, "user", "hola"), row(2, "assistant", "", calls=(call(G9JN),)),
            row(3, "tool", "residuo", call_id=G9JN, data=DATA, orphan=True)]
    built = history.build(rows)
    assert built.dropped == [f"tool:3:{G9JN}"]
    assert built.messages[1].tool_calls == ()            # the call is noted instead


# --- window and summaries -------------------------------------------------------------------


def test_the_window_cuts_at_a_user_text_boundary():
    rows = [row(1, "user", "primero"), row(2, "assistant", "", calls=(call("c1"),)),
            row(3, "tool", "un archivo", call_id="c1", owner_id=2, data=DATA),
            row(4, "user", "segundo"), row(5, "assistant", "vale")]
    built = history.build(rows, window=3)                 # the cut lands inside the exchange
    assert [m.role for m in built.messages] == ["user", "assistant"]
    assert built.messages[0].content == "segundo"


def test_an_older_exchange_travels_as_its_stored_summary():
    rows = [row(1, "user", "primero"), row(2, "assistant", "", calls=(call("c1"),)),
            row(3, "tool", "Leyó 4 archivos.", call_id="c1", owner_id=2, data=DATA),
            row(4, "user", "segundo"), row(5, "assistant", "", calls=(call("c2"),)),
            row(6, "tool", "Aplicó la versión 12.", call_id="c2", owner_id=5, data=DATA)]
    built = history.build(rows)
    by_id = {message.tool_call_id: message.content for message in built.messages
             if message.role == "tool"}
    assert by_id["c1"] == "Leyó 4 archivos."             # summary, not the data block
    assert by_id["c2"] == DATA                           # the newest exchange keeps the data


def test_an_older_in_memory_exchange_replays_its_stored_summary():
    """The turn's own history carries the data block, not the stored summary: 015 needs both."""
    rows = history.from_chat([
        ChatMessage("user", "propon"),
        ChatMessage("assistant", "", tool_calls=(ToolCall("c1", "propose_draft",
                                                          {"files": {"a": "x"}, "summary": "s"}),)),
        ChatMessage("tool", DATA, tool_call_id="c1"),
        ChatMessage("assistant", "", tool_calls=(ToolCall("c2", "list_sources", {}),)),
        ChatMessage("tool", "<datos>x</datos>", tool_call_id="c2"),
    ])
    built = history.build(rows, summaries={"c1": "Propuso un borrador."})
    contents = {m.tool_call_id: m.content for m in built.messages if m.role == "tool"}
    assert contents["c1"] == "Propuso un borrador."      # older: one line
    assert contents["c2"] == "<datos>x</datos>"          # newest: what it is working with
    older = next(m for m in built.messages if m.role == "assistant" and m.tool_calls)
    assert older.tool_calls[0].args == {"files": ["a"], "summary": "s"}   # args compacted


def test_a_window_without_a_user_message_keeps_the_whole_turn():
    rows = [row(1, "assistant", "", calls=(call("c1"),)),
            row(2, "tool", "ok", call_id="c1", owner_id=1, data=DATA)]
    built = history.build(rows, window=1)
    assert built.messages == []                          # nothing to replay without a user turn


# --- the shape rules ------------------------------------------------------------------------


def test_roles_alternate_ids_are_unique_and_nothing_is_empty():
    rows = [row(1, "user", "hola"), row(2, "assistant", "uno"), row(3, "assistant", "dos"),
            row(4, "user", "tres"), row(5, "assistant", "", calls=(call("c1"), call("c1"))),
            row(6, "tool", "ok", call_id="c1", owner_id=5, data=DATA)]
    built = history.build(rows)
    assert validate_messages(built.messages) == []
    assert [m.role for m in built.messages] == ["user", "assistant", "user", "assistant", "tool"]
    assert built.messages[1].content == "uno\n\ndos"
    assert len(built.messages[3].tool_calls) == 1        # one call per id
    assert built.dropped == ["duplicate:c1"]


def test_a_stray_result_and_an_empty_turn_never_reach_the_provider():
    broken = [ChatMessage("user", "hola"), ChatMessage("tool", "suelto", tool_call_id="c1"),
              ChatMessage("assistant", "")]
    built = history.build(history.from_chat(broken))
    assert [m.role for m in built.messages] == ["user"]
    assert built.dropped == ["tool:1:c1"]


def test_the_repair_pass_is_the_safety_net_for_a_hand_built_list():
    """What `build` cannot produce, `_repair` must still refuse to send."""
    messages = [ChatMessage("user", "hola"),
                ChatMessage("tool", "suelto", tool_call_id="c1"),
                ChatMessage("assistant", ""),
                ChatMessage("assistant", "vale"),
                ChatMessage("user", "")]
    repaired, extra = history._repair(messages)
    assert [m.role for m in repaired] == ["user", "assistant"]
    assert extra == ["tool:c1", "empty:assistant", "empty:user"]


def test_for_provider_repairs_once_and_then_gives_up(monkeypatch):
    monkeypatch.setattr(history, "_merge", lambda messages: messages)   # keep the breakage

    def explode(*args, **kwargs):
        return history.Built(messages=[ChatMessage("tool", "suelto", tool_call_id="c1")])

    monkeypatch.setattr(history, "build", explode)
    from app.ai.history_rules import HistoryInvalid
    with pytest.raises(HistoryInvalid):
        history.for_provider([], "anthropic", session_id=1)


# --- fuzz -----------------------------------------------------------------------------------

def random_history(rng: random.Random) -> list[history.StoredMessage]:
    """A stored history with everything a real one has: notes, orphans, lost results, repeats."""
    rows: list[history.StoredMessage] = []
    next_id = 1
    open_calls: list[str] = []
    rows.append(row(next_id, "user", "hola"))
    next_id += 1

    def add(role: str, content: str = "", **kw) -> None:
        nonlocal next_id
        rows.append(row(next_id, role, content, **kw))
        next_id += 1

    for _ in range(rng.randint(1, 12)):
        kind = rng.choice(["user", "assistant", "tool", "tool", "note", "orphan"])
        if kind == "user":
            add("user", rng.choice(["hola", "continua", "aplica el proyecto", ""]))
            open_calls.clear()
        elif kind == "assistant":
            calls = [call(f"call_{rng.randrange(1000)}") for _ in range(rng.randint(0, 2))]
            open_calls.extend(item.id for item in calls)
            add("assistant", rng.choice(["", "listo", "voy"]), calls=calls)
        elif kind == "note":
            add("assistant", "Contrato del run autorizado.")
        elif kind == "tool":
            if not open_calls:
                continue
            call_id = open_calls.pop(rng.randrange(len(open_calls)))
            owner = next((r.id for r in reversed(rows) if r.role == "assistant"
                          and any(c.id == call_id for c in r.calls)), None)
            add("tool", "resultado", call_id=call_id, owner_id=owner,
                data=DATA, orphan=rng.random() < 0.1)
        else:
            add("tool", "huérfano", call_id=f"call_x{rng.randrange(1000)}", data=DATA)
    return rows


def test_fuzz_every_generated_history_passes_for_both_providers():
    rng = random.Random(20261026)
    for _ in range(5000):        # 10 000 builds (both providers): SC-001
        rows = random_history(rng)
        window = rng.choice([None, 1, 2, 3, 5, 8, 30, 50])
        for provider in ("anthropic", "openai_compatible"):
            built = history.build(rows, window=window)
            problems = validate_messages(built.messages, provider)
            assert problems == [], (provider, window, problems, rows)
            assert check_payload(payload_for(built.messages, provider), provider) == []
