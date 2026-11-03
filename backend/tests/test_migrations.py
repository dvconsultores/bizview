"""SC-007 / FR-031: migrations on DATABASE_URL_BI create exactly the product's tables and are
repeatable. The suite runs them in a temporary app_test_* schema; conftest asserts that the real
schema `public` is unchanged after the run.

Feature 045 removed the in-app authoring agent and, with it, this module's assistant half: the
tests that seeded `assistant_*` rows or downgraded below `0041_drop_authoring_agent` are gone,
because that migration cannot be downgraded (it deleted a subsystem — see its docstring; recovery
is the backup taken before the upgrade). What is left covers the migrations of the tables the
product still has."""
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import MetaData, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.db import get_engine
from app.models import Base
from tests.conftest import TEST_SCHEMA, alembic_cfg, make_user, outside_snapshot, sql

APP_TABLES = {"alembic_version", "app_user", "audit_event", "dashboard", "dashboard_access",
              "user_session", "data_source", "security_state", "recovery_code",
              "login_throttle", "workspace_version", "integration_run",
              "integration_run_request", "report_cache", "api_token", "telegram_settings",
              "telegram_link", "telegram_request", "integration_control",
              "share_link", "email_send", "email_delivery", "email_subscription",
              "direct_read_log", "report_rollup", "project", "project_file_revision",
              "google_link", "ai_status", "appearance_settings", "image_cache",
              "theme", "direct_snapshot", "project_limits"}


def schema_tables():
    return {r[0] for r in sql("SELECT table_name FROM information_schema.tables "
                              "WHERE table_schema = :s", s=TEST_SCHEMA)}


def test_migrations_create_only_the_product_schema(database):
    assert schema_tables() == APP_TABLES
    assert outside_snapshot() == database  # public untouched, no extension installed


def test_upgrade_is_idempotent_and_stops_downgrading_on_purpose(database):
    """A second `upgrade head` changes nothing; going back stops on purpose (045, 047)."""
    command.upgrade(alembic_cfg(), "head")  # second run: no-op
    assert schema_tables() == APP_TABLES
    with pytest.raises(RuntimeError, match="cannot be downgraded"):
        command.downgrade(alembic_cfg(), "base")
    # The refusal leaves the tree at head: nothing was half-dropped or half-created.
    assert schema_tables() == APP_TABLES
    assert sql("SELECT code, status FROM dashboard") == []   # 046: no dashboard by default
    assert outside_snapshot() == database


def test_0042_seeds_the_themes_the_product_ships():
    """The built-ins come from the files the app and the PDF read, not from a copy in SQL.

    Feature 051 added `elegante` and refreshed the other five from their files, so the head of the
    chain carries the six."""
    assert sql("SELECT id, origin, version FROM theme ORDER BY id") == [
        ("clasico", "builtin", 1), ("contraste", "builtin", 1), ("daltonico", "builtin", 1),
        ("elegante", "builtin", 1), ("impacto", "builtin", 1), ("monocromo", "builtin", 1)]
    assert sql("SELECT tokens ->> 'id' FROM theme WHERE id = 'impacto'") == [("impacto",)]


def test_models_match_migrations():
    target = MetaData(schema=TEST_SCHEMA, naming_convention=Base.metadata.naming_convention)
    for table in Base.metadata.tables.values():
        table.to_metadata(target, schema=TEST_SCHEMA)
    raw = get_engine().execution_options(schema_translate_map=None)
    with raw.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={
            "include_schemas": True,
            "include_name": lambda name, type_, parent: type_ != "schema" or name == TEST_SCHEMA,
        })
        diff = [d for d in compare_metadata(ctx, target)
                if not (d[0] == "remove_table" and d[1].name == "alembic_version")]
    assert diff == []


def test_database_allows_only_one_superuser():
    make_user("a@example.com", is_superuser=True)
    with pytest.raises(IntegrityError):
        make_user("b@example.com", is_superuser=True)


def test_user_theme_defaults_to_system_and_is_checked():
    """Feature 006: existing and new users start on "system"; other values are refused."""
    user = make_user("theme@example.com")
    assert sql("SELECT theme FROM app_user WHERE id = :i", i=user.id) == [("system",)]
    with pytest.raises(IntegrityError):
        sql("UPDATE app_user SET theme = 'sepia' WHERE id = :i", i=user.id)


