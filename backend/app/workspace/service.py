"""Workspace versions (feature 005, research R7, FR-017 to FR-020).

The installation mounts the customer's workspace checkout read-only. Validation runs the same
rules as `bizview validate` plus live checks (sources exist in the catalogue, the committed lock
matches the files). Applying copies the validated artifacts into `workspace_version`; the engine
runs from that copy only, so files changed after apply do nothing until the next apply. Rollback
re-activates the previous version.
"""
import hashlib
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from bizview_cli import layout
from bizview_cli import validate as wsv
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import lock_key
from app.errors import ApiError, not_found
from app.i18n import M, t
from app.models import (
    AppUser,
    Dashboard,
    DataSource,
    DirectReadLog,
    Project,
    WorkspaceVersion,
)
from app.services import audit

MAX_DASHBOARD_CODE = 40


@dataclass
class Validation:
    result: wsv.Result | None
    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    changes: dict = field(default_factory=dict)
    root: Path | None = None   # tree that was validated (feature 020: project file maps)

    @property
    def ok(self) -> bool:
        return self.result is not None and not self.errors

    def to_json(self) -> dict:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings,
                "changes": self.changes}


def mounted_path() -> Path:
    return Path(get_settings().workspace_path)


def _git_commit(root: Path) -> str | None:
    head = root / ".git" / "HEAD"
    try:
        ref = head.read_text().strip()
        if not ref.startswith("ref: "):
            return ref[:40] or None
        name = ref[5:]
        loose = root / ".git" / name
        if loose.is_file():
            return loose.read_text().strip()[:40]
        packed = root / ".git" / "packed-refs"
        for line in packed.read_text().splitlines():
            if line.endswith(" " + name):
                return line.split(" ", 1)[0][:40]
    except OSError:
        return None
    return None


def mounted_info() -> dict | None:
    root = mounted_path()
    if not (root / "bizview.yaml").is_file():
        return None
    lock = wsv.read_lock(root)
    return {"path": str(root), "commit": _git_commit(root),
            "checksum": wsv.lock_checksum(lock) if isinstance(lock, dict) else None,
            "read_at": datetime.now(UTC)}


def active(db: Session) -> WorkspaceVersion | None:
    return db.scalar(select(WorkspaceVersion).where(WorkspaceVersion.state == "active"))


@dataclass(frozen=True)
class VersionSnapshot:
    """What report reads need from the active version (versions never change once applied)."""
    id: int
    artifacts: dict
    checksum: str | None = None    # part of the report context cache key (engine.cached_context)


_active_cache: dict = {"at": float("-inf"), "value": None}
_active_cache_lock = threading.Lock()


def active_for_reads(db: Session) -> VersionSnapshot | None:
    """The active version for read-only report requests, kept in memory for
    `active_version_cache_seconds` (applies/rollbacks in this process clear it at once; other
    processes see a new version within that time)."""
    ttl = get_settings().active_version_cache_seconds
    now = time.monotonic()
    with _active_cache_lock:
        if ttl > 0 and now - _active_cache["at"] < ttl:
            return _active_cache["value"]
    v = active(db)
    snap = (VersionSnapshot(id=v.id, artifacts=v.artifacts, checksum=v.checksum)
            if v is not None else None)
    with _active_cache_lock:
        _active_cache.update(at=now, value=snap)
    return snap


def forget_active_version() -> None:
    with _active_cache_lock:
        _active_cache.update(at=float("-inf"), value=None)


def previous(db: Session) -> WorkspaceVersion | None:
    return db.scalar(select(WorkspaceVersion).where(WorkspaceVersion.state == "previous"))


def _spec_meta(key: str, item: dict) -> dict:
    return {"key": key, "kind": item.get("kind") or key.split("/", 1)[0].removesuffix("s"),
            "project": item.get("project"), "folder": item.get("folder"),
            "title": item.get("title"), "status": item.get("status"),
            "sha256": item.get("sha256")}


