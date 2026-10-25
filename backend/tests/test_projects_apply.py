"""Feature 020 T063: apply, rollback and delete projects."""
from datetime import UTC, datetime, timedelta
from textwrap import dedent

import pytest
import yaml

from app.config import get_settings
from app.db import get_sessionmaker
from app.projects import service as project_service
from tests.conftest import reauth, signed_in, sql
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import applied as applied  # fixture
from tests.test_vibe_reporting import workspace as workspace  # fixture
from tests.workspace_fixture import LAYOUT_REPORT, REPORT, integration_yaml, queries

OWNED_B = "SELECT count(*) FROM email_subscription WHERE distribution_id = 'envio-b'"
DISTRIBUTION_B = ("id: envio-b\nspec: specs/002-envio-b\nreport: ventas-b\nsubscriptions:\n"
                  "  - frequency: daily\n    hour: 7\n    period: mtd\n"
                  "    recipients:\n      roles: [admin]\n")


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))
    # Readiness and query re-checks have their own tests; here only the apply mechanics.
    monkeypatch.setattr("app.assistant.readiness.compute",
                        lambda *a, **k: {"ready": True, "pending": []})
    monkeypatch.setattr("app.assistant.origin.recheck_draft", lambda *a, **k: [])
    return tmp_path / "projects"


def put(c, slug, files):
    for path, content in files.items():
        r = c.put(f"/api/projects/{slug}/file", json={"path": path, "content": content})
        assert r.status_code == 200, r.text


def replace(c, slug, path, content):
    """Reescribe un archivo ya existente (forzando la revisión actual, como el editor)."""
    r = c.put(f"/api/projects/{slug}/file",
              json={"path": path, "content": content, "force": True})
    assert r.status_code == 200, r.text


def spec(folder, kind):
    return {f"specs/{folder}/spec.md": f"# {folder}\n\n**Tipo**: {kind}\n**Status**: Implemented\n",
            f"specs/{folder}/plan.md": "# Plan\n",
            f"specs/{folder}/tasks.md": "- [X] T001 hecho\n"}