def test_integration_control_window_pair_and_default_paused(database):
    """Feature 013: a one-sided window is refused; paused defaults to false."""
    with pytest.raises(IntegrityError):
        sql("INSERT INTO integration_control (integration_id, window_start) "
            "VALUES ('one-sided-start', '22:00')")
    with pytest.raises(IntegrityError):
        sql("INSERT INTO integration_control (integration_id, window_end) "
            "VALUES ('one-sided-end', '06:00')")

    sql("INSERT INTO integration_control (integration_id, window_start, window_end) "
        "VALUES ('paired', '22:00', '06:00')")
    assert sql("SELECT paused FROM integration_control WHERE integration_id = 'paired'") == [
        (False,)
    ]


def test_integration_run_accepts_stopped(database):
    """Feature 013: a run may be stopped, recording who stopped it and when."""
    user = make_user("stopper@example.com")
    sql("INSERT INTO integration_run (integration_id, kind, status, stop_requested_by, "
        "stop_requested_at) VALUES ('demo', 'incremental', 'stopped', :u, '2026-10-02T10:00:00Z')",
        u=user.id)
    assert sql("SELECT status, stop_requested_by FROM integration_run "
               "WHERE integration_id = 'demo'") == [("stopped", user.id)]


def _project(slug: str) -> int:
    """Conversations belong to a project since migration 0018 (feature 020)."""
    return sql("INSERT INTO project (slug, name, origin) VALUES (:s, 'P', 'app') RETURNING id",
               s=slug)[0][0]


def test_dashboard_sharing_tables_and_checks(database):
    make_user("share-owner@example.com", role="admin")
    dashboard_id = sql(
        "INSERT INTO dashboard (code, name, description, icon, sort_order, status) "
        "VALUES ('ventas', 'Ventas', 'd', 'chart-line', 10, 'available') RETURNING id")[0][0]

    # share_link defaults and unique token_hash
    sql(
        """
        INSERT INTO share_link (dashboard_id, token_hash, created_by, expires_at)
        VALUES (:d, decode('00ff', 'hex'), (SELECT id FROM app_user LIMIT 1),
                now() + interval '7 days')
        """,
        d=dashboard_id,
    )
    row = sql("SELECT visits, revoked_at FROM share_link")[0]
    assert row[0] == 0 and row[1] is None

    with pytest.raises(IntegrityError):
        sql(
            """
            INSERT INTO share_link (dashboard_id, token_hash, created_by, expires_at)
            VALUES (:d, decode('00ff', 'hex'), (SELECT id FROM app_user LIMIT 1),
                    now() + interval '1 day')
            """,
            d=dashboard_id,
        )

    with pytest.raises(IntegrityError):
        sql(
            """
            INSERT INTO share_link (dashboard_id, token_hash, created_by, expires_at, note)
            VALUES (:d, decode('abcd', 'hex'), (SELECT id FROM app_user LIMIT 1),
                    now() + interval '1 day', repeat('a', 201))
            """,
            d=dashboard_id,
        )

    with pytest.raises(IntegrityError):
        sql(
            """
            INSERT INTO share_link (dashboard_id, token_hash, created_by, expires_at)
            VALUES (:d, decode('abcd', 'hex'), (SELECT id FROM app_user LIMIT 1), now())
            """,
            d=dashboard_id,
        )

    # email_subscription frequency validations
    with pytest.raises(IntegrityError):
        sql(
            """
            INSERT INTO email_subscription
                (dashboard_id, created_by, frequency, hour, period, next_due_at)
            VALUES (:d, (SELECT id FROM app_user LIMIT 1), 'weekly', 9, 'p1', now())
            """,
            d=dashboard_id,
        )

    with pytest.raises(IntegrityError):
        sql(
            """
            INSERT INTO email_subscription
                (dashboard_id, created_by, frequency, hour, weekday, period, next_due_at)
            VALUES (:d, (SELECT id FROM app_user LIMIT 1), 'daily', 9, 1, 'p1', now())
            """,
            d=dashboard_id,
        )

    with pytest.raises(IntegrityError):
        sql(
            """
            INSERT INTO email_subscription
                (dashboard_id, created_by, frequency, hour, monthday, period, next_due_at)
            VALUES (:d, (SELECT id FROM app_user LIMIT 1), 'monthly', 9, 29, 'p1', now())
            """,
            d=dashboard_id,
        )

    sql(
        """
        INSERT INTO email_subscription
            (dashboard_id, created_by, frequency, hour, weekday, period, next_due_at)
        VALUES (:d, (SELECT id FROM app_user LIMIT 1), 'weekly', 9, 1, 'p1', now())
        """,
        d=dashboard_id,
    )

    # email_send and email_delivery cascade
    sql(
        """
        INSERT INTO email_send (dashboard_id, subject)
        VALUES (:d, 'Ventas')
        """,
        d=dashboard_id,
    )
    send_id = sql("SELECT id FROM email_send WHERE subject = 'Ventas'")[0][0]
    sql("INSERT INTO email_delivery (send_id, recipient) VALUES (:s, 'a@b.co')", s=send_id)
    row = sql("SELECT status, attempts FROM email_delivery WHERE send_id = :s", s=send_id)[0]
    assert row == ("queued", 0)

    sql("DELETE FROM email_send WHERE id = :s", s=send_id)
    assert sql("SELECT count(*) FROM email_delivery WHERE send_id = :s", s=send_id)[0][0] == 0

    # new audit kind accepted
    sql("INSERT INTO audit_event (kind) VALUES ('share_link_created')")

    # cleanup
    sql("DELETE FROM email_delivery WHERE send_id IN (SELECT id FROM email_send)")
    sql("DELETE FROM email_send")
    sql("DELETE FROM email_subscription")
    sql("DELETE FROM share_link")
    sql("DELETE FROM audit_event WHERE kind = 'share_link_created'")