def _version_projects(v: WorkspaceVersion) -> dict:
    """Owners of the version's artifacts (feature 020); legacy versions: one `principal`."""
    groups = {g: v.artifacts.get(g, {}) for g in ("integrations", "reports", "distributions")}
    metas = dict(v.projects or {})
    if not metas and any(groups.values()):
        metas = {"principal": {"project_id": None, "name": "principal", "origin": "git"}}
    return {
        slug: {"project_id": meta.get("project_id"), "name": meta.get("name") or slug,
               "origin": meta.get("origin") or "git",
               **{g: sorted(i for i, item in items.items()
                            if (item.get("project") or "principal") == slug)
                  for g, items in groups.items()}}
        for slug, meta in sorted(metas.items())
    }


def version_json(v: WorkspaceVersion | None) -> dict | None:
    if v is None:
        return None
    return {"id": v.id, "commit": v.commit, "checksum": v.checksum, "applied_at": v.applied_at,
            "applied_by": v.applied_by, "workspace": v.lock.get("workspace"),
            "integrations": sorted(v.artifacts.get("integrations", {})),
            "reports": sorted(v.artifacts.get("reports", {})),
            "distributions": sorted(v.artifacts.get("distributions", {})),
            "specs": [_spec_meta(k, item) for k, item in sorted((v.specs or {}).items())],
            "projects": _version_projects(v)}


_DIRECT_STATUS = {
    "ok": "ok",
    "structure_changed": "broken",
    "product_table": "broken",
    "not_allowed": "broken",
    "timeout": "failing",
    "unreachable": "failing",
    "busy": "failing",
    "error": "failing",
}


def report_details(db: Session, version: WorkspaceVersion | None) -> list[dict]:
    """Per report: mode, source, tables and, for direct reports, the status of the newest
    direct read (feature 019 FR-014)."""
    if version is None:
        return []
    reports = version.artifacts.get("reports", {})
    integrations = version.artifacts.get("integrations", {})
    details: list[dict] = []
    direct_ids: list[str] = []
    for report_id in sorted(reports):
        definition = reports[report_id].get("definition", {})
        if "direct" in definition:
            direct = definition["direct"] or {}
            tables = []
            for t in (direct.get("tables") or {}).values():
                if isinstance(t, dict) and "table" in t:
                    tables.append(t["table"])
            details.append({
                "id": report_id,
                "mode": "direct",
                "source": direct.get("source"),
                "tables": tables,
                "status": None,
                "last_read_at": None,
            })
            direct_ids.append(report_id)
        else:
            uses = definition.get("uses") or {}
            tables = list(uses.values())
            sources: list[str] = []
            for value in uses.values():
                integration_id = str(value).partition(".")[0]
                integration = integrations.get(integration_id, {})
                source = integration.get("definition", {}).get("source")
                if source and source not in sources:
                    sources.append(source)
            details.append({
                "id": report_id,
                "mode": "dataset",
                "source": ", ".join(sources) if sources else None,
                "tables": tables,
                "status": None,
                "last_read_at": None,
            })

    if direct_ids:
        rows = db.execute(
            select(DirectReadLog.report_id, DirectReadLog.outcome, DirectReadLog.occurred_at)
            .distinct(DirectReadLog.report_id)
            .where(DirectReadLog.report_id.in_(direct_ids))
            .order_by(DirectReadLog.report_id, DirectReadLog.occurred_at.desc(),
                      DirectReadLog.id.desc())
        ).all()
        newest = {row.report_id: row for row in rows}
        for detail in details:
            if detail["mode"] == "direct" and detail["id"] in newest:
                row = newest[detail["id"]]
                detail["status"] = _DIRECT_STATUS.get(row.outcome)
                detail["last_read_at"] = row.occurred_at

    return details


def _issue(i: wsv.Issue) -> dict:
    return {"entry": i.entry, "code": i.code, "message": i.message}


def _rel_spec(entry) -> str | None:
    """Spec folder relative to the entry's project (v2) or to the workspace (legacy)."""
    folder = entry.spec.get("folder")
    prefix = f"projects/{entry.project}/"
    return folder[len(prefix):] if folder and folder.startswith(prefix) else folder


