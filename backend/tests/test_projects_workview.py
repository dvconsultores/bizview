"""Feature 020 T035: WorkView adapter (no database)."""
from types import SimpleNamespace

import pytest

from app.projects import workview


@pytest.fixture
def view(monkeypatch):
    monkeypatch.setattr(workview.fs, "list_files",
                        lambda slug: ({"project.yaml": (1, "x"), "specs/001-a/spec.md": (1, "y")},
                                      []))
    monkeypatch.setattr(workview.fs, "read_text", lambda slug, path: f"text of {path}")
    saved = []
    monkeypatch.setattr(workview, "_persist", lambda pid, name, value: saved.append((pid, name)))
    project = SimpleNamespace(id=3, slug="demo", name="Demo", validation=None, query_checks=None,
                              preview=None, saved=saved)
    session = SimpleNamespace(id=7, status="open", working_state={"seen": {}}, stats={})
    return workview.WorkView(project, session), project, session


def test_draft_comes_from_the_folder(view):
    v, _project, _session = view
    assert v.draft == {"files": {"project.yaml": "text of project.yaml",
                                 "specs/001-a/spec.md": "text of specs/001-a/spec.md"},
                       "summary": "Demo"}
    with pytest.raises(AttributeError):
        v.draft = {"files": {}}


def test_state_lives_on_project_and_session(view):
    v, project, session = view
    v.validation = {"valid": True}
    v.preview = {"status": "succeeded"}
    v.query_checks = {"a": 1}
    assert project.validation == {"valid": True} and project.preview["status"] == "succeeded"
    assert project.query_checks == {"a": 1}
    assert project.saved == [(3, "validation"), (3, "preview"), (3, "query_checks")]
    v.working_state = {"seen": {"project.yaml": "x"}}
    assert session.working_state == {"seen": {"project.yaml": "x"}}
    assert v.id == 7 and v.status == "open"
    assert workview.real(v) is session and workview.real(session) is session
