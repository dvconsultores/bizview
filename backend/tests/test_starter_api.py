"""Feature 057: the starter pack download and the public template (no DB writes beyond the audit).

The download is the product's front door: a non-technical administrator names a project and hands
the zip to their AI. These tests keep it honest — a rendered zip must be importable, the filename
must be the one the dialog promises, and the committed template must be what the pack renders now.
"""
import io
import zipfile

import pytest
from bizview_cli import starter as pack
from bizview_cli.validate import validate
from fastapi.testclient import TestClient

from app.projects import starter as project_starter
from tests.conftest import signed_in

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def projects(tmp_path, monkeypatch):
    from app.config import get_settings

    path = tmp_path / "projects"
    monkeypatch.setattr(get_settings(), "projects_dir", str(path))
    return path


@pytest.fixture
def client(superuser):
    return signed_in("root@example.com")


def entries(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return {name: zf.read(name) for name in zf.namelist()}


def test_download_is_a_zip_named_after_the_slug(client):
    r = client.get("/api/projects/starter", params={"name": "Ventas de prueba"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    assert r.headers["content-disposition"] == (
        'attachment; filename="bizview-starter-ventas-de-prueba.zip"')
    files = entries(r.content)
    assert "PROMPT.md" in files and "REQUEST.md" in files
    assert "CONTENIDO.md" in files and "CONTENTS.md" in files
    assert "QUE-HACE-BIZVIEW.md" in files and "WHAT-BIZVIEW-DOES.md" in files
    assert "specs/001-ventas-de-prueba/spec.md" in files
    assert "specs/002-ventas-de-prueba-reporte/spec.md" in files
    assert "reports/ventas-de-prueba/report.yaml" in files


@pytest.mark.parametrize("kind", ["integration", "direct"])
@pytest.mark.parametrize("lang", ["es", "en"])
def test_every_combination_imports_as_a_valid_project(client, kind, lang, tmp_path, monkeypatch):
    r = client.get("/api/projects/starter",
                   params={"name": "Ventas de prueba", "kind": kind, "lang": lang})
    assert r.status_code == 200, r.text
    project = tmp_path / "projects" / "ventas-de-prueba"
    for path, data in entries(r.content).items():
        if path == "bizview.yaml":
            (tmp_path / path).write_bytes(data)
        elif not path.startswith(".bizview/schemas/"):
            (project / path).parent.mkdir(parents=True, exist_ok=True)
            (project / path).write_bytes(data)
    result = validate(tmp_path)
    assert result.ok, [str(i) for i in result.issues]
    assert result.integrations or kind == "direct"


def test_a_direct_report_ships_no_integration(client):
    r = client.get("/api/projects/starter",
                   params={"name": "Ventas", "kind": "direct"})
    files = entries(r.content)
    assert not any(path.startswith("integrations/") for path in files)
    assert any(path.startswith("reports/") for path in files)


def test_the_downloaded_zip_imports_untouched_as_a_draft(client):
    """The whole promise: download it, import it, and the only problems are the fill-me markers."""
    from tests.conftest import reauth

    r = client.get("/api/projects/starter", params={"name": "Ventas de prueba"})
    assert r.status_code == 200
    imported = reauth(client).post("/api/projects/import", content=r.content,
                                   headers={"Content-Type": "application/zip"})
    assert imported.status_code == 200, imported.text
    body = imported.json()
    assert body["mode"] == "created"
    assert body["project"]["slug"] == "ventas-de-prueba"
    codes = {error["code"] for error in body["validation"]["errors"]}
    assert "schema_error" not in codes, body["validation"]["errors"]
    # The pack's own files are explained, not imported.
    assert any(path.endswith("PROMPT.md") for path in body["ignored"])


def test_the_name_is_required(client):
    assert client.get("/api/projects/starter", params={"name": "  "}).status_code == 422
    assert client.get("/api/projects/starter").status_code == 422


def test_a_lower_allowance_refuses_before_serving(client):
    from tests.conftest import reauth

    assert reauth(client).put("/api/projects/limits",
                              json={"artifact_max_files": 1}).status_code == 200
    r = client.get("/api/projects/starter", params={"name": "Ventas"})
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "artifacts_over_files"


def test_template_is_the_committed_file(client):
    committed = (ROOT / pack.TEMPLATE_NAME).read_bytes()
    r = client.get("/api/projects/starter-template")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert r.headers["content-disposition"] == (
        'attachment; filename="bizview-starter-template.zip"')
    assert r.headers["content-length"] == str(len(committed))
    assert r.content == committed


def test_the_explanations_are_the_same_in_the_zip_and_in_the_help():
    """One text, two places: what the author reads in the zip is what the help says.

    `QUE-HACE-BIZVIEW.md`/`WHAT-BIZVIEW-DOES.md` ship inside every zip and are also the help topic
    `importar-y-aplicar`; a fix in one that never reaches the other is how the guide drifted from the
    product before."""
    import re

    from app import guide

    pairs = {"es": ("QUE-HACE-BIZVIEW.md", "importar-y-aplicar"),
             "en": ("WHAT-BIZVIEW-DOES.md", "importar-y-aplicar")}
    for lang, (name, topic_id) in pairs.items():
        shipped = (ROOT / "pack" / "bizview-starter-pack" / lang / name).read_text(encoding="utf-8")
        steps = re.findall(r"((?:^[12]\. .*\n(?:   .*\n)*)+)", shipped, re.M)
        body = guide.load().bodies[(lang, topic_id)]
        assert len(steps) == 2, lang
        for block in steps:
            for line in block.rstrip("\n").split("\n"):
                assert line.strip() in body, (lang, "missing from the help:", line)


def test_committed_template_equals_the_rendered_one():
    """CI's promise: change the pack and forget the template, and this fails."""
    expected = pack.zip_bytes(pack.render(template=True, lang="es"))
    assert (ROOT / pack.TEMPLATE_NAME).read_bytes() == expected


def test_template_falls_back_to_a_render(monkeypatch):
    monkeypatch.setenv(project_starter.TEMPLATE_ENV, "/nonexistent/bizview-starter-template.zip")
    assert project_starter.template_path() is None
    result = project_starter.template()
    assert result["data"] == pack.zip_bytes(pack.render(template=True, lang="es"))


def test_only_the_superuser_downloads(superuser):
    from tests.conftest import make_user

    make_user("user@example.com", full_name="Ulises Usuario")
    c: TestClient = signed_in("user@example.com")
    assert c.get("/api/projects/starter", params={"name": "Ventas"}).status_code == 403