def create(c, name):
    r = c.post("/api/projects", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["slug"]


def project_a(c, origin):
    slug = create(c, "Proyecto A")
    files = spec("001-ventas-a", "integracion")
    files["integrations/ventas-a/integration.yaml"] = (
        dedent(integration_yaml()).lstrip().replace("id: ventas-prueba", "id: ventas-a")
        .replace("spec: specs/integrations/001-ventas-prueba", "spec: specs/001-ventas-a"))
    for name, content in queries(origin).items():
        files[f"integrations/ventas-a/queries/{name}"] = content
    put(c, slug, files)
    return slug


def project_b(c):
    slug = create(c, "Proyecto B")
    files = {**spec("001-ventas-b", "reporte"), **spec("002-envio-b", "distribucion")}
    files["reports/ventas-b/report.yaml"] = (
        dedent(REPORT.format(title="Ventas B")).lstrip().replace("id: ventas\n", "id: ventas-b\n")
        .replace("spec: specs/reports/001-ventas", "spec: specs/001-ventas-b")
        .replace("ventas-prueba.", "ventas-a."))
    files["distributions/envio-b.yaml"] = DISTRIBUTION_B
    put(c, slug, files)
    return slug


def apply_ok(c, slug):
    r = reauth(c).post(f"/api/projects/{slug}/apply")
    assert r.status_code == 200, r.text
    return r.json()["version"]


def test_step_up_required(applied, origin):
    slug = project_a(applied, origin)
    r = signed_in("root@example.com").post(f"/api/projects/{slug}/apply")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "reauth_required"


def test_apply_a_then_b_and_rollback(applied, origin):
    c = applied
    va = apply_ok(c, project_a(c, origin))
    assert va["projects"]["proyecto-a"]["integrations"] == ["ventas-a"]
    assert "principal" in va["projects"]
    assert c.get("/api/projects/proyecto-a").json()["last_applied"]["version"] == va["id"]
    vb = apply_ok(c, project_b(c))
    last = c.get("/api/projects/proyecto-b").json()["last_applied"]      # 020 T086
    assert (last["version"], last["by"]) == (vb["id"], "Super Usuario") and last["at"]
    assert c.get("/api/projects/proyecto-a").json()["last_applied"]["version"] == va["id"]
    assert vb["projects"]["proyecto-a"]["integrations"] == ["ventas-a"]
    assert vb["projects"]["proyecto-b"]["reports"] == ["ventas-b"]
    assert vb["projects"]["proyecto-b"]["distributions"] == ["envio-b"]
    assert sql(OWNED_B)[0][0] == 1
    assert reauth(c).post("/api/workspace/rollback").status_code == 200
    active = c.get("/api/workspace").json()["active"]
    assert "proyecto-a" in active["projects"]
    assert "proyecto-b" not in active["projects"]
    assert sql(OWNED_B)[0][0] == 0


def test_id_clash_names_owner(applied):
    c = applied
    slug = create(c, "Choque")
    files = spec("001-ventas-prueba", "integracion")
    files["integrations/ventas-prueba/integration.yaml"] = dedent(integration_yaml()).lstrip(
    ).replace("spec: specs/integrations/001-ventas-prueba", "spec: specs/001-ventas-prueba")
    put(c, slug, files)
    r = reauth(c).post(f"/api/projects/{slug}/apply")
    assert r.status_code == 409
    assert any(e["code"] == "duplicate_id" and "principal" in e["message"]
               for e in r.json()["error"]["errors"])


def test_applying_one_project_leaves_the_other_untouched(applied, origin, env):
    """Reported 2026-10-25: applying coinmarketcap left artemisa in «Cambios sin aplicar».

    Composing a version dumped every project's YAML again, so the projects that were not being
    applied came out reformatted and their file hashes stopped matching their folders.
    """
    c = applied
    a = project_a(c, origin)
    apply_ok(c, a)
    b = project_b(c)
    apply_ok(c, b)
    apply_ok(c, a)                                   # a second apply of the first project
    other = c.get(f"/api/projects/{b}").json()
    assert other["status"] == "aplicado"
    assert other["changed_files"] == {"added": [], "changed": [], "removed": []}
    assert c.get(f"/api/projects/{a}").json()["status"] == "aplicado"


def test_deleting_an_applied_project_leaves_the_workspace_first(applied, origin, env):
    """«Retirar del espacio» is gone from the interface: deleting an applied project does both."""
    c = applied
    a = project_a(c, origin)
    apply_ok(c, a)
    b = project_b(c)
    apply_ok(c, b)
    r = reauth(c).delete(f"/api/projects/{a}")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "project_dependants"
    assert "proyecto-b" in r.json()["error"]["message"]
    r = reauth(c).delete(f"/api/projects/{b}")
    assert r.status_code == 204, r.text
    assert "proyecto-b" not in sql(
        "SELECT projects FROM workspace_version ORDER BY id DESC LIMIT 1")[0][0]
    assert sql(OWNED_B)[0][0] == 0
    assert not (env / b).exists()
    assert sql("SELECT count(*) FROM project_file_revision r JOIN project p "
               "ON p.id = r.project_id WHERE p.slug = 'proyecto-b'")[0][0] > 0
    kinds = [row[0] for row in sql("SELECT kind FROM audit_event "
                                   "WHERE kind LIKE 'project_%' ORDER BY id")]
    assert kinds[-2:] == ["project_withdrawn", "project_deleted"]


def test_delete_and_purge(applied, origin, env):
    c = applied
    a = project_a(c, origin)
    apply_ok(c, a)
    assert reauth(c).delete(f"/api/projects/{a}").status_code == 204
    assert not (env / a).exists()
    trash = list((env / ".papelera").iterdir())
    assert len(trash) == 1
    assert trash[0].name.startswith("proyecto-a--")
    assert c.get(f"/api/projects/{a}").status_code == 404
    with get_sessionmaker().begin() as db:
        assert project_service.purge_trash(db, datetime.now(UTC) + timedelta(days=31)) == 1
    assert not trash[0].exists()
    assert sql("SELECT count(*) FROM project WHERE slug = 'proyecto-a'")[0][0] == 0


# --- FR-013 / FR-009: el layout entra en el "no spec, no run" ------------------------------------

def layout_definition() -> dict:
    """El reporte con layout del fixture, con id y spec propios del proyecto."""
    definition = yaml.safe_load(dedent(LAYOUT_REPORT.format(title="Ventas")).lstrip())
    definition.update(id="ventas-proyecto", spec="specs/001-ventas-layout")
    return definition


def layout_project(c, mutate=None):
    """Proyecto sobre el workspace aplicado con ese reporte, opcionalmente con el layout roto."""
    slug = create(c, "Proyecto Layout")
    definition = layout_definition()
    if mutate is not None:
        mutate(definition)
    put(c, slug, {**spec("001-ventas-layout", "reporte"),
                  "reports/ventas-proyecto/report.yaml":
                      yaml.safe_dump(definition, sort_keys=False, allow_unicode=True)})
    return slug


def refused(c, slug, code, path):
    """El apply se niega con el problema del layout, su archivo y su puntero JSON."""
    before = sql("SELECT count(*) FROM workspace_version")[0][0]
    r = reauth(c).post(f"/api/projects/{slug}/apply")
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "invalid_draft"
    errors = r.json()["error"]["errors"]
    assert code in [e["code"] for e in errors], errors
    issue = next(e for e in errors if e["code"] == code)
    assert issue["path"] == path
    assert issue["file"].endswith("reports/ventas-proyecto/report.yaml")
    # Nada se aplicó: el número de versiones no cambió.
    assert sql("SELECT count(*) FROM workspace_version")[0][0] == before


def _view_missing(definition):
    definition["layout"]["web"]["components"][0]["view"] = "fantasma"


def _color_literal(definition):
    definition["layout"]["web"]["components"].append(
        {"id": "nota", "type": "text", "text": "#ff0000"})


def _address(definition):
    definition["layout"]["web"]["components"].append(
        {"id": "nota", "type": "text", "text": "Ver https://ejemplo.test/informe"})


@pytest.mark.parametrize("mutate,code,path", [
    (_view_missing, "layout_view_missing", "/layout/web/components/0/view"),
    (_color_literal, "layout_color_literal", "/layout/web/components/4/text"),
    (_address, "layout_address_forbidden", "/layout/web/components/4/text"),
], ids=["view_missing", "color_literal", "address"])
def test_invalid_layout_refuses_apply(applied, mutate, code, path):
    """FR-013: un layout inválido no se aplica y el problema es el del layout."""
    refused(applied, layout_project(applied, mutate), code, path)


def test_report_without_layout_applies(applied):
    """FR-009: el mismo reporte, sin `layout`, se aplica como siempre."""
    c = applied
    slug = layout_project(c, _view_missing)
    refused(c, slug, "layout_view_missing", "/layout/web/components/0/view")
    definition = layout_definition()
    definition.pop("layout")
    replace(c, slug, "reports/ventas-proyecto/report.yaml",
            yaml.safe_dump(definition, sort_keys=False, allow_unicode=True))
    version = apply_ok(c, slug)
    assert version["projects"][slug]["reports"] == ["ventas-proyecto"]
