"""Feature 039 follow-up (owner, 2026-10-27): an Auto run is not stopped by a round counter.

The report: `/speckit-all` on the `coinmarketcap` panorama stopped at `limit:rounds` with
"Tokens usados: 3 927 419" while `implement` was in progress — the 200-round valve of feature 028.
An Auto run now ends when its plan ends, when the contract or the human stops it, or on a provider
error; and when the turn's own history grows past its budget it is compacted, not abandoned.
"""
from app.ai import fake
from app.config import get_settings
from app.projects import fs
from tests.conftest import PASSWORD
from tests.test_assistant_api import _chat_reply, _tool_call
from tests.test_assistant_auto_mode import _send
from tests.test_assistant_commands_service import chat as chat  # fixture
from tests.test_assistant_commands_service import fake_provider as fake_provider  # fixture

CONTRACT = {"goal": "panorama cripto", "stages": ["draft", "preview", "apply"], "limits": {}}
BIG = "specs/001-x/research.md"
OTHER = "specs/001-x/data-model.md"
# Above the verbatim tail (60 000) but well below the read the tool allows (60 000 each): two reads
# with the run's own messages cross it, one alone does not.
BUDGET = 80_000


def _auto(client, sid):
    client.post(f"/api/assistant/sessions/{sid}/mode", json={"mode": "auto"})
    confirmed = client.post(f"/api/assistant/sessions/{sid}/contract",
                            json={"contract": CONTRACT, "password": PASSWORD})
    assert confirmed.status_code == 201, confirmed.text


def _write(project, files):
    fs.apply_ops(project["id"], [{"op": "write", "path": path, "content": content,
                                  "base_sha256": None, "force": False}
                                 for path, content in files.items()],
                 {"kind": "user", "user_id": None, "session_id": None, "command": "edit"})


def _two_reads():
    return (
        _chat_reply(tool_calls=[_tool_call("read_draft", {"paths": [BIG]}, "r1")],
                    stop_reason="tool_use"),
        _chat_reply(tool_calls=[_tool_call("read_draft", {"paths": [OTHER]}, "r2")],
                    stop_reason="tool_use"),
        _chat_reply("Listo."),
    )


def test_auto_runs_past_the_chat_round_ceiling(chat, monkeypatch):
    """No `limit:rounds`: the rounds belong to the run, not to a single question."""
    client, _project, sid = chat
    _auto(client, sid)
    monkeypatch.setattr(get_settings(), "ai_chat_max_rounds", 1)
    monkeypatch.setattr(get_settings(), "ai_auto_max_rounds", None)

    rounds = 6
    steps = [_chat_reply(tool_calls=[_tool_call("get_project_overview", {}, f"t{index}")],
                         stop_reason="tool_use")
             for index in range(rounds)]
    fake.SHARED.queue(*steps, _chat_reply("Terminado."))
    body = _send(client, sid, "hazlo")

    assert len([m for m in body["messages"] if m["role"] == "tool"]) == rounds
    assert "Terminado." in [m["content"] for m in body["messages"] if m["role"] == "assistant"]
    assert not any("rondas" in (m.get("content") or "") for m in body["messages"])


def test_the_turn_history_is_compacted_instead_of_growing(chat, monkeypatch):
    """The compaction of other agents: the run keeps going and the transcript says so."""
    client, project, sid = chat
    _auto(client, sid)
    _write(project, {BIG: "# A\n\n" + "línea de contexto\n" * 3_400,
                     OTHER: "# B\n\n" + "otra línea\n" * 4_800})      # about 57 KB each
    monkeypatch.setattr(get_settings(), "ai_context_compact_chars", BUDGET)
    fake.SHARED.queue(*_two_reads())
    body = _send(client, sid, "lee los dos archivos y continúa")

    notes = [m["content"] for m in body["messages"] if m["role"] == "assistant"]
    assert any("Comprimí el contexto" in (text or "") for text in notes), notes
    # The newest result travels verbatim; the older one is a one-line summary by then, so the
    # payload of the third round is smaller than the second one even with a round more in it.
    last, before = str(fake.SHARED.requests[-1]), str(fake.SHARED.requests[-2])
    assert "otra línea" in last
    assert "línea de contexto" not in last
    assert len(last) < len(before)


def test_the_compaction_note_names_how_much_it_saved(chat, monkeypatch):
    client, project, sid = chat
    _auto(client, sid)
    _write(project, {BIG: "# A\n\n" + "línea de contexto\n" * 3_400,
                     OTHER: "# B\n\n" + "otra línea\n" * 4_800})
    monkeypatch.setattr(get_settings(), "ai_context_compact_chars", BUDGET)
    fake.SHARED.queue(*_two_reads())
    body = _send(client, sid, "lee y continúa")

    note = next(m["content"] for m in body["messages"]
                if "Comprimí el contexto" in (m.get("content") or ""))
    assert "caracteres menos" in note
    assert any(char.isdigit() for char in note)
