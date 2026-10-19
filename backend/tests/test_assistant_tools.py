from __future__ import annotations

import json
import textwrap

import pytest
import yaml

from app.assistant import tools
from app.assistant.tools import run_tool, sanitize
from app.assistant.tree import bootstrap_manifest, workspace_name
from app.config import get_settings
from app.models import AppUser
from app.sources.service import by_name, secrets_of
from tests.conftest import project_view, signed_in, sql, v2_files
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import apply, lock
from tests.test_vibe_reporting import workspace as workspace  # fixture
from tests.workspace_fixture import REPORT, integration_yaml

# 017/020 tool mechanics through plain-mode calls; the 021 command guard has its own tests.
pytestmark = pytest.mark.usefixtures("without_command_guard")


def _run(db, superuser, session, name, args):
    return run_tool(
        db,
        db.get(AppUser, superuser.id),
        session,
        name,
        args,
        get_settings(),
    )


def test_sanitize_drops_sensitive_keys():
    payload = {
        "tables": [
            {
                "name": "t",
                "columns": [{"name": "host", "type": "text"}],
                "host": "secret-host",
                "password": "secret-pass",
                "values": [1, 2, 3],
                "rows": [{"value": "x"}],
                "sample": "drop",
            }
        ],
        "host": "outer-secret",
        "value": "outer-value",
    }
    cleaned = sanitize(payload)
    assert "host" not in cleaned
    assert "password" not in cleaned
    assert "values" not in cleaned
    assert "rows" not in cleaned
    assert "sample" not in cleaned
    assert "value" not in cleaned
    assert cleaned["tables"][0]["name"] == "t"
    assert cleaned["tables"][0]["columns"][0] == {"name": "host", "type": "text"}


def test_sanitize_truncates_strings_and_lists():
    assert sanitize("a" * 300) == "a" * 200
    assert len(sanitize(list(range(1000)))) == 500


def _make_session(db, superuser):
    """The WorkView of a conversation on a new project (020)."""
    return project_view(db, superuser.id)


def test_list_sources_excludes_settings(db, superuser, pg_source):
    session = _make_session(db, superuser)
    result, _summary = run_tool(
        db,
        db.get(AppUser, superuser.id),
        session,
        "list_sources",
        {},
        get_settings(),
    )
    dumped = json.dumps(result)
    source = by_name(db, "Origen prueba")
    settings_str = json.dumps(source.settings)
    secrets_str = json.dumps(secrets_of(source))
    assert settings_str
    assert secrets_str
    for secret in (
        source.settings.get("host"),
        source.settings.get("user"),
        source.settings.get("password"),
        secrets_of(source).get("password"),
    ):
        if secret:
            assert str(secret) not in dumped
    assert "Origen prueba" in dumped
    assert "postgresql" in dumped


def test_describe_source_has_no_row_values(db, superuser, pg_source, origin):
    session = _make_session(db, superuser)
    sql(
        "INSERT INTO origin_sales VALUES "
        "('ZETA-UNICO-4242', 9, 'sale', now(), 1, 'ZETA-PROD-4242')"
    )

    result, _summary = run_tool(
        db,
        db.get(AppUser, superuser.id),
        session,
        "describe_source",
        {"name": "Origen prueba"},
        get_settings(),
    )
    dumped = json.dumps(result)
    assert "tables" in result or "kind" in result
    assert "ZETA-UNICO-4242" not in dumped
    assert "ZETA-PROD-4242" not in dumped
    source = by_name(db, "Origen prueba")
    for key, value in source.settings.items():
        if isinstance(value, str) and len(value) >= 6:
            assert value not in dumped
        elif value:
            assert f'"{key}": {json.dumps(value)}' not in dumped
    assert secrets_of(source)["password"] not in dumped


def test_describe_source_unknown_name(db, superuser, pg_source):
    session = _make_session(db, superuser)
    result, _summary = run_tool(
        db,
        db.get(AppUser, superuser.id),
        session,
        "describe_source",
        {"name": "No Existe"},
        get_settings(),
    )
    assert result == {"error": "No existe una fuente con ese nombre."}


