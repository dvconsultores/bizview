"""Metadata summary of a BI project for the agent (feature 023, plan §7).

Computed from the project folder, its stage and the catalogue: never source rows, credentials,
host names or email addresses (recipients are role names only).
"""
import json
import re

import yaml
from sqlalchemy import select

from app.assistant import readiness
from app.i18n import t, use_locale
from app.models import DataSource
from app.projects import fs
from app.projects import service as project_service
from app.projects import specs as project_specs
from app.workspace.service import active

MAX_CHARS = 20000
DECISION_RE = re.compile(
    r"^\s*[-*]?\s*\*\*(Tipo|Type|Modo|Mode|Fuente|Source|Tablas|Tables|Mantiene|"
    r"Mantenido por|Maintained by|Volumen|Volumen esperado|Expected volume|Datos personales|"
    r"Personal data)\*\*:")
SOURCE_RE = re.compile(r"^\s*[-*]?\s*\*\*(?:Fuente|Source)\*\*:\s*`?([^`\n]+?)`?\s*$")
CHECK_RE = re.compile(r"^\s*[-*] \[( |x|X)\]", re.M)
MODE_RE = re.compile(r"^\s*[-*]?\s*\*\*(?:Modo|Mode)\*\*:\s*(\w+)", re.M)
NEEDS = "[NEEDS CLARIFICATION"
NEW_SOURCE_LINK = "app:/admin/fuentes/nueva"


def _read(slug: str, path: str) -> str | None:
    try:
        return fs.read_text(slug, path)
    except (OSError, fs.ProjectPathError):
        return None


def _yaml(text: str | None) -> dict:
    try:
        loaded = yaml.safe_load(text or "")
    except yaml.YAMLError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def next_command(spec: dict, ready: bool, pending_paths: set[str]) -> tuple[str | None, str | None]:
    """(command, action key) that comes next for a spec (plan §7 table); `_spec_item` turns the
    action key ("source", "apply") into the text of the request language."""
    stage = spec.get("stage")
    if spec.get("kind") == "fuente" and spec.get("source_missing"):
        return None, "source"
    if stage == "especificada":
        return ("/speckit-clarify" if spec.get("open_clarifications", 0) > 0
                else "/speckit-plan"), None
    if stage == "aclarada":
        return "/speckit-plan", None
    if stage == "planificada":
        return "/speckit-tasks", None
    if stage == "tareas":
        return "/speckit-implement", None
    if stage == "implementada":
        return (None, "apply") if ready else ("/speckit-converge", None)
    if stage == "aplicada" and set(spec.get("paths") or ()) & pending_paths:
        return None, "apply"
    return None, None


def _artifacts(files: dict[str, str]) -> dict[str, tuple[str, dict, set[str]]]:
    """{artifact key: (kind, document, its paths)} for integrations, reports, distributions."""
    out: dict[str, tuple[str, dict, set[str]]] = {}
    for path, text in files.items():
        parts = path.split("/")
        if len(parts) == 3 and parts[0] == "integrations" and parts[2] == "integration.yaml":
            prefix = f"integrations/{parts[1]}/"
            out[f"i:{parts[1]}"] = ("integration", _yaml(text),
                                     {p for p in files if p.startswith(prefix)})
        elif len(parts) == 3 and parts[0] == "reports" and parts[2] == "report.yaml":
            out[f"r:{parts[1]}"] = ("report", _yaml(text), {path})
        elif len(parts) == 2 and parts[0] == "distributions" and path.endswith(".yaml"):
            out[f"d:{parts[1][:-5]}"] = ("distribution", _yaml(text), {path})
    return out


