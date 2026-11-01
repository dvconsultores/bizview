"""Feature 047 (US5): a project may bring its themes, and they enter the installation's library.

Every answer is explicit — imported, replaced, renamed or skipped, or refused with the problems that
kept it out — and the project's own copy always travels with it, so an export returns what came in.
"""
import io
import json
import zipfile
from pathlib import Path

import pytest
import yaml

from app.config import get_settings
from tests.conftest import reauth, signed_in, sql

THEMES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "theme" / "themes"


@pytest.fixture(autouse=True)
def projects(tmp_path, monkeypatch):
    path = tmp_path / "projects"
    monkeypatch.setattr(get_settings(), "projects_dir", str(path))
    return path


@pytest.fixture
def client(superuser):
    return signed_in("root@example.com")


def authored(theme_id: str = "acme-azul", **changes) -> dict:
    data = json.loads((THEMES / "impacto.json").read_text(encoding="utf-8"))
    data["id"], data["name"], data["name_en"] = theme_id, "Acme · azul", "Acme · blue"
    data.update(changes)
    return data


# The smallest report the schema accepts (a direct one, so no integration is needed), so the only
# problem left in most of these tests is the theme it names.
REPORT = (
    "id: ventas\n"
    "spec: specs/001-x/\n"
    "title: Ventas\n"
    "date: v.fecha\n"
    "direct:\n"
    "  source: bi\n"
    "  tables:\n"
    "    v:\n"
    "      table: public.bi_ventas\n"
    "      columns:\n"
    "        fecha: {{type: date}}\n"
    "        importe: {{type: numeric}}\n"
    "metrics:\n"
    "  total:\n"
    "    label: Total\n"
    "    sql: sum(v.importe)\n"
    "views:\n"
    "  - id: kpis\n"
    "    type: kpis\n"
    "    metrics: [total]\n"
    "layout:\n  theme:\n    id: {theme}\n    mode: dark\n"
)


def bundle(theme: dict | None = None, *, theme_id: str = "acme-azul",
           report_theme: str | None = None, extra: dict | None = None) -> bytes:
    entries = {
        "project.yaml": "name: Con temas\nslug: con-temas\n",
        "specs/001-x/spec.md": (
            "# X\n\n**Tipo**: reporte\n**Modo**: directo\n**Status**: Approved\n"
        ),
        "specs/001-x/plan.md": "# Plan\n",
        "specs/001-x/tasks.md": "# Tasks\n",
        "reports/ventas/report.yaml": REPORT.format(theme=report_theme or theme_id),
    }
    if theme is not None:
        entries[f"themes/{theme_id}.yaml"] = yaml.safe_dump(theme, sort_keys=False)
    entries.update(extra or {})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buffer.getvalue()


def post(client, data, **params):
    return reauth(client).post("/api/projects/import", content=data, params=params,
                               headers={"Content-Type": "application/zip"})


def library(client) -> dict[str, dict]:
    body = client.get("/api/admin/themes").json()
    return {row["id"]: row for row in body["themes"]}


def test_a_theme_inside_the_zip_enters_the_library_with_the_project_as_origin(client):
    r = post(client, bundle(authored()))
    assert r.status_code == 200, r.text
    assert r.json()["themes"] == [{"file": "themes/acme-azul.yaml", "outcome": "imported",
                                   "id": "acme-azul"}]
    row = library(client)["acme-azul"]
    assert row["origin"] == "project"
    assert row["project"] == r.json()["project"]["id"]
    assert row["tokens"]["light"]["surface"] == "#FFFFFF"
    # The report that named it is no longer told its theme is missing.
    assert "theme_unknown" not in {e["code"] for e in r.json()["validation"]["errors"]}


def test_the_project_keeps_its_copy_and_export_returns_it(client):
    r = post(client, bundle(authored()))
    assert r.status_code == 200, r.text
    slug = r.json()["project"]["slug"]
    data = client.get(f"/api/projects/{slug}/export.zip").content
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert f"{slug}/themes/acme-azul.yaml" in names


