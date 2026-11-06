"""Project zip download and import (feature 020, research R13)."""
import io
import re
import shutil
import zipfile
from importlib import resources

import yaml
from bizview_cli import budgets as shared_budgets
from bizview_cli import layout
from sqlalchemy import select

from app.errors import ApiError
from app.i18n import M
from app.projects import assets as asset_rules
from app.projects import budgets as project_budgets
from app.projects import fs
from app.projects import service as project_service
from app.services import audit

MAX_RATIO = 100
LAYOUT_TOPS = {"specs", "integrations", "reports", "distributions", "themes", "assets", ".specify",
               "project.yaml"}

README = """# {name}

Proyecto BI de Bizview. Para trabajarlo con un agente de código, una sola vez en esta carpeta:

```sh
specify init --here --force --integration claude --script sh --non-interactive \\
  --ignore-agent-tools
specify preset add --dev .bizview/preset
specify extension add .bizview/extension --dev
```

Dentro de un espacio de trabajo v2 la carpeta va en `projects/<slug>/`; valida desde la raíz con
`bizview validate --write-lock`. Para volver a subirlo: Proyectos → Importar proyecto.
"""


def _walk(node, prefix: str):
    for item in node.iterdir():
        if item.is_dir():
            yield from _walk(item, f"{prefix}{item.name}/")
        elif item.is_file():
            yield f"{prefix}{item.name}", item.read_bytes()


def _package_files(name: str) -> dict[str, bytes]:
    """Spec Kit templates, preset, extension, schemas and agent rules for the download."""
    pkg = resources.files("bizview_cli")
    tpl = pkg / "workspace_template"
    files = {f".specify/templates/{rel}": data
             for rel, data in _walk(tpl / "preset" / "templates", "")}
    files.update({f".bizview/preset/{rel}": data for rel, data in _walk(tpl / "preset", "")})
    files.update({f".bizview/extension/{rel}": data
                  for rel, data in _walk(tpl / "extension", "")})
    files.update({f".bizview/schemas/{rel}": data for rel, data in _walk(pkg / "schemas", "")
                  if rel.endswith(".json")})
    for rules in ("AGENTS.md", "CLAUDE.md"):
        files[rules] = (tpl / "files" / rules).read_bytes()
    files["README.md"] = README.format(name=name).encode("utf-8")
    return files


def export(db, actor, project, ip: str | None = None) -> bytes:
    """`<slug>/` with the project's layout files plus the files an agent needs to work on it."""
    listed, _ = fs.list_files(project.slug)
    entries = {f"{project.slug}/{rel}": data for rel, data in _package_files(project.name).items()}
    for path in sorted(listed):
        if path.startswith("assets/"):          # 044: images are binary
            entries[f"{project.slug}/{path}"] = fs.read_asset(project.slug, path)[0]
        else:
            entries[f"{project.slug}/{path}"] = fs.read_text(project.slug, path).encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in sorted(entries.items()):
            zf.writestr(name, data)
    audit.record(db, "project_exported", actor_id=actor.id, ip=ip,
                 detail={"project_id": project.id, "project": project.slug,
                         "files": len(listed)})
    return buffer.getvalue()


def export_revision(db, actor, project, revision, ip: str | None = None) -> tuple[bytes, list[str]]:
    """One revision as a zip of the same shape `export` produces (FR-013).

    Text comes from the history by `(path, sha256)`; an image comes from disk while the file still
    carries that hash. Whatever cannot be read back is returned so the caller can say it — 044 keeps
    images by hash, never by content, and silence would look like data loss."""
    from app.projects import reimport as reimport_rules

    files, missing = reimport_rules.revisions.resolve_files(db, project, revision)
    entries = {f"{project.slug}/{rel}": data for rel, data in _package_files(project.name).items()}
    for path, text in sorted(files.items()):
        if path.startswith(layout.ASSET_PREFIX):
            entries[f"{project.slug}/{path}"] = fs.read_asset(project.slug, path)[0]
        else:
            entries[f"{project.slug}/{path}"] = text.encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in sorted(entries.items()):
            zf.writestr(name, data)
    audit.record(db, "project_exported", actor_id=actor.id, ip=ip,
                 detail={"project_id": project.id, "project": project.slug,
                         "revision": revision.number, "files": len(files) + len(missing)})
    return buffer.getvalue(), missing


