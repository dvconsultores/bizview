"""Feature 055: re-importing a project — the same project, a new revision.

Every case here starts from an archive, because that is the only way a project enters the product.
"""
import io
import zipfile

import pytest

from app.config import get_settings
from tests.conftest import make_project, reauth, signed_in, sql


@pytest.fixture(autouse=True)
def projects(tmp_path, monkeypatch):
    """The composition itself is feature 020's (its suite applies real projects); here the apply is
    stubbed so the *revision* bookkeeping of 055 is what the test reads."""
    from types import SimpleNamespace

    path = tmp_path / "projects"
    monkeypatch.setattr(get_settings(), "projects_dir", str(path))
    monkeypatch.setattr("app.projects.readiness.compute", lambda *a, **k: {"ready": True,
                                                                         "pending": []})
    monkeypatch.setattr("app.projects.origin_checks.recheck_draft", lambda *a, **k: [])
    # `version_json` of the apply endpoint reads these; the composition is 020's business.
    monkeypatch.setattr("app.projects.apply._activate_composed",
                        lambda *a, **k: SimpleNamespace(id=1, commit=None, checksum="0" * 64,
                                                        applied_at=None, applied_by=None,
                                                        lock={"workspace": {}}, artifacts={},
                                                        specs={}, projects={}, state="active"))
    return path


@pytest.fixture
def client(superuser):
    return signed_in("root@example.com")


