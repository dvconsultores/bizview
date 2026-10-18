"""Feature 014/020: applying the conversation's project from the chat (the same path as a Git
apply) and version export.

The 017 rules on rewriting an integration of the active version (`duplicate_integration`,
declared edits) were replaced by project ownership in 020; those cases live in
test_projects_apply.py (id clashes, dependants) and test_workspace_git_v2.py.
"""
import io
import secrets
import textwrap
import zipfile

import pytest

from app.assistant import readiness, service
from app.assistant.tools import run_tool
from app.config import get_settings
from app.models import AppUser, AssistantSession
from app.projects import fs
from app.projects import service as project_service
from app.projects.workview import for_session
from tests.conftest import reauth, signed_in, sql, v2_files
from tests.test_assistant_readiness import _ready_draft
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import apply, lock
from tests.test_vibe_reporting import workspace as workspace  # fixture
from tests.workspace_fixture import REPORT


@pytest.fixture(autouse=True)
def projects_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))


def _draft_files(open_task=False):
    report = textwrap.dedent(REPORT.format(title="Ventas 2")).lstrip()
    report = report.replace("id: ventas\n", "id: ventas2\n").replace(
        "spec: specs/reports/001-ventas\n", "spec: specs/reports/002-ventas2\n"
    )
    return v2_files({
        "reports/ventas2/report.yaml": report,
        "specs/reports/002-ventas2/spec.md": (
            "# Ventas 2\n\n**Spec type**: report\n\n**Status**: Implemented\n"
        ),
        "specs/reports/002-ventas2/plan.md": "# Plan\n",
        "specs/reports/002-ventas2/tasks.md": (
            "- [ ] T001 pendiente\n" if open_task else "- [X] T001 hecho\n"
        ),
    })


def _session(db, superuser, files, *, previewed=True) -> AssistantSession:
    """A conversation on a new project holding `files`, previewed as they are."""
    actor = db.get(AppUser, superuser.id)
    project = project_service.create(db, actor, f"Chat {secrets.token_hex(3)}")
    db.commit()
    fs.apply_ops(project.id, [{"op": "write", "path": path, "content": text, "base_sha256": None,
                               "force": False} for path, text in files.items()],
                 {"kind": "user", "user_id": superuser.id, "session_id": None, "command": "edit"})
    session = service.create_session(db, actor, project_id=project.id)
    db.commit()
    if previewed:
        view = for_session(db, session)
        view.preview = {"status": "succeeded", "fingerprint": readiness.fingerprint(view.files())}
    return session


def _applied(workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))


def _apply(session):
    return reauth(signed_in("root@example.com")).post(f"/api/assistant/sessions/{session.id}/apply")


def _slug(session) -> str:
    return sql("SELECT slug FROM project WHERE id = :i", i=session.project_id)[0][0]


def test_apply_requires_step_up(db, superuser, workspace):
    _applied(workspace)
    session = _session(db, superuser, _draft_files())
    resp = signed_in("root@example.com").post(f"/api/assistant/sessions/{session.id}/apply")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "reauth_required"


def test_apply_creates_version_dashboard_and_audit(db, superuser, workspace):
    _applied(workspace)
    session = _session(db, superuser, _draft_files())
    resp = _apply(session)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert {"ventas", "ventas2"} <= set(body["version"]["reports"])
    assert body["session"]["applied_version_id"] == body["version"]["id"]
    assert body["session"]["status"] == "open"      # 020: the conversation keeps working

    vid = body["version"]["id"]
    assert sql("SELECT state FROM workspace_version WHERE id = :i", i=vid)[0][0] == "active"
    assert sql("SELECT count(*) FROM dashboard WHERE code = 'ventas2'")[0][0] == 1
    slug = _slug(session)
    assert sql("SELECT count(*) FROM audit_event WHERE kind = 'workspace_applied' "
               "AND detail->>'origin' = :o", o=f"project:{slug}")[0][0] == 1
    assert sql("SELECT (detail->>'session')::int FROM audit_event "
               "WHERE kind = 'project_applied'")[0][0] == session.id


def test_invalid_project_is_refused(db, superuser, workspace):
    _applied(workspace)
    session = _session(db, superuser, _draft_files(open_task=True))
    before = sql("SELECT count(*) FROM workspace_version")[0][0]
    resp = _apply(session)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] in ("not_ready", "invalid_draft")
    assert sql("SELECT count(*) FROM workspace_version")[0][0] == before


