"""Feature 039: `/speckit-all` — plan order, resume detection, decisions guard and the report.

The unit half needs no database and no provider: the pipeline is a pure plan over what the
artifacts and the stored cursor say.
"""
import pytest

from app.assistant.commands import guard, pipeline, registry
from app.errors import ApiError

# --------------------------------------------------------------------------- arguments

def test_parse_args_strips_flags():
    args = pipeline.parse_args("Tablero de facturas por día --until tasks")
    assert (args.text, args.until, args.force) == ("Tablero de facturas por día", "tasks", False)
    assert pipeline.parse_args("002-ventas --force").force is True
    assert pipeline.parse_args("002-ventas --until=verify").until == "verify"
    assert pipeline.parse_args("--unTil Converge 002-ventas").until == "converge"
    assert pipeline.parse_args("").text == ""


@pytest.mark.parametrize("argument", ["--until nope", "--until", "--until 3"])
def test_parse_args_refuses_an_unknown_stage(argument):
    with pytest.raises(ApiError) as exc:
        pipeline.parse_args(f"002-ventas {argument}")
    assert (exc.value.status, exc.value.code) == (422, "until_invalid")
    assert exc.value.extra["stages"] == list(pipeline.STAGES)


def test_stage_list_is_the_contract():
    assert pipeline.STAGES == ("specify", "clarify", "plan", "tasks", "analyze", "implement",
                              "converge", "verify")
    assert pipeline.TOTAL == 8
    assert pipeline.STAGE_COMMANDS["verify"] == "speckit-verify"
    assert registry.REGISTRY["speckit-all"].writes == ("run_report", "decisions_append")
    assert registry.REGISTRY["speckit-verify"].writes == ()


# --------------------------------------------------------------------------- the plan

def _facts(stage="tareas", files=None, **kwargs):
    files = files if files is not None else {
        "specs/002-x/spec.md": "# X\n\n**Tipo**: reporte\n", "specs/002-x/plan.md": "p",
        "specs/002-x/tasks.md": "t"}
    return pipeline.Facts(row={"stage": stage}, files=files, clarified=True, **kwargs)


def test_completed_needs_every_earlier_stage():
    facts = _facts(stage="tareas", converged=False, validation_ok=True, preview_ok=True,
                   cursor=0)
    done = pipeline.completed("002-x", facts)
    assert done == {"specify", "clarify", "plan", "tasks"}


def test_completed_implemented_runs_through_verify():
    done = pipeline.completed("002-x", _facts(stage="implementada", converged=False,
                                              validation_ok=True, preview_ok=True, cursor=8))
    assert set(pipeline.STAGES) == done
    # A converge that left open tasks is not complete; an applied spec is.
    assert "converge" not in pipeline.completed(
        "002-x", _facts(stage="implementada", converged=True, validation_ok=True,
                        preview_ok=True, cursor=8))


def test_completed_is_empty_without_a_spec():
    assert pipeline.completed("002-x", _facts(files={})) == set()


def test_advance_walks_specs_then_finishes():
    state = pipeline.seed(1, None, ["001-int", "002-report"])
    state = pipeline.advance(state, 0, 7)
    assert (state["spec_index"], state["cursor"]) == (1, 0)
    state = pipeline.advance(state, 1, 7)
    assert (state["spec_index"], state["cursor"]) == (1, 8)
    assert pipeline.finished(state)
    assert pipeline.ends_here(state)
    assert pipeline.open_stage(state) is None


def test_until_bounds_the_plan():
    state = pipeline.seed(1, pipeline.parse_args("x --until tasks"), ["002-x"])
    for _ in range(4):
        at = pipeline.next_position(state)
        assert at is not None
        state = pipeline.advance(state, *at)
    assert pipeline.next_position(state) is None
    assert pipeline.ends_here(state)


