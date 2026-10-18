"""Feature 020 T020: project folders, safe paths and revisions."""
import os

import pytest

from app.config import get_settings
from app.models import Project
from app.projects import fs, history
from tests.conftest import sql

ACTOR = {"kind": "user", "user_id": None, "session_id": None, "command": "edit"}


def w(path: str, content: str, base: str | None = None, force: bool = False) -> dict:
    return {"op": "write", "path": path, "content": content, "base_sha256": base, "force": force}


def count(path: str, op: str | None = None) -> int:
    if op is None:
        return sql("SELECT count(*) FROM project_file_revision WHERE path = :p", p=path)[0][0]
    return sql("SELECT count(*) FROM project_file_revision WHERE path = :p AND op = :o",
               p=path, o=op)[0][0]


@pytest.fixture
def projects(tmp_path, monkeypatch):
    path = tmp_path / "projects"
    monkeypatch.setattr(get_settings(), "projects_dir", str(path))
    return path


@pytest.fixture
def project(db, projects):
    proj = Project(slug="demo", name="Demo")
    db.add(proj)
    db.commit()
    return proj


def test_path_safety(projects):
    for rel in ("../x", "/etc/passwd", "specs\\a", "specs/../../a.md", ".git/config",
                "specs/001-x/\x00.md"):
        with pytest.raises(fs.ProjectPathError) as exc:
            fs.resolve("demo", rel)
        assert exc.value.code == "path_unsafe", rel
    with pytest.raises(fs.ProjectPathError) as exc:
        fs.resolve("demo", "notes.txt")
    assert exc.value.code == "path_not_allowed"
    assert "project.yaml" in str(exc.value)


def test_symlinks_refused(projects):
    root = projects / "demo"
    root.mkdir(parents=True)
    os.symlink("/etc", root / "integrations")
    with pytest.raises(fs.ProjectPathError) as exc:
        fs.resolve("demo", "integrations/abc/integration.yaml")
    assert exc.value.code == "path_unsafe"
    os.symlink(root, projects / "evil")
    with pytest.raises(fs.ProjectPathError) as exc:
        fs.resolve("evil", "project.yaml")
    assert exc.value.code == "path_unsafe"


def test_write_creates_file_and_revision(project, projects):
    content = "name: Demo\nslug: demo\n"
    result = fs.apply_ops(project.id, [w("project.yaml", content)], ACTOR)
    assert result[0]["sha256"] == history.sha(content)
    assert (projects / "demo" / "project.yaml").read_text() == content
    rows = sql("SELECT op, path, actor_kind, command FROM project_file_revision")
    assert [tuple(r) for r in rows] == [("create", "project.yaml", "user", "edit")]


def test_stale_base_refused_and_force_wins(project, projects):
    v1, v2, v3 = (f"name: Demo {n}\nslug: demo\n" for n in (1, 2, 3))
    sha1 = fs.apply_ops(project.id, [w("project.yaml", v1)], ACTOR)[0]["sha256"]
    fs.apply_ops(project.id, [w("project.yaml", v2, sha1)], ACTOR)
    with pytest.raises(fs.FileChanged) as exc:
        fs.apply_ops(project.id, [w("project.yaml", v3, sha1)], ACTOR)
    assert exc.value.code == "file_changed"
    assert exc.value.current["revision_id"] is not None
    assert (projects / "demo" / "project.yaml").read_text() == v2
    fs.apply_ops(project.id, [w("project.yaml", v3, sha1, force=True)], ACTOR)
    assert (projects / "demo" / "project.yaml").read_text() == v3
    assert count("project.yaml") == 3


def test_spec_numbering(project, projects):
    with pytest.raises(fs.ProjectPathError) as exc:
        fs.apply_ops(project.id, [w("specs/002-b/spec.md", "b")], ACTOR)
    assert exc.value.code == "spec_number"
    fs.apply_ops(project.id, [w("specs/001-a/spec.md", "a")], ACTOR)
    fs.apply_ops(project.id, [w("specs/002-b/spec.md", "b")], ACTOR)
    assert sql("SELECT spec_seq FROM project WHERE id = :i", i=project.id)[0][0] == 2


def test_limits(project, projects, monkeypatch):
    monkeypatch.setattr(get_settings(), "project_max_mb", 1)
    with pytest.raises(fs.ProjectPathError) as exc:
        fs.apply_ops(project.id, [w("specs/001-a/spec.md", "a" * (600 * 1024))], ACTOR)
    assert exc.value.code == "too_large"
    chunk = "a" * (400 * 1024)     # three of them exceed 1 MiB, each is under 512 KB
    fs.apply_ops(project.id, [w("specs/001-a/spec.md", chunk), w("specs/001-a/plan.md", chunk)],
                 ACTOR)
    with pytest.raises(fs.ProjectPathError) as exc:
        fs.apply_ops(project.id, [w("specs/001-a/tasks.md", chunk)], ACTOR)
    assert exc.value.code == "project_too_large"
    assert count("specs/001-a/tasks.md") == 0


def test_failure_after_replace_restores_bytes(project, projects, monkeypatch):
    v1 = "name: Demo\nslug: demo\n"
    fs.apply_ops(project.id, [w("project.yaml", v1)], ACTOR)

    def boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr("app.projects.history.record", boom)
    with pytest.raises(RuntimeError):
        fs.apply_ops(project.id, [w("project.yaml", "name: Otro\nslug: demo\n",
                                    history.sha(v1))], ACTOR)
    assert (projects / "demo" / "project.yaml").read_text() == v1
    assert count("project.yaml") == 1


def test_external_change_recorded(project, projects):
    fs.apply_ops(project.id, [w("project.yaml", "name: Demo\nslug: demo\n")], ACTOR)
    (projects / "demo" / "project.yaml").write_text("name: Otro\nslug: demo\n")
    fs.apply_ops(project.id, [w("specs/001-a/spec.md", "x")], ACTOR)
    rows = sql("SELECT op FROM project_file_revision WHERE path = 'project.yaml' ORDER BY id")
    assert [tuple(r) for r in rows] == [("create",), ("external",)]


def test_rename_and_rmdir(project, projects):
    spec, plan = "spec content", "plan content"
    fs.apply_ops(project.id, [w("specs/001-a/spec.md", spec), w("specs/001-a/plan.md", plan)],
                 ACTOR)
    fs.apply_ops(project.id, [{"op": "rename", "from": "specs/001-a/spec.md",
                               "to": "specs/001-a/research.md",
                               "base_sha256": history.sha(spec)}], ACTOR)
    root = projects / "demo"
    files = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    assert files == {"specs/001-a/plan.md", "specs/001-a/research.md"}
    assert count("specs/001-a/research.md", "rename") == 1
    fs.apply_ops(project.id, [{"op": "rmdir", "path": "specs/001-a"}], ACTOR)
    assert not (root / "specs" / "001-a").exists()
    assert count("specs/001-a/plan.md", "delete") == 1
    assert count("specs/001-a/research.md", "delete") == 1
