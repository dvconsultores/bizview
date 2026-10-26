"""Project trees from applied workspace versions (feature 020, research R3/R10)."""

import re
from pathlib import Path

import yaml

KIND_LINE = {"integration": "integracion", "report": "reporte"}
_KIND_V2 = re.compile(r"^\s*[-*]?\s*\*\*(?:Tipo|Type)\*\*:", re.M)


def _dump(definition: dict) -> str:
    return yaml.safe_dump(definition, sort_keys=False, allow_unicode=True)


def legacy_tree(version) -> dict[str, str]:
    """Deterministic project tree of a version applied before feature 020 (research R10)."""
    tree: dict[str, str] = {}
    entries = []
    for key, spec in (version.specs or {}).items():
        name = str(spec.get("folder", "")).rstrip("/").split("/")[-1]
        m = re.match(r"^(\d{3})-", name)
        old_num, short = (int(m.group(1)), name[4:]) if m else (999, name)
        if key.startswith("integrations/"):
            kind_order, kind = 0, "integration"
        elif key.startswith("reports/"):
            kind_order, kind = 1, "report"
        else:
            continue
        entries.append((old_num, kind_order, name, short, spec, kind))
    entries.sort(key=lambda e: (e[0], e[1], e[2]))

    old_to_new: dict[str, str] = {}
    for _num, _order, _name, short, spec, kind in entries:
        old_folder = str(spec["folder"]).rstrip("/")
        if old_folder not in old_to_new:
            old_to_new[old_folder] = f"specs/{len(old_to_new) + 1:03d}-{short}"
        new_folder = old_to_new[old_folder]
        for doc_name, doc_text in (spec.get("documents") or {}).items():
            if doc_name == "spec.md" and not _KIND_V2.search(doc_text):
                doc_text = re.sub(r"(^\*\*Spec type\*\*:.*$)",
                                  rf"\1\n\n**Tipo**: {KIND_LINE[kind]}",
                                  doc_text, count=1, flags=re.M)
            tree[f"{new_folder}/{doc_name}"] = doc_text

    for group, kind in (("integrations", "integration"), ("reports", "report")):
        for rid, entry in sorted((version.artifacts or {}).get(group, {}).items()):
            definition = dict(entry["definition"])
            old = str(definition.get("spec", "")).rstrip("/")
            if old in old_to_new:
                definition["spec"] = old_to_new[old]
            tree[f"{group}/{rid}/{kind}.yaml"] = _dump(definition)
            for rel, text in sorted((entry.get("files") or {}).items()):
                tree[f"{group}/{rid}/{rel}"] = text
    return dict(sorted(tree.items()))


# A version applied before feature 020 has no project manifest: `principal` gets this one.
LEGACY_PROJECT_YAML = ('name: "Principal"\nslug: principal\n'
                       'description: "Espacio aplicado antes de los proyectos"\n'
                       'created: "2026-10-01"\n')


def version_projects(version) -> dict[str, dict[str, str]]:
    """Project trees of an applied version: {slug: {path: text}} (research R3).

    A version stores each project's files as they were applied (`projects[slug]["tree"]`), so
    composing the next one replays them byte for byte: rebuilding them from the parsed artifacts
    reformatted the projects that were not being applied and left them in «Cambios sin aplicar».
    Versions applied before that answer without a tree and are rebuilt: the artifact's `source`
    text first, then the dumped definition.
    """
    projects = getattr(version, "projects", None) or {}
    if not projects:
        return {"principal": {**legacy_tree(version), "project.yaml": LEGACY_PROJECT_YAML}}
    result = {}
    for slug, meta in sorted(projects.items()):
        stored = meta.get("tree")
        if isinstance(stored, dict) and stored:
            result[slug] = dict(sorted(stored.items()))
            continue
        tree: dict[str, str] = {}
        if meta.get("project_yaml"):
            tree["project.yaml"] = meta["project_yaml"]
        prefix = f"{slug}/specs/"
        for key, spec in (version.specs or {}).items():
            if key.startswith(prefix):
                folder = "specs/" + key.split("/")[2]
                for name, text in (spec.get("documents") or {}).items():
                    tree[f"{folder}/{name}"] = text
        for group, kind in (("integrations", "integration"), ("reports", "report"),
                            ("distributions", "distribution")):
            for rid, entry in sorted((version.artifacts or {}).get(group, {}).items()):
                if entry.get("project") != slug:
                    continue
                own = (f"distributions/{rid}.yaml" if kind == "distribution"
                       else f"{group}/{rid}/{kind}.yaml")
                tree[own] = entry.get("source") or _dump(entry["definition"])
                if kind != "distribution":
                    for rel, text in sorted((entry.get("files") or {}).items()):
                        tree[f"{group}/{rid}/{rel}"] = text
        result[slug] = dict(sorted(tree.items()))
    return result