# --- 048 hotfix: the audit constraint accepts history -------------------------------------------

HISTORICAL = (
    "assistant_attachment_deleted", "assistant_attachment_uploaded", "assistant_budget_extended",
    "assistant_contract_confirmed", "assistant_conversation_repaired", "assistant_draft_applied",
    "assistant_mode_changed", "assistant_profile_created", "assistant_profile_deleted",
    "assistant_profile_edited", "assistant_run_applied", "assistant_run_rolled_back",
    "assistant_run_started", "assistant_run_stopped", "assistant_session_archived",
    "assistant_session_deleted",
)


def _migration(name: str):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"mig_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_model_keeps_the_two_catalogues_apart():
    from app.models import AUDIT_KINDS, AUDIT_KINDS_ALLOWED, HISTORICAL_AUDIT_KINDS

    assert set(HISTORICAL_AUDIT_KINDS) == set(HISTORICAL)
    assert not set(AUDIT_KINDS) & set(HISTORICAL_AUDIT_KINDS)
    assert set(AUDIT_KINDS_ALLOWED) == set(AUDIT_KINDS) | set(HISTORICAL_AUDIT_KINDS)


def test_every_migration_that_recreates_the_constraint_accepts_history():
    """A migration may not narrow the constraint: the rows it would reject cannot be deleted."""
    forties = _migration("0041_drop_authoring_agent")._audit_kinds_for_constraint()
    themes = _migration("0042_themes").KINDS_0042
    bi_ready = _migration("0044_bi_ready_sources").KINDS_0044
    for name, kinds in (("0041", forties), ("0042", themes), ("0044", bi_ready)):
        missing = [kind for kind in HISTORICAL if kind not in kinds]
        assert not missing, f"{name} would reject historical rows: {missing}"
    # And they agree on what may be written: the later one is a superset of the earlier one.
    assert set(forties) <= set(themes) <= set(bi_ready)


def test_the_constraint_in_the_database_accepts_history_and_refuses_the_unknown():
    """The rule the migration leaves behind, checked where it is enforced."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.db import get_engine

    with get_engine().begin() as c:
        c.execute(text(f'SET LOCAL search_path TO "{TEST_SCHEMA}"'))
        c.execute(text(
            "INSERT INTO audit_event (kind, detail) VALUES "
            "('assistant_run_applied', '{}'::jsonb), ('project_applied', '{}'::jsonb)"))
    assert sql("SELECT count(*) FROM audit_event") == [(2,)]
    with pytest.raises(IntegrityError):
        with get_engine().begin() as c:
            c.execute(text(f'SET LOCAL search_path TO "{TEST_SCHEMA}"'))
            c.execute(text(
                "INSERT INTO audit_event (kind, detail) VALUES ('not_a_kind', '{}'::jsonb)"))
    assert sql("SELECT count(*) FROM audit_event") == [(2,)]
