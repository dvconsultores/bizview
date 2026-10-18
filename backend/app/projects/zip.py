"""Project zip download and import (feature 020, research R13)."""
import io
import re
import shutil
import zipfile
from importlib import resources

import yaml
from bizview_cli import layout

from app.config import get_settings
from app.errors import ApiError
from app.i18n import M
from app.projects import fs
from app.projects import service as project_service
from app.services import audit

MAX_ENTRIES = 1000
MAX_RATIO = 100
LAYOUT_TOPS = {"specs", "integrations", "reports", "distributions", ".specify", "project.yaml"}

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
        entries[f"{project.slug}/{path}"] = fs.read_text(project.slug, path).encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in sorted(entries.items()):
            zf.writestr(name, data)
    audit.record(db, "project_exported", actor_id=actor.id, ip=ip,
                 detail={"project_id": project.id, "project": project.slug,
                         "files": len(listed)})
    return buffer.getvalue()


class ZipRejected(Exception):
    def __init__(self, code: str, reason: str) -> None:
        self.code = code
        self.message = M("projects.zip_invalid", reason=reason)
        super().__init__(reason)


def _unsafe_name(name: str) -> bool:
    parts = name.split("/")
    return (name.startswith("/") or "\\" in name or "\x00" in name
            or re.match(r"^[A-Za-z]:", name) is not None
            or any(part in ("", ".", "..") for part in parts))


def _entries(data: bytes) -> list[tuple[str, bytes]]:
    """(name, content) of the regular files of the archive, after every safety check."""
    max_bytes = get_settings().project_max_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise ZipRejected("too_large", "size")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise ZipRejected("zip_invalid", "format") from e
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ENTRIES:
            raise ZipRejected("zip_invalid", "entries")
        entries: list[tuple[str, bytes]] = []
        total = 0
        for info in infos:
            if info.is_dir():
                continue
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ZipRejected("zip_invalid", "symlink")
            if _unsafe_name(info.filename):
                raise ZipRejected("zip_invalid", "path")
            total += info.file_size
            if total > max_bytes:
                raise ZipRejected("too_large", "size")
            if info.compress_size > 0 and info.file_size / info.compress_size > MAX_RATIO:
                raise ZipRejected("zip_invalid", "ratio")
            try:
                with archive.open(info) as handle:
                    content = handle.read(max_bytes + 1)
            except (RuntimeError, zipfile.BadZipFile, OSError) as e:   # encrypted / corrupt
                raise ZipRejected("zip_invalid", "format") from e
            if len(content) != info.file_size:
                raise ZipRejected("zip_invalid", "size")
            entries.append((info.filename, content))
    return entries


def _strip_top(names: list[str]) -> str | None:
    """One top folder shared by every entry (e.g. `<slug>/`) is dropped."""
    tops = {name.split("/", 1)[0] for name in names}
    if len(tops) != 1 or not all("/" in name for name in names):
        return None
    top = tops.pop()
    return None if top in LAYOUT_TOPS else f"{top}/"


def import_zip(db, actor, data: bytes, *, name: str | None = None, slug: str | None = None,
               ip: str | None = None) -> dict:
    """New project from a zip: layout files imported (`command=import`), the rest ignored;
    validation problems are reported, never blocking."""
    entries = _entries(data)
    prefix = _strip_top([n for n, _ in entries]) or ""
    files: dict[str, str] = {}
    ignored: list[str] = []
    for raw, content in entries:
        rel = raw[len(prefix):]
        try:
            fs.check_rel(rel)
            if not layout.is_allowed(rel):
                raise ValueError(rel)
            files[rel] = content.decode("utf-8")
        except (fs.ProjectPathError, ValueError):   # UnicodeDecodeError is a ValueError
            ignored.append(rel)
    try:
        meta = yaml.safe_load(files.get("project.yaml") or "")
    except yaml.YAMLError:
        meta = None
    meta = meta if isinstance(meta, dict) else {}
    title = str(name or meta.get("name") or prefix.strip("/") or "Proyecto importado")[:80]
    wanted = slug or meta.get("slug")
    if not (isinstance(wanted, str) and layout.ID_RE.match(wanted)):
        wanted = project_service.suggest_slug(db, title)
    try:
        project = project_service.create(db, actor, title, wanted, "", ip)
    except ApiError as e:
        if e.code != "slug_taken":
            raise
        project = project_service.create(db, actor, title,
                                         project_service.suggest_slug(db, wanted), "", ip)
    db.commit()
    if "project.yaml" in files:
        files["project.yaml"] = re.sub(r"^slug:.*$", f"slug: {project.slug}",
                                       files["project.yaml"], flags=re.M)
    try:
        fs.apply_ops(project.id, [
            {"op": "write", "path": path, "content": text, "base_sha256": None, "force": True}
            for path, text in sorted(files.items())
        ], {"kind": "user", "user_id": actor.id, "session_id": None, "command": "import"})
    except fs.ProjectPathError as e:
        # Nothing half-imported stays behind (e.g. two spec folders with the same number).
        shutil.rmtree(fs.project_root(project.slug), ignore_errors=True)
        db.delete(project)
        db.commit()
        raise ApiError(422, e.code, e.message) from e
    result = project_service.revalidate(db, project)
    audit.record(db, "project_imported", actor_id=actor.id, ip=ip,
                 detail={"project_id": project.id, "project": project.slug,
                         "files": len(files), "ignored": len(ignored), "source": "zip"})
    db.flush()
    return {"project": project_service.project_json(project), "ignored": sorted(ignored),
            "validation": result["validation"]}