SPEC_TEXT_SUFFIXES = (".md", ".yaml", ".yml", ".json")
_STATUS_RE = re.compile(r"^\s*\*\*Status\*\*:\s*(\w+)", re.MULTILINE)
_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _spec_folder_docs(folder: Path) -> dict[str, str]:
    """Text documents of a v2 spec folder (recursive), keyed by their path inside it."""
    docs: dict[str, str] = {}
    if not folder.is_dir() or folder.is_symlink():
        return docs
    for path in sorted(folder.rglob("*")):
        if path.is_file() and not path.is_symlink() and path.suffix in SPEC_TEXT_SUFFIXES:
            try:
                docs[path.relative_to(folder).as_posix()] = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
    return docs


def _v2_specs(result: wsv.Result, root: Path | None) -> dict:
    """Spec archive of a v2 tree: one `<slug>/specs/<folder>` key per spec folder."""
    specs: dict = {}
    for slug, info in sorted(result.projects.items()):
        for name, meta in sorted((info.get("specs") or {}).items()):
            docs = _spec_folder_docs(root / "projects" / slug / "specs" / name) if root else {}
            text = docs.get("spec.md", "")
            status, title = _STATUS_RE.search(text), _TITLE_RE.search(text)
            specs[f"{slug}/specs/{name}"] = {
                "folder": f"specs/{name}", "project": slug, "kind": meta.get("kind"),
                "sha256": meta.get("sha256"), "status": status.group(1) if status else None,
                "title": (title.group(1).strip().removeprefix("Feature Specification:").strip()
                          or None) if title else None,
                "documents": docs,
            }
    return specs


def _artifacts(result: wsv.Result, root: Path | None = None) -> tuple[dict, dict]:
    artifacts: dict = {"workspace": result.manifest, "integrations": {}, "reports": {},
                       "distributions": {}}
    specs: dict = {}
    for group, entries in (("integrations", result.integrations), ("reports", result.reports)):
        for entry in entries.values():
            prefix = f"{entry.folder.as_posix()}/"
            own = f"{prefix}{entry.kind}.yaml"
            files = {path[len(prefix):]: data.decode("utf-8")
                     for path, data in entry.files.items()
                     if path.startswith(prefix) and path != own}
            # `source` is the artifact's own file, byte for byte: composing the next version
            # replays it instead of dumping the parsed definition, which rewrote the files of every
            # project that was not being applied (applying one marked the others as changed).
            artifacts[group][entry.id] = {"definition": entry.artifact, "files": files,
                                          "project": entry.project, "spec": _rel_spec(entry),
                                          "source": (entry.files.get(own) or b"").decode()
                                          or None}
            if result.layout == "v2":
                continue
            documents = {
                name: entry.files[f"{entry.spec.get('folder')}/{name}"].decode("utf-8")
                for name in wsv.SPEC_FILES
                if f"{entry.spec.get('folder')}/{name}" in entry.files
            }
            specs[entry.key] = {
                k: entry.spec.get(k) for k in ("folder", "status", "title", "sha256")
            }
            specs[entry.key]["documents"] = documents
    for entry in result.distributions.values():
        own = f"distributions/{entry.id}.yaml"
        artifacts["distributions"][entry.id] = {
            "definition": entry.artifact, "project": entry.project,
            "spec": entry.artifact.get("spec"),
            "source": (entry.files.get(own) or b"").decode("utf-8") or None}
    if result.layout == "v2":
        specs = _v2_specs(result, root)
    return artifacts, specs