def test_detect_resumes_at_the_first_incomplete_stage():
    facts = {"002-x": _facts(stage="tareas", converged=False)}
    state = pipeline.detect(pipeline.seed(None, None, ["002-x"]), facts)
    assert pipeline.open_stage(state) == ("002-x", "analyze")
    forced = pipeline.seed(None, pipeline.parse_args("x --force"), ["002-x"])
    assert pipeline.open_stage(forced) == ("002-x", "specify")


def test_ordered_specs_puts_the_integration_first():
    rows = [{"folder": "003-report", "kind": "reporte", "number": 3},
            {"folder": "002-int", "kind": "integracion", "number": 2},
            {"folder": "001-int", "kind": "integracion", "number": 1}]
    assert pipeline.ordered_specs(rows) == ["001-int", "002-int", "003-report"]


def test_position_is_what_the_status_bar_reads():
    state = pipeline.advance(pipeline.seed(7, None, ["002-x"]), 0, 2)
    assert pipeline.position(state) == {"id": 7, "cursor": 3, "total": 8, "stage": "tasks",
                                        "until": None, "spec": "002-x", "spec_index": 0}


# --------------------------------------------------------------------------- decisions

SPEC_WITH_DECISIONS = (
    "# Spec\n\nCuerpo.\n\n"
    f"{pipeline.DECISIONS_HEADING}\n\n"
    "- [clarify] Se agrupa por día — es el orden de las historias.\n"
    "- [plan] Reusa el dataset existente — no añade una consulta.\n"
)


def test_decisions_are_read_back_verbatim():
    lines = pipeline.decisions_block(SPEC_WITH_DECISIONS)
    assert lines == ["- [clarify] Se agrupa por día — es el orden de las historias.",
                     "- [plan] Reusa el dataset existente — no añade una consulta."]
    assert pipeline.without_decisions(SPEC_WITH_DECISIONS) == "# Spec\n\nCuerpo."
    assert pipeline.is_decision(lines[0])
    assert not pipeline.is_decision("- [nope] algo — porqué")
    assert not pipeline.is_decision("texto suelto")


def _ctx(files, spec="002-x"):
    return guard.Context(definition=registry.REGISTRY["speckit-all"], spec=spec, kind=None,
                         reserved_number=None, plan_text="", installation_block="", files=files)


def test_guard_allows_only_an_appended_decision():
    files = {"specs/002-x/spec.md": SPEC_WITH_DECISIONS}
    allowed = SPEC_WITH_DECISIONS + "- [tasks] Una fase por dataset — lo pide el plan.\n"
    assert guard.check_ops(_ctx(files), [{"op": "write", "path": "specs/002-x/spec.md",
                                          "content": allowed}]) is None

    for refused in (
        SPEC_WITH_DECISIONS.replace("día", "día y hora"),          # changed a decision
        SPEC_WITH_DECISIONS.replace("Cuerpo.", "Otro cuerpo."),     # changed the spec
        allowed + "- línea sin etapa — sin porqué\n",               # not a decision line
        allowed.replace("- [tasks]", "- [inventada]"),              # unknown stage
    ):
        with pytest.raises(guard.GuardError) as exc:
            guard.check_ops(_ctx(files), [{"op": "write", "path": "specs/002-x/spec.md",
                                           "content": refused}])
        assert exc.value.code == "path_not_allowed"


def test_guard_allows_the_run_report_of_the_spec():
    files = {"specs/002-x/spec.md": SPEC_WITH_DECISIONS}
    assert guard.check_ops(_ctx(files), [{"op": "write", "path": "specs/002-x/run-report.md",
                                          "content": "# Run report\n"}]) is None
    with pytest.raises(guard.GuardError):
        guard.check_ops(_ctx(files), [{"op": "write", "path": "reports/x/report.yaml",
                                       "content": "id: x\n"}])


# --------------------------------------------------------------------------- report

