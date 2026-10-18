"""Direct-source failure behaviour through the HTTP API (feature 019)."""
import copy
import time
from contextlib import contextmanager

import pytest
from sqlalchemy import select, text

from app.config import get_settings
from app.db import get_engine, lock_key
from app.engine import direct, report
from app.models import AppUser
from tests.conftest import signed_in, sql
from tests.test_direct_engine import US1_REPORT, _write_workspace
from tests.test_vibe_reporting import apply, lock

BUCKET_A = 1_000_000 * 300 + 1
BUCKET_B = BUCKET_A + 300
TIMEOUT = 10

DATA_URL = (
    "/api/reports/bi-ventas/data?period=custom&from=2026-09-01&to=2026-09-30&compare=none"
)
DATA_URL_B = (
    "/api/reports/bi-ventas/data?period=custom&from=2026-09-02&to=2026-09-30&compare=none"
)


@pytest.fixture(autouse=True)
def _direct_sync(monkeypatch):
    monkeypatch.setattr(direct, "LOG_ASYNC", False)
    direct.clear_cache()
    direct._inflight.clear()
    sql("DELETE FROM direct_read_log")
    yield
    direct.clear_cache()


@pytest.fixture
def ws(superuser, tmp_path, monkeypatch):
    phys = direct.physical_schema("public")
    sql(f'CREATE SCHEMA IF NOT EXISTS "{phys}"')
    sql(f'DROP TABLE IF EXISTS "{phys}".bi_ventas CASCADE')
    sql(f'CREATE TABLE "{phys}".bi_ventas (day date, amount numeric, product text)')
    sql(
        f'INSERT INTO "{phys}".bi_ventas(day, amount, product) VALUES '
        f"('2026-09-01', 10.5, 'A'), ('2026-09-02', 20.0, 'B'), ('2026-09-03', 5.25, 'A')"
    )

    rep = copy.deepcopy(US1_REPORT)
    rep["direct"]["timeout_seconds"] = TIMEOUT
    root = tmp_path / "ws"
    root.mkdir()
    _write_workspace(root, rep, "public.bi_ventas")
    monkeypatch.setattr(get_settings(), "workspace_path", str(root))
    lock(root)
    c = signed_in("root@example.com")
    apply(c)
    monkeypatch.setattr(report, "_epoch", lambda: BUCKET_A)
    try:
        yield c, phys
    finally:
        sql(f'DROP TABLE IF EXISTS "{phys}".bi_ventas CASCADE')


@contextmanager
def _held_slot(key: str):
    conn = get_engine().connect()
    pg = conn.connection.driver_connection
    pg.autocommit = True
    try:
        got = pg.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s, 0))", (key,)
        ).fetchone()[0]
        assert got is True
        yield
    finally:
        pg.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", (key,))
        pg.autocommit = False
        conn.close()


def _rtt() -> float:
    conn = get_engine().connect()
    try:
        conn.execute(text("SELECT 1"))
        started = time.monotonic()
        for _ in range(5):
            conn.execute(text("SELECT 1"))
        return (time.monotonic() - started) / 5
    finally:
        conn.close()


def _make_fake_unreachable(calls):
    @contextmanager
    def fake(src, deadline, timeout_seconds):
        calls["n"] += 1
        raise direct.DirectError("unreachable")
        yield

    return fake


def test_unreachable_serves_stale_then_backoff(ws, monkeypatch):
    c, _ = ws
    first = c.get(DATA_URL)
    assert first.status_code == 200, first.text
    first_fresh = first.json()["freshness"]
    assert first_fresh["stale"] is False
    remembered = first_fresh["queried_at"]

    calls = {"n": 0}
    monkeypatch.setattr(direct, "_connect", _make_fake_unreachable(calls))
    monkeypatch.setattr(report, "_epoch", lambda: BUCKET_B)

    r = c.get(DATA_URL)
    assert r.status_code == 200, r.text
    fresh = r.json()["freshness"]
    assert fresh["stale"] is True
    assert fresh["stale_reason"] == "unreachable"
    assert fresh["queried_at"] == remembered
    assert r.json()["views"][0]["items"][0]["value"] == 35.75
    assert calls["n"] == 1

    r2 = c.get(DATA_URL)
    assert r2.status_code == 200, r2.text
    assert r2.json()["freshness"]["stale"] is True
    assert calls["n"] == 1

    r3 = c.get(DATA_URL_B)
    assert r3.status_code == 503
    assert r3.json()["error"]["code"] == "source_unavailable"
    assert calls["n"] == 1


def test_unreachable_without_cache_is_503(ws, monkeypatch):
    c, _ = ws
    monkeypatch.setattr(direct, "_connect", _make_fake_unreachable({"n": 0}))
    r = c.get(DATA_URL)
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "source_unavailable"
    assert r.json()["error"]["message"] == "No se pudo conectar con la fuente"