@pytest.mark.parametrize("policy,outcome,expected_id", [
    ("skip", "skipped", "acme-azul"),
    ("replace", "replaced", "acme-azul"),
    ("rename", "renamed", "acme-azul-2"),
])
def test_a_collision_answers_skip_replace_or_rename(client, policy, outcome, expected_id):
    mine = authored()
    assert client.post("/api/admin/themes",
                       json={"yaml": yaml.safe_dump(mine)}).status_code == 201

    theirs = authored(**{"name": "Acme · del proyecto", "name_en": "Acme · from the project"})
    r = post(client, bundle(theirs, report_theme="acme-azul"), themes=policy)
    assert r.status_code == 200, r.text
    line = r.json()["themes"][0]
    assert line["outcome"] == outcome
    assert line["id"] == expected_id

    rows = library(client)
    assert rows[expected_id]["name"] == ("Acme · azul" if policy == "skip"
                                        else "Acme · del proyecto")
    if policy == "rename":
        assert rows["acme-azul"]["origin"] == "upload"
        assert rows["acme-azul-2"]["origin"] == "project"
        # The renamed theme carried the project's own reference with it.
        report = client.get(f"/api/projects/{r.json()['project']['slug']}/file"
                            "?path=reports/ventas/report.yaml").json()["content"]
        assert "id: acme-azul-2" in report
        assert "id: acme-azul\n" not in report
        assert "theme_unknown" not in {e["code"] for e in r.json()["validation"]["errors"]}


def test_a_builtin_is_never_replaced_by_an_import(client):
    impostor = authored("impacto", name="Impacto del proyecto")
    for policy in ("skip", "replace", "rename"):
        r = post(client, bundle(impostor, theme_id="impacto", report_theme="impacto"),
                 themes=policy)
        assert r.status_code == 200, r.text
        assert r.json()["themes"][0]["outcome"] == "skipped"
        assert r.json()["themes"][0]["reason"] == "builtin"
    assert library(client)["impacto"]["origin"] == "builtin"


def test_a_theme_that_breaks_the_contract_is_refused_and_named(client):
    broken = authored()
    broken["light"]["text"] = "#EEEEEE"
    r = post(client, bundle(broken))
    assert r.status_code == 200, r.text
    line = r.json()["themes"][0]
    assert line["outcome"] == "refused"
    assert [p["path"] for p in line["problems"]] == ["light.text"]
    assert "acme-azul" not in library(client)
    # The report that named it says so, instead of rendering with a theme nobody chose.
    codes = {e["code"] for e in r.json()["validation"]["errors"]}
    assert "theme_unknown" in codes


def test_a_report_naming_a_theme_nobody_has_is_a_validation_error(client):
    r = post(client, bundle(None, report_theme="no-existe"))
    assert r.status_code == 200, r.text
    problem = next(e for e in r.json()["validation"]["errors"] if e["code"] == "theme_unknown")
    assert problem["file"] == "reports/ventas/report.yaml"
    assert problem["path"] == "/layout/theme/id"
    assert "no-existe" in problem["message"]
    assert "impacto" in problem["expected"]["theme"]


def test_the_installation_themes_satisfy_the_check_too(client):
    mine = authored()
    assert client.post("/api/admin/themes",
                       json={"yaml": yaml.safe_dump(mine)}).status_code == 201
    r = post(client, bundle(None, report_theme="acme-azul"))
    assert r.status_code == 200, r.text
    assert "theme_unknown" not in {e["code"] for e in r.json()["validation"]["errors"]}


def test_deleting_the_project_takes_its_themes_with_it(client):
    r = post(client, bundle(authored()))
    assert r.status_code == 200, r.text
    slug = r.json()["project"]["slug"]
    assert "acme-azul" in library(client)
    assert client.delete(f"/api/projects/{slug}").status_code == 204
    assert "acme-azul" not in library(client)
    assert sql("SELECT count(*) FROM theme WHERE id = 'acme-azul'") == [(0,)]


def test_the_project_page_shows_the_theme_problem_after_a_refusal(client):
    broken = authored()
    del broken["dark"]["card"]
    r = post(client, bundle(broken))
    assert r.status_code == 200, r.text
    slug = r.json()["project"]["slug"]
    again = reauth(client).post(f"/api/projects/{slug}/validate")
    assert again.status_code == 200, again.text
    codes = {e["code"] for e in again.json()["validation"]["errors"]}
    assert "theme_unknown" in codes
