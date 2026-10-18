"""Tests for schema-scoped advisory lock keys."""

import types

from app import db as app_db
from app.assistant import preview
from app.config import get_settings
from app.db import lock_key
from app.engine import runner


def test_keys_differ_per_schema(monkeypatch):
    monkeypatch.setattr(
        app_db,
        "get_settings",
        lambda: types.SimpleNamespace(db_schema="app_test_aaaa"),
    )
    key_aaaa = lock_key("integration", "x")
    assert key_aaaa == "bizview:app_test_aaaa:integration:x"

    monkeypatch.setattr(
        app_db,
        "get_settings",
        lambda: types.SimpleNamespace(db_schema="app_test_bbbb"),
    )
    key_bbbb = lock_key("integration", "x")
    assert key_bbbb != key_aaaa

    monkeypatch.setattr(
        app_db,
        "get_settings",
        lambda: types.SimpleNamespace(db_schema="public"),
    )
    assert lock_key("integration", "x") == "bizview:public:integration:x"


def test_runner_and_preview_keys_include_schema():
    schema = get_settings().db_schema

    assert runner._lock_key("ventas") == f"bizview:{schema}:integration:ventas"
    assert preview.preview_lock_key(7) == f"bizview:{schema}:assistant-preview:7"
    assert schema in lock_key("preview", 7)
    assert lock_key("workspace") == f"bizview:{schema}:workspace"


def test_runner_lock_key_scoped_via_monkeypatch(monkeypatch):
    monkeypatch.setattr(
        app_db,
        "get_settings",
        lambda: types.SimpleNamespace(db_schema="app_test_zzzz"),
    )

    assert runner._lock_key("a") == "bizview:app_test_zzzz:integration:a"
    assert preview.preview_lock_key(1) == "bizview:app_test_zzzz:assistant-preview:1"