def test_rollback_after_chat_apply(db, superuser, workspace):
    _applied(workspace)
    before_id = sql("SELECT id FROM workspace_version WHERE state = 'active'")[0][0]
    session = _session(db, superuser, _draft_files())
    c = reauth(signed_in("root@example.com"))
    assert c.post(f"/api/assistant/sessions/{session.id}/apply").status_code == 200
    assert c.post("/api/workspace/rollback").status_code == 200
    assert sql("SELECT id FROM workspace_version WHERE state = 'active'")[0][0] == before_id


def test_export_zip_contains_the_projects(db, superuser, workspace):
    _applied(workspace)
    session = _session(db, superuser, _draft_files())
    resp = _apply(session)
    assert resp.status_code == 200, resp.text
    vid = resp.json()["version"]["id"]

    resp = signed_in("root@example.com").get(f"/api/workspace/versions/{vid}/export.zip")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(resp.content)).namelist()
    slug = _slug(session)
    for expected in ("bizview.yaml", "bizview.lock",
                     f"projects/{slug}/reports/ventas2/report.yaml",
                     f"projects/{slug}/specs/001-ventas2/spec.md",
                     "projects/principal/integrations/ventas-prueba/integration.yaml"):
        assert expected in names, names


def test_export_unknown_version_404(superuser):
    resp = signed_in("root@example.com").get("/api/workspace/versions/999999/export.zip")
    assert resp.status_code == 404


def test_apply_reports_revalidation_after_other_apply(db, superuser, workspace):
    """Edge: another apply happened after validation — the project is checked again."""
    _applied(workspace)
    session = _session(db, superuser, _draft_files())
    for_session(db, session).validation = {"valid": True, "errors": [], "warnings": [],
                                           "base_version": -1}
    resp = _apply(session)
    assert resp.status_code == 200, resp.text
    assert resp.json()["revalidated"] is True


def test_apply_not_revalidated_when_base_is_active(db, superuser, workspace):
    _applied(workspace)
    active_id = sql("SELECT id FROM workspace_version WHERE state = 'active'")[0][0]
    session = _session(db, superuser, _draft_files())
    for_session(db, session).validation = {"valid": True, "errors": [], "warnings": [],
                                           "base_version": active_id}
    resp = _apply(session)
    assert resp.status_code == 200, resp.text
    assert resp.json()["revalidated"] is False


def test_archive_drops_preview(db, superuser, monkeypatch):
    session = _session(db, superuser, _draft_files(), previewed=False)
    session.preview = {"status": "succeeded"}
    db.commit()
    calls = []
    monkeypatch.setattr("app.assistant.preview.drop_for_session", calls.append)
    resp = signed_in("root@example.com").post(f"/api/assistant/sessions/{session.id}/archive")
    assert resp.status_code == 200, resp.text
    assert calls == [session.id]
    assert sql("SELECT preview FROM assistant_session WHERE id = :i",
               i=session.id)[0][0] == {"status": "expired"}


def test_apply_from_empty_installation_uses_template_manifest(
        db, superuser, origin, pg_source, monkeypatch, without_command_guard):
    monkeypatch.setattr(get_settings(), "organization_name", "Cliente Demo")
    assert sql("SELECT count(*) FROM workspace_version")[0][0] == 0

    files = v2_files(_ready_draft())
    assert "bizview.yaml" not in files
    session = _session(db, superuser, files)
    view = for_session(db, session)
    actor = db.get(AppUser, superuser.id)
    for path in files:
        if readiness.QUERY_FILE.match(path):
            result, _ = run_tool(db, actor, view, "check_query",
                                 {"source": "Origen prueba", "path": path}, get_settings())
            assert result["ok"] is True, result
    db.commit()

    resp = _apply(session)
    assert resp.status_code == 200, resp.text
    assert "ventas2" in resp.json()["version"]["reports"]
    assert sql("SELECT artifacts->'workspace'->>'name' FROM workspace_version "
               "WHERE state = 'active'")[0][0] == "cliente-demo"
    assert sql("SELECT count(*) FROM dashboard WHERE code = 'ventas2'")[0][0] == 1