def test_describe_source_error_is_generic(db, superuser, pg_source, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("host=secret-host password=x")

    monkeypatch.setattr(tools, "describe", boom)

    session = _make_session(db, superuser)
    result, _summary = run_tool(
        db,
        db.get(AppUser, superuser.id),
        session,
        "describe_source",
        {"name": "Origen prueba"},
        get_settings(),
    )
    assert result == {"error": "No se pudo leer la estructura de la fuente."}
    assert "secret-host" not in json.dumps(result)


def test_get_workspace_after_apply(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))

    session = _make_session(db, superuser)
    result, _summary = run_tool(
        db,
        db.get(AppUser, superuser.id),
        session,
        "get_workspace",
        {},
        get_settings(),
    )
    assert result["workspace"] is not None
    assert "integrations" in result
    assert "reports" in result
    assert "specs" in result
    assert result["integrations"]
    assert result["reports"]


def test_propose_draft_rejects_bad_paths(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))

    session = _make_session(db, superuser)
    bad_cases = {
        "../x": "content",
        "/abs": "content",
        "reports/ventas/../../x": "content",
        "other/file.txt": "content",
        "reports/ventas/extra.txt": "content",
        "integrations/x/queries/../../a.sql": "content",
    }
    for path, content in bad_cases.items():
        with pytest.raises(tools.ToolError) as exc_info:
            run_tool(
                db,
                db.get(AppUser, superuser.id),
                session,
                "propose_draft",
                {"files": {path: content}, "summary": "test"},
                get_settings(),
            )
        assert "integrations/<id>/integration.yaml" in exc_info.value.message

    # 020: the 40-file draft cap became the project limit (test_projects_fs.py).
    too_big = {"reports/big/report.yaml": "x" * (512 * 1024 + 1),     # with a spec: not a probe
               "specs/001-big/spec.md": "# Big\n\n**Tipo**: reporte\n"}
    with pytest.raises(tools.ToolError):
        run_tool(
            db,
            db.get(AppUser, superuser.id),
            session,
            "propose_draft",
            {"files": too_big, "summary": "test"},
            get_settings(),
        )


def _draft_files(open_task: bool) -> dict[str, str]:
    """The draft as v2 project files (feature 020)."""
    return v2_files(_legacy_draft_files(open_task))


def _legacy_draft_files(open_task: bool) -> dict[str, str]:
    report_text = textwrap.dedent(REPORT.format(title="Ventas 2")).lstrip()
    report_text = report_text.replace("id: ventas\n", "id: ventas2\n")
    report_text = report_text.replace(
        "spec: specs/reports/001-ventas\n",
        "spec: specs/reports/002-ventas2\n",
    )
    tasks_text = "- [ ] T001 pendiente\n" if open_task else "- [X] T001 hecho\n"
    return {
        "reports/ventas2/report.yaml": report_text,
        "specs/reports/002-ventas2/spec.md": (
            "# Ventas 2\n\n**Spec type**: report\n\n**Status**: Implemented\n"
        ),
        "specs/reports/002-ventas2/plan.md": "# Plan\n",
        "specs/reports/002-ventas2/tasks.md": tasks_text,
    }


def test_propose_draft_accepts_valid_report(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))

    session = _make_session(db, superuser)
    files = _draft_files(open_task=False)
    result, summary = run_tool(
        db,
        db.get(AppUser, superuser.id),
        session,
        "propose_draft",
        {"files": files, "summary": "Nuevo reporte ventas2"},
        get_settings(),
    )
    assert result["valid"] is True
    assert "4" in summary
    session.refresh()
    assert {p: session.files()[p] for p in files} == files
    assert session.validation["valid"] is True


def test_propose_draft_open_task_fails(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))

    session = _make_session(db, superuser)
    files = _draft_files(open_task=True)
    result, _summary = run_tool(
        db,
        db.get(AppUser, superuser.id),
        session,
        "propose_draft",
        {"files": files, "summary": "Tarea abierta"},
        get_settings(),
    )
    assert result["valid"] is False
    assert result["errors"]
    assert session.validation["valid"] is False


def test_get_authoring_guide_index(db, superuser):
    session = _make_session(db, superuser)
    result, summary = _run(db, superuser, session, "get_authoring_guide", {})
    assert "summary" in result
    assert "Consultó la guía de autoría (index)." in summary


