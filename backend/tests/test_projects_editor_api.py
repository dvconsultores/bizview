"""Feature 020 T049: editor API (save, ops, changes)."""
import pytest

from app.config import get_settings
from app.projects import history
from tests.conftest import signed_in


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECTS_DIR", str(tmp_path / "projects"))
    get_settings.cache_clear()
    yield tmp_path / "projects"
    get_settings.cache_clear()


@pytest.fixture
def client(superuser):
    c = signed_in("root@example.com")
    slug = c.post("/api/projects", json={"name": "Demo"}).json()["slug"]
    return c, slug


def test_save_returns_validation(client, env):
    c, slug = client
    content = "# A\n\n**Tipo**: reporte\n"
    r = c.put(f"/api/projects/{slug}/file", json={"path": "specs/001-a/spec.md",
                                                   "content": content})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "valid" in body["validation"]
    assert "ready" in body["readiness"]
    assert (env / slug / "specs/001-a/spec.md").read_text() == content
    assert body["file"]["sha256"] == history.sha(content)


def test_stale_save_and_force(client):
    c, slug = client
    url, path = f"/api/projects/{slug}/file", "specs/001-a/spec.md"
    r = c.put(url, json={"path": path, "content": "v1"})
    assert r.status_code == 200, r.text
    sha1 = r.json()["file"]["sha256"]
    assert c.put(url, json={"path": path, "content": "v2", "base_sha256": sha1}).status_code == 200
    r = c.put(url, json={"path": path, "content": "v3", "base_sha256": sha1})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "file_changed"
    r = c.put(url, json={"path": path, "content": "v3", "base_sha256": sha1, "force": True})
    assert r.status_code == 200


def test_ops_allowed_patterns(client, env):
    c, slug = client
    url = f"/api/projects/{slug}/ops"
    r = c.post(url, json={"ops": [{"op": "mkdir", "path": "specs/001-a"}]})
    assert r.status_code == 200, r.text
    assert (env / slug / "specs/001-a").is_dir()
    base = history.sha((env / slug / "project.yaml").read_text())
    r = c.post(url, json={"ops": [{"op": "rename", "from": "project.yaml", "to": "notes.txt",
                                   "base_sha256": base}]})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "path_not_allowed"
    assert "project.yaml" in r.json()["error"]["message"]
    assert c.post(url, json={"ops": [{"op": "write", "path": "x"}]}).status_code == 422


def test_changes_feed_order(client):
    c, slug = client
    url = f"/api/projects/{slug}/changes"
    after = c.get(url).json()["latest"]
    for path in ("specs/001-a/spec.md", "specs/001-a/plan.md"):
        assert c.put(f"/api/projects/{slug}/file",
                     json={"path": path, "content": "x"}).status_code == 200
    items = c.get(url, params={"after": after}).json()["items"]
    assert [i["path"] for i in items] == ["specs/001-a/spec.md", "specs/001-a/plan.md"]
    ids = [i["id"] for i in items]
    assert ids == sorted(set(ids))
    assert all(i["actor"] == "user" and i["command"] == "edit" for i in items)