def test_timeout_is_bounded(ws, monkeypatch):
    c, phys = ws
    rtt = _rtt()
    monkeypatch.setattr(direct, "LOG_ASYNC", True)
    conn = get_engine().connect()
    trans = conn.begin()
    conn.execute(text(f'LOCK TABLE "{phys}".bi_ventas IN ACCESS EXCLUSIVE MODE'))
    try:
        started = time.monotonic()
        r = c.get(DATA_URL)
        elapsed = time.monotonic() - started
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "source_timeout"
        assert f"tiempo límite de {TIMEOUT} s" in r.json()["error"]["message"]
        # SC-004 is timeout + 1 s on a local database; the 12 round trips cover
        # authentication, cache lookups and cleanup after the deadline on a remote test database.
        assert elapsed <= TIMEOUT + 1 + 12 * rtt
    finally:
        trans.rollback()
        conn.close()
        direct.flush_log()


def test_busy_with_held_slot(ws, monkeypatch):
    c, _ = ws
    rtt = _rtt()
    monkeypatch.setattr(get_settings(), "direct_report_concurrency", 1)
    monkeypatch.setattr(direct, "LOG_ASYNC", True)
    key = lock_key("direct", "bi", "0")
    with _held_slot(key):
        started = time.monotonic()
        r = c.get(DATA_URL)
        elapsed = time.monotonic() - started
    direct.flush_log()
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "source_busy"
    assert r.json()["error"]["message"] == "La fuente está ocupada"
    # SC-004 is timeout + 1 s on a local database; the 12 round trips cover
    # authentication, cache lookups and cleanup after the deadline on a remote test database.
    assert elapsed <= TIMEOUT + 1 + 12 * rtt

    r = c.get(DATA_URL)
    assert r.status_code == 200, r.text
    assert r.json()["views"][0]["items"][0]["value"] == 35.75


def test_structure_changed_marks_report_broken(ws, monkeypatch):
    c, phys = ws
    assert c.get(DATA_URL).status_code == 200
    sql(f'ALTER TABLE "{phys}".bi_ventas DROP COLUMN product')
    monkeypatch.setattr(report, "_epoch", lambda: BUCKET_B)

    r = c.get(DATA_URL)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "direct_structure_changed"
    assert r.json()["error"]["message"] == "La estructura de la fuente cambió: falta product"

    workspace = c.get("/api/workspace").json()
    entry = next(d for d in workspace["report_details"] if d["id"] == "bi-ventas")
    assert entry["mode"] == "direct"
    assert entry["status"] == "broken"


def test_read_log_has_no_values(ws, monkeypatch):
    c, _ = ws
    assert c.get(DATA_URL).status_code == 200

    calls = {"n": 0}
    monkeypatch.setattr(direct, "_connect", _make_fake_unreachable(calls))
    monkeypatch.setattr(report, "_epoch", lambda: BUCKET_B)
    assert c.get(DATA_URL).status_code == 200

    cols = sorted(
        row[0]
        for row in sql(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'direct_read_log' AND table_schema = current_schema()"
        )
    )
    assert cols == [
        "duration_ms", "id", "occurred_at", "outcome", "report_id", "rows",
        "source", "stale_served",
    ]
    rows = sql(
        "SELECT report_id, source, rows, outcome, stale_served "
        "FROM direct_read_log ORDER BY id"
    )
    assert [(r[0], r[1], r[3], r[4]) for r in rows] == [
        ("bi-ventas", "bi", "ok", False),
        ("bi-ventas", "bi", "unreachable", False),
        ("bi-ventas", "bi", "unreachable", True),
    ]
    assert rows[0][2] > 0
    blob = str(sql("SELECT * FROM direct_read_log"))
    for value in ("10.5", "20.0", "5.25", "'A'"):
        assert value not in blob


def test_security_counts_direct_reads(ws, monkeypatch):
    c, _ = ws
    assert c.get(DATA_URL).status_code == 200

    calls = {"n": 0}
    monkeypatch.setattr(direct, "_connect", _make_fake_unreachable(calls))
    monkeypatch.setattr(report, "_epoch", lambda: BUCKET_B)
    assert c.get(DATA_URL).status_code == 200

    r = c.get("/api/security")
    assert r.status_code == 200
    assert r.json()["direct_reads"] == [{"source": "bi", "total": 2, "failed": 1}]


def test_security_counts_chat_briefs(ws, monkeypatch):
    """Feature 024 FR-014: the overview shows what the chat has sent, never the images."""
    from app.assistant import attachments as chat_attachments
    from app.config import get_settings
    from app.db import get_sessionmaker
    from tests.test_assistant_api import _stored_session

    c, _ = ws
    assert c.get("/api/security").json()["attachments"]["total"] == 0

    PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    with get_sessionmaker()() as db:          # `_stored_session` commits on its own
        user = db.scalar(select(AppUser).where(AppUser.email == "root@example.com"))
        session = _stored_session(db, user)
        chat_attachments.store(db, session.id, PNG, "boceto.png", user.id)
        db.commit()
        session_id = session.id

    summary = c.get("/api/security").json()["attachments"]
    assert summary["total"] == 1
    assert summary["bytes"] == len(PNG)
    assert summary["conversations"] == 1
    assert summary["provider"] == get_settings().ai_provider
    assert "PNG" not in str(summary) and "boceto" not in str(summary)
    assert get_settings().attachments_dir
    assert session_id
