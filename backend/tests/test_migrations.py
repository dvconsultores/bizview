"""SC-007 / FR-031: migrations on DATABASE_URL_BI create exactly the product's tables and are
repeatable. The suite runs them in a temporary app_test_* schema; conftest asserts that the real
schema `public` is unchanged after the run."""
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import MetaData
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
              "assistant_session", "assistant_message", "assistant_preview_request",
              "share_link", "email_send", "email_delivery", "email_subscription",
              "direct_read_log", "report_rollup", "project", "project_file_revision",
              "assistant_command_run", "assistant_attachment", "google_link",
              "assistant_auto_run", "assistant_run_profile"}


def schema_tables():
    return {r[0] for r in sql("SELECT table_name FROM information_schema.tables "
                              "WHERE table_schema = :s", s=TEST_SCHEMA)}


def test_migrations_create_only_the_product_schema(database):
    assert schema_tables() == APP_TABLES
    assert outside_snapshot() == database  # public untouched, no extension installed


def test_upgrade_is_idempotent_and_reversible(database):
    command.upgrade(alembic_cfg(), "head")  # second run: no-op
    command.downgrade(alembic_cfg(), "base")
    assert schema_tables() == {"alembic_version"}
    command.upgrade(alembic_cfg(), "head")
    assert schema_tables() == APP_TABLES
    assert sql("SELECT code, status FROM dashboard") == [("ventas", "coming_soon")]
    assert outside_snapshot() == database


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


