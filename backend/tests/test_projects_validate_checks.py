"""Feature 043 WS-A D4: the explicit validate action runs origin checks; file saves do not."""
import pytest

from app.config import get_settings
from tests.conftest import make_project, signed_in, sql


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    monkeypatch.setenv("BIZVIEW_TEST_HOOKS", "1")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    monkeypatch.setenv("PROJECTS_DIR", str(projects))
    get_settings.cache_clear()
    yield projects
    get_settings.cache_clear()


@pytest.fixture
def recorder(monkeypatch):
    calls = []

    def fake_recheck(db, view, settings):
        calls.append((db, view, settings))
        return []

    monkeypatch.setattr("app.projects.origin_checks.recheck_draft", fake_recheck)
    return calls


def test_validate_runs_origin_checks(env, superuser, recorder, monkeypatch):
    monkeypatch.setattr("app.projects.compose.validate_project",
                        lambda db, project: {"valid": True})
    c = signed_in("root@example.com")
    slug = make_project("Ventas Caracas")
    resp = c.post(f"/api/projects/{slug}/validate")
    assert resp.status_code == 200, resp.text
    assert len(recorder) == 1


def test_save_does_not_run_origin_checks(env, superuser, recorder, monkeypatch):
    monkeypatch.setattr("app.projects.compose.validate_project",
                        lambda db, project: {"valid": True})
    c = signed_in("root@example.com")
    slug = make_project("Ventas Caracas")
    saved = c.put(f"/api/projects/{slug}/file",
                  json={"path": "specs/001-demo/spec.md", "content": "# Demo\n"})
    assert saved.status_code == 200, saved.text
    assert recorder == []


def test_validate_stores_every_check_while_holding_no_row_lock(env, superuser, monkeypatch):
    """Every check writes `query_checks` through WorkView._persist — its own session and
    transaction — and a scan of the sources runs in between, exactly as `recheck_draft` does. The
    stored validation used to lock the project row first, and the in-memory value used to be left
    dirty for the request's session to flush, so each write waited on a lock its own request held:
    «Volver a comprobar» spun with nothing coming back (owner, 2026-11-04)."""
    from sqlalchemy import select

    from app.models import DataSource

    monkeypatch.setattr("app.projects.compose.validate_project",
                        lambda db, project: {"valid": True})

    def write_checks(db, view, settings):
        view.query_checks = {"integrations/demo/queries/a.sql": {"ok": True, "sha256": "x"}}
        db.scalars(select(DataSource)).all()          # flushes anything the session keeps dirty
        view.query_checks = {"integrations/demo/queries/a.sql": {"ok": True, "sha256": "x"},
                             "integrations/demo/queries/b.sql": {"ok": True, "sha256": "y"}}
        return []

    monkeypatch.setattr("app.projects.origin_checks.recheck_draft", write_checks)
    c = signed_in("root@example.com")
    slug = make_project("Ventas Caracas")
    resp = c.post(f"/api/projects/{slug}/validate")
    assert resp.status_code == 200, resp.text
    stored = sql("select query_checks from project where slug = :slug", slug=slug)
    assert stored[0][0] == {"integrations/demo/queries/a.sql": {"ok": True, "sha256": "x"},
                            "integrations/demo/queries/b.sql": {"ok": True, "sha256": "y"}}