def _spec_item(spec: dict, files: dict[str, str], artifacts: dict, ready: bool,
               pending: set[str]) -> dict:
    folder = spec["folder"]
    spec_path = f"specs/{folder}/spec.md"
    spec_text = files.get(spec_path, "")
    marks = CHECK_RE.findall(files.get(f"specs/{folder}/tasks.md", ""))
    mode = None
    if spec.get("kind") == "reporte":
        found = MODE_RE.search(spec_text)
        mode = "directo" if found and found.group(1).lower().startswith("direct") else "dataset"
    decisions = [{"file": spec_path, "line": n, "text": line.strip()[:200]}
                 for n, line in enumerate(spec_text.splitlines(), start=1)
                 if DECISION_RE.match(line)]
    paths = {p for p in files if p.startswith(f"specs/{folder}/")}
    for _kind, doc, own in artifacts.values():
        if doc.get("spec") == f"specs/{folder}":
            paths |= own
    open_clarifications = spec_text.count(NEEDS)
    command, action = next_command(
        {**spec, "open_clarifications": open_clarifications, "paths": paths}, ready, pending)
    item = {"number": spec["number"], "folder": folder, "title": spec.get("title"),
            "kind": spec.get("kind"), "mode": mode, "stage": spec.get("stage"),
            "status": spec.get("status"), "converged": bool(spec.get("converged")),
            "open_clarifications": open_clarifications,
            "tasks": {"done": sum(1 for m in marks if m in ("x", "X")), "total": len(marks)},
            "next_command": command, "next_action": t(f"guide.next.{action}") if action else None,
            "decisions": decisions}
    if command == "/speckit-implement" and spec.get("stage") == "tareas":
        item["next_hint"] = "/speckit-analyze"             # plan §7: check before implementing
    if action == "source":
        link = (spec.get("source_missing") or {}).get("link")       # with ?kind= when known
        item["next_link"] = f"app:{link}" if link else NEW_SOURCE_LINK
    return item


def _integration(key: str, doc: dict) -> dict:
    datasets = doc.get("datasets") if isinstance(doc.get("datasets"), dict) else {}
    checks = {check.get("type") for ds in datasets.values() if isinstance(ds, dict)
              for check in (ds.get("checks") or []) if isinstance(check, dict)}
    return {"id": key[2:], "spec": doc.get("spec"), "source": doc.get("source"),
            "schedule": doc.get("schedule"),
            "transform": any(isinstance(ds, dict) and ds.get("transform")
                             for ds in datasets.values()),
            "checks": sorted(c for c in checks if c), "datasets": sorted(datasets)}


def _report(key: str, doc: dict) -> dict:
    direct = doc.get("direct") if isinstance(doc.get("direct"), dict) else None
    if direct:
        tables = direct.get("tables") if isinstance(direct.get("tables"), dict) else {}
        source_or_uses = direct.get("source")
        targets = sorted(str(t["table"]) for t in tables.values()
                         if isinstance(t, dict) and t.get("table"))
    else:
        uses = doc.get("uses") if isinstance(doc.get("uses"), dict) else {}
        source_or_uses = sorted(str(v) for v in uses.values())
        targets = list(source_or_uses)
    views = [v.get("type") for v in (doc.get("views") or []) if isinstance(v, dict)]
    return {"id": key[2:], "spec": doc.get("spec"), "mode": "directo" if direct else "dataset",
            "source_or_uses": source_or_uses, "tables_or_datasets": targets,
            "metrics": sorted(doc.get("metrics") or {}), "views": [v for v in views if v],
            "pdf": bool((doc.get("pdf") or {}).get("enabled"))}


def _distribution(key: str, doc: dict) -> dict:
    subscriptions = []
    for sub in doc.get("subscriptions") or []:
        if not isinstance(sub, dict):
            continue
        recipients = sub.get("recipients") if isinstance(sub.get("recipients"), dict) else {}
        subscriptions.append({"frequency": sub.get("frequency"), "hour": sub.get("hour"),
                              "period": sub.get("period"), "pdf": bool(sub.get("attach_pdf")),
                              "link_days": sub.get("link_days"),
                              "recipients": {"users": 0,
                                             "roles": list(recipients.get("roles") or [])}})
    share = doc.get("share") if isinstance(doc.get("share"), dict) else {}
    return {"id": key[2:], "spec": doc.get("spec"), "report": doc.get("report"),
            "subscriptions": subscriptions, "share_link_max_days": share.get("max_days")}


