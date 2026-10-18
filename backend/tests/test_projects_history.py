"""Feature 020 T068: history, diff, restore and spec timeline."""
import pytest

from app.assistant import service as assistant
from app.config import get_settings
from app.models import AppUser
from app.projects import fs, history
from app.projects import service as project_service
from app.services import audit
from tests.conftest import signed_in


@pytest.fixture(autouse=True)
def projects(tmp_path, monkeypatch):
    path = tmp_path / "projects"
    monkeypatch.setattr(get_settings(), "projects_dir", str(path))
    return path


@pytest.fixture
def project(db, superuser):
    p = project_service.create(db, db.get(AppUser, superuser.id), "Demo")
    db.commit()
    return p


def w(path, content, base=None):
    return {"op": "write", "path": path, "content": content, "base_sha256": base, "force": False}


def by(kind="user", command="edit", user_id=None, session_id=None):
    return {"kind": kind, "user_id": user_id, "session_id": session_id, "command": command}


def groups(db, project, **kw):
    return [i for i in history.list_revisions(db, project.id, **kw)["items"] if "files" in i]


def test_groups_order_and_actors(db, project, projects, superuser):
    fs.apply_ops(project.id, [w("specs/001-a/spec.md", "# A\n"), w("specs/001-a/plan.md", "p\n")],
                 by(user_id=superuser.id))
    fs.apply_ops(project.id, [w("specs/001-a/tasks.md", "- [ ] T1\n")],
                 by("agent", "/speckit-tasks"))
    (projects / "demo" / "specs/001-a/plan.md").write_text("p2\n")
    history.sync_external(db, project)
    db.commit()
    audit.record(db, "project_applied", actor_id=superuser.id, ip=None,
                 detail={"project_id": project.id, "project": "demo", "version": 7})
    db.commit()

    items = history.list_revisions(db, project.id)["items"]
    assert items[0]["event"] == "project_applied" and items[0]["version"] == 7
    found = groups(db, project)
    assert [(g["actor"], g["command"]) for g in found[:3]] == [
        ("external", "external"), ("agent", "/speckit-tasks"), ("user", "edit")]
    assert sorted(f["path"] for f in found[2]["files"]) == ["specs/001-a/plan.md",
                                                          "specs/001-a/spec.md"]
    assert found[2]["actor_name"] == "Super Usuario"
    assert [g["command"] for g in groups(db, project, path="specs/001-a/plan.md")] == [
        "external", "edit"]
    assert all(f["path"].startswith("specs/001-a/")
               for g in groups(db, project, spec="001-a") for f in g["files"])


def test_diff_hunks():
    a = "".join(f"l{i}\n" for i in range(1, 21))
    b = a.replace("l5\n", "cinco\n") + "l21\n"
    hunks = history.diff(a, b)["hunks"]
    assert len(hunks) == 2
    assert hunks[0]["a_start"] == 2
    assert [(x["t"], x["text"]) for x in hunks[0]["lines"]] == [
        (" ", "l2"), (" ", "l3"), (" ", "l4"), ("-", "l5"), ("+", "cinco"), (" ", "l6"),
        (" ", "l7"), (" ", "l8")]
    assert hunks[1]["lines"][-1] == {"t": "+", "text": "l21"}
    assert history.diff(None, "x\n")["hunks"][0]["lines"] == [{"t": "+", "text": "x"}]
    big = history.diff("", "".join(f"{i}\n" for i in range(20)), cap=5)
    assert big["truncated"] is True
    assert sum(len(h["lines"]) for h in big["hunks"]) == 5


def test_restore_creates_new_revision(db, project, projects):
    first = fs.apply_ops(project.id, [w("specs/001-a/spec.md", "v1\n")], by())[0]
    fs.apply_ops(project.id, [w("specs/001-a/spec.md", "v2\n", history.sha("v1\n"))], by())
    history.restore(db, project, first["revision_id"], history.sha("v2\n"), by())
    assert (projects / "demo" / "specs/001-a/spec.md").read_text() == "v1\n"
    rev = history.latest(db, project.id, "specs/001-a/spec.md")
    assert (rev.op, rev.restored_from, rev.command) == ("restore", first["revision_id"],
                                                        "restore")
    with pytest.raises(fs.FileChanged):
        history.restore(db, project, first["revision_id"], history.sha("v2\n"), by())


def test_history_api_and_timeline(db, project, superuser):
    session = assistant.create_session(db, db.get(AppUser, superuser.id), project_id=project.id)
    db.commit()
    fs.apply_ops(project.id, [w("specs/001-a/spec.md", "# A\n\n**Tipo**: reporte\n")],
                 by("agent", "/speckit-specify", session_id=session.id))
    fs.apply_ops(project.id, [w("specs/001-a/plan.md", "p\n"), w("specs/001-a/tasks.md",
                                                                  "- [x] T1\n")], by())
    c = signed_in("root@example.com")
    body = c.get("/api/projects/demo/specs/001-a/timeline").json()
    assert [s["stage"] for s in body["stages"]] == [
        "especificada", "planificada", "tareas", "implementada"]
    assert body["conversations"] == [{"id": session.id, "title": session.title}]
    assert c.get("/api/projects/demo/specs/bad/timeline").status_code == 404

    items = c.get("/api/projects/demo/history").json()["items"]
    rid = next(f["id"] for g in items for f in g["files"] if f["path"] == "specs/001-a/plan.md")
    assert c.get(f"/api/projects/demo/history/{rid}").json()["content"] == "p\n"
    fs.apply_ops(project.id, [w("specs/001-a/plan.md", "p2\n", history.sha("p\n"))], by())
    lines = c.get("/api/projects/demo/diff", params={"from": rid}).json()["hunks"][0]["lines"]
    assert [(x["t"], x["text"]) for x in lines] == [("-", "p"), ("+", "p2")]
    r = c.post(f"/api/projects/demo/history/{rid}/restore",
               json={"base_sha256": history.sha("p2\n")})
    assert r.status_code == 200, r.text
    assert "validation" in r.json()
