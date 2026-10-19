"""Feature 020 T028: projects API, conversations bound to projects."""
import re

import pytest

from app.ai import fake
from app.config import get_settings
from tests.conftest import signed_in, sql


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("BIZVIEW_TEST_HOOKS", "1")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path / "projects"))
    get_settings.cache_clear()
    fake.SHARED.reset()
    yield tmp_path / "projects"
    get_settings.cache_clear()


def test_create_builds_the_folder(env, superuser):
    c = signed_in("root@example.com")
    r = c.post("/api/projects", json={"name": "Ventas Caracas"})
    assert r.status_code == 201
    assert r.json()["slug"] == "ventas-caracas"
    base = env / "ventas-caracas"
    assert (base / "project.yaml").exists()
    assert (base / ".specify" / "memory" / "constitution.md").exists()
    for folder in ("specs", "integrations", "reports", "distributions"):
        assert (base / folder).is_dir()
    assert 'name: "Ventas Caracas"' in (base / "project.yaml").read_text()
    rows = sql("SELECT path, op, command FROM project_file_revision")
    assert sorted(tuple(r) for r in rows) == [
        (".specify/memory/constitution.md", "create", "create"),
        ("project.yaml", "create", "create"),
    ]
    assert sql("SELECT count(*) FROM audit_event WHERE kind = 'project_created'")[0][0] == 1