def _projects_meta(db: Session, result: wsv.Result, root: Path | None) -> dict:
    """`workspace_version.projects` of a v2 tree: owner row and file map per project."""
    if result.layout != "v2" or root is None:
        return {}
    meta: dict = {}
    for slug in sorted(result.projects):
        base = root / "projects" / slug
        files, tree = {}, {}
        for path in sorted(base.rglob("*")) if base.is_dir() else ():
            rel = path.relative_to(base).as_posix()
            if path.is_file() and not path.is_symlink() and layout.is_allowed(rel):
                data = path.read_bytes()
                files[rel] = hashlib.sha256(data).hexdigest()
                try:
                    tree[rel] = data.decode("utf-8")
                except UnicodeDecodeError:      # not project text: the digest is all there is
                    continue
        row = db.scalar(select(Project).where(Project.slug == slug, Project.deleted_at.is_(None)))
        manifest = base / "project.yaml"
        meta[slug] = {
            "project_id": row.id if row else None,
            "origin": row.origin if row else "git",
            "name": row.name if row else slug,
            "project_yaml": manifest.read_text(encoding="utf-8") if manifest.is_file() else None,
            "files": files,
            # The project's files as applied: composing the next version replays them instead of
            # rebuilding them (`compose.version_projects`).
            "tree": tree,
        }
    return meta


def _dataset_changes(old: dict, new: dict) -> list[dict]:
    """Datasets whose table the engine must rebuild (type/key/nullability change or removal)."""
    out = []
    for iid, integ in new.get("integrations", {}).items():
        before = old.get("integrations", {}).get(iid)
        if before is None:
            continue
        for name, ds in integ["definition"]["datasets"].items():
            prev = before["definition"]["datasets"].get(name)
            if prev is None:
                continue
            cols, pcols = ds["columns"], prev["columns"]
            changed = [c for c in cols if c in pcols and cols[c]["type"] != pcols[c]["type"]]
            removed = [c for c in pcols if c not in cols]
            if changed or removed or ds.get("primary_key") != prev.get("primary_key"):
                out.append({"integration": iid, "dataset": name, "changed": changed,
                            "removed": removed,
                            "key_changed": ds.get("primary_key") != prev.get("primary_key")})
    return out


def validate_mounted(db: Session) -> Validation:
    root = mounted_path()
    if not (root / "bizview.yaml").is_file():
        return Validation(None, errors=[{"entry": "bizview.yaml", "code": "missing_spec",
                                         "message": t("workspace.no_workspace")}])
    return validate_root(db, root)


def validate_root(db: Session, root: Path) -> Validation:
    """Validation of a workspace tree: the mounted Git checkout or an assistant draft tree."""
    from app.engine import direct

    names = {n.lower() for n in db.scalars(select(DataSource.name))}
    result = wsv.validate(root, known_sources=names,
                          direct=direct.validation_context(db))
    v = Validation(result, errors=[_issue(i) for i in result.issues if i.level == "error"],
                   warnings=[_issue(i) for i in result.issues if i.level != "error"], root=root)
    for rid in result.reports:
        if len(rid) > MAX_DASHBOARD_CODE:
            v.errors.append({"entry": f"reports/{rid}", "code": "schema_error",
                             "message": t("tree.report_id_max_length", max=MAX_DASHBOARD_CODE)})
    committed = wsv.read_lock(root)
    if result.lock is not None:
        if not isinstance(committed, dict):
            v.errors.append({"entry": "bizview.lock", "code": "lock_missing",
                             "message": t("workspace.lock_missing")})
        else:
            for key in wsv.lock_differences(committed, result.lock):
                v.errors.append({"entry": key, "code": "lock_mismatch",
                                 "message": t("workspace.files_changed_after_validation")})
    current = active(db)
    old_entries = (current.lock.get("entries", {}) if current else {})
    new_entries = (result.lock or {}).get("entries", {})
    artifacts = _artifacts(result)[0] if result.lock else {}
    v.changes = {
        "added": sorted(set(new_entries) - set(old_entries)),
        "removed": sorted(set(old_entries) - set(new_entries)),
        "changed": wsv.lock_differences({"entries": {k: old_entries[k] for k in old_entries
                                                     if k in new_entries}},
                                        {"entries": {k: new_entries[k] for k in new_entries
                                                     if k in old_entries}}),
        "dataset_changes": _dataset_changes(current.artifacts, artifacts) if current else [],
    }
    for change in v.changes["dataset_changes"]:
        v.warnings.append({"entry": f"integrations/{change['integration']}",
                           "code": "breaking_dataset_change",
                           "message": t(
                               "workspace.dataset_will_reload",
                               dataset=change['dataset'])})
    return v


