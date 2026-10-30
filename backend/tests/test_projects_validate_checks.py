"""Feature 043 WS-A D4: the explicit validate action runs origin checks; file saves do not."""
import pytest

from app.config import get_settings
from tests.conftest import signed_in


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
    created = c.post("/api/projects", json={"name": "Ventas Caracas"})
    assert created.status_code in (200, 201), created.text
    slug = created.json()["slug"]
    resp = c.post(f"/api/projects/{slug}/validate")
    assert resp.status_code == 200, resp.text
    assert len(recorder) == 1


def test_save_does_not_run_origin_checks(env, superuser, recorder, monkeypatch):
    monkeypatch.setattr("app.projects.compose.validate_project",
                        lambda db, project: {"valid": True})
    c = signed_in("root@example.com")
    created = c.post("/api/projects", json={"name": "Ventas Caracas"})
    assert created.status_code in (200, 201), created.text
    slug = created.json()["slug"]
    saved = c.put(f"/api/projects/{slug}/file",
                  json={"path": "specs/001-demo/spec.md", "content": "# Demo\n"})
    assert saved.status_code == 200, saved.text
    assert recorder == []