def test_get_authoring_guide_example(db, superuser):
    session = _make_session(db, superuser)
    result, _summary = _run(
        db, superuser, session, "get_authoring_guide", {"topic": "example"}
    )
    assert "files" in result
    assert "project.yaml" in result["files"]       # 020: the example is a v2 project


def test_get_authoring_guide_unknown_topic(db, superuser):
    session = _make_session(db, superuser)
    result, _summary = _run(
        db, superuser, session, "get_authoring_guide", {"topic": "no-existe"}
    )
    assert "error" in result


def test_propose_draft_probe(db, superuser):
    session = _make_session(db, superuser)
    files = {"reports/xx/report.yaml": "id: xx\n"}
    result, summary = _run(
        db, superuser, session, "propose_draft", {"files": files, "summary": "prueba"}
    )
    assert result["probe"] is True
    assert result["stored"] is False
    assert "properties" in result["fragments"]["reports/xx/report.yaml"]
    assert "Prueba" in summary
    session.refresh()
    assert "reports/xx/report.yaml" not in session.files()
    assert session.validation is None
    assert session.stats == {"probes": 1}

    result2, _summary2 = _run(
        db, superuser, session, "propose_draft", {"files": files, "summary": "prueba 2"}
    )
    assert result2["probe"] is True
    session.refresh()
    assert session.stats == {"probes": 2}


def test_propose_draft_with_spec_validations(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))

    session = _make_session(db, superuser)
    files = _draft_files(open_task=True)
    result, _summary = _run(
        db, superuser, session, "propose_draft", {"files": files, "summary": "tarea"}
    )
    assert result["valid"] is False
    for problem in result["errors"]:
        for key in ("entry", "code", "message", "file", "path", "expected", "fix"):
            assert key in problem
    session.refresh()
    assert session.stats == {"validations": 1}
    assert "probes" not in session.stats
    open_task_problem = next(
        p for p in result["errors"] if p.get("code") == "open_tasks" and p.get("file")
    )
    assert open_task_problem["file"].endswith("tasks.md")


def test_propose_draft_not_probe_when_draft_exists(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))

    session = _make_session(db, superuser)
    _run(
        db,
        superuser,
        session,
        "propose_draft",
        {"files": _draft_files(open_task=False), "summary": "primer borrador"},
    )
    session.refresh()
    assert "specs/001-ventas2/spec.md" in session.files()

    files = {"reports/xx/report.yaml": "id: xx\n"}
    result, _summary = _run(
        db, superuser, session, "propose_draft", {"files": files, "summary": "segundo"}
    )
    assert result.get("probe") is not True
    session.refresh()
    assert session.stats == {"validations": 2}


def test_edit_draft_replace_valid(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))

    session = _make_session(db, superuser)
    files = _draft_files(open_task=False)
    _run(
        db,
        superuser,
        session,
        "propose_draft",
        {"files": files, "summary": "primer borrador"},
    )
    result, summary = _run(
        db,
        superuser,
        session,
        "edit_draft",
        {
            "ops": [
                {
                    "op": "replace",
                    "path": "reports/ventas2/report.yaml",
                    "old": "title: Ventas 2",
                    "new": "title: Ventas tres",
                }
            ]
        },
    )
    assert result["valid"] is True
    assert "Editó el borrador" in summary
    session.refresh()
    assert "title: Ventas tres" in session.files()["reports/ventas2/report.yaml"]
    assert session.stats == {"validations": 2}


def test_edit_draft_replace_zero_occurrences(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))

    session = _make_session(db, superuser)
    original = _draft_files(open_task=False)
    _run(
        db,
        superuser,
        session,
        "propose_draft",
        {"files": original, "summary": "primer borrador"},
    )
    with pytest.raises(tools.ToolError) as exc_info:
        _run(
            db,
            superuser,
            session,
            "edit_draft",
            {
                "ops": [
                    {
                        "op": "replace",
                        "path": "reports/ventas2/report.yaml",
                        "old": "no-existe-xyz",
                        "new": "otro",
                    }
                ]
            },
        )
    assert "0 ocurrencias" in exc_info.value.message
    session.refresh()
    assert {p: session.files()[p] for p in original} == original


