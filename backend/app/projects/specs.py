"""Spec folders of a BI project: kind, stage and convergence (feature 020, research R7)."""

import re
from typing import Any

import yaml
from bizview_cli import layout
from sqlalchemy import select

from app.models import DataSource, ProjectFileRevision
from app.projects import fs, history

STAGES = ("especificada", "aclarada", "planificada", "tareas", "implementada", "aplicada")

_STATUS_RE = re.compile(r"^\s*\*\*Status\*\*:\s*(\w+)", re.MULTILINE)
_SOURCE_RE = re.compile(r"^\s*\*\*Fuente\*\*:\s*(.+)$", re.MULTILINE)
_SOURCE_KIND_RE = re.compile(r"^\s*\*\*Tipo de fuente\*\*:\s*(\w+)", re.MULTILINE)
_CLARIFICATIONS_RE = re.compile(r"^## Clarifications[ \t]*\n(.*?)(?=^## |\Z)",
                                re.MULTILINE | re.DOTALL)
_OPEN_TASK_RE = re.compile(r"^\s*- \[ \]", re.MULTILINE)
_ARTIFACT_PATTERNS = {
    "integracion": re.compile(r"^integrations/[^/]+/integration\.yaml$"),
    "reporte": re.compile(r"^reports/[^/]+/report\.yaml$"),
    "distribucion": re.compile(r"^distributions/[^/]+\.yaml$"),
}


def _clarified(text: str) -> bool:
    """A `- Q:` bullet in Clarifications whose question is not the template placeholder."""
    match = _CLARIFICATIONS_RE.search(text)
    if not match:
        return False
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith("- Q:"):
            question = stripped[4:].split("→", 1)[0]
            if re.search(r"[^\W_]", question):
                return True
    return False


def parse_spec(text: str) -> dict[str, Any]:
    """Title, kind, status, source (fuente specs) and clarification of a spec.md."""
    title = None
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            if title.startswith("Feature Specification:"):
                title = title[len("Feature Specification:"):].strip()
            break
    status = _STATUS_RE.search(text)
    source = None
    source_match = _SOURCE_RE.search(text)
    if source_match:
        raw = source_match.group(1).strip().strip('"`')
        if not raw.startswith("["):
            source = raw
    source_kind = _SOURCE_KIND_RE.search(text)
    return {
        "title": title,
        "kind": layout.spec_kind(text),
        "status": status.group(1) if status else None,
        "source": source,
        "source_kind": source_kind.group(1).lower() if source_kind else None,
        "clarified": _clarified(text),
    }


def open_tasks(text: str) -> int:
    """Number of unchecked task boxes."""
    return len(_OPEN_TASK_RE.findall(text))


def linked_artifacts(files: dict[str, str], folder: str) -> dict[str, list[str]]:
    """Integration/report/distribution files whose `spec:` is `specs/<folder>`, by kind."""
    target = f"specs/{folder}"
    result: dict[str, list[str]] = {}
    for path, content in files.items():
        for kind, pattern in _ARTIFACT_PATTERNS.items():
            if not pattern.match(path):
                continue
            try:
                doc = yaml.safe_load(content)
            except yaml.YAMLError:
                doc = None
            spec = doc.get("spec") if isinstance(doc, dict) else None
            if isinstance(spec, str) and spec.strip().rstrip("/") == target:
                result.setdefault(kind, []).append(path)
            break
    return {kind: sorted(paths) for kind, paths in result.items()}


def _command(cmd: str | None) -> str:
    return (cmd or "").lstrip("/").lower()


def revised_by(db, project_id: int, path: str, command: str) -> bool:
    """True when some revision of the file was made by `command` (e.g. speckit-clarify)."""
    target = _command(command)
    commands = db.scalars(select(ProjectFileRevision.command).where(
        ProjectFileRevision.project_id == project_id, ProjectFileRevision.path == path))
    return any(_command(c) == target for c in commands)


