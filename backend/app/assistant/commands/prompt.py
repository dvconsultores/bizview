"""Prompt assembly for chat commands (feature 021, plan §4).

The system text is stable per command and locale (cacheable prefix); the per-round context tail
carries the project, the command and its documents (each inside an untrusted-data block).
"""

from app.assistant.commands.registry import DOCS, CommandDef, prompt_body
from app.assistant.commands.scope import wrap_data
from app.projects.fs import CONSTITUTION

CONSTITUTION_CHARS = 8000
DOC_CHARS = 12000
DOCS_CHARS = 40000

_LABELS = {
    "es": {
        "project": "## Proyecto",
        "command": "## Comando",
        "documents": "## Documentos",
        "current": "actual",
        "none": "ninguna",
        "status": "Estado del comando",
        "spec": "Spec",
        "new_folder": ("Carpeta nueva: specs/{number:03d}-<nombre-corto>/ "
                       "(número reservado {number:03d})"),
        "prereqs": "Prerrequisitos",
        "pending": "Pendiente de confirmación",
        "resume": ("Reanudación: el comando anterior se interrumpió; continúa desde ahí sin "
                   "repetir lo hecho."),
        "resume_files": "Archivos ya escritos",
        "resume_notes": "Notas",
        "run_files": "Archivos escritos por este comando",
        "truncated": "… (recortado: {size} caracteres; usa read_draft)",
        "omitted": "Omitidos por tamaño (usa read_draft): {paths}",
        "missing": "No existen todavía: {paths}",
    },
    "en": {
        "project": "## Project",
        "command": "## Command",
        "documents": "## Documents",
        "current": "current",
        "none": "none",
        "status": "Command status",
        "spec": "Spec",
        "new_folder": ("New folder: specs/{number:03d}-<short-name>/ "
                       "(reserved number {number:03d})"),
        "prereqs": "Prerequisites",
        "pending": "Awaiting confirmation",
        "resume": ("Resume: the previous run was interrupted; continue from there without "
                   "repeating what is done."),
        "resume_files": "Files already written",
        "resume_notes": "Notes",
        "run_files": "Files written by this command",
        "truncated": "… (truncated: {size} characters; use read_draft)",
        "omitted": "Omitted for size (use read_draft): {paths}",
        "missing": "Not present yet: {paths}",
    },
}


def _labels(locale: str) -> dict[str, str]:
    return _LABELS["en"] if locale == "en" else _LABELS["es"]


def system_for(definition: CommandDef, locale: str) -> str:
    """Stable system prompt of a command: base prefix + `## /<name>` + the prompt file."""
    from app.assistant.service import system_prefix  # service imports this module

    return (f"{system_prefix(locale)}\n\n## /{definition.name}\n"
            f"{prompt_body(definition.name, locale)}")


def doc_path(key: str, spec: str | None) -> str | None:
    """Project path of a document key, None for spec documents while there is no spec."""
    if key == "constitution":
        return CONSTITUTION
    if key in DOCS and spec:
        return f"specs/{spec}/{DOCS[key]}"
    return None


def documents(definition: CommandDef, spec: str | None, files: dict[str, str],
              locale: str) -> list[str]:
    """Data blocks of `definition.reads` with the per-document and total caps."""
    labels = _labels(locale)
    blocks: list[str] = []
    missing: list[str] = []
    omitted: list[str] = []
    remaining = DOCS_CHARS
    for key in definition.reads:
        path = doc_path(key, spec)
        if path is None:
            continue
        if path not in files:
            missing.append(path)
            continue
        if remaining <= 0:
            omitted.append(path)
            continue
        cap = min(CONSTITUTION_CHARS if key == "constitution" else DOC_CHARS, remaining)
        text = files[path]
        shown = text
        if len(text) > cap:
            shown = text[:cap] + "\n" + labels["truncated"].format(size=len(text))
        remaining -= min(len(text), cap)
        blocks.append(wrap_data(path, shown))
    if omitted:
        blocks.append(labels["omitted"].format(paths=", ".join(omitted)))
    if missing:
        blocks.append(labels["missing"].format(paths=", ".join(missing)))
    return blocks


def context_for(*, project_name: str, project_slug: str, specs: list[dict],
                current_spec: str | None, next_spec: int, run, definition: CommandDef,
                files: dict[str, str], locale: str, resume: dict | None = None,
                state: str = "", extra: str = "") -> str:
    """Per-round context tail: `## Proyecto`, `## Comando`, documents, then the 017 Estado."""
    labels = _labels(locale)
    sections: list[str] = []

    project_lines = [labels["project"], f"{project_name} ({project_slug})"]
    for item in specs:
        line = f"- {item['folder']} · {item.get('kind') or '-'} · {item.get('stage') or '-'}"
        if item["folder"] == current_spec:
            line += f" ({labels['current']})"
        project_lines.append(line)
    if not specs:
        project_lines.append(f"- {labels['none']}")
    sections.append("\n".join(project_lines))

    spec = run.spec or current_spec
    lines = [labels["command"], f"/{definition.name} · {labels['status']}: {run.status}"]
    if spec:
        lines.append(f"{labels['spec']}: specs/{spec}/")
    elif definition.name == "speckit-specify":
        lines.append(labels["new_folder"].format(number=run.reserved_number or next_spec))
    if definition.prereqs:
        marks = []
        for key in definition.prereqs:
            path = doc_path(key, spec)
            marks.append(f"{DOCS[key]} {'✓' if path in files else '✗'}")
        lines.append(f"{labels['prereqs']}: " + ", ".join(marks))
    if run.pending:
        lines.append(f"{labels['pending']}: {run.pending.get('gate', '')}")
    if resume:
        lines.append(labels["resume"])
        if resume.get("files"):
            lines.append(f"{labels['resume_files']}: " + ", ".join(resume["files"]))
        if resume.get("notes"):
            lines.append(f"{labels['resume_notes']}: {resume['notes']}")
    if run.files:
        written: dict[str, str] = {}
        for entry in run.files:
            written[entry["path"]] = entry["action"]
        lines.append(f"{labels['run_files']}: "
                     + ", ".join(f"{path} ({action})" for path, action in written.items()))
    if extra:
        lines.append(extra)
    sections.append("\n".join(lines))

    blocks = documents(definition, spec, files, locale)
    if blocks:
        sections.append(labels["documents"] + "\n\n" + "\n\n".join(blocks))
    if state:
        sections.append(state.lstrip("\n"))
    return "\n\n".join(sections)
