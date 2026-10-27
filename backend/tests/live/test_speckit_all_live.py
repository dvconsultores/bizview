"""SC-001/SC-002 live eval for feature 039: `/speckit-all` must reach "ready to apply" with no
user message after the contract.

Run with:

    AI_LIVE_TESTS=1 AI_LIVE_API_KEY=... [AI_LIVE_BASE_URL=...] [AI_LIVE_MODEL=...] \
        uv run pytest tests/live/test_speckit_all_live.py -s

WARNING: this contacts the live provider, costs tokens and may be slow.
Uses only the synthetic reference table (`tests.e2e_schema.seed_reference`); never real data.
"""
import os
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import get_engine
from tests.conftest import TEST_SCHEMA, signed_in, sql
from tests.e2e_schema import seed_reference
from tests.test_runner import pg_source as pg_source

pytestmark = pytest.mark.skipif(
    os.environ.get("AI_LIVE_TESTS") != "1",
    reason="contacts the live AI provider; set AI_LIVE_TESTS=1",
)

RUNS = 5
REQUIRED = 4
REQUEST = ("/speckit-all Tablero de facturas por día y estado, actualizado cada hora, con PDF")
MAX_WAIT_ROUNDS = 120          # polls of the session while the run works
MAX_FOLLOW_UPS = 0             # SC-001: nothing typed after the command


@dataclass(frozen=True)
class Outcome:
    run: int
    ready: bool
    runs: tuple[str, ...]
    report: bool
    tokens: int
    error: str | None

    @property
    def ok(self) -> bool:
        return self.ready and self.report and self.error is None


@pytest.fixture
def live_provider(monkeypatch):
    if not os.environ.get("AI_LIVE_API_KEY"):
        pytest.skip("set AI_LIVE_API_KEY for the live eval")
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_BASE_URL", os.environ.get("AI_LIVE_BASE_URL", "https://api.deepseek.com"))
    monkeypatch.setenv("AI_MODEL", os.environ.get("AI_LIVE_MODEL", "deepseek-chat"))
    monkeypatch.setenv("AI_API_KEY", os.environ["AI_LIVE_API_KEY"])
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", "120")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def reference(pg_source):
    with get_engine().begin() as c:
        seed_reference(c, TEST_SCHEMA)
    yield pg_source
    sql("DROP TABLE IF EXISTS origin_invoices")


def _run_once(client: TestClient, run: int) -> Outcome:
    project = client.post("/api/projects", json={"name": f"speckit-all {run}"})
    if project.status_code not in (200, 201):
        return Outcome(run, False, (), False, 0, f"HTTP {project.status_code}")
    session = client.post("/api/assistant/sessions",
                          json={"project": project.json()["slug"]})
    if session.status_code != 200:
        return Outcome(run, False, (), False, 0, f"HTTP {session.status_code}")
    sid = session.json()["id"]
    client.post(f"/api/assistant/sessions/{sid}/mode", json={"mode": "auto"})

    sent = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": REQUEST})
    if sent.status_code != 202:
        return Outcome(run, False, (), False, 0, f"HTTP {sent.status_code}")

    body = sent.json()
    for _ in range(MAX_WAIT_ROUNDS):
        if not body.get("busy"):
            break
        body = client.get(f"/api/assistant/sessions/{sid}").json()

    runs = tuple(item["command"] for item in body.get("command_runs") or [])
    ready = bool((body.get("readiness") or {}).get("ready"))
    report = any(message.get("run_report") for message in body.get("messages") or [])
    return Outcome(run, ready, runs, report, int(body.get("tokens_used") or 0), None)


def test_speckit_all_reaches_ready_without_a_human(live_provider, reference):
    client = signed_in("root@example.com")
    outcomes = [_run_once(client, run) for run in range(1, RUNS + 1)]
    for item in outcomes:
        print(f"run {item.run}: ready={item.ready} report={item.report} "
              f"tokens={item.tokens} runs={item.runs} error={item.error}")
    good = [item for item in outcomes if item.ok]
    # SC-001: 4 of 5; SC-002 is the same run with both specs in one version.
    assert len(good) >= REQUIRED, [f"{i.run}: {i.error or 'not ready'}" for i in outcomes]
    # SC-003: the run tells the human nothing beyond applying.
    assert all("speckit-verify" in item.runs for item in good)
