"""The installation's AI status and its health block (feature 035, FR-004/FR-005)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.ai import state
from app.ai.errors import MAX_DETAIL
from tests.conftest import client, sql


def _row() -> tuple:
    return sql("SELECT last_ok_at, last_error_code, last_error_at, last_error_detail, last_model "
               "FROM ai_status WHERE id = 1")[0]


def test_a_fresh_installation_has_no_status():
    assert state.read()["last_error_code"] is None
    assert state.blocked_reason() is None
    assert state.healthy() is True


def test_a_success_records_the_model_and_clears_the_error(db):
    state.record_error("no_credit", "HTTP 402: Insufficient Balance", "deepseek-flash")
    assert state.blocked_reason() == "no_credit"
    assert state.healthy() is False

    state.record_ok("deepseek-reasoner")
    ok_at, code, err_at, detail, model = _row()
    assert code is None and err_at is None and detail is None
    assert ok_at is not None and model == "deepseek-reasoner"
    assert state.blocked_reason() is None and state.healthy() is True


def test_an_old_error_is_not_a_reason_to_refuse(db):
    """A failure the next call cleared must not block the run that follows it."""
    state.record_error("bad_key", "401", "m")
    with_old = datetime.now(UTC) - timedelta(minutes=5)
    sql("UPDATE ai_status SET last_error_at = :t WHERE id = 1", t=with_old)
    state.record_ok("m")
    sql("UPDATE ai_status SET last_ok_at = :t WHERE id = 1", t=datetime.now(UTC))
    assert state.blocked_reason() is None


def test_only_the_codes_a_person_fixes_block(db):
    for code in ("rate_limited", "provider_down", "provider_error", "refused",
                 "context_too_long", "invalid_tool_call"):
        state.record_ok("m")
        state.record_error(code, "x", "m")
        assert state.blocked_reason() is None, code
    for code in ("no_credit", "bad_key", "model_not_found"):
        state.record_ok("m")
        state.record_error(code, "x", "m")
        assert state.blocked_reason() == code, code


def test_the_stored_detail_is_capped(db):
    state.record_error("provider_error", "z" * 900, "m")
    detail = _row()[3]
    assert len(detail) == MAX_DETAIL


def test_health_reports_the_ai_block_without_the_key(db, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "ai_provider", "anthropic")
    monkeypatch.setattr(get_settings(), "ai_api_key", None)
    sql("DELETE FROM ai_status")
    state.record_error("model_not_found", "HTTP 404: model: nope", "deepseek-flash")
    body = client().get("/api/health").json()
    assert body["ai"] == {"configured": False, "provider": "anthropic",
                          "model": get_settings().ai_model_effective,
                          "last_ok_at": None, "last_error_code": "model_not_found",
                          "last_error_at": body["ai"]["last_error_at"]}
    assert body["ai"]["last_error_at"]
    assert "HTTP 404" not in str(body) and "nope" not in str(body)