def test_edit_draft_replace_two_occurrences(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))

    session = _make_session(db, superuser)
    _run(
        db,
        superuser,
        session,
        "propose_draft",
        {"files": _draft_files(open_task=False), "summary": "primer borrador"},
    )
    with pytest.raises(tools.ToolError) as exc_info:
        _run(
            db,
            superuser,
            session,
            "edit_draft",
            {
                "ops": [
                    {
                        "op": "replace",
                        "path": "reports/ventas2/report.yaml",
                        "old": "net_sales",
                        "new": "otro",
                    }
                ]
            },
        )
    assert "ocurrencias" in exc_info.value.message


def test_edit_draft_delete_missing_file(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))

    session = _make_session(db, superuser)
    _run(
        db,
        superuser,
        session,
        "propose_draft",
        {"files": _draft_files(open_task=False), "summary": "primer borrador"},
    )
    with pytest.raises(tools.ToolError):
        _run(
            db,
            superuser,
            session,
            "edit_draft",
            {"ops": [{"op": "delete", "path": "no/existe.yaml"}]},
        )


def test_edit_draft_delete_tasks(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))

    session = _make_session(db, superuser)
    _run(
        db,
        superuser,
        session,
        "propose_draft",
        {"files": _draft_files(open_task=False), "summary": "primer borrador"},
    )
    result, _summary = _run(
        db,
        superuser,
        session,
        "edit_draft",
        {"ops": [{"op": "delete", "path": "specs/001-ventas2/tasks.md"}]},
    )
    assert result["valid"] is False
    session.refresh()
    assert "specs/001-ventas2/tasks.md" not in session.files()


def test_edit_draft_write_bizview_yaml_is_refused(db, superuser, workspace):
    """020: bizview.yaml is composed by the product; a project never holds it."""
    lock(workspace)
    apply(signed_in("root@example.com"))

    session = _make_session(db, superuser)
    _run(
        db,
        superuser,
        session,
        "propose_draft",
        {"files": _draft_files(open_task=False), "summary": "primer borrador"},
    )
    with pytest.raises(tools.ToolError):
        _run(db, superuser, session, "edit_draft",
             {"ops": [{"op": "write", "path": "bizview.yaml", "content": "name: otro\n"}]})
    assert "bizview.yaml" not in session.files()


def test_edit_draft_write_bad_path(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))

    session = _make_session(db, superuser)
    _run(
        db,
        superuser,
        session,
        "propose_draft",
        {"files": _draft_files(open_task=False), "summary": "primer borrador"},
    )
    with pytest.raises(tools.ToolError) as exc_info:
        _run(
            db,
            superuser,
            session,
            "edit_draft",
            {"ops": [{"op": "write", "path": "other/x.txt", "content": "x"}]},
        )
    assert "integrations/<id>/integration.yaml" in exc_info.value.message


def test_edit_draft_write_too_big(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))

    session = _make_session(db, superuser)
    _run(
        db,
        superuser,
        session,
        "propose_draft",
        {"files": _draft_files(open_task=False), "summary": "primer borrador"},
    )
    with pytest.raises(tools.ToolError):
        _run(
            db,
            superuser,
            session,
            "edit_draft",
            {
                "ops": [
                    {
                        "op": "write",
                        "path": "reports/ventas2/report.yaml",
                        "content": "x" * (512 * 1024 + 1),
                    }
                ]
            },
        )


def test_edit_draft_on_a_new_project_refuses_bad_paths(db, superuser):
    session = _make_session(db, superuser)
    with pytest.raises(tools.ToolError) as exc_info:
        _run(db, superuser, session, "edit_draft",
             {"ops": [{"op": "write", "path": "bizview.yaml", "content": "x"}]})
    assert "integrations/<id>/integration.yaml" in exc_info.value.message


def test_edit_draft_atomic(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))

    session = _make_session(db, superuser)
    original = _draft_files(open_task=False)
    _run(
        db,
        superuser,
        session,
        "propose_draft",
        {"files": original, "summary": "primer borrador"},
    )
    with pytest.raises(tools.ToolError):
        _run(
            db,
            superuser,
            session,
            "edit_draft",
            {
                "ops": [
                    {"op": "write", "path": "specs/001-ventas2/plan.md",
                     "content": "# Otro plan\n"},
                    {
                        "op": "replace",
                        "path": "reports/ventas2/report.yaml",
                        "old": "no-existe-xyz",
                        "new": "a",
                    },
                ]
            },
        )
    session.refresh()
    assert {p: session.files()[p] for p in original} == original


