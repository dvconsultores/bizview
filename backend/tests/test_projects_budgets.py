"""Feature 049: the two import allowances, resolved per installation and enforced by the server.

The failure this fixes, in the owner's words: a project with 483 logos and a few dozen artifacts was
refused with "el proyecto supera el límite (20 MB o 400 archivos)" — a message about a budget the
author could not act on, because the images were being charged to the artifacts' allowance.
"""
import io
import zipfile

import pytest

from app.config import get_settings
from app.projects import budgets as project_budgets
from tests.conftest import reauth, signed_in, sql

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 56


@pytest.fixture
def client(superuser):
    return signed_in("root@example.com")


def make_zip(entries: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as zf:
        for name, content in entries.items():
            zf.writestr(name, content.encode() if isinstance(content, str) else content)
    return buffer.getvalue()


def project_entries(images: int = 0, artifacts: int = 2) -> dict:
    """A minimal valid project with `artifacts` text files and `images` pictures."""
    entries = {"project.yaml": "name: Logos\nslug: logos\n"}
    for i in range(1, artifacts):
        entries[f"specs/{i:03d}-x/spec.md"] = "---\n**Tipo**: reporte\n**Status**: Approved\n"
    for i in range(images):
        entries[f"assets/coins/C{i}.png"] = PNG
    return entries


def post(client, data, **params):
    return reauth(client).post("/api/projects/import", content=data, params=params,
                               headers={"Content-Type": "application/zip"})


# --- the reporting defect ------------------------------------------------------------------------

def test_a_project_with_483_logos_imports(client, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))
    r = post(client, make_zip(project_entries(images=483, artifacts=40)))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["budgets"]["assets"]["files"] == 483
    assert body["budgets"]["artifacts"]["files"] == 40
    slug = body["project"]["slug"]
    stored = list((tmp_path / "projects" / slug / "assets" / "coins").iterdir())
    assert len(stored) == 483


def test_the_import_reports_the_budgets_it_measured(client, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))
    body = post(client, make_zip(project_entries(images=3))).json()
    assert body["budgets"]["assets"] == {"name": "assets", "max_files": 2000, "max_kb": 300,
                                         "max_mb": 25, "label": "assets/",
                                         "files": 3, "bytes": 3 * len(PNG), "over": []}
    assert body["budgets"]["artifacts"]["files"] == 2
    assert body["budgets"]["artifacts"]["over"] == []


# --- each refusal names one allowance -----------------------------------------------------------

def test_too_many_images_names_the_images(client, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))
    r = post(client, make_zip(project_entries(images=2001)))
    assert r.status_code == 422
    error = r.json()["error"]
    assert error["code"] == "assets_over_files"
    assert "2001" in error["message"] and "2000" in error["message"]
    assert "assets/" in error["message"]
    assert "artefact" not in error["message"]        # never a combined figure
    assert sql("SELECT count(*) FROM project")[0][0] == 0


def test_too_many_artifacts_names_the_artifacts(client, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))
    r = post(client, make_zip(project_entries(artifacts=401)))
    assert r.status_code == 422
    error = r.json()["error"]
    assert error["code"] == "artifacts_over_files"
    assert "401" in error["message"] and "400" in error["message"]
    assert "specs/" in error["message"]
    assert "imágenes" not in error["message"]


def test_images_over_their_total_name_the_images(client, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))
    monkeypatch.setattr(get_settings(), "project_asset_max_mb", 1)   # 1 MB of images is legal
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (290 * 1024)               # under the 300 KB per image
    r = post(client, make_zip({**project_entries(), **{f"assets/{i}.png": big for i in range(6)}}))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "assets_over_bytes"
    assert "assets/" in r.json()["error"]["message"]


def test_one_image_over_its_own_limit_names_the_file(client, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))
    r = post(client, make_zip({**project_entries(), "assets/BTC.png": b"\x89PNG\r\n\x1a\n"
                               + b"\x00" * (420 * 1024)}))
    assert r.status_code == 422
    error = r.json()["error"]
    assert error["code"] == "assets_file_too_large"
    assert "assets/BTC.png" in error["message"] and "300" in error["message"]


