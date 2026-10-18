"""Feature 021 T004: tools and writable paths per command (pure, no DB)."""
import pytest

from app.assistant.commands.guard import (
    CONSTITUTION,
    Context,
    GuardError,
    allowed_tools,
    check_ops,
    check_tool,
    installation_block,
    protected_block,
)
from app.assistant.commands.registry import REGISTRY

BLOCK = "<!-- bizview:reglas-instalacion -->\nreglas\n<!-- /bizview:reglas-instalacion -->"


def ctx(command, *, spec="003-ventas", kind=None, reserved=None, plan="", files=None):
    return Context(REGISTRY[command], spec, kind, reserved, plan, BLOCK, files or {})


def w(path, content="x"):
    return {"op": "write", "path": path, "content": content}


def refused(context, *ops):
    with pytest.raises(GuardError) as exc:
        check_ops(context, list(ops))
    assert exc.value.code == "path_not_allowed"
    return exc.value


def test_tools_per_mode():
    with pytest.raises(GuardError) as exc:
        check_tool(None, "edit_draft")
    assert exc.value.code == "write_needs_command"
    check_tool(None, "suggest_command")
    check_tool(None, "describe_source")
    check_tool(REGISTRY["speckit-plan"], "edit_draft")
    check_tool(REGISTRY["speckit-plan"], "finish_command")
    for definition, tool in ((REGISTRY["speckit-analyze"], "edit_draft"), (None, "finish_command"),
                             (REGISTRY["speckit-plan"], "run_preview")):
        with pytest.raises(GuardError) as exc:
            check_tool(definition, tool)
        assert exc.value.code == "tool_not_allowed"
    assert "check_query" in allowed_tools(REGISTRY["speckit-implement"])
    assert "suggest_command" not in allowed_tools(REGISTRY["speckit-implement"])


def test_constitution_block_is_protected():
    c = ctx("speckit-constitution", spec=None)
    assert protected_block(f"x\n{BLOCK}\ny") == BLOCK
    check_ops(c, [w(CONSTITUTION, f"# Nueva\n\n{BLOCK}\n\nOtros principios\n")])
    refused(c, w(CONSTITUTION, BLOCK.replace("reglas", "sin reglas")))
    refused(c, w(CONSTITUTION, "# sin bloque\n"))
    refused(c, w("specs/001-a/spec.md"))


def test_constitution_keeps_the_installation_template_block():
    """021 T052: the block is the template's, so a project file without it cannot drop it."""
    tpl = installation_block()
    assert tpl.startswith("<!-- bizview:reglas-instalacion -->")
    assert tpl.endswith("<!-- /bizview:reglas-instalacion -->") and "read-only" in tpl
    c = Context(REGISTRY["speckit-constitution"], None, None, None, "", tpl,
                {CONSTITUTION: "# Proyecto sin bloque\n"})
    check_ops(c, [w(CONSTITUTION, f"# Proyecto\n\n{tpl}\n\nOtros principios\n")])
    refused(c, w(CONSTITUTION, "# Proyecto\n\nSolo mis reglas\n"))
    refused(c, w(CONSTITUTION, f"# Proyecto\n\n{BLOCK}\n"))
    no_template = Context(REGISTRY["speckit-constitution"], None, None, None, "", "", {})
    refused(no_template, w(CONSTITUTION, "# Proyecto\n"))


def test_specify_new_folder_only():
    c = ctx("speckit-specify", spec=None, reserved=4, files={"specs/003-old/spec.md": "x"})
    assert check_ops(c, [w("specs/004-ventas/spec.md"),
                         w("specs/004-ventas/checklists/requirements.md")]) == "004-ventas"
    refused(c, w("specs/005-x/spec.md"))
    refused(c, w("specs/004-ventas/spec.md"), w("specs/004-clientes/spec.md"))
    refused(c, w("specs/004-a-b-c-d-e-f-g/spec.md"))
    refused(c, w("specs/004-ventas/plan.md"))
    taken = ctx("speckit-specify", spec=None, reserved=4, files={"specs/004-ventas/spec.md": "x"})
    refused(taken, w("specs/004-ventas/spec.md"))
    # Later calls of the same run: the folder exists and is the run's spec.
    later = ctx("speckit-specify", spec="004-ventas", reserved=4,
                files={"specs/004-ventas/spec.md": "x"})
    assert check_ops(later, [w("specs/004-ventas/spec.md", "y")]) is None
    refused(later, w("specs/004-otra/spec.md"))


