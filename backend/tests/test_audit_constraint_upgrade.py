"""HOTFIX-045-AUDIT-CONSTRAINT: a database with history upgrades without losing a row.

The failure this covers: `0041_drop_authoring_agent` rebuilt `ck_audit_event_ck_audit_event_kind`
from the live catalogue, so an installation that had ever recorded an `assistant_*` event could not
upgrade — 165 rows in the installation that reported it.

Each test builds its own schema and does its assertions in the same body: the suite's autouse
fixture truncates the product tables before every test, so a schema built in a fixture would be
emptied before the assertions could look at it.
"""
import json

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.db import get_engine
from app.models import AUDIT_KINDS, AUDIT_KINDS_ALLOWED, HISTORICAL_AUDIT_KINDS
from tests.conftest import TEST_SCHEMA, alembic_cfg, drop_test_schema, sql

AUDIT_CHECK = "ck_audit_event_ck_audit_event_kind"

# The kinds and counts the affected installation had (read-only inspection, 2026-11-01).
AFFECTED = {
    "assistant_attachment_deleted": 2, "assistant_attachment_uploaded": 12,
    "assistant_budget_extended": 44, "assistant_contract_confirmed": 46,
    "assistant_mode_changed": 5, "assistant_run_applied": 10, "assistant_run_stopped": 36,
    "assistant_session_archived": 9, "assistant_session_deleted": 1,
    "integration_run_requested": 6, "login_failed": 9, "login_ok": 23, "logout": 11,
    "password_changed": 1, "password_reset": 1, "project_applied": 25, "project_created": 13,
    "project_deleted": 11, "project_exported": 4, "project_fix_applied": 1,
    "project_withdrawn": 1, "reauth_failed": 4, "reauth_ok": 28, "share_link_created": 1,
    "source_created": 3, "source_deleted": 1, "source_described": 494, "source_tested": 7,
    "source_updated": 3, "superuser_created": 1, "user_created": 2, "workspace_applied": 26,
    "workspace_validated": 1,
}


def _reset_and_build(rev: str) -> None:
    drop_test_schema()
    command.upgrade(alembic_cfg(), rev)


def _seed(counts: dict[str, int]) -> None:
    """Audit rows whose every column is checkable after the upgrade."""
    with get_engine().begin() as c:
        c.execute(text(f'SET LOCAL search_path TO "{TEST_SCHEMA}"'))
        for kind, total in counts.items():
            for index in range(total):
                c.execute(text(
                    "INSERT INTO audit_event (kind, detail, ip) "
                    "VALUES (:kind, CAST(:detail AS jsonb), '203.0.113.7')"),
                    {"kind": kind, "detail": json.dumps({"n": index})})


def _rows() -> list[tuple]:
    return sql("SELECT id, kind, occurred_at, actor_id, ip, detail FROM audit_event ORDER BY id")


def _constraint() -> str:
    """The constraint on *this* schema's table: `pg_constraint` is global, and old test schemas
    left behind by interrupted runs carry a constraint with the same name."""
    rows = sql(
        "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
        "WHERE c.conname = 'ck_audit_event_ck_audit_event_kind' "
        "AND c.conrelid = to_regclass(:table)", table=f'"{TEST_SCHEMA}".audit_event')
    assert rows, "the audit kind constraint is missing"
    return rows[0][0]


def _kinds_in(definition: str) -> set[str]:
    import re

    return set(re.findall(r"'([a-z0-9_]+)'::text", definition))


def _leave_at_head() -> None:
    drop_test_schema()
    command.upgrade(alembic_cfg(), "head")


def test_a_database_with_history_upgrades_and_keeps_every_row():
    """The affected installation: 0040, 842 rows, 165 of them from the removed agent."""
    try:
        _reset_and_build("0040_auto_run_stages")
        before_definition = _constraint()
        _seed(AFFECTED)
        before = _rows()
        assert len(before) == 842

        command.upgrade(alembic_cfg(), "head")

        assert _rows() == before, "the migration changed or lost audit rows"

        # The constraint after the upgrade accepts everything it accepted before, and history.
        after = _kinds_in(_constraint())
        assert set(HISTORICAL_AUDIT_KINDS) <= after
        assert set(AUDIT_KINDS) <= after
        assert _kinds_in(before_definition) <= after, "the upgrade narrowed what is accepted"

        # And it still refuses a kind nobody knows.
        with pytest.raises(IntegrityError):
            with get_engine().begin() as c:
                c.execute(text(f'SET LOCAL search_path TO "{TEST_SCHEMA}"'))
                c.execute(text("INSERT INTO audit_event (kind) VALUES ('kind_from_the_future')"))
        assert len(_rows()) == 842

        # Re-running the upgrade changes nothing.
        command.upgrade(alembic_cfg(), "head")
        assert _rows() == before
    finally:
        _leave_at_head()