def test_read_draft_basic(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))

    session = _make_session(db, superuser)
    files = _draft_files(open_task=False)
    _run(
        db,
        superuser,
        session,
        "propose_draft",
        {"files": files, "summary": "primer borrador"},
    )
    result, summary = _run(
        db,
        superuser,
        session,
        "read_draft",
        {"paths": ["reports/ventas2/report.yaml", "no/existe.md"]},
    )
    assert result["files"]["reports/ventas2/report.yaml"] == files[
        "reports/ventas2/report.yaml"
    ]
    assert result["missing"] == ["no/existe.md"]
    assert result["truncated"] == []
    assert "reports/ventas2/report.yaml" in result["available"]
    assert "Leyó 1" in summary


def test_read_draft_truncation(db, superuser):
    session = project_view(db, superuser.id, {
        "reports/aa/report.yaml": "a" * 50_000,
        "reports/bb/report.yaml": "b" * 50_000,
        "reports/cc/report.yaml": "c",
    })

    result, _summary = _run(
        db,
        superuser,
        session,
        "read_draft",
        {
            "paths": [
                "reports/aa/report.yaml",
                "reports/bb/report.yaml",
                "reports/cc/report.yaml",
            ]
        },
    )
    total = sum(len(v) for v in result["files"].values())
    assert total <= tools.MAX_TOOL_RESULT_CHARS
    assert "reports/aa/report.yaml" in result["files"]
    assert "reports/bb/report.yaml" in result["files"]
    assert len(result["files"]["reports/bb/report.yaml"]) < 50_000
    assert "reports/bb/report.yaml" in result["truncated"]
    assert "reports/cc/report.yaml" not in result["files"]
    assert "reports/cc/report.yaml" in result["truncated"]


def test_workspace_name_slug(db, superuser, monkeypatch):
    monkeypatch.setattr(get_settings(), "organization_name", "Cliente Demo")
    assert workspace_name() == "cliente-demo"
    monkeypatch.setattr(get_settings(), "organization_name", "")
    assert workspace_name() == "bizview"
    monkeypatch.setattr(get_settings(), "organization_name", "Ñandú 2026 S.A.")
    assert workspace_name() == "nandu-2026-s-a"
    monkeypatch.setattr(get_settings(), "organization_name", "123")
    assert workspace_name() == "bizview"


# The 017 draft tree helpers (build_tree, validate_draft, materialize) were replaced by the 020
# project composition (test_projects_compose*.py); the manifest template is still used by it.
def test_bootstrap_manifest_names_the_organization(monkeypatch):
    monkeypatch.setattr(get_settings(), "organization_name", "Cliente Demo")
    assert yaml.safe_load(bootstrap_manifest())["name"] == "cliente-demo"


def test_bootstrap_manifest_empty_org(monkeypatch):
    monkeypatch.setattr(get_settings(), "organization_name", "")
    assert yaml.safe_load(bootstrap_manifest())["name"] == "bizview"


def test_propose_draft_new_report_without_specs_is_still_probe(db, superuser, workspace):
    lock(workspace)
    apply(signed_in("root@example.com"))

    session = _make_session(db, superuser)
    result, _ = _run(db, superuser, session, "propose_draft",
                     {"files": {"reports/otro/report.yaml": "id: otro\n"}, "summary": "s"})
    assert result["probe"] is True


def _edited_integration():
    doc = yaml.safe_load(textwrap.dedent(integration_yaml()).lstrip())
    doc["datasets"]["products"]["checks"] = [{"type": "row_count", "min": 1}]
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)

def test_suggest_command_keeps_the_button_short():
    """A full brief in `arguments` makes an unreadable button: the detail belongs in the reply."""
    class Session:
        working_state: dict = {}

    limit = tools.MAX_SUGGESTION_ARGUMENTS
    result, _ = tools._suggest_command(Session(), {"command": "speckit-specify",
                                                   "arguments": "x" * limit})
    assert result["suggested"] == f"/speckit-specify {'x' * limit}"

    with pytest.raises(tools.ToolError):
        tools._suggest_command(Session(), {"command": "speckit-specify",
                                           "arguments": "x" * (limit + 1)})
