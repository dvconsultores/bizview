from __future__ import annotations

import re
import tempfile
import unicodedata
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from bizview_cli import layout
from bizview_cli import validate as wsv
from sqlalchemy.orm import Session

from app.config import get_settings
from app.i18n import t
from app.workspace.service import MAX_DASHBOARD_CODE, active

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,49}$")
_MAX_FILES = 40
_MAX_FILE_SIZE = 512 * 1024

ALLOWED_PATHS_TEXT: str = "rutas permitidas: " + layout.ALLOWED_TEXT


def paths_error(errors: list[str]) -> str:
    """Devuelve el mensaje de error de rutas no permitidas con la lista de rutas válidas."""
    return "Rutas no permitidas: " + "; ".join(errors) + ". " + ALLOWED_PATHS_TEXT


class TreeError(Exception):
    """Error de construcción del árbol con mensaje en español."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def check_paths(files: dict[str, str]) -> list[str]:
    """Valida rutas y tamaños del borrador. Devuelve lista de errores."""
    errors: list[str] = []
    if len(files) > _MAX_FILES:
        errors.append(f"máximo {_MAX_FILES} archivos")

    for path, content in files.items():
        if "\x00" in path or "\x00" in content:
            errors.append(f"{path}: caracteres NUL no permitidos")
            continue
        if not layout.is_allowed(path):
            errors.append(f"{path}: ruta no permitida")
            continue
        if len(content.encode("utf-8")) > _MAX_FILE_SIZE:
            errors.append(f"{path}: excede {_MAX_FILE_SIZE} bytes")

    return errors


def workspace_name() -> str:
    """Devuelve el nombre del espacio de trabajo a partir del nombre de la organización."""
    settings = get_settings()
    raw = (settings.organization_name or "").strip()
    if not raw:
        return "bizview"

    slug = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    slug = slug.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    slug = re.sub(r"^[^a-z]+", "", slug)
    slug = slug[:50].rstrip("-")
    if not _NAME_RE.match(slug):
        return "bizview"
    return slug


def bootstrap_manifest() -> str:
    """Devuelve el manifiesto YAML inicial para un espacio de trabajo sin versión activa."""
    template_path = (
        resources.files("bizview_cli")
        / "workspace_template"
        / "files"
        / "bizview.yaml"
    )
    template = template_path.read_text(encoding="utf-8")
    return template.format(name=workspace_name())


def _valid_spec_folder(folder: Any) -> bool:
    return isinstance(folder, str) and (
        (
            folder.startswith("specs/integrations/")
            and ".." not in Path(folder).parts
        )
        or (
            folder.startswith("specs/reports/")
            and ".." not in Path(folder).parts
        )
    )


def _write_draft_files(root: Path, files: dict[str, str]) -> None:
    for path, content in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def build_tree(
    db: Session,
    files: dict[str, str] | None,
    dest: Path,
    missing_specs: list[str] | None = None,
) -> Path:
    """Escribe el árbol del espacio de trabajo activo más el borrador en dest."""
    if files:
        errors = check_paths(files)
        if errors:
            raise TreeError(paths_error(errors))

    version = active(db)
    build_version_tree(version, dest, missing_specs)

    if files:
        _write_draft_files(dest, files)

    return dest


def build_version_tree(
    version: Any,
    dest: Path,
    missing_specs: list[str] | None = None,
) -> Path:
    """Write one applied version as a workspace tree (manifest, artifacts, spec documents)."""
    dest.mkdir(parents=True, exist_ok=True)
    if version is None:
        (dest / "bizview.yaml").write_text(bootstrap_manifest(), encoding="utf-8")
    else:
        manifest = version.artifacts.get("workspace")
        if not isinstance(manifest, dict):
            manifest = yaml.safe_load(bootstrap_manifest())
        (dest / "bizview.yaml").write_text(
            yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

        for iid, artifact in version.artifacts.get("integrations", {}).items():
            folder = dest / "integrations" / iid
            folder.mkdir(parents=True, exist_ok=True)
            definition = artifact.get("definition", {})
            (folder / "integration.yaml").write_text(
                yaml.safe_dump(definition, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            for file_path, content in artifact.get("files", {}).items():
                target = folder / file_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

        for rid, artifact in version.artifacts.get("reports", {}).items():
            folder = dest / "reports" / rid
            folder.mkdir(parents=True, exist_ok=True)
            definition = artifact.get("definition", {})
            (folder / "report.yaml").write_text(
                yaml.safe_dump(definition, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            for file_path, content in artifact.get("files", {}).items():
                target = folder / file_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

        for _spec_key, spec_data in (version.specs or {}).items():
            folder_name = spec_data.get("folder")
            if not _valid_spec_folder(folder_name):
                raise TreeError(t("tree.specs_folder_invalid"))

            documents = spec_data.get("documents")
            if not documents:
                if missing_specs is None:
                    raise TreeError(t("tree.apply_workspace_from_git_first"))
                missing_specs.append(folder_name)
                continue

            folder = dest / folder_name
            folder.mkdir(parents=True, exist_ok=True)
            for doc_name, content in documents.items():
                (folder / doc_name).write_text(content, encoding="utf-8")

    return dest


def validate_draft(
    db: Session,
    files: dict[str, str],
    summary: str | None = None,
) -> dict[str, Any]:
    """Valida un borrador contra el espacio de trabajo activo."""
    current = active(db)
    base_integrations = sorted(
        (current.artifacts or {}).get("integrations", {}) if current else {}
    )
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing_specs: list[str] = []
            build_tree(db, files, root, missing_specs)
            from app.engine import direct

            source_names = {name.lower() for name in _source_names(db)}
            result = wsv.validate(root, known_sources=source_names,
                                  direct=direct.validation_context(db))

            errors: list[dict[str, Any]] = []
            warnings: list[dict[str, Any]] = []
            for issue in result.issues:
                problem = issue.as_dict()
                problem.pop("level", None)
                if getattr(issue, "level", "error") == "error":
                    errors.append(problem)
                else:
                    warnings.append(problem)

            for rid in _report_ids(files):
                if len(rid) > MAX_DASHBOARD_CODE:
                    errors.append(
                        {
                            "entry": f"reports/{rid}",
                            "code": "invalid_report_id",
                            "message": t("tree.report_id_max_length", max=MAX_DASHBOARD_CODE),
                            "file": f"reports/{rid}/report.yaml",
                            "path": "/id",
                            "expected": {
                                "type": "string",
                                "maxLength": MAX_DASHBOARD_CODE,
                            },
                            "fix": t("tree.report_id_max_length_fix", max=MAX_DASHBOARD_CODE),
                        }
                    )

            for folder in missing_specs:
                if f"{folder}/spec.md" not in files:
                    errors.append(
                        {
                            "entry": folder,
                            "code": "missing_spec_documents",
                            "message": t("tree.active_version_missing_docs", folder=folder),
                            "file": f"{folder}/spec.md",
                            "path": None,
                            "expected": None,
                            "fix": t("tree.regenerate_folder_docs", folder=folder),
                        }
                    )

            valid = result.ok and not errors
            return {
                "valid": valid,
                "errors": errors,
                "warnings": warnings,
                "lock": result.lock,
                "base_version": current.id if current else None,
                "base_integrations": base_integrations,
            }
    except TreeError as exc:
        return {
            "valid": False,
            "errors": [
                {
                    "entry": "workspace",
                    "code": "missing_spec",
                    "message": exc.message,
                    "file": None,
                    "path": None,
                    "expected": None,
                    "fix": None,
                }
            ],
            "warnings": [],
            "lock": None,
            "base_version": current.id if current else None,
            "base_integrations": base_integrations,
        }


def materialize(
    db: Session, files: dict[str, str]
) -> tuple[tempfile.TemporaryDirectory, Path, Any]:
    """Prepara el árbol para aplicar, validando y escribiendo el lock."""
    tmpdir = tempfile.TemporaryDirectory()
    root = Path(tmpdir.name)
    from app.engine import direct

    build_tree(db, files, root, missing_specs=[])
    source_names = {name.lower() for name in _source_names(db)}
    result = wsv.validate(root, known_sources=source_names,
                          direct=direct.validation_context(db))
    if result.ok:
        wsv.write_lock(root, result.lock)
    return tmpdir, root, result


def _source_names(db: Session) -> list[str]:
    from app.sources.service import list_all

    return [src.name for src in list_all(db)]


def _report_ids(files: dict[str, str]) -> list[str]:
    ids: set[str] = set()
    for path in files:
        parts = Path(path).parts
        if len(parts) >= 2 and parts[0] == "reports":
            ids.add(parts[1])
    return sorted(ids)
