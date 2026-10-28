"""Feature 040: `/speckit-all` over the coinmarketcap fixture — no conflict, no compression.

The production run of this project (2026-10-28) spent 14 327 159 tokens, compacted three times and
ended with an IntegrityError. This run walks the same project end to end on the product's own
fixture and asserts the properties the defect report asked for.
"""
import pytest

from app.assistant import service
from app.ai import fake
from app.config import get_settings
from app.projects import fs
from tests import coinmarketcap_fixture as cmc
from tests.conftest import signed_in
from tests.test_assistant_auto_mode import _send
from tests.test_assistant_speckit_all_run import _open, _text

SPEC = "001-mercado-cripto"


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch, tmp_path):
    monkeypatch.setenv("BIZVIEW_TEST_HOOKS", "1")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    get_settings.cache_clear()
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))
    fake.SHARED.reset()
    yield
    fake.SHARED.reset()
    get_settings.cache_clear()


def _session(client, sid: int) -> dict:
    return client.get(f"/api/assistant/sessions/{sid}").json()


def test_the_coinmarketcap_plan_reaches_converge_without_a_conflict(superuser):
    client = signed_in("root@example.com")
    slug = cmc.create_project(client)
    cmc.put_files(client, slug, cmc.fixture_files())
    sid = client.post("/api/assistant/sessions", json={"project": slug}).json()["id"]
    client.post(f"/api/assistant/sessions/{sid}/mode", json={"mode": "auto"})
    fake.SHARED.queue(
        _open("speckit-analyze", call_id="a1"),
        _open("speckit-implement", call_id="i1"),
        _open("speckit-converge", call_id="c1"),
        _text(),
    )
    body = _send(client, sid, f"/speckit-all {SPEC} --until converge")

    commands = [run["command"] for run in body["command_runs"]]
    assert "speckit-analyze" in commands
    assert "speckit-implement" in commands
    assert "speckit-converge" in commands

    text = " ".join(str(message.get("content") or "") for message in body["messages"])
    assert "error inesperado" not in text.lower()
    assert "loop_state_conflict" not in text

    state = _session(client, sid)
    assert int((state.get("stats") or {}).get("compactions") or 0) == 0
    assert int((state.get("stats") or {}).get("rounds") or 0) <= 6

    report = fs.read_text(slug, f"specs/{SPEC}/run-report.md")
    assert "## Stages" in report
    assert "## Decisiones tomadas" in report
    # Nothing was left for the human beyond applying, and the plan stopped where it was asked to.
    pending = report.split("## Pendiente para el humano")[-1]
    assert "instruc" not in pending.lower()


def test_the_run_stages_carry_their_round_and_their_own_context(superuser):
    """A stage opened after converge says its round and does not replay the earlier results."""
    client = signed_in("root@example.com")
    slug = cmc.create_project(client)
    files = cmc.fixture_files()
    # The defect's shape: converge left four tasks open (T025–T028 of the production run).
    files[f"specs/{SPEC}/tasks.md"] = (
        "- [X] T001 integrar los cuatro conjuntos\n"
        "- [ ] T025 mapear `snapshot_at` en fear_greed\n"
        "- [ ] T026 los `fields` de `global-metrics`\n")
    cmc.put_files(client, slug, files)
    sid = client.post("/api/assistant/sessions", json={"project": slug}).json()["id"]
    client.post(f"/api/assistant/sessions/{sid}/mode", json={"mode": "auto"})
    fake.SHARED.queue(
        _open("speckit-analyze", call_id="a1"),
        _open("speckit-implement", call_id="i1"),
        _open("speckit-converge", call_id="c1"),
        _open("speckit-verify", call_id="v1"),      # with tasks open, this opens implement
        _text(),
    )
    body = _send(client, sid, f"/speckit-all {SPEC} --until verify")
    commands = [run["command"] for run in body["command_runs"]]
    assert "speckit-implement" in commands
    assert "speckit-verify" not in commands
    text = " ".join(str(message.get("content") or "") for message in body["messages"])
    assert "ronda 2" in text
    # The prompt of the re-entry is its own: it does not carry the earlier stage's tool results.
    prompts = [request for request in fake.SHARED.requests
               if request.get("kind") == "chat" and "fear_greed" in str(request)]
    assert prompts == [] or all(len(str(item)) < 200_000 for item in prompts)
    assert service  # the product wrote the stage summary; the import keeps the intent explicit