def _lock_workspace(db: Session) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
        {"k": lock_key("workspace")},
    )


def lock_workspace(db: Session) -> None:
    """Serialises applies (transaction-scoped, re-entrant within the same transaction)."""
    _lock_workspace(db)


def apply(db: Session, actor: AppUser, ip: str | None) -> WorkspaceVersion:
    """Git apply (R9): the mounted checkout is validated alone, then composed with the
    projects edited in the app; Git projects are mirrored as read-only `git` projects."""
    from app.projects import compose, importer

    _lock_workspace(db)
    v = validate_mounted(db)
    _refuse_invalid(v)
    info = mounted_info() or {}
    git_slugs = sorted(v.result.projects) if v.result.layout == "v2" else ["principal"]
    app_slugs = set(db.scalars(select(Project.slug).where(
        Project.origin != "git", Project.deleted_at.is_(None))))
    clash = sorted(set(git_slugs) & app_slugs)
    if clash:
        raise ApiError(409, "git_slug_conflict",
                       M("projects.git_slug_conflict", slugs=", ".join(clash)),
                       extra={"projects": clash})
    current = active(db)
    app_trees = ({slug: tree for slug, tree in compose.version_projects(current).items()
                  if slug in app_slugs} if current is not None else {})
    if not app_trees:
        version = _activate(db, actor, v, commit=info.get("commit"), ip=ip)
    else:
        version = _apply_composed(db, actor, v, app_trees, commit=info.get("commit"), ip=ip)
    importer.mirror_git_projects(db, version, git_slugs)
    return version


def _apply_composed(db: Session, actor: AppUser, v: Validation, app_trees: dict, *,
                    commit: str | None, ip: str | None) -> WorkspaceVersion:
    """Checkout + app projects of the active version in one tree, validated and locked."""
    import shutil
    import tempfile
    from types import SimpleNamespace

    from app.engine import direct
    from app.projects import compose

    mounted = mounted_path()
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        shutil.copyfile(mounted / "bizview.yaml", tmp / "bizview.yaml")
        if v.result.layout == "v2":
            shutil.copytree(mounted / "projects", tmp / "projects", symlinks=False,
                            ignore=shutil.ignore_patterns(".git"))
        else:
            artifacts, specs = _artifacts(v.result, mounted)
            legacy = compose.legacy_tree(SimpleNamespace(specs=specs, artifacts=artifacts))
            compose.write_tree({**legacy, "project.yaml": compose.LEGACY_PROJECT_YAML},
                               tmp / "projects" / "principal")
        for slug, tree in app_trees.items():
            compose.write_tree(tree, tmp / "projects" / slug)
        names = {n.lower() for n in db.scalars(select(DataSource.name))}
        result = wsv.validate(tmp, known_sources=names, direct=direct.validation_context(db))
        if not result.ok:
            raise ApiError(409, "invalid_workspace", M("workspace.invalid_fix_errors"),
                           extra={"errors": [_issue(i) for i in result.issues
                                             if i.level == "error"]})
        wsv.write_lock(tmp, result.lock)
        composed = validate_root(db, tmp)
        _refuse_invalid(composed)
        return _activate(db, actor, composed, commit=commit, ip=ip,
                         detail_extra={"app_projects": sorted(app_trees)})


def apply_tree(db: Session, actor: AppUser, root: Path, ip: str | None, *,
               origin: str) -> WorkspaceVersion:
    """Apply a workspace tree built outside Git (feature 014 assistant): same checks, same path."""
    _lock_workspace(db)
    v = validate_root(db, root)
    _refuse_invalid(v)
    return _activate(db, actor, v, commit=None, ip=ip, detail_extra={"origin": origin})