class ZipRejected(Exception):
    """An import that stops. `code` is the API's error code; `message` is already translated."""

    def __init__(self, code: str, message: "M") -> None:
        self.code = code
        self.message = message
        super().__init__(code)


#: The i18n key that says why a refusal happened, and the params each one needs.
REFUSAL_KEYS = {
    "zip_disallowed": "projects.zip_disallowed",
    "artifacts_over_files": "projects.artifacts_over_files",
    "artifacts_over_bytes": "projects.artifacts_over_bytes",
    "artifacts_file_too_large": "projects.artifacts_file_too_large",
    "assets_over_files": "projects.assets_over_files",
    "assets_over_bytes": "projects.assets_over_bytes",
    "assets_file_too_large": "projects.assets_file_too_large",
}


def _refusal(refusal: shared_budgets.Refusal) -> ZipRejected:
    """One budget's refusal, in the language of the request, naming only that budget."""
    return ZipRejected(refusal.code, M(REFUSAL_KEYS[refusal.code], **refusal.params))


def _structural(reason: str) -> ZipRejected:
    return ZipRejected("zip_invalid", M("projects.zip_invalid", reason=reason))


def _unsafe_name(name: str) -> bool:
    parts = name.split("/")
    return (name.startswith("/") or "\\" in name or "\x00" in name
            or re.match(r"^[A-Za-z]:", name) is not None
            or any(part in ("", ".", "..") for part in parts))


def _max_entries(limits: dict[str, shared_budgets.Budget]) -> int:
    """How many archive entries to walk at all: the two allowances, twice over for directories."""
    return 2 * sum(budget.max_files for budget in limits.values())