def make_zip(entries: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            zf.writestr(name, content.encode() if isinstance(content, str) else content)
    return buffer.getvalue()


def post(client, data, **params):
    return reauth(client).post("/api/projects/import", content=data, params=params,
                               headers={"Content-Type": "application/zip"})


REPORT_V1 = """id: cripto
spec: specs/001-reporte
title: Cripto
date: "2024-01-01"
uses:
  lines: ventas.sale_lines
metrics: []
views:
  - id: v1
    title: Uno
    blocks: []
"""

REPORT_V2 = REPORT_V1.replace("Cripto", "Cripto impacto").replace("v1", "v2")

PROJECT = 'name: "Ventas marca"\nslug: ventas-marca\ndescription: ""\n'
SPEC = "# Reporte\n\n**Tipo**: reporte\n**Status**: Approved\n"
INTEGRATION = """id: ventas
spec: specs/003-integracion
source: Origen
datasets:
  sale_lines:
    primary_key: [document_id]
    date_column: local_date
    columns:
      document_id: {type: text, nullable: false}
      local_date: {type: date, nullable: false}
      net_amount: {type: numeric, nullable: false}
    extract: {query: queries/lines.sql}
    incremental: {mode: full}
"""


def archive(**overrides) -> bytes:
    entries = {
        "ventas/project.yaml": PROJECT,
        "ventas/specs/001-reporte/spec.md": SPEC,
        "ventas/specs/003-integracion/spec.md": "# Integración\n\n**Tipo**: integracion\n",
        "ventas/integrations/ventas/integration.yaml": INTEGRATION,
        "ventas/integrations/ventas/queries/lines.sql": "SELECT 1 AS document_id\n",
        "ventas/reports/cripto/report.yaml": REPORT_V1,
        "ventas/.DS_Store": b"\x00\x01",
    }
    entries.update(overrides)
    return make_zip(entries)


# --- the same project, a new revision ---------------------------------------------------------

def test_the_same_zip_twice_is_one_project_at_revision_two(client, projects):
    first = post(client, archive())
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["mode"] == "created"
    assert body["revision"]["number"] == 1
    slug = body["project"]["slug"]
    assert slug == "ventas-marca"

    second = post(client, archive(**{"ventas/reports/cripto/report.yaml": REPORT_V2}))
    assert second.status_code == 200, second.text
    again = second.json()
    assert again["mode"] == "reimported"
    assert again["project"]["slug"] == slug and again["project"]["id"] == body["project"]["id"]
    assert again["revision"]["number"] == 2
    assert again["revision"]["status"] == "draft"
    assert again["diff"]["changed"] == ["reports/cripto/report.yaml"]
    assert sql("SELECT count(*) FROM project")[0][0] == 1
    assert (projects / slug / "reports/cripto/report.yaml").read_text() == REPORT_V2
    detail = client.get(f"/api/projects/{slug}").json()
    assert detail["revision"] == {"number": 2, "status": "draft", "source": "import",
                                  "applied": None, "previous": None, "keep": 20}
    kinds = {row[0] for row in sql("SELECT kind FROM audit_event")}
    assert {"project_imported", "project_reimported"} <= kinds


def test_the_derived_slug_is_the_match_when_the_zip_has_none(client, projects):
    """`project.yaml` without `slug:`: the name is what derives the identity, so the second import
    is revision 2 of the same project — the old `-2` suggestion is what 055 removes."""
    manifest = 'name: "Ventas marca"\n'
    first = post(client, archive(**{"ventas/project.yaml": manifest})).json()
    assert first["mode"] == "created" and first["project"]["slug"] == "ventas-marca"

    again = post(client, archive(**{"ventas/project.yaml": manifest})).json()
    assert again["mode"] == "reimported"
    assert again["project"]["id"] == first["project"]["id"]
    assert again["project"]["slug"] == "ventas-marca"
    assert again["revision"]["number"] == 2
    assert sql("SELECT count(*) FROM project")[0][0] == 1


def test_a_manifest_without_its_slug_gets_the_projects_own(client, projects):
    """An archive exported from the product carries `slug: ""`; the re-import pins the project's
    slug, so the manifest is not a change and the apply's schema still finds a valid slug."""
    post(client, archive())
    again = post(client, archive(**{
        "ventas/project.yaml": 'name: "Ventas marca"\nslug: ""\ndescription: ""\n'})).json()
    assert again["mode"] == "reimported"
    assert again["diff"]["changed"] == []
    assert "slug: ventas-marca" in (projects / "ventas-marca" / "project.yaml").read_text()


def test_a_reimport_removes_what_the_zip_no_longer_carries(client, projects):
    post(client, archive(**{"ventas/specs/002-extra/spec.md": "# Extra\n",
                            "ventas/assets/coins/BTC.png": _png()}))
    slug = "ventas-marca"
    assert (projects / slug / "specs/002-extra/spec.md").exists()
    assert (projects / slug / "assets/coins/BTC.png").exists()

    body = post(client, archive()).json()
    assert sorted(body["diff"]["removed"]) == ["assets/coins/BTC.png", "specs/002-extra/spec.md"]
    assert body["diff"]["specs"]["removed"] == ["002-extra"]
    assert not (projects / slug / "specs/002-extra/spec.md").exists()
    assert not (projects / slug / "assets/coins/BTC.png").exists()
    assert sql("SELECT count(*) FROM project_file_revision "
               "WHERE path = 'assets/coins/BTC.png' AND op = 'delete'")[0][0] >= 1


def test_a_reimport_keeps_shares_grants_and_the_loaded_data(client, projects):
    post(client, archive())
    slug = "ventas-marca"
    user_id = sql("INSERT INTO app_user (email, full_name, role) VALUES "
                  "('ana@example.com', 'Ana', 'user') RETURNING id")[0][0]
    dashboard = sql("SELECT id FROM dashboard LIMIT 1")
    if dashboard:
        sql("INSERT INTO dashboard_access (user_id, dashboard_id) VALUES (:u, :d)",
            u=user_id, d=dashboard[0][0])
    sql("INSERT INTO share_link (dashboard_id, token_hash, expires_at) SELECT id, 'x', now() "
        "+ interval '1 day' FROM dashboard LIMIT 1") if dashboard else None
    before = {table: sql(f"SELECT count(*) FROM {table}")[0][0]
              for table in ("app_user", "share_link", "dashboard_access")}

    body = post(client, archive(**{"ventas/reports/cripto/report.yaml": REPORT_V2})).json()
    assert body["mode"] == "reimported"
    after = {table: sql(f"SELECT count(*) FROM {table}")[0][0] for table in before}
    assert after == before
    assert sql("SELECT slug FROM project WHERE id = :i", i=body["project"]["id"])[0][0] == slug


def test_a_reimport_follows_the_new_name_and_never_the_slug(client, projects):
    post(client, archive())
    body = post(client, archive(**{
        "ventas/project.yaml": 'name: "Ventas marca 2026"\nslug: ventas-marca\n'})).json()
    assert body["project"]["slug"] == "ventas-marca"
    assert body["project"]["name"] == "Ventas marca 2026"


def test_the_applied_revision_keeps_serving_until_the_apply(client, projects):
    post(client, archive())
    slug = "ventas-marca"
    applied = client.post(f"/api/projects/{slug}/apply")
    assert applied.status_code == 200, applied.text
    assert applied.json()["project"]["revision"]["number"] == 1
    assert applied.json()["project"]["revision"]["status"] == "applied"

    body = post(client, archive(**{"ventas/reports/cripto/report.yaml": REPORT_V2})).json()
    assert body["revision"]["status"] == "draft"
    # The revision in force is still the one applied: the draft waits for its own apply.
    assert sql("SELECT status FROM project_revision WHERE number = 1")[0][0] == "applied"

    again = client.post(f"/api/projects/{slug}/apply")
    assert again.status_code == 200, again.text
    chip = again.json()["project"]["revision"]
    assert (chip["number"], chip["status"], chip["previous"]) == (2, "applied", 1)
    detail = sql("SELECT detail FROM audit_event WHERE kind = 'project_applied' "
                 "ORDER BY id DESC LIMIT 1")[0][0]
    assert (detail["revision"], detail["previous_revision"]) == (2, 1)


# --- the diff before anything is written ------------------------------------------------------

def test_the_dry_run_reports_the_same_diff_and_writes_nothing(client, projects):
    post(client, archive())
    before = sql("SELECT count(*) FROM project_revision")[0][0]
    data = archive(**{"ventas/reports/cripto/report.yaml": REPORT_V2,
                      "ventas/specs/002-extra/spec.md": "# Extra\n"})

    preview = post(client, data, dry_run=True).json()
    assert preview["mode"] == "reimported" and preview["revision"] is None
    assert preview["diff"]["changed"] == ["reports/cripto/report.yaml"]
    assert preview["diff"]["specs"]["added"] == ["002-extra"]
    assert sql("SELECT count(*) FROM project_revision")[0][0] == before
    assert not (projects / "ventas-marca" / "specs/002-extra").exists()

    real_response = post(client, data)
    real = real_response.json()
    assert real_response.status_code == 200, real
    assert real["diff"] == preview["diff"]


def test_a_no_op_reimport_still_records_the_revision(client, projects):
    post(client, archive())
    body = post(client, archive()).json()
    assert body["diff"]["counts"] == {"added": 0, "changed": 0, "removed": 0, "specs_added": 0,
                                      "specs_removed": 0, "ids_added": 0, "ids_removed": 0}
    assert body["revision"]["number"] == 2


# --- a copy is a copy -------------------------------------------------------------------------

def test_a_copy_gets_its_own_slug_and_its_own_ids(client, projects):
    post(client, archive())
    copy = post(client, archive(), copy=True).json()
    assert copy["mode"] == "created"
    assert copy["project"]["slug"] == "ventas-marca-2"
    text = (projects / "ventas-marca-2" / "reports/cripto-2/report.yaml").read_text()
    assert "id: cripto-2" in text and "ventas-2.sale_lines" in text
    assert (projects / "ventas-marca" / "reports/cripto/report.yaml").exists()
    assert sql("SELECT count(*) FROM project")[0][0] == 2
    # Only the original was re-imported; the copy is untouched by it.
    body = post(client, archive()).json()
    assert body["mode"] == "reimported" and body["project"]["slug"] == "ventas-marca"


def test_a_copy_repoints_a_distribution_to_the_copied_report(client, projects):
    post(client, archive(**{
        "ventas/specs/004-envio/spec.md": "# Envío\n\n**Tipo**: distribucion\n",
        "ventas/distributions/envio.yaml": 'id: envio\nspec: specs/004-envio\nreport: cripto\n'}))
    copy_response = post(client, archive(**{
        "ventas/specs/004-envio/spec.md": "# Envío\n\n**Tipo**: distribucion\n",
        "ventas/distributions/envio.yaml": 'id: envio\nspec: specs/004-envio\nreport: cripto\n'}),
         copy=True)
    assert copy_response.status_code == 200, copy_response.text
    tree = sorted(p.relative_to(projects / "ventas-marca-2").as_posix()
                  for p in (projects / "ventas-marca-2").rglob("*") if p.is_file())
    assert "distributions/envio-2.yaml" in tree, tree
    text = (projects / "ventas-marca-2" / "distributions/envio-2.yaml").read_text()
    assert "report: cripto-2" in text


# --- the draft conflict -----------------------------------------------------------------------

def test_editor_changes_make_the_reimport_ask_first(client, projects):
    post(client, archive())
    slug = "ventas-marca"
    assert client.put(f"/api/projects/{slug}/file", json={
        "path": "reports/cripto/report.yaml", "content": REPORT_V2,
        "force": True}).status_code == 200

    asked = post(client, archive()).json()
    assert asked["needs_confirmation"] is True and asked["revision"] is None
    assert (projects / slug / "reports/cripto/report.yaml").read_text() == REPORT_V2
    assert sql("SELECT max(number) FROM project_revision")[0][0] == 2   # the editor's revision

    done = post(client, archive(), replace_draft=True).json()
    assert done["needs_confirmation"] is False
    assert (projects / slug / "reports/cripto/report.yaml").read_text() == REPORT_V1


# --- revert -----------------------------------------------------------------------------------

def test_the_previous_revision_comes_back_and_is_applied(client, projects):
    post(client, archive())
    slug = "ventas-marca"
    client.post(f"/api/projects/{slug}/apply")
    post(client, archive(**{"ventas/reports/cripto/report.yaml": REPORT_V2}))
    client.post(f"/api/projects/{slug}/apply")
    assert REPORT_V2 in (projects / slug / "reports/cripto/report.yaml").read_text()

    back = reauth(client).post(f"/api/projects/{slug}/revisions/1/revert")
    assert back.status_code == 200, back.text
    body = back.json()
    assert body["restored"] == 1
    assert (projects / slug / "reports/cripto/report.yaml").read_text() == REPORT_V1
    chip = body["project"]["revision"]
    assert chip["number"] == body["revision"]["number"] == 3
    assert chip["status"] == "applied" and chip["previous"] == 2
    detail = sql("SELECT detail FROM audit_event WHERE kind = 'project_reverted'")[0][0]
    assert (detail["revision"], detail["applied_revision"]) == (1, 3)


def test_reverting_the_draft_itself_is_refused(client, projects):
    post(client, archive())
    r = reauth(client).post("/api/projects/ventas-marca/revisions/1/revert")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "revision_is_draft"


def test_an_unknown_revision_is_404(client, projects):
    post(client, archive())
    assert client.get("/api/projects/ventas-marca/revisions/9/zip").status_code == 404


# --- downloads and the history ----------------------------------------------------------------

def test_a_revision_downloads_with_its_own_files(client, projects):
    post(client, archive())
    post(client, archive(**{"ventas/reports/cripto/report.yaml": REPORT_V2}))
    data = client.get("/api/projects/ventas-marca/revisions/1/zip")
    assert data.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(data.content)).namelist()
    assert "ventas-marca/reports/cripto/report.yaml" in names
    archived = zipfile.ZipFile(io.BytesIO(data.content)).read(
        "ventas-marca/reports/cripto/report.yaml").decode()
    assert archived == REPORT_V1
    assert "rev1" in data.headers["content-disposition"]


