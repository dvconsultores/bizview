"""Feature 020 T077: project zip download and import."""
import io
import os
import stat
import zipfile

import pytest

from app.config import get_settings
from tests.conftest import reauth, signed_in, sql


@pytest.fixture(autouse=True)
def projects(tmp_path, monkeypatch):
    path = tmp_path / "projects"
    monkeypatch.setattr(get_settings(), "projects_dir", str(path))
    return path


@pytest.fixture
def client(superuser):
    return signed_in("root@example.com")


def make_zip(entries: dict, *, symlink: str | None = None,
             method: int = zipfile.ZIP_DEFLATED) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", method) as zf:
        for name, content in entries.items():
            info = zipfile.ZipInfo("x")
            info.filename = name        # keep unsafe names exactly as given
            info.compress_type = method
            zf.writestr(info, content.encode() if isinstance(content, str) else content)
        if symlink is not None:
            info = zipfile.ZipInfo(symlink)
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(info, b"/etc/passwd")
    return buffer.getvalue()


def post(client, data, **params):
    return reauth(client).post("/api/projects/import", content=data, params=params,
                               headers={"Content-Type": "application/zip"})


def test_round_trip(client, projects):
    slug = client.post("/api/projects", json={"name": "Ventas"}).json()["slug"]
    spec = "# A\n\n**Tipo**: reporte\n"
    assert client.put(f"/api/projects/{slug}/file",
                      json={"path": "specs/001-a/spec.md", "content": spec}).status_code == 200
    data = client.get(f"/api/projects/{slug}/export.zip").content
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    for name in ("ventas/specs/001-a/spec.md", "ventas/project.yaml", "ventas/README.md",
                 "ventas/.bizview/schemas/project.schema.json", "ventas/CLAUDE.md"):
        assert name in names, name
    assert any(n.startswith("ventas/.specify/templates/") for n in names)

    r = post(client, data, name="Ventas copia")
    assert r.status_code == 200, r.text
    body = r.json()
    new = body["project"]["slug"]
    assert new == "ventas-2"
    assert (projects / new / "specs/001-a/spec.md").read_text() == spec
    assert "slug: ventas-2" in (projects / new / "project.yaml").read_text()
    assert {"README.md", ".bizview/schemas/project.schema.json"} <= set(body["ignored"])
    assert sql("SELECT count(*) FROM audit_event WHERE kind = 'project_exported'")[0][0] == 1


@pytest.mark.parametrize("name", ["../evil.md", "/abs/project.yaml", "a\\b.md", "C:/x.md",
                                  "x/./project.yaml"])
def test_unsafe_names(client, name):
    r = post(client, make_zip({name: "x"}))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "zip_invalid"
    assert sql("SELECT count(*) FROM project")[0][0] == 0


def test_rejections(client, monkeypatch):
    for data in (make_zip({"project.yaml": "name: x\n"}, symlink="specs/001-a/spec.md"),
                 make_zip({"specs/001-a/spec.md": "a" * 2_000_000}),   # ratio bomb
                 b"hello"):
        r = post(client, data)
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "zip_invalid"
    r = signed_in("root@example.com").post(
        "/api/projects/import", content=make_zip({"project.yaml": "name: x\n"}),
        headers={"Content-Type": "application/zip"})
    assert r.status_code == 403   # step-up required
    monkeypatch.setattr(get_settings(), "project_max_mb", 1)
    r = post(client, make_zip({"specs/001-a/spec.md": os.urandom(1_500_000)},
                              method=zipfile.ZIP_STORED))
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "too_large"
    assert sql("SELECT count(*) FROM project")[0][0] == 0


def test_spec_number_gap_is_kept_and_duplicates_leave_nothing(client, projects):
    """020 T085: imported numbers keep their gaps (never reused); a duplicate number is refused
    and nothing half-imported stays behind."""
    r = post(client, make_zip({"x/project.yaml": 'name: "Hueco"\nslug: hueco\n',
                               "x/specs/003-c/spec.md": "# C\n\n**Tipo**: reporte\n"}))
    assert r.status_code == 200, r.text
    assert (projects / "hueco" / "specs" / "003-c" / "spec.md").exists()
    assert sql("SELECT spec_seq FROM project WHERE slug = 'hueco'")[0][0] == 3
    client.put("/api/projects/hueco/file", json={"path": "specs/004-d/spec.md", "content": "# D\n"})
    assert (projects / "hueco" / "specs" / "004-d").is_dir()     # the next number follows

    r = post(client, make_zip({"x/project.yaml": 'name: "Doble"\nslug: doble\n',
                               "x/specs/001-a/spec.md": "# A\n",
                               "x/specs/001-b/spec.md": "# B\n"}))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "spec_number_duplicate"
    assert sql("SELECT count(*) FROM project WHERE slug = 'doble'")[0][0] == 0
    assert not (projects / "doble").exists()


def test_export_after_a_spec_delete_imports_back(client, projects):
    """020 T085, FR-018: a downloaded project with a deleted spec (001 + 003) imports again."""
    slug = client.post("/api/projects", json={"name": "Huecos"}).json()["slug"]
    for path in ("specs/001-a/spec.md", "specs/002-b/spec.md", "specs/003-c/spec.md"):
        r = client.put(f"/api/projects/{slug}/file", json={"path": path, "content": "# X\n"})
        assert r.status_code == 200, r.text
    r = client.post(f"/api/projects/{slug}/ops", json={"ops": [{"op": "rmdir",
                                                                "path": "specs/002-b"}]})
    assert r.status_code == 200, r.text
    data = client.get(f"/api/projects/{slug}/export.zip").content
    r = post(client, data, name="Huecos copia")
    assert r.status_code == 200, r.text
    copy = r.json()["project"]["slug"]
    assert sorted(p.name for p in (projects / copy / "specs").iterdir()) == ["001-a", "003-c"]


def test_export_and_applied_version_never_carry_a_chat_image(client, projects, db, superuser):
    """Feature 024/SC-004: a chat image is outside the project folder and its export."""
    from app.assistant import attachments as chat_attachments
    from tests.test_assistant_api import _stored_session

    PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    session = _stored_session(db, superuser)
    row = chat_attachments.store(db, session.id, PNG, "boceto.png", superuser.id)
    db.commit()
    slug = sql("SELECT p.slug FROM project p JOIN assistant_session s ON s.project_id = p.id"
               " WHERE s.id = :i", i=session.id)[0][0]

    data = client.get(f"/api/projects/{slug}/export.zip").content
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert names, "the export must not be empty"
    assert not [n for n in names if row.sha256 in n or "boceto" in n or "attachment" in n]

    # The project folder is what the Git mirror copies: the file lives outside it.
    folder = projects / slug
    assert not [p for p in folder.rglob("*") if row.sha256 in p.name]
    attachment_file = get_settings().attachments_dir
    assert os.path.isdir(os.path.join(attachment_file, str(session.id)))
