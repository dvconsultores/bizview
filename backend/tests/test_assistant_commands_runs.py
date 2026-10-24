"""Command runs (feature 021 T029/T030): end-of-turn mapping, gates, preflight, resume."""
from types import SimpleNamespace

from app.assistant.commands import runs
from app.assistant.commands.registry import REGISTRY
from app.i18n import use_locale
from app.projects.history import sha

SPEC = "003-x"


def _run(**kwargs):
    fields = {"status": "running", "pending": {"x": 1}, "error": None, "ended_at": None,
              "tokens": 0, "files": [], "result": None, "resumed_from": None}
    fields.update(kwargs)
    return SimpleNamespace(**fields)


def test_end_from_activity_mapping():
    plan, clarify = REGISTRY["speckit-plan"], REGISTRY["speckit-clarify"]
    for activity, expected in (("ready", "completed"), ("done", "completed"),
                               ("stopped", "interrupted"), ("budget", "budget"),
                               ("limit", "interrupted")):
        run = _run()
        runs.end_from_activity(run, activity, plan)
        assert (run.status, run.pending) == (expected, None)
        assert run.ended_at is not None

    run = _run()
    runs.end_from_activity(run, "done", clarify)
    assert (run.status, run.pending, run.ended_at) == ("waiting", {"x": 1}, None)

    run = _run()
    runs.end_from_activity(run, "done", clarify, finished=True)
    assert run.status == "completed"

    run = _run()
    runs.end_from_activity(run, "error", plan, error="ai_timeout")
    assert (run.status, run.error) == ("failed", "ai_timeout")
    run = _run()
    runs.end_from_activity(run, "error", plan)
    assert run.error == "error"

    run = _run()
    runs.end_from_activity(run, "running", plan)
    assert (run.status, run.ended_at) == ("running", None)

    run = _run(status="waiting")
    runs.end_from_activity(run, "error", plan)
    assert (run.status, run.ended_at) == ("waiting", None)


def test_answer():
    for text in ("sí", "Si, dale", "yes please", "OK", "continúa"):
        assert runs.answer(text) == "yes", text
    for text in ("no", "No gracias", "cancelar"):
        assert runs.answer(text) == "no", text
    # The owner's third answer (2026-10-24): have the checklist completed instead of skipped.
    for text in ("arregla", "Arréglalas por favor", "corrige la spec", "completa las listas",
                 "marca lo que falte", "fix it", "fix them", "complete the checklist"):
        assert runs.answer(text) == "fix", text
    for text in ("B", "tal vez", "nosotros", "ya veremos"):
        assert runs.answer(text) is None, text


def test_the_checklist_gate_offers_the_fix_answer():
    implement = REGISTRY["speckit-implement"]
    files = {f"specs/{SPEC}/spec.md": "**Status**: Approved\n",
             f"specs/{SPEC}/plan.md": "plan", f"specs/{SPEC}/tasks.md": "tasks",
             f"specs/{SPEC}/checklists/requirements.md": "- [x] a\n- [ ] b\n"}
    with use_locale("es"):
        message = runs.preflight(implement, SPEC, files).message
        assert "arregla" in message and "sí" in message and "no" in message
    with use_locale("en"):
        message = runs.preflight(implement, SPEC, files).message
        assert "fix" in message and "yes" in message and "no" in message


def test_only_clarify_may_toggle_the_requirement_checklist():
    """The gate hand-off depends on it: implement cannot tick what clarify owns."""
    owners = [name for name, definition in REGISTRY.items()
              if "req_checklist_toggle" in definition.writes]
    assert owners == ["speckit-clarify"]


def test_spec_status_and_approved_text():
    original = "# T\n\n**Status**: Draft\nBody\n"
    assert runs.spec_status(original) == "Draft"
    assert runs.approved_text(original) == "# T\n\n**Status**: Approved\nBody\n"
    assert runs.spec_status("# Title\nSome text\n") is None
    assert (runs.approved_text("# Title\nSome text\n")
            == "# Title\n**Status**: Approved\nSome text\n")
    assert runs.approved_text("Just text\n") == "**Status**: Approved\nJust text\n"

    ops = runs.approve_ops(SPEC, {f"specs/{SPEC}/spec.md": original})
    assert ops == [{"op": "write", "path": f"specs/{SPEC}/spec.md",
                    "content": runs.approved_text(original), "base_sha256": sha(original)}]