def test_the_history_lists_every_revision_newest_first(client, projects):
    post(client, archive())
    client.put("/api/projects/ventas-marca/file", json={
        "path": "reports/cripto/report.yaml", "content": REPORT_V2, "force": True})
    body = client.get("/api/projects/ventas-marca/revisions").json()
    assert [item["number"] for item in body["items"]] == [2, 1]
    assert body["items"][0]["source"] == "editor" and body["items"][1]["source"] == "import"
    assert body["items"][0]["by"] == "Root" or body["items"][0]["by"]
    assert body["keep"] == 20


# --- retention --------------------------------------------------------------------------------

def test_retention_keeps_the_applied_and_the_previous(client, projects, monkeypatch):
    monkeypatch.setattr(get_settings(), "project_revisions_keep", 3)
    post(client, archive())
    client.post("/api/projects/ventas-marca/apply")
    for index in range(4):
        post(client, archive(**{"ventas/reports/cripto/report.yaml": f"# {index}\n" +
                                REPORT_V1}))
        if index == 1:
            client.post("/api/projects/ventas-marca/apply")
    numbers = [row[0] for row in sql("SELECT number FROM project_revision ORDER BY number")]
    statuses = {row[0]: row[1] for row in sql("SELECT number, status FROM project_revision")}
    # The three newest (3, 4, 5) plus the previous applied (1), which is never pruned (FR-017).
    assert numbers == [1, 3, 4, 5]
    assert statuses[3] == "applied" and statuses[1] == "previous"
    assert 2 not in numbers                  # the plain draft that fell out of the window
    assert numbers[-1] == max(numbers)


