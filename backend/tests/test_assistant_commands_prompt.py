"""Prompt assembly of chat commands (feature 021 T027): stable system, reads, caps, context."""
from types import SimpleNamespace

import app.assistant.service as service
from app.assistant.commands.prompt import DOCS_CHARS, context_for, documents, system_for
from app.assistant.commands.registry import REGISTRY

CONSTITUTION = ".specify/memory/constitution.md"
SPEC = "003-ventas"


def _files() -> dict[str, str]:
    files = {CONSTITUTION: "C"}
    for name, text in (("spec", "S"), ("plan", "P"), ("tasks", "T"), ("data-model", "D"),
                       ("research", "R"), ("quickstart", "Q")):
        files[f"specs/{SPEC}/{name}.md"] = text
    return files


def _origin(path: str) -> str:
    return f'origen="{path}"'


def test_system_is_stable_and_localized(monkeypatch):
    monkeypatch.setattr(service, "system_prefix", lambda locale=None: f"BASE-{locale}")
    es = system_for(REGISTRY["speckit-plan"], "es")
    assert es == system_for(REGISTRY["speckit-plan"], "es")
    assert es.startswith("BASE-es\n\n## /speckit-plan\n")
    en = system_for(REGISTRY["speckit-plan"], "en")
    assert en != es
    assert en.startswith("BASE-en\n\n## /speckit-plan\n")


def test_reads_per_command():
    files = _files()

    text = "\n".join(documents(REGISTRY["speckit-specify"], None, files, "en"))
    assert _origin(CONSTITUTION) in text
    assert "specs/" not in text

    text = "\n".join(documents(REGISTRY["speckit-clarify"], SPEC, files, "en"))
    assert _origin(CONSTITUTION) in text
    assert _origin(f"specs/{SPEC}/spec.md") in text
    assert "plan.md" not in text

    text = "\n".join(documents(REGISTRY["speckit-tasks"], SPEC, files, "en"))
    for doc in ("spec", "plan", "tasks", "research", "data-model", "quickstart"):
        assert _origin(f"specs/{SPEC}/{doc}.md") in text

    text = "\n".join(documents(REGISTRY["speckit-analyze"], SPEC, files, "en"))
    for doc in ("spec", "plan", "tasks"):
        assert _origin(f"specs/{SPEC}/{doc}.md") in text
    assert "data-model.md" not in text


def test_caps():
    files = {CONSTITUTION: "W" * 9000, f"specs/{SPEC}/spec.md": "X" * 13000}
    text = "\n".join(documents(REGISTRY["speckit-clarify"], SPEC, files, "en"))
    assert text.count("W") == 8000
    assert "truncated: 9000" in text
    assert text.count("X") == 12000
    assert "truncated: 13000" in text

    letters = {"spec": "X", "plan": "Y", "tasks": "Z", "research": "K", "data-model": "J"}
    files = {CONSTITUTION: "W" * 8000}
    files.update({f"specs/{SPEC}/{name}.md": letter * 12000 for name, letter in letters.items()})
    text = "\n".join(documents(REGISTRY["speckit-tasks"], SPEC, files, "en"))
    assert sum(text.count(letter) for letter in "WXYZKJ") == DOCS_CHARS
    omitted = next(line for line in text.splitlines() if line.startswith("Omitted for size"))
    assert "research.md" in omitted and "data-model.md" in omitted
    assert text.splitlines()[-1] == f"Not present yet: specs/{SPEC}/quickstart.md"


def test_missing_line():
    files = {f"specs/{SPEC}/spec.md": "S"}
    blocks = documents(REGISTRY["speckit-implement"], SPEC, files, "es")
    assert blocks[-1].startswith("No existen todavía:")
    assert "plan.md" in blocks[-1] and "tasks.md" in blocks[-1]


def test_context_sections():
    run = SimpleNamespace(status="running", spec=None, reserved_number=4, pending=None, files=[])
    ctx = context_for(project_name="Ventas", project_slug="ventas", specs=[], current_spec=None,
                      next_spec=4, run=run, definition=REGISTRY["speckit-specify"], files={},
                      locale="en", state="\n\n## Estado\nX")
    assert "## Project\nVentas (ventas)\n- none" in ctx
    assert "## Command\n/speckit-specify · Command status: running" in ctx
    assert "specs/004-<short-name>/ (reserved number 004)" in ctx
    assert ctx.endswith("## Estado\nX")

    run = SimpleNamespace(status="running", spec=None, reserved_number=None, pending=None,
                          files=[{"path": f"specs/{SPEC}/plan.md", "action": "write"},
                                 {"path": f"specs/{SPEC}/plan.md", "action": "replace"}])
    ctx = context_for(project_name="Ventas", project_slug="ventas",
                      specs=[{"folder": SPEC, "kind": "reporte", "stage": "tareas"}],
                      current_spec=SPEC, next_spec=4, run=run,
                      definition=REGISTRY["speckit-plan"],
                      files={f"specs/{SPEC}/spec.md": "S"}, locale="es")
    assert "## Proyecto" in ctx and "## Comando" in ctx
    assert f"- {SPEC} · reporte · tareas (actual)" in ctx
    assert "Prerrequisitos: spec.md ✓" in ctx
    assert ctx.count(f"specs/{SPEC}/plan.md (") == 1
    assert f"specs/{SPEC}/plan.md (replace)" in ctx


def test_resume_and_pending():
    run = SimpleNamespace(status="waiting", spec=SPEC, reserved_number=None,
                          pending={"gate": "approve_spec"}, files=[])
    ctx = context_for(project_name="Ventas", project_slug="ventas",
                      specs=[{"folder": SPEC, "kind": None, "stage": None}], current_spec=SPEC,
                      next_spec=4, run=run, definition=REGISTRY["speckit-implement"], files={},
                      locale="en", resume={"files": ["a.yaml"], "notes": "n"})
    assert "Awaiting confirmation: approve_spec" in ctx
    assert "Resume: the previous run was interrupted" in ctx
    assert "Files already written: a.yaml" in ctx
    assert "Notes: n" in ctx
    assert "Prerequisites: tasks.md ✗" in ctx


def test_base_prefix_has_catalogue_refusal_and_rules():
    from app.i18n import t, use_locale

    for locale, prefix in (("es", service.SYSTEM_PREFIX), ("en", service.SYSTEM_PREFIX_EN)):
        with use_locale(locale):
            refusal = t("scope.refusal")
        assert refusal in prefix
        assert service.system_prefix(locale).startswith(prefix)
        for marker in ('confianza="no"', "finish_command", "suggest_command"):
            assert marker in prefix
        assert "## spec-template.md" not in prefix