def write_tree(tree: dict[str, str], dest: Path) -> None:
    """Write {path: text} under dest (relative, no `..`)."""
    for path, text in tree.items():
        if "\\" in path or path.startswith("/") or ".." in path.split("/"):
            raise ValueError(f"invalid project path: {path}")
        target = dest / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


_OTHERS: dict[int, dict[str, dict[str, str]]] = {}


def _snapshots(version) -> dict[str, dict[str, str]]:
    """Project trees of a version, cached per version id (versions never change)."""
    if version is None:
        return {}
    if version.id not in _OTHERS:
        if len(_OTHERS) >= 4:
            _OTHERS.pop(next(iter(_OTHERS)))
        _OTHERS[version.id] = version_projects(version)
    return _OTHERS[version.id]


def manifest_text(version) -> str:
    """bizview.yaml of the composed tree: the active manifest or a default one."""
    manifest = (version.artifacts or {}).get("workspace") if version is not None else None
    if manifest:
        return _dump(manifest)
    # First apply of an installation: the workspace template named after the organization (014).
    from app.assistant.tree import bootstrap_manifest

    return bootstrap_manifest()


def compose(db, *, include=None, exclude_slug: str | None = None, dest: Path) -> Path:
    """Workspace tree = other projects of the active version + the project's folder (R3)."""
    from app.projects import fs, history
    from app.workspace import service as workspace_service

    active = workspace_service.active(db)
    (dest / "bizview.yaml").write_text(manifest_text(active), encoding="utf-8")
    for slug, tree in _snapshots(active).items():
        if slug == exclude_slug or (include is not None and slug == include.slug):
            continue
        write_tree(tree, dest / "projects" / slug)
    if include is not None:
        history.sync_external(db, include)
        files, _ = fs.list_files(include.slug)
        for path in files:
            target = dest / "projects" / include.slug / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(fs.read_text(include.slug, path), encoding="utf-8")
    return dest


def _fingerprint(files: dict[str, tuple[int, str]]) -> str:
    """Hash of the project's layout files (path and sha256)."""
    import hashlib

    lines = sorted(f"{path}:{digest}" for path, (_size, digest) in files.items())
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()



def _project_fix(fix: dict | None, problem: dict, prefix: str,
                 file: str) -> tuple[dict | None, str | None]:
    """The fix and the problem id with a project-relative path (035).

    The validator composes the tree, so it names files `projects/<slug>/…`; the interface and the
    fix endpoint speak project-relative paths. Keeping the composed path made every fix refuse
    itself with «el archivo no existe».
    """
    from bizview_cli.validate import problem_id

    if isinstance(fix, dict) and isinstance(fix.get("file"), str):
        fix = {**fix, "file": fix["file"][len(prefix):]
               if fix["file"].startswith(prefix) else fix["file"]}
    relative = file[len(prefix):] if file.startswith(prefix) else (file or None)
    return fix, problem_id(str(problem.get("code") or ""), relative, problem.get("path"))

def validate_project(db, project) -> dict:
    """Validate the project composed with the other applied projects (plan section 7)."""
    import tempfile

    from bizview_cli import validate as wsv
    from sqlalchemy import select

    from app.engine import direct
    from app.i18n import t
    from app.models import DataSource
    from app.projects import fs, positions
    from app.workspace import service as workspace_service
    from app.workspace.service import MAX_DASHBOARD_CODE

    active = workspace_service.active(db)
    errors: list[dict] = []
    warnings: list[dict] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = compose(db, include=project, dest=Path(tmp))
        names = {n.lower() for n in db.scalars(select(DataSource.name))}
        result = wsv.validate(root, known_sources=names, direct=direct.validation_context(db))
    prefix = f"projects/{project.slug}/"
    for issue in result.issues:
        p = issue.as_dict()
        level = p.pop("level", "error")
        file = p.get("file") or ""
        p["line"] = None
        if file.startswith(prefix):
            rel = file[len(prefix):]
            p["file"] = rel
            try:
                text = fs.read_text(project.slug, rel)
            except Exception:
                text = None
            p["line"] = positions.problem_line({**p, "file": rel}, text)
            p["project"] = project.slug
        elif file.startswith("projects/"):
            p["project"] = file.split("/")[1]
        else:
            p["project"] = None
        p["fix_data"], p["problem_id"] = _project_fix(p.get("fix_data"), p, prefix, file)
        (errors if level == "error" else warnings).append(p)
    for rid, report in result.reports.items():
        if len(rid) > MAX_DASHBOARD_CODE and report.project == project.slug:
            errors.append({
                "entry": f"reports/{rid}", "code": "invalid_report_id",
                "message": t("tree.report_id_max_length", max=MAX_DASHBOARD_CODE),
                "file": f"reports/{rid}/report.yaml", "path": "/id", "expected": None,
                "fix": t("tree.report_id_max_length_fix", max=MAX_DASHBOARD_CODE),
                "line": 1, "project": project.slug,
            })
    warnings += _subscription_cap_warnings(db, project, result)
    files, _ = fs.list_files(project.slug)
    return {
        "valid": not errors, "errors": errors, "warnings": warnings,
        "base_version": active.id if active else None,
        "fingerprint": _fingerprint(files),
        "project_ok": not any(e.get("project") == project.slug for e in errors),
    }