def test_slug_suggestion_and_uniqueness(env, superuser):
    c = signed_in("root@example.com")
    assert c.get("/api/projects/slug", params={"name": "Ventas Caracas"}).json()["slug"] == (
        "ventas-caracas")
    assert c.post("/api/projects", json={"name": "Ventas Caracas"}).status_code == 201
    assert c.get("/api/projects/slug", params={"name": "Ventas Caracas"}).json()["slug"] == (
        "ventas-caracas-2")
    r = c.post("/api/projects", json={"name": "Otra", "slug": "ventas-caracas"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "slug_taken"
    assert c.get("/api/projects/slug", params={"name": "Ñandú 2024"}).json()["slug"] == (
        "nandu-2024")


def test_leftover_folder_is_refused(env, superuser):
    """DB and folders live on different hosts: an old tree must not be adopted silently."""
    c = signed_in("root@example.com")
    stale = env / "artemisa"
    stale.mkdir(parents=True)
    (stale / "project.yaml").write_text("name: artemisa\n")
    (stale / "specs").mkdir()
    r = c.post("/api/projects", json={"name": "artemisa"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "folder_exists"
    assert (stale / "project.yaml").read_text() == "name: artemisa\n"     # nothing touched


def test_rename_name_vs_slug_lock(env, superuser):
    c = signed_in("root@example.com")
    slug = c.post("/api/projects", json={"name": "Uno"}).json()["slug"]
    r = c.patch(f"/api/projects/{slug}", json={"name": "Uno bis"})
    assert r.status_code == 200
    assert "Uno bis" in (env / slug / "project.yaml").read_text()
    r = c.patch(f"/api/projects/{slug}", json={"slug": "uno-nuevo"})
    assert r.status_code == 200
    assert not (env / slug).exists()
    assert (env / "uno-nuevo").exists()
    assert c.get("/api/projects/uno-nuevo").status_code == 200
    # 020 T088: every change is audited with its fields (and the slugs when it moves).
    events = sql("SELECT detail FROM audit_event WHERE kind = 'project_updated' ORDER BY id")
    assert [e.detail["fields"] for e in events] == [["name"], ["slug"]]
    assert (events[1].detail["old_slug"], events[1].detail["new_slug"]) == (slug, "uno-nuevo")
    assert c.patch("/api/projects/uno-nuevo", json={"name": "Uno bis"}).status_code == 200
    assert sql("SELECT count(*) FROM audit_event WHERE kind = 'project_updated'")[0][0] == 2
    sql("UPDATE project SET first_applied_at = now() WHERE slug = :s", s="uno-nuevo")
    r = c.patch("/api/projects/uno-nuevo", json={"slug": "otro"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "slug_locked"


def test_tree_equals_disk(env, superuser):
    c = signed_in("root@example.com")
    slug = c.post("/api/projects", json={"name": "Arbol"}).json()["slug"]
    base = env / slug
    (base / "specs" / "001-a").mkdir(parents=True, exist_ok=True)
    (base / "specs" / "001-a" / "spec.md").write_text("# A\n")
    (base / "notes.txt").write_text("ignored")
    body = c.get(f"/api/projects/{slug}/tree").json()
    assert {f["path"] for f in body["files"]} == {
        "project.yaml", ".specify/memory/constitution.md", "specs/001-a/spec.md"}
    assert "notes.txt" in body["ignored"]
    assert "specs/001-a" in body["folders"]
    rows = sql("SELECT op FROM project_file_revision WHERE path = 'specs/001-a/spec.md'")
    assert [tuple(r) for r in rows] == [("external",)]
    r = c.get(f"/api/projects/{slug}/file", params={"path": "specs/001-a/spec.md"})
    assert r.status_code == 200
    assert r.json()["content"] == "# A\n"
    r = c.get(f"/api/projects/{slug}/file", params={"path": "../x"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "path_unsafe"
    r = c.get(f"/api/projects/{slug}/file", params={"path": "specs/009-z/spec.md"})
    assert r.status_code == 404


def test_sessions_require_a_project(env, superuser):
    c = signed_in("root@example.com")
    assert c.post("/api/assistant/sessions", json={}).status_code == 422
    assert c.post("/api/assistant/sessions", json={"project": "no-existe"}).status_code == 404
    chat = c.post("/api/projects", json={"name": "Chat"}).json()["slug"]
    r = c.post("/api/assistant/sessions", json={"project": chat})
    assert r.status_code == 200
    assert r.json()["project"]["slug"] == chat
    assert r.json()["read_only"] is False
    other = c.post("/api/projects", json={"name": "Otro"}).json()["slug"]
    assert c.post("/api/assistant/sessions", json={"project": other}).status_code == 200
    r = c.get("/api/assistant/sessions", params={"project": chat})
    assert len(r.json()["sessions"]) == 1


def test_read_only_session_refuses_messages(env, superuser):
    c = signed_in("root@example.com")
    slug = c.post("/api/projects", json={"name": "RO"}).json()["slug"]
    session_id = c.post("/api/assistant/sessions", json={"project": slug}).json()["id"]
    sql("UPDATE assistant_session SET read_only = true WHERE id = :i", i=session_id)
    r = c.post(f"/api/assistant/sessions/{session_id}/messages", json={"text": "hola"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "read_only"
    assert fake.SHARED.payloads() == []


def test_current_spec_must_exist(env, superuser):
    c = signed_in("root@example.com")
    slug = c.post("/api/projects", json={"name": "SpecTest"}).json()["slug"]
    session_id = c.post("/api/assistant/sessions", json={"project": slug}).json()["id"]
    url = f"/api/assistant/sessions/{session_id}"
    assert c.patch(url, json={"current_spec": "001-a"}).status_code == 422
    (env / slug / "specs" / "001-a").mkdir(parents=True, exist_ok=True)
    r = c.patch(url, json={"current_spec": "001-a"})
    assert r.status_code == 200
    assert r.json()["current_spec"] == "001-a"
    r = c.patch(url, json={"current_spec": ""})
    assert r.status_code == 200
    assert r.json()["current_spec"] is None


def test_proposal_without_provider(env, superuser):
    c = signed_in("root@example.com")
    r = c.post("/api/assistant/project-proposal",
               json={"text": "Quiero un reporte de ventas por sucursal"})
    assert r.status_code == 200
    assert r.json()["name"]
    assert re.match(r"^[a-z][a-z0-9-]{1,49}$", r.json()["slug"])
    assert fake.SHARED.payloads() == []


def test_list_shows_artifacts_applied_and_problems(env, superuser):
    """020 T084, plan §4: folder artifacts, applied ones and the last validation's problems."""
    c = signed_in("root@example.com")
    slug = c.post("/api/projects", json={"name": "Lista"}).json()["slug"]
    for path in ("integrations/carga/integration.yaml", "reports/ventas/report.yaml",
                 "distributions/semanal.yaml"):
        r = c.put(f"/api/projects/{slug}/file", json={"path": path, "content": "id: x\n"})
        assert r.status_code == 200, r.text
    item = next(p for p in c.get("/api/projects").json()["projects"] if p["slug"] == slug)
    assert item["artifacts"] == {"integrations": ["carga"], "reports": ["ventas"],
                                 "distributions": ["semanal"]}
    assert item["applied"] == {"integrations": [], "reports": [], "distributions": []}
    assert isinstance(item["problems"], int) and item["problems"] > 0   # stored on save


def test_projects_folder_state_is_reported(env, superuser, tmp_path, monkeypatch):
    """020 T090: the Projects page learns that the folder cannot be written before a create."""
    from app.projects import fs

    c = signed_in("root@example.com")
    assert c.get("/api/projects").json()["folder_writable"] is True
    with monkeypatch.context() as m:
        m.setattr(fs, "check_dir", lambda: False)
        assert c.get("/api/projects").json()["folder_writable"] is False
    blocker = tmp_path / "bloqueo"
    blocker.write_text("no soy una carpeta")
    monkeypatch.setattr(get_settings(), "projects_dir", str(blocker / "projects"))
    assert fs.check_dir() is False                  # a file where the folder should be
