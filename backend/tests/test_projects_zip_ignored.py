"""Feature 049 US3: the pack's own files are listed as ignored, a program is still refused.

An author zips the folder they were working in — the project *and* the authoring pack's scaffolding
(043 puts them side by side on purpose). Refusing the upload teaches nothing; listing what was
skipped teaches exactly the right thing. Executable content is the exception: it stops the import.
"""
import io
import zipfile

import pytest

from app.config import get_settings
from tests.conftest import reauth, signed_in, sql

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 56
SPEC = "---\n**Tipo**: reporte\n**Status**: Approved\n"

PACK_FILES = {
    "PROMPT.md": "# Build a Bizview project with any AI\n",
    "REQUEST.md": "# Mi tablero\n",
    "README.md": "# proyecto\n",
    "request/foto.png": PNG,
    "request/notas.txt": "notas\n",
    "sources/ventas/structure.md": "# estructura\n",
    "sources/ventas/structure.json": "{}",
    ".bizview/preset/preset.yaml": "name: x\n",
    ".bizview/extension/extension.yaml": "x: 1\n",
    ".DS_Store": b"\x00\x01\x02",
    "__MACOSX/._spec.md": b"\x00\x05\x16\x07",
}


@pytest.fixture(autouse=True)
def projects(tmp_path, monkeypatch):
    path = tmp_path / "projects"
    monkeypatch.setattr(get_settings(), "projects_dir", str(path))
    return path


@pytest.fixture
def client(superuser):
    return signed_in("root@example.com")


def make_zip(entries: dict, *, top: str | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as zf:
        for name, content in entries.items():
            zf.writestr(f"{top}/{name}" if top else name,
                        content.encode() if isinstance(content, str) else content)
    return buffer.getvalue()


def post(client, data):
    return reauth(client).post("/api/projects/import", content=data,
                               headers={"Content-Type": "application/zip"})


def a_project() -> dict:
    return {"project.yaml": "name: Ventas\nslug: ventas\n",
            "specs/001-ventas/spec.md": SPEC,
            "assets/coins/BTC.png": PNG}


def test_a_project_folder_with_the_pack_still_in_it_imports(projects, client):
    r = post(client, make_zip({**a_project(), **PACK_FILES}))
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(PACK_FILES) <= set(body["ignored"])
    slug = body["project"]["slug"]
    assert (projects / slug / "specs/001-ventas/spec.md").exists()
    # Nothing from the pack reached the disk.
    for name in PACK_FILES:
        assert not (projects / slug / name).exists(), name


def test_the_same_zip_one_folder_down_still_imports(projects, client):
    """The pack's top folder is stripped, then the pack files inside it are ignored."""
    r = post(client, make_zip({**a_project(), **PACK_FILES}, top="bizview-starter"))
    assert r.status_code == 200, r.text
    assert "PROMPT.md" in r.json()["ignored"]


def test_images_outside_assets_are_ignored_but_still_checked_for_content(projects, client):
    r = post(client, make_zip({**a_project(), "docs/foto.png": b"\x7fELF\x02\x01\x01"}))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "zip_disallowed"
    assert sql("SELECT count(*) FROM project")[0][0] == 0


@pytest.mark.parametrize("name", ["build/pack.js", "tools/run.sh", "x/setup.exe",
                                 "reportes/nota.py", "dist/app.jar"])
def test_a_program_anywhere_keeps_failing_the_import(projects, client, name):
    r = post(client, make_zip({**a_project(), name: "alert(1)\n"}))
    assert r.status_code == 422
    error = r.json()["error"]
    assert error["code"] == "zip_disallowed"
    assert name in error["message"]
    assert sql("SELECT count(*) FROM project")[0][0] == 0
    assert not any((projects).glob("*")), "nothing half-imported stays behind"


def test_a_program_hidden_behind_a_text_extension_is_refused_by_its_bytes(projects, client):
    r = post(client, make_zip({**a_project(), "notas.txt": b"#!/bin/sh\nrm -rf /\n"}))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "zip_disallowed"


def test_the_import_reports_how_much_it_ignored(projects, client):
    post(client, make_zip({**a_project(), **PACK_FILES}))
    detail = sql("SELECT detail FROM audit_event WHERE kind = 'project_imported'")[0][0]
    assert detail["files"] == 2                       # project.yaml and the spec
    assert detail["images"] == 1                      # the image is counted on its own allowance
    assert detail["ignored"] == len(PACK_FILES)
