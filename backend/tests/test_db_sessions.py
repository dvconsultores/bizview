"""Request sessions against a remote database: reads skip BEGIN/COMMIT, writing GETs do not."""
from app.db import TRANSACTIONAL_GETS


def test_writing_get_routes_stay_transactional():
    assert TRANSACTIONAL_GETS.match("/api/auth/telegram/status")
    assert TRANSACTIONAL_GETS.match("/api/sources/Origen%20ERP/describe")
    for path in ("/api/me", "/api/config", "/api/reports/ventas/data", "/api/sources/x",
                 "/api/auth/telegram/status/x"):
        assert not TRANSACTIONAL_GETS.match(path), path


def test_active_version_for_reads_is_kept_briefly_and_cleared_on_apply(monkeypatch):
    from types import SimpleNamespace

    from app.config import get_settings
    from app.workspace import service

    calls = []
    versions = iter([SimpleNamespace(id=1, artifacts={"reports": {}}, checksum="a"),
                     SimpleNamespace(id=2, artifacts={"reports": {}}, checksum="b")])

    def fake_active(_db):
        calls.append(1)
        return next(versions)

    monkeypatch.setattr(service, "active", fake_active)
    monkeypatch.setattr(get_settings(), "active_version_cache_seconds", 5.0)
    service.forget_active_version()
    try:
        assert service.active_for_reads(None).id == 1
        assert service.active_for_reads(None).id == 1      # from memory: no second query
        assert len(calls) == 1
        service.forget_active_version()                      # what apply/rollback do
        assert service.active_for_reads(None).id == 2
        assert len(calls) == 2
    finally:
        service.forget_active_version()