def test_clarify_spec_and_checklist_toggles():
    req = "specs/003-ventas/checklists/requirements.md"
    c = ctx("speckit-clarify", files={req: "# Lista\n- [ ] CHK001 a\n- [x] CHK002 b\n"})
    check_ops(c, [w("specs/003-ventas/spec.md")])
    check_ops(c, [w(req, "# Lista\n- [X] CHK001 a\n- [ ] CHK002 b\n")])
    refused(c, w(req, "# Lista\n- [ ] CHK001 cambiado\n- [x] CHK002 b\n"))
    refused(c, w(req, "# Lista\n- [ ] CHK001 a\n"))
    refused(c, w("specs/003-ventas/plan.md"))
    refused(c, {"op": "delete", "path": "specs/003-ventas/spec.md"})


def test_plan_tasks_and_converge():
    check_ops(ctx("speckit-plan"), [w("specs/003-ventas/plan.md"),
                                    w("specs/003-ventas/data-model.md")])
    refused(ctx("speckit-plan"), w("specs/003-ventas/tasks.md"))
    check_ops(ctx("speckit-tasks"), [w("specs/003-ventas/tasks.md")])
    tasks = "specs/003-ventas/tasks.md"
    conv = ctx("speckit-converge", files={tasks: "- [X] T001 a"})
    check_ops(conv, [w(tasks, "- [X] T001 a\n\n## Phase 2: Convergence\n- [ ] T002 b\n")])
    refused(conv, w(tasks, "- [ ] T001 a\n"))
    refused(ctx("speckit-analyze"), w("specs/003-ventas/plan.md"))


def test_implement_ticks_status_and_artifacts():
    tasks, spec = "specs/003-ventas/tasks.md", "specs/003-ventas/spec.md"
    files = {tasks: "# T\n- [ ] T001 a\n- [ ] T002 b\n",
             spec: "# Ventas\n**Tipo**: reporte\n**Status**: Approved\n",
             "reports/ventas/report.yaml": "id: ventas\n"}
    c = ctx("speckit-implement", kind="reporte", files=files)
    check_ops(c, [w(tasks, "# T\n- [X] T001 a\n- [ ] T002 b\n")])
    refused(c, w(tasks, "# T\n- [X] T001 cambio\n- [ ] T002 b\n"))
    refused(c, w(tasks, "# T\n- [X] T001 a\n- [ ] T002 b\n- [ ] T003 c\n"))
    check_ops(c, [w(spec, "# Ventas\n**Tipo**: reporte\n**Status**: Implemented\n")])
    refused(c, w(spec, "# Ventas\n**Tipo**: reporte\n**Status**: Draft\n"))
    refused(c, w(spec, "# Otro\n**Tipo**: reporte\n**Status**: Implemented\n"))
    check_ops(c, [w("reports/ventas/report.yaml"),
                  {"op": "delete", "path": "reports/ventas/report.yaml"}])
    refused(c, w("reports/otro/report.yaml"))
    refused(c, w("integrations/ventas/integration.yaml"))
    refused(c, {"op": "delete", "path": "specs/003-ventas/plan.md"})
    with_plan = ctx("speckit-implement", kind="reporte", files=files,
                    plan="Crea `reports/otro/report.yaml` y `distributions/envio.yaml`.")
    check_ops(with_plan, [w("reports/otro/report.yaml")])
    integ = ctx("speckit-implement", kind="integracion",
                files={"integrations/ventas/queries/a.sql": "x"})
    check_ops(integ, [w("integrations/ventas/integration.yaml"),
                      w("integrations/ventas/queries/b.sql"),
                      {"op": "delete", "path": "integrations/ventas/queries/a.sql"}])
    refused(integ, {"op": "delete", "path": "integrations/ventas/queries/missing.sql"})
    refused(ctx("speckit-implement", kind="fuente"), w("integrations/ventas/integration.yaml"))


def test_custom_checklists_are_append_only():
    path = "specs/003-ventas/checklists/seguridad.md"
    c = ctx("speckit-checklist", files={path: "- [ ] CHK001 a\n"})
    check_ops(c, [w("specs/003-ventas/checklists/datos.md")])
    check_ops(c, [w(path, "- [ ] CHK001 a\n- [ ] CHK002 b\n")])
    refused(c, w(path, "- [ ] CHK001 otro\n"))
    refused(c, w("specs/003-ventas/checklists/requirements.md"))


def test_refusal_names_the_path_and_the_allowed_patterns():
    err = refused(ctx("speckit-clarify"), w("specs/003-ventas/plan.md"))
    assert err.params["path"] == "specs/003-ventas/plan.md"
    assert err.params["command"] == "speckit-clarify"
    assert "specs/003-ventas/spec.md" in err.params["allowed"]
    assert "specs/003-ventas/plan.md" in str(err)
