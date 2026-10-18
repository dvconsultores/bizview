"""Feature 020 T060: versions with owners, spec archive keys, project status."""
from tests.conftest import reauth
from tests.test_projects_apply import apply_ok, project_a
from tests.test_projects_apply import env as env  # fixture
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import applied as applied  # fixture
from tests.test_vibe_reporting import workspace as workspace  # fixture


def test_spec_archive_keys_both_styles(applied, origin):
    c = applied
    legacy = {s["key"] for s in c.get("/api/workspace").json()["active"]["specs"]}
    assert "integrations/ventas-prueba" in legacy
    doc = c.get("/api/workspace/specs", params={"key": "integrations/ventas-prueba"}).json()
    assert "spec.md" in doc["documents"]

    apply_ok(c, project_a(c, origin))
    specs = {s["key"]: s for s in c.get("/api/workspace").json()["active"]["specs"]}
    item = specs["proyecto-a/specs/001-ventas-a"]
    assert (item["project"], item["kind"], item["folder"]) == (
        "proyecto-a", "integracion", "specs/001-ventas-a")
    assert any(key.startswith("principal/specs/") for key in specs)
    doc = c.get("/api/workspace/specs",
                params={"key": "proyecto-a/specs/001-ventas-a"}).json()
    assert {"spec.md", "plan.md", "tasks.md"} <= set(doc["documents"])


def test_version_owners_and_status_after_edit(applied, origin):
    c = applied
    slug = project_a(c, origin)
    assert c.get(f"/api/projects/{slug}").json()["status"] == "borrador"
    version = apply_ok(c, slug)
    owners = version["projects"]
    assert owners["proyecto-a"]["integrations"] == ["ventas-a"]
    assert owners["principal"]["integrations"] == ["ventas-prueba"]
    assert owners["principal"]["reports"] == ["ventas", "ventas-layout"]
    assert c.get(f"/api/projects/{slug}").json()["status"] == "aplicado"

    r = c.put(f"/api/projects/{slug}/file",
              json={"path": "specs/001-ventas-a/plan.md", "content": "# Plan v2\n",
                    "force": True})
    assert r.status_code == 200, r.text
    detail = c.get(f"/api/projects/{slug}").json()
    assert detail["status"] == "cambios"
    assert detail["changed_files"] == {"added": [], "changed": ["specs/001-ventas-a/plan.md"],
                                       "removed": []}
    assert reauth(c).post(f"/api/projects/{slug}/apply").status_code == 200
    assert c.get(f"/api/projects/{slug}").json()["status"] == "aplicado"