def test_checklist_table():
    base = f"specs/{SPEC}/checklists/"
    files = {base + "requirements.md": "- [x] CHK001 a\n- [X] CHK002 b\n",
             base + "security.md": "- [x] CHK001 a\n- [ ] CHK002 b\n- [x] CHK003 c\n"}
    table = runs.checklist_table(SPEC, files)
    assert "| requirements.md | 2 | 2 | 0 |" in table
    assert "| security.md | 3 | 2 | 1 |" in table
    files[base + "security.md"] = "- [x] CHK001 a\n"
    assert runs.checklist_table(SPEC, files) == ""


def test_preflight():
    plan, tasks = REGISTRY["speckit-plan"], REGISTRY["speckit-tasks"]
    implement = REGISTRY["speckit-implement"]
    with use_locale("es"):
        result = runs.preflight(plan, SPEC, {})
        assert (result.missing, result.command) == ("spec.md", "speckit-specify")
        assert "/speckit-specify" in result.message and result.pending is None
        assert runs.preflight(plan, None, {}).missing == "spec.md"

        files = {f"specs/{SPEC}/spec.md": "**Status**: Approved\n"}
        assert runs.preflight(implement, SPEC, files).command == "speckit-tasks"

        files = {f"specs/{SPEC}/spec.md": "x [NEEDS CLARIFICATION: y]\n",
                 f"specs/{SPEC}/plan.md": "plan"}
        assert runs.preflight(tasks, SPEC, files).pending["gate"] == "open_clarifications"

        files = {f"specs/{SPEC}/spec.md": "**Status**: Draft\n",
                 f"specs/{SPEC}/plan.md": "plan", f"specs/{SPEC}/tasks.md": "tasks",
                 f"specs/{SPEC}/checklists/security.md": "- [ ] CHK001 a\n"}
        result = runs.preflight(implement, SPEC, files)
        assert result.pending["gates"] == ["unchecked_checklists", "approve_spec"]
        assert "security.md" in result.message

        files[f"specs/{SPEC}/spec.md"] = "**Status**: Approved\n"
        del files[f"specs/{SPEC}/checklists/security.md"]
        assert runs.preflight(implement, SPEC, files) == runs.Preflight()


def test_advance():
    run = _run(status="waiting",
               pending={"gates": ["unchecked_checklists", "approve_spec"],
                        "gate": "unchecked_checklists", "table": "t", "status": "Draft"})
    with use_locale("es"):
        message = runs.advance(run)
        assert run.pending["gate"] == "approve_spec"
        assert "Draft" in message
        assert runs.advance(run) is None
    assert (run.pending, run.status) == (None, "running")


def test_the_gate_names_where_the_auto_switch_is():
    """A gate the user has to answer says how to stop answering gates (the Auto contract)."""
    pending = {"gates": ["unchecked_checklists"], "gate": "unchecked_checklists",
               "table": "| requirements.md | 16 | 15 | 1 |", "status": "Draft"}
    with use_locale("es"):
        hint = runs.t("commands.auto_hint")
        plain = runs.gate_message(pending)
        hinted = runs.gate_message(pending, hint=hint)
        assert "Auto" in hint      # the switch is named by the label the composer shows
        assert hinted == f"{plain}\n\n{hint}"
        assert plain in hinted
        # a "yes" that lands on the next gate carries the same line
        run = _run(status="waiting",
                   pending={"gates": ["unchecked_checklists", "approve_spec"],
                            "gate": "unchecked_checklists", "table": "t", "status": "Draft"})
        assert runs.advance(run, hint=hint).endswith(hint)
    with use_locale("en"):
        assert "Auto" in runs.t("commands.auto_hint")


def test_add_file_and_tokens():
    run = _run()
    runs.add_file(run, "a.md", "write", 1)
    first = run.files
    runs.add_file(run, "b.md", "create", None)
    assert run.files is not first
    assert run.files == [{"path": "a.md", "action": "write", "revision_id": 1},
                         {"path": "b.md", "action": "create", "revision_id": None}]
    runs.add_tokens(run, 5)
    runs.add_tokens(run, -10)
    assert run.tokens == 5


def test_resume_info():
    class FakeDB:
        def __init__(self, rows):
            self.rows = rows

        def get(self, _model, key):
            return self.rows.get(key)

    one = _run(status="interrupted", files=[{"path": "b"}, {"path": "c"}], resumed_from=3)
    two = _run(status="interrupted", files=[{"path": "a"}, {"path": "b"}], resumed_from=1)
    three = _run(status="interrupted", files=[], resumed_from=2)
    db = FakeDB({1: one, 2: two, 3: three})
    assert runs.resume_info(db, three, "n") == {"files": ["a", "b", "c"], "notes": "n"}
    one.status = "completed"
    assert runs.resume_info(db, three, None) == {"files": ["a", "b"], "notes": ""}
    assert runs.resume_info(db, _run(), None) is None