def test_report_is_deterministic_and_names_what_is_pending():
    state = pipeline.seed(12, None, ["002-x"])
    rows = [{"stage": "specify", "run_id": 4, "status": "completed",
             "files": [{"path": "specs/002-x/spec.md"}]},
            {"stage": "verify", "run_id": 9, "status": "completed", "files": []}]
    verdict = {"ok": True, "checks": [{"check": "validation", "ok": True, "detail": ""}],
               "stories": [{"story": "US1", "ok": True, "test": "row counts"}]}
    first = pipeline.report_markdown(spec="002-x", state=state, rows=rows,
                                     decisions_lines=pipeline.decisions_block(SPEC_WITH_DECISIONS),
                                     verify_result=verdict, result="ready", stop=None,
                                     tokens=1500, started=None, ended=None)
    second = pipeline.report_markdown(spec="002-x", state=state, rows=rows,
                                      decisions_lines=pipeline.decisions_block(SPEC_WITH_DECISIONS),
                                      verify_result=verdict, result="ready", stop=None,
                                      tokens=1500, started=None, ended=None)
    assert first == second
    assert "## Stages" in first and "| 2 | verify | 9 | completed | — |" in first
    assert "- [clarify] Se agrupa por día — es el orden de las historias." in first
    assert "| US1 Independent Test | pass | row counts |" in first
    assert "## Pendiente para el humano" in first
    # Nothing pending, nothing said: SC-003.
    stopped = pipeline.report_markdown(spec="002-x", state=state, rows=rows, decisions_lines=[],
                                       verify_result=None, result="stopped", stop="limit:tokens",
                                       tokens=0, started=None, ended=None)
    assert "## Pendiente para el humano" not in stopped
    assert "**Result**: stopped · limit:tokens" in stopped


def test_stories_are_read_from_the_spec():
    text = ("## User Scenarios\n\n### User Story 1 - One command (Priority: P1) 🎯\n\n"
            "**Independent Test**: the replay reaches ready.\n\n"
            "### User Story 4 - Verify (Priority: P2)\n\n"
            "**Independent Test**: one check per file.\n")
    assert pipeline.stories(text) == [
        {"story": "US1", "title": "One command", "test": "the replay reaches ready."},
        {"story": "US4", "title": "Verify", "test": "one check per file."}]


def test_a_plan_without_specs_offers_only_specify():
    """The first stage creates the spec, so before it the plan owns no spec at all."""
    state = pipeline.seed(1, pipeline.parse_args("x --until tasks"), [])
    assert pipeline.next_position(state) == (0, 0)
    assert pipeline.open_stage(state) == (None, "specify")
    # With no spec the plan cannot move past the stage that creates it; the runner grows the
    # spec list from the specify run before asking again.
    assert pipeline.next_position(pipeline.advance(state, 0, 0)) is None
    grown = {**state, "specs": ["001-int"]}
    assert pipeline.open_stage(pipeline.advance(grown, 0, 0)) == ("001-int", "clarify")


# --------------------------------------------------------------------------- resume, per stage

DONE_DOCS = ["spec.md", "plan.md", "tasks.md"]


def _resume_case(stage, files, row_stage, *, clarified=True, converged=False,
                 validation_ok=False, preview_ok=True, passed=0):
    facts = {"002-x": pipeline.Facts(row={"stage": row_stage}, files=files,
                                     clarified=clarified, converged=converged,
                                     validation_ok=validation_ok, preview_ok=preview_ok,
                                     cursor=passed)}
    state = pipeline.detect(pipeline.seed(None, None, ["002-x"]), facts)
    return pipeline.open_stage(state), pipeline.position(state)["cursor"]