def test_an_old_revision_is_gone_from_the_history(client, projects, monkeypatch):
    monkeypatch.setattr(get_settings(), "project_revisions_keep", 2)
    post(client, archive())
    for index in range(3):
        post(client, archive(**{"ventas/reports/cripto/report.yaml": f"# {index}\n" + REPORT_V1}))
    numbers = [row[0] for row in sql("SELECT number FROM project_revision ORDER BY number")]
    assert numbers == [3, 4]
    assert client.get("/api/projects/ventas-marca/revisions/1/zip").status_code == 404


# --- the project that predates the table -------------------------------------------------------

def test_a_project_without_revisions_gets_its_first_on_read(client, projects):
    slug = make_project("Viejo")
    assert sql("SELECT count(*) FROM project_revision")[0][0] == 0
    body = client.get(f"/api/projects/{slug}").json()
    assert body["revision"]["number"] == 1 and body["revision"]["status"] == "draft"
    assert sql("SELECT count(*) FROM project_revision")[0][0] == 1


# --- refusals that must not move ---------------------------------------------------------------

def test_a_git_project_is_not_reimported(client, projects):
    slug = make_project("Espejo")
    sql("UPDATE project SET origin = 'git' WHERE slug = :s", s=slug)
    r = post(client, archive(**{"ventas/project.yaml": f'name: "Espejo"\nslug: {slug}\n'}))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "git_project"


def test_a_deleted_project_is_not_the_match(client, projects):
    post(client, archive())
    sql("UPDATE project SET deleted_at = now() WHERE slug = 'ventas-marca'")
    r = post(client, archive())
    assert r.status_code == 200
    assert r.json()["mode"] == "created"          # a new one, never into the trashed folder


def test_a_zip_that_collides_with_itself_still_leaves_nothing(client, projects):
    post(client, archive())
    r = post(client, archive(**{"ventas/specs/001-b/spec.md": "# B\n"}))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "spec_number_duplicate"
    assert sql("SELECT count(*) FROM project_revision")[0][0] == 1


def _png() -> bytes:
    """A one-pixel PNG: `assets.prepare` sniffs the bytes, so the header has to be real."""
    import base64

    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
        "IQAAAABJRU5ErkJggg==")