def test_a_zip_over_the_sum_of_both_allowances_is_refused_for_its_size(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "project_asset_max_mb", 1)
    monkeypatch.setattr(get_settings(), "project_max_mb", 1)
    payload = make_zip({**project_entries(), "assets/relleno.bin": b"\x00" * (3 * 1024 * 1024)})
    r = post(client, payload)
    assert r.status_code in (413, 422)
    assert r.json()["error"]["code"] in ("too_large", "zip_invalid")


# --- the settings chain --------------------------------------------------------------------------

def test_with_no_row_the_deployment_defaults_apply(client):
    assert client.get("/api/projects/limits").status_code == 200
    body = client.get("/api/projects/limits").json()
    assert body["artifacts"]["max_files"] == get_settings().project_max_files
    assert body["assets"]["max_files"] == get_settings().project_asset_max_files
    assert body["zip_max_mb"] == (get_settings().project_max_mb
                                  + get_settings().project_asset_max_mb)
    assert body["stored"] == {column: None for column in project_budgets.FIELDS}


def test_an_operators_environment_value_survives_an_untouched_row(client, monkeypatch):
    """A NULL column means "inherit", so raising a limit in `.env` still works after 0047."""
    monkeypatch.setattr(get_settings(), "project_max_mb", 33)
    assert client.get("/api/projects/limits").json()["artifacts"]["max_mb"] == 33


def test_a_stored_override_wins_over_the_environment(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "project_max_mb", 33)
    r = reauth(client).put("/api/projects/limits", json={"artifact_max_mb": 12})
    assert r.status_code == 200, r.text
    assert r.json()["artifacts"]["max_mb"] == 12
    assert r.json()["stored"]["artifact_max_mb"] == 12
    assert client.get("/api/projects/limits").json()["artifacts"]["max_mb"] == 12


def test_clearing_an_override_goes_back_to_the_default(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "project_max_mb", 33)
    reauth(client).put("/api/projects/limits", json={"artifact_max_mb": 12})
    r = reauth(client).put("/api/projects/limits", json={"artifact_max_mb": None})
    assert r.json()["artifacts"]["max_mb"] == 33
    assert r.json()["stored"]["artifact_max_mb"] is None


def test_the_change_is_audited(client):
    reauth(client).put("/api/projects/limits", json={"asset_max_files": 5000})
    row = sql("SELECT detail FROM audit_event WHERE kind = 'project_limits_changed'")[0][0]
    assert row["after"]["asset_max_files"] == 5000
    assert row["before"]["asset_max_files"] is None


def test_a_per_file_limit_above_the_total_is_a_field_error(client):
    r = reauth(client).put("/api/projects/limits",
                           json={"asset_max_kb": 4000, "asset_max_mb": 1})
    assert r.status_code == 422
    assert r.json()["error"]["fields"] == {"asset_max_kb": "greater_than_total"}


def test_a_limit_cannot_be_zero_or_negative(client):
    assert reauth(client).put("/api/projects/limits",
                              json={"artifact_max_files": 0}).status_code == 422
    assert reauth(client).put("/api/projects/limits",
                              json={"artifact_max_files": -5}).status_code == 422


def test_a_raised_limit_lets_the_import_through(client, tmp_path, monkeypatch):
    """The whole point of an editable limit: an installation that ships more logos can say so.

    The default is lowered here rather than importing thousands of images: what is under test is
    the resolution (stored row beats the deployment default) and its effect, not throughput."""
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))
    monkeypatch.setattr(get_settings(), "project_asset_max_files", 5)
    assert post(client, make_zip(project_entries(images=8))).json()["error"]["code"] == \
        "assets_over_files"
    reauth(client).put("/api/projects/limits", json={"asset_max_files": 20})
    r = post(client, make_zip(project_entries(images=8)))
    assert r.status_code == 200, r.text
    assert r.json()["budgets"]["assets"]["files"] == 8
    assert r.json()["budgets"]["assets"]["max_files"] == 20


def test_a_non_superuser_cannot_read_or_change_the_limits(user):
    c = signed_in(user.email)
    assert c.get("/api/projects/limits").status_code == 403
    assert reauth(c).put("/api/projects/limits", json={"asset_max_files": 10}).status_code == 403