def test_the_removed_tables_are_gone_and_the_audit_rows_are_not():
    try:
        _reset_and_build("0040_auto_run_stages")
        _seed({"assistant_run_applied": 3, "project_applied": 1})
        before = _rows()
        command.upgrade(alembic_cfg(), "head")
        tables = {row[0] for row in sql(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = :s",
            s=TEST_SCHEMA)}
        assert not {t for t in tables if t.startswith("assistant_")}
        assert "audit_event" in tables
        assert _rows() == before
    finally:
        _leave_at_head()


def test_a_database_with_only_current_kinds_upgrades():
    try:
        _reset_and_build("0040_auto_run_stages")
        _seed({"login_ok": 3, "project_applied": 2})
        before = _rows()
        command.upgrade(alembic_cfg(), "head")
        assert _rows() == before
        assert set(HISTORICAL_AUDIT_KINDS) <= _kinds_in(_constraint())
    finally:
        _leave_at_head()


def test_an_empty_database_upgrades():
    try:
        _reset_and_build("0040_auto_run_stages")
        command.upgrade(alembic_cfg(), "head")
        assert sql("SELECT count(*) FROM audit_event") == [(0,)]
        assert sql("SELECT version_num FROM alembic_version") != []
    finally:
        _leave_at_head()


def test_five_thousand_five_five_s_broken_constraint_is_repaired_at_head():
    """`0056` heals a database that upgraded while 0055 shipped a broken audit CHECK.

    The defect: two literals of 0055's frozen copy ran together (`"project_reverted"` + newline +
    `"starter_downloaded""mail_list_created"`), so Python concatenated three names into one and the
    constraint 0055 created forbade `starter_downloaded`, the three `mail_list_*` kinds and
    `mail_send_resent`. A starter download, a mailing list and every mailing-list send therefore
    died on the audit insert.

    0055 is repaired in place for fresh installations, so this test rebuilds the constraint exactly
    as it shipped and then upgrades to head: `0056` must accept the kinds the product writes — and
    the history a database already holds, including the removed agent's `assistant_*` rows, which
    is why building that CHECK from `AUDIT_KINDS` alone made an installation with history fail.
    """
    broken = (
        "kind IN ('login_ok', 'assistant_run_applied', 'project_reverted', "
        "'mail_list_created', 'integration_busy')"
    )
    try:
        _reset_and_build("0055_source_connection_limits")
        with get_engine().begin() as c:
            c.execute(text(f'SET LOCAL search_path TO "{TEST_SCHEMA}"'))
            c.execute(text(f"ALTER TABLE audit_event DROP CONSTRAINT {AUDIT_CHECK}"))
            c.execute(text(
                f"ALTER TABLE audit_event ADD CONSTRAINT {AUDIT_CHECK} CHECK ({broken})"))
        _seed({"assistant_run_applied": 2, "login_ok": 1})

        # As it shipped: a kind the product writes is refused.
        with pytest.raises(IntegrityError):
            with get_engine().begin() as c:
                c.execute(text(f'SET LOCAL search_path TO "{TEST_SCHEMA}"'))
                c.execute(text("INSERT INTO audit_event (kind) VALUES ('starter_downloaded')"))

        command.upgrade(alembic_cfg(), "head")

        after = _kinds_in(_constraint())
        assert set(AUDIT_KINDS) <= after, "a kind the product writes is still refused after 0056"
        assert set(HISTORICAL_AUDIT_KINDS) <= after, "the upgrade dropped history it must keep"
        assert {"starter_downloaded", "mail_list_created", "mail_list_updated",
                "mail_list_deleted", "mail_send_resent"} <= after

        # The repaired constraint still refuses a kind nobody knows, and the rows are untouched.
        with pytest.raises(IntegrityError):
            with get_engine().begin() as c:
                c.execute(text(f'SET LOCAL search_path TO "{TEST_SCHEMA}"'))
                c.execute(text("INSERT INTO audit_event (kind) VALUES ('kind_from_the_future')"))
        assert len(_rows()) == 3
    finally:
        _leave_at_head()


def test_the_application_still_cannot_emit_a_historical_kind():
    """The database accepts history; only `AUDIT_KINDS` may be written, and the app says so."""
    from app.services import audit

    with pytest.raises(AssertionError):
        audit.record(None, "assistant_run_applied")  # type: ignore[arg-type]
    with pytest.raises(AssertionError):
        audit.record(None, "kind_from_the_future")  # type: ignore[arg-type]
    assert set(AUDIT_KINDS_ALLOWED) == set(AUDIT_KINDS) | set(HISTORICAL_AUDIT_KINDS)