def _sources(db, names: set[str]) -> list[dict]:
    catalogue = {ds.name.lower(): ds for ds in db.scalars(select(DataSource))}
    out = []
    for name in sorted(names):
        if name.lower() == "bi":
            out.append({"name": "bi", "kind": "bi", "exists": True, "last_test_ok": True,
                        "direct_reports": True})
            continue
        ds = catalogue.get(name.lower())
        out.append({"name": name, "kind": ds.kind if ds else None, "exists": ds is not None,
                    "last_test_ok": ds.last_test_ok if ds else None,
                    "direct_reports": bool(ds.direct_reports) if ds else False})
    return out


def _cap(result: dict) -> dict:
    lists = [result["specs"], result["integrations"], result["reports"], result["distributions"]]
    truncated = False
    while len(json.dumps(result, ensure_ascii=False, default=str)) > MAX_CHARS:
        longest = max(lists, key=len)
        if len(longest) > 1:
            del longest[max(1, len(longest) // 2):]
        else:
            decisions = max((s["decisions"] for s in result["specs"]), key=len, default=[])
            if len(decisions) <= 1:
                break
            del decisions[len(decisions) // 2:]
        truncated = True
    if truncated:
        result["truncated"] = True
    return result


def build(db, project) -> dict:
    """The project's metadata summary (plan §7), capped at MAX_CHARS."""
    listed, _ = fs.list_files(project.slug)
    files = {}
    for path in listed:
        if path.endswith((".md", ".yaml", ".yml", ".sql")):
            text = _read(project.slug, path)
            if text is not None:
                files[path] = text
    status, changes = project_service.status(db, project)
    pending = set(changes.get("added", [])) | set(changes.get("changed", [])) | set(
        changes.get("removed", []))
    ready = bool(readiness.compute(project_service.readiness_view(db, project))["ready"])
    artifacts = _artifacts(files)
    specs = [_spec_item(spec, files, artifacts, ready, pending)
             for spec in project_specs.list_specs(db, project)]
    integrations = [_integration(k, doc) for k, (kind, doc, _) in sorted(artifacts.items())
                    if kind == "integration"]
    reports = [_report(k, doc) for k, (kind, doc, _) in sorted(artifacts.items())
               if kind == "report"]
    distributions = [_distribution(k, doc) for k, (kind, doc, _) in sorted(artifacts.items())
                     if kind == "distribution"]
    names = {str(i["source"]) for i in integrations if i.get("source")}
    names |= {str(r["source_or_uses"]) for r in reports
              if r["mode"] == "directo" and r.get("source_or_uses")}
    for spec in specs:
        for decision in spec["decisions"]:
            found = SOURCE_RE.match(decision["text"])
            if found:
                names.add(found.group(1))
    version = active(db)
    applied = None
    if version is not None and project.slug in (version.projects or {}) and status != "borrador":
        applied = {"version_id": version.id, "at": version.applied_at.isoformat()}
    validation = project.validation or {}
    return _cap({
        "project": {"name": project.name, "slug": project.slug, "status": status,
                    "description": (project.description or "")[:300]},
        "specs": specs, "sources": _sources(db, names), "integrations": integrations,
        "reports": reports, "distributions": distributions, "applied": applied,
        "pending_changes": {"paths": sorted(pending)[:50], "count": len(pending)},
        "validation": {"valid": bool(validation.get("valid")),
                       "problems": len(validation.get("errors") or [])},
        "ready": ready,
    })


def next_steps(db, project, lang: str) -> str:
    """Up to five "what comes next" lines for the fixed /ayuda reply ("" when none)."""
    with use_locale("en" if lang == "en" else "es"):
        built = build(db, project)
        lines = []
        for spec in sorted(built["specs"], key=lambda s: s["number"]):
            step = spec["next_command"] or spec["next_action"]
            if step and spec.get("next_hint"):
                step = t("guide.next.with_hint", command=step, hint=spec["next_hint"])
            if step and spec.get("next_link"):
                step = f"[{step}]({spec['next_link']})"
            if step:
                lines.append(f"- {spec['folder']} ({spec['stage']}) → {step}")
            if len(lines) == 5:
                break
        if not lines:
            return ""
        heading = t("guide.next.heading", name=built["project"]["name"])
    return f"\n## {heading}\n\n" + "\n".join(lines) + "\n"