@pytest.mark.parametrize(("stage", "files", "row_stage", "extra"), [
    # No spec yet: the plan starts by creating it.
    ("specify", {}, "", {}),
    # A spec with open clarifications is clarified next.
    ("clarify", ["spec.md"], "especificada", {"clarified": False}),
    ("plan", ["spec.md"], "aclarada", {}),
    ("tasks", ["spec.md", "plan.md"], "planificada", {}),
    # analyze writes nothing, so a spec with plan and tasks resumes at analyze.
    ("analyze", DONE_DOCS, "tareas", {}),
    # implement is reachable: a converge that left open tasks is the one missing.
    ("converge", DONE_DOCS, "implementada", {"converged": True, "validation_ok": True,
                                             "passed": 5}),
    # implemented and converged, but the preview never succeeded.
    ("verify", DONE_DOCS, "implementada", {"validation_ok": True, "preview_ok": False,
                                           "passed": 5}),
])
def test_resume_starts_at_the_first_incomplete_stage(stage, files, row_stage, extra):
    """SC-004: a plan stopped (or a spec built by hand) resumes where it is, not from the start."""
    written = {f"specs/002-x/{name}": "# X\n\nCuerpo.\n" for name in files}
    opened, cursor = _resume_case(stage, written, row_stage, **extra)
    assert opened == ("002-x", stage)
    assert cursor == pipeline.STAGES.index(stage)


def test_a_finished_spec_has_nothing_to_resume():
    files = {f"specs/002-x/{name}": "# X\n" for name in DONE_DOCS}
    opened, cursor = _resume_case("verify", files, "implementada",
                                  validation_ok=True, preview_ok=True, passed=8)
    assert opened is None and cursor == pipeline.TOTAL


# --------------------------------------------------------------------------- verify

def _verify_session(files):
    class Session:
        spec = "002-x"

        def __init__(self):
            self.draft = {"files": files}
            self.validation = {"valid": True}
            self.preview = {"status": "succeeded", "integrations": {
                "facturas": {"status": "succeeded", "datasets": {"facturas": {"rows": 7}}}}}

        def files(self):
            return files

    return Session()


def _verify_files():
    return {
        "specs/002-x/spec.md": (
            "### User Story 1 - Tablero (Priority: P1)\n\n**Independent Test**: 7 rows.\n"),
        "integrations/facturas/integration.yaml": "id: facturas\nspec: specs/002-x\n"
                                                  "source: origen\n",
        "integrations/facturas/queries/facturas.sql": "select 1",
        "integrations/otra/integration.yaml": "id: otra\nspec: specs/999-other\nsource: origen\n",
        "integrations/otra/queries/otra.sql": "select 2",
    }


def test_verify_checks_validation_each_owned_file_and_the_preview(monkeypatch):
    from app.assistant import origin, preview

    asked = []

    def fake_check(db, actor, session, args, app, ip):
        asked.append(args["path"])
        return {"ok": True}, "ok"

    monkeypatch.setattr(origin, "check_query", fake_check)
    monkeypatch.setattr(preview, "run_draft_preview",
                        lambda db, session, time_limit_s=120: session.preview)
    monkeypatch.setattr(preview, "summary_text", lambda outcome: "3 filas")
    session = _verify_session(_verify_files())
    result = pipeline.verify(None, None, session, "002-x", app_settings=None)
    assert result["ok"] is True and result["failures"] == []
    assert asked == ["integrations/facturas/queries/facturas.sql"]   # only this spec's files
    assert [c["check"] for c in result["checks"]] == [
        "validation", "check_query integrations/facturas/queries/facturas.sql", "preview"]
    assert result["stories"] == [{"story": "US1", "title": "Tablero",
                                  "test": "7 rows.", "ok": True}]


def test_verify_reports_the_failure_and_the_story_that_fails(monkeypatch):
    from app.assistant import origin, preview

    monkeypatch.setattr(origin, "check_query",
                        lambda *a, **k: ({"ok": False}, "no"))
    monkeypatch.setattr(preview, "run_draft_preview",
                        lambda db, session, time_limit_s=120: {"status": "failed",
                                                               "integrations": {}})
    monkeypatch.setattr(preview, "summary_text", lambda outcome: "falló")
    result = pipeline.verify(None, None, _verify_session(_verify_files()), "002-x",
                             app_settings=None)
    assert result["ok"] is False
    assert "preview" in result["failures"] and "US1" in result["failures"]
    assert result["stories"][0]["ok"] is False
