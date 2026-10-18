"""SC-001 live eval for feature 017: the agent must reach "Listo para aplicar" on the
reference invoice table with real AI calls.

Run with:

    AI_LIVE_TESTS=1 AI_LIVE_API_KEY=... [AI_LIVE_BASE_URL=https://api.deepseek.com] \
    [AI_LIVE_MODEL=deepseek-chat] uv run pytest tests/live/test_agent_eval.py -s

WARNING: this contacts the live provider, costs tokens and may be slow.
Uses only the synthetic reference table (tests.e2e_schema.seed_reference); never real data.
"""
import os
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
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
REQUEST = "dashboard de facturas por día y estado, actualizado cada hora, con PDF"
FOLLOW_UP = (
    "Usa valores por defecto razonables para lo que falte y continúa "
    "hasta dejarlo listo para aplicar."
)
MAX_FOLLOW_UPS = 3
MAX_VALIDATIONS = 3
MAX_BUDGET_RATIO = 0.40
DEFAULT_BUDGET = Settings.model_fields["ai_chat_token_budget"].default


@dataclass(frozen=True)
class RunReport:
    run: int
    ready: bool
    validations: int
    probes: int
    previews: int
    rounds: int
    tokens: int
    budget_pct: float
    turns: int
    error: str | None

    @property
    def within_limits(self) -> bool:
        return (
            self.ready
            and self.validations <= MAX_VALIDATIONS
            and self.probes == 0
            and self.tokens <= MAX_BUDGET_RATIO * DEFAULT_BUDGET
        )


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


def _report(run: int, session: dict | None, turns: int, error: str | None = None) -> RunReport:
    if session is None:
        return RunReport(run, False, 0, 0, 0, 0, 0, 0.0, turns, error)
    stats = session.get("stats", {}) or {}
    readiness = session.get("readiness", {}) or {}
    validations = stats.get("validations", 0)
    probes = stats.get("probes", 0)
    previews = stats.get("previews", 0)
    rounds = stats.get("rounds", 0)
    tokens = session.get("tokens_used", 0)
    budget_pct = round(100 * tokens / DEFAULT_BUDGET, 1)
    ready = bool(readiness.get("ready") and not error)
    return RunReport(
        run,
        ready,
        validations,
        probes,
        previews,
        rounds,
        tokens,
        budget_pct,
        turns,
        error,
    )


def _run_once(client: TestClient, run: int) -> RunReport:
    session_r = client.post("/api/assistant/sessions", json={})
    if session_r.status_code != 200:
        return _report(run, None, 0, f"HTTP {session_r.status_code}")

    session_id = session_r.json()["id"]
    session: dict | None = None
    turns = 0
    for _ in range(MAX_FOLLOW_UPS + 1):
        text = REQUEST if turns == 0 else FOLLOW_UP
        r = client.post(f"/api/assistant/sessions/{session_id}/messages", json={"text": text})
        turns += 1
        if r.status_code != 202:
            content_type = r.headers.get("content-type", "")
            body = r.json() if "application/json" in content_type else {}
            detail = body.get("detail") if isinstance(body.get("detail"), dict) else {}
            code = body.get("code") or detail.get("code")
            error = f"HTTP {r.status_code} {code or ''}".strip()
            return _report(run, session, turns, error)
        session = r.json()["session"]
        if session.get("readiness", {}).get("ready"):
            break
        if session.get("status") != "open":
            break
        if session.get("tokens_used", 0) >= session.get("token_budget", DEFAULT_BUDGET):
            break

    return _report(run, session, turns)


def test_sc001_agent_reaches_ready(superuser, reference, live_provider, capsys):
    client = signed_in("root@example.com")
    reports = [_run_once(client, n) for n in range(1, RUNS + 1)]

    headers = ["run", "ready", "valid", "probe", "prev", "rounds", "tokens", "budget",
               "turns", "ok"]
    widths = [3, 5, 5, 5, 4, 6, 6, 6, 5, 3]
    lines = [" ".join(h.rjust(w) for h, w in zip(headers, widths, strict=True))]
    for r in reports:
        values = [
            str(r.run),
            str(r.ready),
            str(r.validations),
            str(r.probes),
            str(r.previews),
            str(r.rounds),
            str(r.tokens),
            f"{r.budget_pct:.1f}%",
            str(r.turns),
            str(r.within_limits),
        ]
        lines.append(" ".join(v.rjust(w) for v, w in zip(values, widths, strict=True)))
        if r.error:
            lines.append(f"    error: {r.error}")
    passed = sum(1 for r in reports if r.within_limits)
    lines.append(f"\nSC-001: {passed}/{RUNS} ejecuciones dentro de los límites")
    table = "\n".join(lines)

    with capsys.disabled():
        print(f"\n{table}\n")

    assert passed >= REQUIRED, f"expected at least {REQUIRED}/{RUNS} within limits:\n{table}"
