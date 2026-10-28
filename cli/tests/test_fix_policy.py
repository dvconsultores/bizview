"""Feature 040 (B): a fix changes content, never evidence.

The 039 validator answered an open task with «marca todas las tareas como - [X]» (and the English
«mark every task as - [X]»), which turns an unfinished task into a finished one without doing the
work. This test enumerates the deterministic fixes the product registers and the fix messages of
both catalogues, and refuses any that touches a checkbox or a `**Status**:` line.
"""
from __future__ import annotations

from bizview_cli import fixops
from bizview_cli.i18n import en, es, t
from bizview_cli.validate import OPEN_TASK_ID_RE, validate
from tests.conftest import spec_folder


def test_the_registry_lists_every_deterministic_fix():
    codes = {fix.code for fix in fixops.DETERMINISTIC_FIXES}
    assert {"unjoined_sets", "schedule_missing", "label_missing", "view_type_unknown",
            "invalid_reference", "layout_palette_missing", "layout_filter_missing"} <= codes
    # The two that changed evidence are gone for good: no fix ticks a task, no fix approves a spec.
    assert not codes & {"open_tasks", "spec_not_approved", "spec_incomplete"}


def test_no_fix_message_touches_a_checkbox_or_a_status_line():
    for locale, catalogue in (("es", es.MESSAGES), ("en", en.MESSAGES)):
        for key, text in catalogue.items():
            if not key.startswith("validate.fix"):
                continue
            assert not fixops.FORBIDDEN_FIX_TEXT.search(text), f"{locale}:{key} → {text}"


def test_the_open_tasks_problem_points_to_the_honest_action(ws):
    spec_folder(ws, "integration", "001-ventas", open_task=True)
    result = validate(ws)
    problem = next(i for i in result.issues if i.code == "open_tasks")
    assert problem.fix_data is None
    assert "/speckit-implement" in str(problem.fix)
    assert "--only T002" in str(problem.fix)
    assert not fixops.FORBIDDEN_FIX_TEXT.search(str(problem.fix))


def test_is_content_fix_refuses_a_status_or_task_edit():
    assert fixops.is_content_fix({"file": "reports/r/report.yaml", "json_path": "/joins",
                                  "op": "append", "value": {}})
    assert not fixops.is_content_fix({"file": "specs/001-x/spec.md", "json_path": "/status",
                                      "op": "set", "value": "Implemented"})
    assert not fixops.is_content_fix({"file": "specs/001-x/tasks.md", "json_path": "/tasks/0",
                                      "op": "set", "value": "[X] T001"})
    assert not fixops.is_content_fix({"file": "reports/r/report.yaml", "json_path": "/title",
                                      "op": "set", "value": "- [X] done"})


def test_the_task_id_pattern_reads_the_open_boxes():
    text = "- [ ] T025 mapear `x`\n- [X] T026 hecho\n- [ ] T027 otra\n"
    assert OPEN_TASK_ID_RE.findall(text) == ["T025", "T027"]
    message = t("validate.fix_tasks_implement", spec="specs/001-x", tasks="T025")
    assert "/speckit-implement specs/001-x --only T025" in message