def converged(db, project_id: int, path: str, current_text: str | None) -> bool:
    """The latest tasks.md revision by /speckit-converge added open tasks, still open."""
    revisions = db.scalars(select(ProjectFileRevision).where(
        ProjectFileRevision.project_id == project_id, ProjectFileRevision.path == path,
    ).order_by(ProjectFileRevision.id)).all()
    latest = predecessor = None
    for index, rev in enumerate(revisions):
        if _command(rev.command) == "speckit-converge" and rev.op != "delete":
            latest = rev
            predecessor = revisions[index - 1] if index > 0 else None
    if latest is None or latest.content is None or current_text is None:
        return False
    before = predecessor.content if predecessor is not None and predecessor.content else ""
    return open_tasks(latest.content) > open_tasks(before) and open_tasks(current_text) > 0


def applied_files(db, project) -> dict[str, str] | None:
    """{path: sha256} of the project in the active version, None when it is not applied."""
    from app.projects.compose import version_projects
    from app.workspace.service import active

    version = active(db)
    if version is None:
        return None
    projects = version.projects
    if isinstance(projects, dict) and project.slug in projects:
        return dict((projects[project.slug] or {}).get("files") or {})
    tree = version_projects(version).get(project.slug)
    if not tree:
        return None
    # The manifest of a legacy version is synthesized: it never counts as applied content.
    return {p: history.sha(t) for p, t in tree.items() if p != "project.yaml"}


def stage(
    folder: str,
    files: dict[str, str],
    *,
    applied: dict[str, str] | None,
    sources: dict[str, bool | None],
    clarify_revision: bool,
) -> dict[str, Any]:
    """Stage of a spec folder per R7, with kind, title, status and linked artifacts."""
    spec_path = f"specs/{folder}/spec.md"
    if spec_path not in files:
        return {"stage": None, "kind": None}
    info = parse_spec(files[spec_path])
    current = "especificada"
    if info["clarified"] or clarify_revision:
        current = "aclarada"
    if f"specs/{folder}/plan.md" in files:
        current = "planificada"
    tasks = files.get(f"specs/{folder}/tasks.md")
    if tasks is not None:
        current = "tareas"
    result: dict[str, Any] = {"kind": info["kind"], "title": info["title"],
                              "status": info["status"]}
    linked = linked_artifacts(files, folder)
    status = (info["status"] or "").lower()
    if tasks is not None and status in ("approved", "implemented") and open_tasks(tasks) == 0:
        kind = info["kind"]
        if kind == "fuente":
            name = info["source"]
            ok = name is not None and sources.get(name.lower()) is True
            if not ok:
                query = f"?kind={info['source_kind']}" if info["source_kind"] else ""
                result["source_missing"] = {"source": name,
                                            "link": f"/admin/fuentes/nueva{query}"}
        else:
            ok = bool(linked.get(kind or ""))
        if ok:
            current = "implementada"
            own = [p for p in files if p.startswith(f"specs/{folder}/")]
            own += [p for paths in linked.values() for p in paths]
            if applied is not None and all(applied.get(p) == history.sha(files[p]) for p in own):
                current = "aplicada"
    result["stage"] = current
    result["linked"] = linked
    return result


def list_specs(db, project) -> list[dict[str, Any]]:
    """Spec folders of the project: number, kind, title, status, stage, converged."""
    listed, _ = fs.list_files(project.slug)
    files: dict[str, str] = {}
    for path in listed:
        if path.endswith((".md", ".yaml", ".yml")):
            try:
                files[path] = fs.read_text(project.slug, path)
            except (OSError, fs.ProjectPathError):
                continue
    folders = sorted({
        p.split("/")[1] for p in files
        if p.startswith("specs/") and p.count("/") >= 2
        and layout.SPEC_FOLDER_RE.match(p.split("/")[1])
    })
    applied = applied_files(db, project)
    sources = {name.lower(): ok
               for name, ok in db.execute(select(DataSource.name, DataSource.last_test_ok))}
    result = []
    for folder in folders:
        data = stage(folder, files, applied=applied, sources=sources,
                     clarify_revision=revised_by(db, project.id, f"specs/{folder}/spec.md",
                                                 "speckit-clarify"))
        tasks_path = f"specs/{folder}/tasks.md"
        result.append({"folder": folder, "number": int(folder[:3]), **data,
                       "converged": converged(db, project.id, tasks_path,
                                              files.get(tasks_path))})
    return result