def _refuse_invalid(v: Validation) -> None:
    if not v.ok:
        codes = {e["code"] for e in v.errors}
        code = "lock_mismatch" if codes <= {"lock_mismatch"} else "invalid_workspace"
        raise ApiError(409, code, M("workspace.invalid_fix_errors"),
                       extra={"errors": v.errors})


def _activate(db: Session, actor: AppUser, v: Validation, *, commit: str | None,
              ip: str | None, detail_extra: dict | None = None) -> WorkspaceVersion:
    from app.projects import distributions

    artifacts, specs = _artifacts(v.result, v.root)
    old_active = active(db)
    for old in db.scalars(select(WorkspaceVersion).where(
            WorkspaceVersion.state.in_(("active", "previous")))):
        old.state = "previous" if old.state == "active" else "archived"
        db.flush()
    forget_active_version()
    version = WorkspaceVersion(commit=commit, checksum=wsv.lock_checksum(v.result.lock),
                               lock=v.result.lock, artifacts=artifacts, specs=specs,
                               projects=_projects_meta(db, v.result, v.root),
                               state="active", applied_by=actor.id)
    db.add(version)
    db.flush()
    sync_dashboards(db, version)
    distributions.sync(db, version, actor, previous=old_active)
    audit.record(db, "workspace_applied", actor_id=actor.id, ip=ip,
                 detail={"version": version.id, "commit": version.commit,
                         "checksum": version.checksum, "changes": v.changes,
                         **(detail_extra or {})})
    return version


def spec_document(db: Session, key: str) -> dict:
    version = active(db)
    item = (version.specs or {}).get(key) if version else None
    if item is None:
        raise not_found(M("workspace.spec_not_found"))
    return {**_spec_meta(key, item), "documents": item.get("documents") or None}


def rollback(db: Session, actor: AppUser, ip: str | None) -> WorkspaceVersion:
    _lock_workspace(db)
    prev, cur = previous(db), active(db)
    if prev is None:
        raise not_found(M("workspace.no_previous_version"))
    if cur is not None:
        cur.state = "archived"
        db.flush()
    prev.state = "active"
    db.flush()
    forget_active_version()
    sync_dashboards(db, prev)
    from app.projects import distributions

    distributions.sync(db, prev, actor, previous=cur)
    audit.record(db, "workspace_rolled_back", actor_id=actor.id, ip=ip,
                 detail={"version": prev.id, "from": cur.id if cur else None})
    return prev


def sync_dashboards(db: Session, version: WorkspaceVersion) -> None:
    """Reports of the version become available dashboards (grants kept); workspace dashboards
    whose report left the version are hidden, never deleted."""
    reports = version.artifacts.get("reports", {})
    managed = {d.report_id: d for d in db.scalars(
        select(Dashboard).where(Dashboard.report_id.is_not(None)))}
    for order, (rid, rep) in enumerate(sorted(reports.items())):
        d = rep["definition"]
        dash = managed.get(rid) or db.scalar(select(Dashboard).where(Dashboard.code == rid))
        if dash is None:
            dash = Dashboard(code=rid)
            db.add(dash)
        dash.report_id, dash.managed_by, dash.status = rid, "workspace", "available"
        dash.name = d["title"]
        dash.description = (d.get("description") or "")[:200]
        dash.icon = d.get("icon") or "chart-line"
        dash.sort_order = 10 + order
    for rid, dash in managed.items():
        if rid not in reports:
            dash.status = "hidden"
    db.flush()


def integration(db: Session, integration_id: str) -> tuple[WorkspaceVersion, dict]:
    version = active(db)
    item = (version.artifacts.get("integrations", {}).get(integration_id)
            if version else None)
    if item is None:
        raise not_found(M("workspace.integration_not_found"))
    return version, item


def report(db: Session, report_id: str) -> tuple[WorkspaceVersion, dict]:
    version = active(db)
    item = version.artifacts.get("reports", {}).get(report_id) if version else None
    if item is None:
        raise not_found(M("workspace.report_not_found"))
    return version, item


def count_versions(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(WorkspaceVersion)) or 0