def _entries(data: bytes, limits: dict[str, shared_budgets.Budget]) -> list[tuple[str, bytes]]:
    """(name, content) of the regular files of the archive, after every safety check.

    Feature 049: the archive may carry both allowances, so its own size cap is their sum and the
    entry cap follows the two file counts. What protects against a zip bomb — the ratio and the
    declared size matching the bytes actually read — is unchanged."""
    max_bytes = project_budgets.zip_max_mb(limits) * 1024 * 1024
    if len(data) > max_bytes:
        raise ZipRejected("too_large", M("projects.zip_too_large", max_mb=max_bytes // 1048576))
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise _structural("format") from e
    with archive:
        infos = archive.infolist()
        if len(infos) > _max_entries(limits):
            raise _structural("entries")
        entries: list[tuple[str, bytes]] = []
        total = 0
        for info in infos:
            if info.is_dir():
                continue
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise _structural("symlink")
            if _unsafe_name(info.filename):
                raise _structural("path")
            total += info.file_size
            if total > max_bytes:
                raise ZipRejected("too_large",
                                  M("projects.zip_too_large", max_mb=max_bytes // 1048576))
            if info.compress_size > 0 and info.file_size / info.compress_size > MAX_RATIO:
                raise _structural("ratio")
            try:
                with archive.open(info) as handle:
                    content = handle.read(max_bytes + 1)
            except (RuntimeError, zipfile.BadZipFile, OSError) as e:   # encrypted / corrupt
                raise _structural("format") from e
            if len(content) != info.file_size:
                raise _structural("size")
            entries.append((info.filename, content))
    return entries


def _strip_top(names: list[str]) -> str | None:
    """One top folder shared by every entry (e.g. `<slug>/`) is dropped."""
    tops = {name.split("/", 1)[0] for name in names}
    if len(tops) != 1 or not all("/" in name for name in names):
        return None
    top = tops.pop()
    return None if top in LAYOUT_TOPS else f"{top}/"


THEME_PATH = re.compile(r"^themes/([a-z][a-z0-9-]{1,39})\.(?:yaml|yml)$")
THEME_POLICIES = ("skip", "replace", "rename")


def _live_project(db, slug: str):
    """The project a zip's slug belongs to, or None. A deleted one is not re-imported into: the
    folder is in the trash waiting for its purge, and resurrecting it would surprise everybody."""
    from app.models import Project

    if not isinstance(slug, str) or not layout.ID_RE.match(slug):
        return None
    return db.scalar(select(Project).where(Project.slug == slug, Project.deleted_at.is_(None)))


def _copy_suffix(db, slug: str) -> str:
    """`-2`, `-3`… for a copy: the smallest number whose slug is free."""
    from app.models import Project

    taken = set(db.scalars(select(Project.slug).where(Project.deleted_at.is_(None))))
    for number in range(2, 1000):
        candidate = f"{slug[:50 - len(str(number)) - 1]}-{number}"
        if candidate not in taken:
            return f"-{number}"
    raise ApiError(409, "slug_taken", M("projects.slug_taken", slug=slug))


def _reimport(db, actor, project, files: dict[str, str], images: dict[str, bytes],
              ignored: list[str], report, ip: str | None, *, dry_run: bool,
              replace_draft: bool, themes_on_conflict: str) -> dict:
    """Write the archive as the project's new draft revision — or answer the diff and stop."""
    from app.projects import reimport as reimport_rules

    reimport_rules.pin_slug(files, project.slug)
    diff = reimport_rules.plan(db, project, files, images)
    base = {
        "project": project_service.project_json(project),
        "mode": "reimported",
        "ignored": sorted(ignored),
        "budgets": report.as_json(),
        "diff": diff,
        "revision": None,
    }
    if dry_run:
        # Nothing is written: the author is reading what the import would do (FR-009).
        db.rollback()
        return {**base, "themes": [], "validation": (project.validation or {}),
                "needs_confirmation": reimport_rules.plan_needs_confirmation(db, project)}
    result = reimport_rules.execute(db, actor, project, files=files, images=images, ip=ip,
                                    replace_draft=replace_draft)
    if result["needs_confirmation"]:
        # Nothing was written: the answer is the question (FR-014).
        db.rollback()
        return {**base, "themes": [], "validation": (project.validation or {}),
                "diff": result["diff"], "needs_confirmation": True}
    themes_report = _project_themes(db, project.id, files, themes_on_conflict)
    db.commit()
    validation = project_service.revalidate(db, project)["validation"]
    db.commit()
    return {**base, "project": project_service.project_json(project), "themes": themes_report,
            "validation": validation,
            "revision": reimport_rules.revision_json(result["revision"]),
            "diff": result["diff"], "needs_confirmation": False}


def import_zip(db, actor, data: bytes, *, name: str | None = None, slug: str | None = None,
               themes_on_conflict: str = "skip", ip: str | None = None, copy: bool = False,
               dry_run: bool = False, replace_draft: bool = False) -> dict:
    """A zip with one project: imports it, or re-imports it as a new revision (feature 055).

    Feature 047: `themes/*.yaml` inside the zip also enters the installation's library, with
    `origin = project`. An id that already exists is answered by `themes_on_conflict` — skip it
    (the library keeps its own), replace it, or rename the project's so both survive.

    Feature 055: a slug that already belongs to a project is the *same* project — the archive
    becomes its new draft revision (full replacement) and the answer says `mode: "reimported"`.
    A second project is only what `copy=True` asks for, and the copy gets its own artifact ids so it
    can apply (037). `dry_run` answers the diff and writes nothing."""
    limits = project_budgets.effective(db)
    entries = _entries(data, limits)
    prefix = _strip_top([n for n, _ in entries]) or ""
    relative = [(raw[len(prefix):], content) for raw, content in entries]
    # 049: measured before anything is written, against the allowance each path belongs to. A
    # project over a limit leaves no row and no folder behind because it never gets that far.
    report = shared_budgets.tally(
        [(rel, len(content), content) for rel, content in relative], limits)
    if report.refusal is not None:
        raise _refusal(report.refusal)
    files: dict[str, str] = {}
    images: dict[str, bytes] = {}
    ignored: list[str] = []
    for rel, content in relative:
        try:
            fs.check_rel(rel)
            if layout.budget_of(rel) is None:
                raise ValueError(rel)
            if rel.startswith(layout.ASSET_PREFIX):
                # 044: validated here so a bad image is reported in `ignored`, never half-written.
                images[rel] = asset_rules.prepare(
                    content, rel, limits[layout.ASSETS].max_kb)[0]
                continue
            files[rel] = content.decode("utf-8")
        except (fs.ProjectPathError, ValueError, asset_rules.AssetRefused):
            # UnicodeDecodeError is a ValueError
            ignored.append(rel)
    try:
        meta = yaml.safe_load(files.get("project.yaml") or "")
    except yaml.YAMLError:
        meta = None
    meta = meta if isinstance(meta, dict) else {}
    title = str(name or meta.get("name") or prefix.strip("/") or "Proyecto importado")[:80]
    wanted = slug or meta.get("slug")
    if not (isinstance(wanted, str) and layout.ID_RE.match(wanted)):
        # 055: the derived slug is the project's identity, not a suggestion — a name that is taken
        # is the same project coming back, so the derivation never appends `-2` (that is `copy`).
        wanted = project_service.plain_slug(title)

    # 055: the same slug is the same project. `copy` is the only way to ask for a second one.
    existing = None if copy else _live_project(db, wanted)
    if existing is not None:
        return _reimport(db, actor, existing, files, images, ignored, report, ip,
                         dry_run=dry_run, replace_draft=replace_draft,
                         themes_on_conflict=themes_on_conflict)
    if dry_run:
        # Nothing exists yet: the preview says "created" and writes nothing (FR-009).
        from app.projects import reimport as reimport_rules
        from app.projects import revisions

        db.rollback()
        return {"project": None, "mode": "created", "revision": None,
                "diff": {**revisions.diff_maps({}, reimport_rules.archive_hashes(files, images)),
                         "base_revision": None},
                "ignored": sorted(ignored), "budgets": report.as_json(), "themes": [],
                "validation": {"errors": [], "warnings": []}, "needs_confirmation": False}

    suffix = ""
    from app.projects import reimport as reimport_rules

    if copy:
        suffix = _copy_suffix(db, wanted)
        wanted = f"{wanted[:50 - len(suffix)]}{suffix}"
        reimport_rules.rename_ids(files, images, suffix)
    try:
        project = project_service.create(db, actor, title, wanted, "", ip)
    except ApiError as e:
        if e.code != "slug_taken":
            raise
        project = project_service.create(db, actor, title,
                                         project_service.suggest_slug(db, wanted), "", ip)
    themes_report = _project_themes(db, project.id, files, themes_on_conflict)
    db.commit()
    try:
        reimport_rules.pin_slug(files, project.slug)
        fs.apply_ops(project.id, [
            {"op": "write", "path": path, "content": text, "base_sha256": None, "force": True}
            for path, text in sorted(files.items())
        ], {"kind": "user", "user_id": actor.id, "session_id": None, "command": "import"})
        for path, data in sorted(images.items()):
            fs.apply_asset(project.id, path, data,
                           {"kind": "user", "user_id": actor.id, "session_id": None,
                            "command": "import"})
    except (fs.ProjectPathError, asset_rules.AssetRefused) as e:
        # Nothing half-imported stays behind (e.g. two spec folders with the same number).
        shutil.rmtree(fs.project_root(project.slug), ignore_errors=True)
        db.delete(project)
        db.commit()
        if isinstance(e, asset_rules.AssetRefused):
            raise ApiError(422, e.reason, M("assets.svg_refused", path=e.detail,
                                            detail=e.reason)) from e
        raise ApiError(422, e.code, e.message) from e
    result = project_service.revalidate(db, project)
    audit.record(db, "project_imported", actor_id=actor.id, ip=ip,
                 detail={"project_id": project.id, "project": project.slug,
                         "files": len(files), "images": len(images),
                         "ignored": len(ignored), "source": "zip",
                         **({"copy_of": slug} if copy else {})})
    db.flush()
    # 055: a project is born at revision 1, so its chip and its history exist from the first import.
    from app.projects import reimport as reimport_rules
    from app.projects import revisions

    first = revisions.create(db, project, source="import", status="draft",
                             files=revisions.snapshot(project.slug),
                             summary={**revisions.empty_diff(), "created": True},
                             actor_id=actor.id)
    db.commit()
    return {"project": project_service.project_json(project), "ignored": sorted(ignored),
            "themes": themes_report, "validation": result["validation"],
            "budgets": report.as_json(), "mode": "created",
            # A new project's diff is its whole content: there was nothing to compare against.
            "diff": {**revisions.diff_maps({}, reimport_rules.archive_hashes(files, images)),
                     "base_revision": None},
            "revision": reimport_rules.revision_json(first),
            "needs_confirmation": False}


def _project_themes(db, project_id: int, files: dict[str, str], policy: str) -> list[dict]:
    """The `themes/*.yaml` of an imported project into the library (047 FR-016).

    Returns one line per theme file: what happened to it (`imported`, `replaced`, `renamed`,
    `skipped`) or why it could not be used. The project's folder keeps its own copy of every file,
    including a skipped one, so the project still exports what it brought."""
    from app.services import themes as store

    if policy not in THEME_POLICIES:
        policy = "skip"
    report: list[dict] = []
    for path in sorted(p for p in files if p.startswith("themes/")):
        data, problems = store.parse(files[path])
        if problems or data is None:
            report.append({"file": path, "outcome": "refused",
                           "problems": [{"path": p.path, "code": p.code, "message": p.message}
                                        for p in problems]})
            continue
        theme_id = str(data["id"])
        existing = store.get(db, theme_id)
        if existing is not None and existing.origin == store.BUILTIN_ORIGIN:
            # The product's own look is never replaced by an import: the project's copy is kept
            # as a file and simply does not become the installation's theme.
            report.append({"file": path, "outcome": "skipped", "id": theme_id,
                           "reason": "builtin"})
            continue
        if existing is not None and policy == "skip":
            report.append({"file": path, "outcome": "skipped", "id": theme_id,
                           "reason": existing.origin})
            continue
        outcome = "imported"
        if existing is not None and policy == "rename":
            renamed = store.free_id(db, theme_id)
            files[path] = yaml.safe_dump({**data, "id": renamed}, sort_keys=False,
                                         allow_unicode=True, width=100)
            _repoint_reports(files, theme_id, renamed)
            data, theme_id = {**data, "id": renamed}, renamed
            outcome = "renamed"
        elif existing is not None:
            outcome = "replaced"
        store.save(db, data, origin=store.PROJECT_ORIGIN, project_id=project_id)
        report.append({"file": path, "outcome": outcome, "id": theme_id})
    return report


def _repoint_reports(files: dict[str, str], old: str, new: str) -> None:
    """A renamed theme carries the project's own references with it, so no report dangles.

    Only the `theme:` block is touched: a report's own `id:` may equal a theme id by coincidence,
    and rewriting it would rename the report."""
    for path in [p for p in files if p.startswith("reports/")]:
        lines = files[path].splitlines()
        in_theme = False
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped == "theme:":
                in_theme = True
                continue
            if in_theme and stripped and not line[:1].isspace():
                in_theme = False
            if not in_theme:
                continue
            match = re.match(r"^(\s*(?:id|palette):\s*)(\S+)\s*$", line)
            if match and match.group(2) == old:
                lines[index] = f"{match.group(1)}{new}"
        files[path] = "\n".join(lines) + ("\n" if files[path].endswith("\n") else "")