def test_downgrade_0007_removes_controls_and_converts_stopped(database):
    """Feature 013 downgrade: stopped -> failed, controls/columns/audit rows removed."""
    user = make_user("downgrade@example.com")
    sql("INSERT INTO integration_run (integration_id, kind, status, stop_requested_by, "
        "stop_requested_at) VALUES ('demo', 'incremental', 'stopped', :u, '2026-10-02T10:00:00Z')",
        u=user.id)
    sql("INSERT INTO integration_control (integration_id, paused) VALUES ('demo', true)")
    sql("INSERT INTO audit_event (kind) VALUES ('integration_paused')")

    try:
        command.downgrade(alembic_cfg(), "0007_telegram_poll_health")
        assert "integration_control" not in schema_tables()
        assert sql("SELECT status FROM integration_run WHERE integration_id = 'demo'") == [
            ("failed",)
        ]
        assert sql("SELECT count(*) FROM audit_event WHERE kind = 'integration_paused'") == [(0,)]
        stops = {r[0] for r in sql(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :s AND table_name = 'integration_run'", s=TEST_SCHEMA)}
        assert "stop_requested_at" not in stops and "stop_requested_by" not in stops
    finally:
        command.upgrade(alembic_cfg(), "head")
        assert "integration_control" in schema_tables()


def _project(slug: str) -> int:
    """Conversations belong to a project since migration 0018 (feature 020)."""
    return sql("INSERT INTO project (slug, name, origin) VALUES (:s, 'P', 'app') RETURNING id",
               s=slug)[0][0]


def test_assistant_session_defaults_and_checks(database):
    """Feature 014: a new conversation is open with no tokens used; invalid rows are refused."""
    user = make_user("assistant-defaults@example.com")
    pid = _project("test-assistant-session-defaults-and-chec")
    session_id = sql(
        "INSERT INTO assistant_session (project_id, title, created_by) "
        "VALUES (:p, 'Ventas por marca', :u) RETURNING id", u=user.id, p=pid)[0][0]
    assert sql("SELECT status, tokens_used FROM assistant_session WHERE id = :s",
               s=session_id) == [("open", 0)]

    with pytest.raises(IntegrityError):
        sql("INSERT INTO assistant_session (project_id, title, created_by, status) "
            "VALUES (:p, 'Bad status', :u, 'done')", u=user.id, p=pid)
    with pytest.raises(IntegrityError):
        sql("INSERT INTO assistant_session (project_id, title, created_by) "
            "VALUES (:p, '   ', :u)", u=user.id, p=pid)
    with pytest.raises(IntegrityError):
        sql("INSERT INTO assistant_session (project_id, title, created_by, status) "
            "VALUES (:p, 'Applied without version', :u, 'applied')", u=user.id, p=pid)
    # 0025 retired the budget: the column is gone (feature 028 revision, unlimited AI).
    assert "token_budget" not in sql(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'assistant_session'")[0]


def test_assistant_messages_cascade_with_session(database):
    """Feature 014: messages and preview requests go with their conversation; roles checked."""
    user = make_user("assistant-messages@example.com")
    pid = _project("test-assistant-messages-cascade-with-ses")
    session_id = sql(
        "INSERT INTO assistant_session (project_id, title, created_by) "
        "VALUES (:p, 'Msgs', :u) RETURNING id", u=user.id, p=pid)[0][0]
    sql("INSERT INTO assistant_message (session_id, role, content) "
        "VALUES (:s, 'user', 'hola')", s=session_id)
    sql("INSERT INTO assistant_message (session_id, role, content, tool_name, tool_payload) "
        "VALUES (:s, 'tool', 'n=1', 'list_sources', '{\"n\": 1}'::jsonb)", s=session_id)
    sql("INSERT INTO assistant_preview_request (session_id, requested_by) VALUES (:s, :u)",
        s=session_id, u=user.id)

    with pytest.raises(IntegrityError):
        sql("INSERT INTO assistant_message (session_id, role, content) "
            "VALUES (:s, 'tool', 'missing name')", s=session_id)
    with pytest.raises(IntegrityError):
        sql("INSERT INTO assistant_message (session_id, role, content) "
            "VALUES (:s, 'system', 'not allowed')", s=session_id)

    sql("DELETE FROM assistant_session WHERE id = :s", s=session_id)
    assert sql("SELECT count(*) FROM assistant_message WHERE session_id = :s",
               s=session_id) == [(0,)]
    assert sql("SELECT count(*) FROM assistant_preview_request WHERE session_id = :s",
               s=session_id) == [(0,)]


def test_downgrade_0008_removes_assistant(database):
    """Feature 014 downgrade: assistant tables and their audit rows removed."""
    user = make_user("assistant-downgrade@example.com")
    pid = _project("principal")  # the 0018 downgrade keeps only principal
    sql("INSERT INTO assistant_session (project_id, title, created_by) "
        "VALUES (:p, 'Downgrade', :u)", u=user.id, p=pid)
    sql("INSERT INTO audit_event (kind) VALUES ('assistant_session_archived')")

    assistant = {"assistant_session", "assistant_message", "assistant_preview_request"}
    try:
        command.downgrade(alembic_cfg(), "0008_integration_control")
        assert not assistant & schema_tables()
        assert sql("SELECT count(*) FROM audit_event "
                   "WHERE kind = 'assistant_session_archived'") == [(0,)]
    finally:
        command.upgrade(alembic_cfg(), "head")
        assert assistant <= schema_tables()


def test_supabase_source_kind_and_guarded_downgrade(database):
    """Feature 016: 'supabase' sources allowed; the downgrade refuses while one exists."""
    sql("INSERT INTO data_source (name, kind) VALUES ('Supabase prueba', 'supabase')")
    with pytest.raises(IntegrityError):
        sql("INSERT INTO data_source (name, kind) VALUES ('Otra', 'mysql')")
    try:
        with pytest.raises(RuntimeError, match="Supabase"):
            command.downgrade(alembic_cfg(), "0009_assistant")
        sql("DELETE FROM data_source WHERE kind = 'supabase'")
        command.downgrade(alembic_cfg(), "0009_assistant")
        with pytest.raises(IntegrityError):
            sql("INSERT INTO data_source (name, kind) VALUES ('Supabase prueba', 'supabase')")
    finally:
        command.upgrade(alembic_cfg(), "head")


def test_assistant_session_agent_columns(database):
    """Feature 017: agentic assistant columns exist with correct defaults and types."""
    user = make_user("assistant-agent@example.com")
    pid = _project("test-assistant-session-agent-columns")
    sql("INSERT INTO assistant_session (project_id, title, created_by) "
        "VALUES (:p, 'Agent', :u)", u=user.id, p=pid)
    assert sql("SELECT stats FROM assistant_session WHERE title = 'Agent'") == [({},)]
    assert sql("SELECT working_state, query_checks FROM assistant_session "
               "WHERE title = 'Agent'") == [(None, None)]

    sql("UPDATE assistant_session SET working_state = '{\"step\": 1}'::jsonb, "
        "query_checks = '{\"sql\": \"ok\"}'::jsonb WHERE title = 'Agent'")
    assert sql("SELECT working_state, query_checks FROM assistant_session "
               "WHERE title = 'Agent'") == [({"step": 1}, {"sql": "ok"})]

    sql("INSERT INTO audit_event (kind) VALUES ('assistant_budget_extended')")
    assert sql("SELECT count(*) FROM audit_event "
               "WHERE kind = 'assistant_budget_extended'") == [(1,)]


def test_downgrade_0010_guarded_by_budget_audit(database):
    """Feature 017: 0011 downgrade refuses while the new audit kind exists."""
    sql("INSERT INTO audit_event (kind) VALUES ('assistant_budget_extended')")
    try:
        with pytest.raises(RuntimeError, match="assistant_budget_extended"):
            command.downgrade(alembic_cfg(), "0010_supabase_source")
        sql("DELETE FROM audit_event WHERE kind = 'assistant_budget_extended'")
        command.downgrade(alembic_cfg(), "0010_supabase_source")
        assert sql("SELECT column_name FROM information_schema.columns "
                   "WHERE table_schema = :s AND table_name = 'assistant_session' "
                   "AND column_name IN ('working_state', 'query_checks', 'stats')",
                   s=TEST_SCHEMA) == []
        with pytest.raises(IntegrityError):
            sql("INSERT INTO audit_event (kind) VALUES ('assistant_budget_extended')")
    finally:
        command.upgrade(alembic_cfg(), "head")


def test_assistant_busy_column_and_downgrade_0011(database):
    """Feature 017: 0012 adds busy_since and downgrade removes it."""
    user = make_user("assistant-busy@example.com")
    pid = _project("principal")  # the 0018 downgrade keeps only principal
    session_id = sql(
        "INSERT INTO assistant_session (project_id, title, created_by) "
        "VALUES (:p, 'Busy claim test', :u) RETURNING id",
        u=user.id, p=pid,
    )[0][0]

    assert sql(
        "SELECT busy_since FROM assistant_session WHERE id = :i", i=session_id
    ) == [(None,)]

    sql(
        "UPDATE assistant_session SET busy_since = now() WHERE id = :i",
        i=session_id,
    )
    assert sql(
        "SELECT busy_since IS NOT NULL FROM assistant_session WHERE id = :i",
        i=session_id,
    ) == [(True,)]

    try:
        command.downgrade(alembic_cfg(), "0011_agentic_assistant")
        assert sql(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :s AND table_name = 'assistant_session' "
            "AND column_name = 'busy_since'",
            s=TEST_SCHEMA,
        ) == []
    finally:
        command.upgrade(alembic_cfg(), "head")


def test_dashboard_sharing_tables_and_checks(database):
    make_user("share-owner@example.com", role="admin")
    dashboard_id = sql("SELECT id FROM dashboard WHERE code = 'ventas'")[0][0]

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


def test_downgrade_0012_guarded_by_sharing_audit(database):
    sql("INSERT INTO audit_event (kind) VALUES ('sharing_toggled')")
    try:
        with pytest.raises(RuntimeError, match="0013"):
            command.downgrade(alembic_cfg(), "0012_assistant_busy")
        sql("DELETE FROM audit_event WHERE kind = 'sharing_toggled'")
        command.downgrade(alembic_cfg(), "0012_assistant_busy")

        for table in ("email_delivery", "email_send", "email_subscription",
                      "email_settings", "share_link"):
            count = sql(
                """
                SELECT count(*) FROM information_schema.tables
                WHERE table_schema = :schema AND table_name = :table
                """,
                schema=TEST_SCHEMA,
                table=table,
            )[0][0]
            assert count == 0

        with pytest.raises(IntegrityError):
            sql("INSERT INTO audit_event (kind) VALUES ('share_link_created')")
    finally:
        command.upgrade(alembic_cfg(), "head")


def test_0014_drops_email_settings_and_downgrade_recreates_it(database):
    assert sql(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema = :schema AND table_name = 'email_settings'",
        schema=TEST_SCHEMA,
    )[0][0] == 0

    try:
        command.downgrade(alembic_cfg(), "0013_dashboard_sharing")
        assert sql("SELECT count(*) FROM email_settings")[0][0] == 0

        sql("INSERT INTO email_settings (id) VALUES (1)")
        row = sql("SELECT enabled, sharing_enabled, security, allowed_domains "
                  "FROM email_settings")[0]
        assert row == (False, False, "starttls", [])

        with pytest.raises(IntegrityError):
            sql("INSERT INTO email_settings (id) VALUES (2)")

        with pytest.raises(IntegrityError):
            sql("UPDATE email_settings SET password_ct = decode('00ff', 'hex') WHERE id = 1")

        with pytest.raises(IntegrityError):
            sql("UPDATE email_settings SET security = 'tls' WHERE id = 1")

        sql("DELETE FROM email_settings")
        command.upgrade(alembic_cfg(), "0014_email_settings_env")
        assert sql(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = 'email_settings'",
            schema=TEST_SCHEMA,
        )[0][0] == 0
    finally:
        command.upgrade(alembic_cfg(), "head")


def test_0015_direct_reports_flag_log_and_guarded_downgrade(database):
    """Feature 019: the flag is only allowed on PostgreSQL sources; the log checks its outcome;
    the downgrade refuses while a source allows direct reports or a new audit kind exists."""
    sql("INSERT INTO data_source (name, kind) VALUES ('PG directo', 'postgresql')")
    assert sql("SELECT direct_reports FROM data_source WHERE name = 'PG directo'")[0][0] is False
    sql("UPDATE data_source SET direct_reports = true WHERE name = 'PG directo'")
    with pytest.raises(IntegrityError):
        sql("INSERT INTO data_source (name, kind, direct_reports) VALUES ('REST', 'rest', true)")
    sql("INSERT INTO direct_read_log (report_id, source, duration_ms, outcome) "
        "VALUES ('ventas', 'bi', 12, 'ok')")
    assert sql("SELECT rows, stale_served FROM direct_read_log")[0] == (0, False)
    with pytest.raises(IntegrityError):
        sql("INSERT INTO direct_read_log (report_id, source, duration_ms, outcome) "
            "VALUES ('ventas', 'bi', 12, 'raro')")
    sql("INSERT INTO audit_event (kind) VALUES ('source_direct_reports_changed')")
    try:
        with pytest.raises(RuntimeError, match="0015"):
            command.downgrade(alembic_cfg(), "0014_email_settings_env")
        sql("DELETE FROM audit_event WHERE kind = 'source_direct_reports_changed'")
        with pytest.raises(RuntimeError, match="0015"):
            command.downgrade(alembic_cfg(), "0014_email_settings_env")
        sql("UPDATE data_source SET direct_reports = false")
        command.downgrade(alembic_cfg(), "0014_email_settings_env")
        assert "direct_read_log" not in schema_tables()
        with pytest.raises(IntegrityError):
            sql("INSERT INTO audit_event (kind) VALUES ('source_direct_reports_changed')")
    finally:
        command.upgrade(alembic_cfg(), "head")
        sql("DELETE FROM data_source WHERE name = 'PG directo'")


def test_0016_report_rollup_and_run_rollups(database):
    """Feature 005 amendment: rollup state table with checked status; runs carry rollup outcomes;
    the downgrade removes both."""
    sql("INSERT INTO report_rollup (report_id, schema_name, table_name, definition_hash, status) "
        "VALUES ('ventas', 'ds_ventas', 'mv_ventas', 'h', 'ready')")
    assert sql("SELECT source_runs, columns FROM report_rollup")[0] == ({}, {})
    with pytest.raises(IntegrityError):
        sql("INSERT INTO report_rollup (report_id, schema_name, table_name, definition_hash, "
            "status) VALUES ('otro', 's', 't', 'h', 'raro')")
    assert sql("SELECT column_default FROM information_schema.columns WHERE table_schema = :s "
               "AND table_name = 'integration_run' AND column_name = 'rollups'",
               s=TEST_SCHEMA)[0][0].startswith("'{}'")
    try:
        command.downgrade(alembic_cfg(), "0015_direct_reports")
        assert "report_rollup" not in schema_tables()
        assert not sql("SELECT 1 FROM information_schema.columns WHERE table_schema = :s "
                       "AND table_name = 'integration_run' AND column_name = 'rollups'",
                       s=TEST_SCHEMA)
    finally:
        command.upgrade(alembic_cfg(), "head")
        sql("DELETE FROM report_rollup")


def test_0017_user_locale_and_run_message_key(database):
    user = make_user('locale@example.com')
    assert user.locale is None

    sql("UPDATE app_user SET locale = 'en' WHERE id = :id", id=user.id)
    rows = sql("SELECT locale FROM app_user WHERE id = :id", id=user.id)
    assert rows[0][0] == "en"

    with pytest.raises(IntegrityError):
        sql("UPDATE app_user SET locale = 'fr' WHERE id = :id", id=user.id)

    rows = sql(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = :schema AND table_name = 'integration_run' "
        "AND column_name IN ('message_key', 'message_params')",
        schema=TEST_SCHEMA,
    )
    assert {row[0] for row in rows} == {"message_key", "message_params"}

    try:
        command.downgrade(alembic_cfg(), '0016_run_transform')
        rows = sql(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = 'app_user' "
            "AND column_name = 'locale'",
            schema=TEST_SCHEMA,
        )
        assert len(rows) == 0
    finally:
        command.upgrade(alembic_cfg(), 'head')


def test_0019_command_runs_one_active_per_conversation(database):
    """Feature 021: command runs are checked, one running/waiting run per conversation, and
    revisions link to their run; the downgrade removes both."""
    user = make_user("runs@example.com")
    pid = sql("INSERT INTO project (slug, name, origin) VALUES ('p021', 'P', 'app') "
              "RETURNING id")[0][0]
    sid = sql("INSERT INTO assistant_session (title, created_by, project_id) "
              "VALUES ('t', :u, :p) RETURNING id", u=user.id, p=pid)[0][0]
    insert = ("INSERT INTO assistant_command_run (session_id, project_id, command, locale, status) "
              "VALUES (:s, :p, :c, 'es', :st)")
    sql(insert, s=sid, p=pid, c="speckit-plan", st="running")
    with pytest.raises(IntegrityError):
        sql(insert, s=sid, p=pid, c="speckit-tasks", st="waiting")
    sql(insert, s=sid, p=pid, c="speckit-tasks", st="completed")
    for bad in ({"c": "rm -rf", "st": "completed"}, {"c": "speckit-plan", "st": "raro"}):
        with pytest.raises(IntegrityError):
            sql(insert, s=sid, p=pid, **bad)
    assert sql("SELECT files, tokens, arguments FROM assistant_command_run LIMIT 1")[0] == (
        [], 0, "")
    try:
        command.downgrade(alembic_cfg(), "0018_projects")
        assert "assistant_command_run" not in schema_tables()
        assert not sql("SELECT 1 FROM information_schema.columns WHERE table_schema = :s "
                       "AND table_name = 'project_file_revision' "
                       "AND column_name = 'command_run_id'", s=TEST_SCHEMA)
    finally:
        command.upgrade(alembic_cfg(), "head")
        sql("DELETE FROM assistant_session WHERE id = :s", s=sid)
        sql("DELETE FROM project WHERE id = :p", p=pid)