def _subscription_cap_warnings(db, project, result) -> list[dict]:
    """Plan §6: warn when this project's distributions would push a dashboard past the
    scheduled-send cap (distribution rows of every project + hand-made rows)."""
    from sqlalchemy import func, select

    from app.i18n import t
    from app.mail.subscriptions import MAX_PER_DASHBOARD
    from app.models import Dashboard, EmailSubscription

    per_report: dict[str, int] = {}
    for entry in result.distributions.values():
        report, subs = entry.artifact.get("report"), entry.artifact.get("subscriptions")
        if isinstance(report, str) and isinstance(subs, list):
            per_report[report] = per_report.get(report, 0) + len(subs)
    warnings, seen = [], set()
    for entry in sorted(result.distributions.values(), key=lambda e: e.id):
        report = entry.artifact.get("report")
        if entry.project != project.slug or report not in per_report or report in seen:
            continue
        seen.add(report)
        manual = db.scalar(
            select(func.count(EmailSubscription.id))
            .join(Dashboard, Dashboard.id == EmailSubscription.dashboard_id)
            .where(Dashboard.report_id == report, EmailSubscription.project_id.is_(None))) or 0
        total = per_report[report] + manual
        if total > MAX_PER_DASHBOARD:
            warnings.append({
                "entry": f"distributions/{entry.id}", "code": "subscription_cap",
                "message": t("projects.subscription_cap", report=report, total=total,
                             max=MAX_PER_DASHBOARD),
                "file": f"distributions/{entry.id}.yaml", "path": "/subscriptions",
                "expected": None, "fix": t("projects.subscription_cap_fix"),
                "line": None, "project": project.slug,
            })
    return warnings


_DRAFT_SPEC = re.compile(r"^specs/(integrations|reports)/([^/]+)/(.+)$")
_SPEC_LINE = re.compile(
    r"""^(spec:\s*)["']?(specs/(?:integrations|reports)/[^\s"']+?)/?["']?\s*$""", re.MULTILINE)


def draft_tree(files: dict[str, str]) -> dict[str, str]:
    """Project tree of a legacy assistant draft (R10): spec folders renumbered like
    `legacy_tree`, artifacts kept with their `spec:` line pointing to the new folder."""
    folders = []
    for path in files:
        m = _DRAFT_SPEC.match(path)
        if m:
            num = re.match(r"^(\d{3})-", m.group(2))
            folders.append((int(num.group(1)) if num else 999,
                            0 if m.group(1) == "integrations" else 1, m.group(2), m.group(1)))
    old_to_new: dict[str, str] = {}
    for _num, _order, name, group in sorted(set(folders)):
        short = name[4:] if re.match(r"^\d{3}-", name) else name
        old_to_new[f"specs/{group}/{name}"] = f"specs/{len(old_to_new) + 1:03d}-{short}"

    def respec(match: re.Match) -> str:
        new = old_to_new.get(match.group(2).rstrip("/"))
        return f"{match.group(1)}{new}" if new else match.group(0)

    tree: dict[str, str] = {}
    for path, text in files.items():
        m = _DRAFT_SPEC.match(path)
        if m:
            group, name, doc = m.groups()
            if doc == "spec.md" and not _KIND_V2.search(text):
                kind = KIND_LINE["integration" if group == "integrations" else "report"]
                tagged = re.sub(r"(^\*\*Spec type\*\*:.*$)", rf"\1\n\n**Tipo**: {kind}", text,
                                count=1, flags=re.M)
                text = tagged if tagged != text else f"**Tipo**: {kind}\n\n{text}"
            tree[f"{old_to_new[f'specs/{group}/{name}']}/{doc}"] = text
        elif path.startswith(("integrations/", "reports/")) and path.count("/") >= 2:
            if path.endswith(("/integration.yaml", "/report.yaml")):
                text = _SPEC_LINE.sub(respec, text)
            tree[path] = text
    return dict(sorted(tree.items()))
