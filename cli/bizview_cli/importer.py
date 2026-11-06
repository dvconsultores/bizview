"""`bizview import`: measure a project against both allowances, and diff it against the workspace.

The server measures a zip with `backend/app/projects/zip.py`; the CLI measures a folder or a zip
with the same `budgets.tally`, so an author who is over a limit learns it before uploading, and
learns the same number the server would tell them. Nothing here writes, uploads or contacts a
server: this is a reading of names and sizes.

Feature 055: the same reading answers *what the import would do* to a project that already exists in
the workspace it is run from — `reimported` plus the added/changed/removed paths, or `created` when
the folder is not there. The app is still the one that imports; the CLI's job is that the author
sees the diff before they press anything.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from bizview_cli import budgets, layout
from bizview_cli.i18n import t


class Unreadable(Exception):
    """The input is not something the product would accept at all (exit code 2)."""


def _zip_entries(path: Path) -> list[tuple[str, int, bytes | None]]:
    """(name, size, first bytes) of the archive's regular files. The head is enough to tell a
    program from a text file, and it keeps the dry run cheap on a large archive."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(path.read_bytes()))
    except (OSError, zipfile.BadZipFile) as e:
        raise Unreadable(str(path)) from e
    with archive:
        out: list[tuple[str, int, bytes | None]] = []
        for info in archive.infolist():
            if info.is_dir():
                continue
            try:
                with archive.open(info) as handle:
                    head = handle.read(8)
            except (RuntimeError, zipfile.BadZipFile, OSError) as e:
                raise Unreadable(str(path)) from e
            out.append((info.filename, info.file_size, head))
        return out


def _folder_entries(root: Path) -> list[tuple[str, int, bytes | None]]:
    if not root.is_dir():
        raise Unreadable(str(root))
    out: list[tuple[str, int, bytes | None]] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            children = sorted(current.iterdir())
        except OSError:
            continue
        for child in children:
            rel = child.relative_to(root).as_posix()
            if child.is_symlink():
                continue          # never followed, never imported: the same rule as the server
            if child.is_dir():
                stack.append(child)
            elif child.is_file():
                try:
                    size = child.stat().st_size
                    with child.open("rb") as handle:
                        head = handle.read(8)
                except OSError as e:
                    raise Unreadable(rel) from e
                out.append((rel, size, head))
    return out


def _strip_top(names: list[str]) -> str:
    """The same rule the importer applies: one shared top folder that is not a layout folder."""
    tops = {name.split("/", 1)[0] for name in names}
    if len(tops) != 1 or not all("/" in name for name in names):
        return ""
    top = tops.pop()
    return "" if top in {"specs", "integrations", "reports", "distributions", "themes", "assets",
                         ".specify", "project.yaml"} else f"{top}/"


def measure(path: Path, *, workspace: Path | None = None) -> dict:
    """What would happen if this folder or zip were imported. Never raises for a refusal."""
    entries = _zip_entries(path) if path.suffix.lower() == ".zip" else _folder_entries(path)
    prefix = _strip_top([name for name, _, _ in entries])
    relative = [(name[len(prefix):], size, head) for name, size, head in entries]
    report = budgets.tally(relative, budgets.defaults())
    slug = _slug(path, prefix)
    existing = _project_folder(workspace or Path.cwd(), slug)
    return {
        "path": str(path),
        "slug": slug,
        "folded_top": bool(prefix),
        "importable": report.importable,
        "reason": _message(report.refusal) if report.refusal else None,
        "ignored": report.ignored,
        "budgets": report.as_json(),
        "code": report.refusal.code if report.refusal else None,
        # 055
        "mode": "reimported" if existing is not None else "created",
        "existing": str(existing) if existing is not None else None,
        "diff": _diff(relative, existing),
    }


def _slug(path: Path, prefix: str) -> str:
    """The slug the server would use: `project.yaml`'s, then the folded folder, then the file name.

    Only the `slug:` line is read — the file itself is the server's to validate."""
    import re

    try:
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(io.BytesIO(path.read_bytes())) as archive:
                name = f"{prefix}project.yaml"
                if name not in archive.namelist():
                    raise KeyError(name)
                text = archive.read(name).decode("utf-8", "replace")
        else:
            text = (path / "project.yaml").read_text("utf-8")
    except (OSError, KeyError, UnicodeDecodeError, zipfile.BadZipFile):
        text = ""
    match = re.search(r"^slug:\s*([a-z][a-z0-9-]{1,49})\s*$", text, re.MULTILINE)
    return match.group(1) if match else (prefix.rstrip("/") or path.stem)


def _project_folder(workspace: Path, slug: str) -> Path | None:
    """The folder of that project in the workspace the command runs in.

    Only the v2 layout (`projects/<slug>/`) and the workspace that *is* that project count: a
    sibling folder named after the slug is the author's source, not a revision to compare with.
    """
    candidate = workspace / "projects" / slug
    if candidate.is_dir():
        return candidate
    if workspace.name == slug and (workspace / "project.yaml").is_file():
        return workspace
    return None


def _diff(relative: list[tuple[str, int, bytes | None]], existing: Path | None) -> dict:
    """What the archive adds, changes and removes against the folder on disk (055)."""
    incoming: dict[str, int] = {name: size for name, size, _head in relative}
    before: dict[str, int] = {}
    if existing is not None:
        for child in sorted(existing.rglob("*")):
            if child.is_file() and not child.is_symlink():
                before[child.relative_to(existing).as_posix()] = child.stat().st_size
    added = sorted(set(incoming) - set(before))
    removed = sorted(set(before) - set(incoming))
    # A size is what the CLI has without reading every file; the server compares hashes.
    changed = sorted(path for path in incoming if path in before
                     and before[path] != incoming[path])
    specs_added = sorted({_spec_folder(p) for p in added if _spec_folder(p)})
    specs_removed = sorted({_spec_folder(p) for p in removed if _spec_folder(p)})
    return {"added": added, "changed": changed, "removed": removed,
            "specs": {"added": specs_added, "removed": specs_removed},
            "counts": {"added": len(added), "changed": len(changed), "removed": len(removed),
                       "specs_added": len(specs_added), "specs_removed": len(specs_removed)}}


def _spec_folder(path: str) -> str | None:
    parts = path.split("/")
    if len(parts) >= 3 and parts[0] == "specs" and layout.SPEC_FOLDER_RE.match(parts[1]):
        return parts[1]
    return None


def _message(refusal: budgets.Refusal) -> str:
    keys = {
        "zip_disallowed": "cli.projects.zip_disallowed",
        "artifacts_over_files": "cli.projects.artifacts_over_files",
        "artifacts_over_bytes": "cli.projects.artifacts_over_bytes",
        "artifacts_file_too_large": "cli.projects.artifacts_file_too_large",
        "assets_over_files": "cli.projects.assets_over_files",
        "assets_over_bytes": "cli.projects.assets_over_bytes",
        "assets_file_too_large": "cli.projects.assets_file_too_large",
    }
    return t(keys[refusal.code], **refusal.params)


def render_diff(diff: dict) -> list[str]:
    """The diff: counts first, then the paths (bounded, so a terminal stays readable)."""
    counts = diff["counts"]
    lines = [t("cli.diff_counts", added=counts["added"], changed=counts["changed"],
               removed=counts["removed"], specs_added=counts["specs_added"],
               specs_removed=counts["specs_removed"])]
    for key, marker in (("added", "+"), ("changed", "~"), ("removed", "-")):
        for path in diff[key][:20]:
            lines.append(f"  {marker} {path}")
        if len(diff[key]) > 20:
            lines.append(t("cli.diff_more", more=len(diff[key]) - 20))
    return lines


def _size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB".replace(".", ",")
    return f"{max(1, round(size / 1024))} KB"


def render_budgets(result: dict) -> str:
    """Just the two allowance lines, for `bizview validate` (the verdict belongs to the import)."""
    lines = []
    for name in (layout.ARTIFACTS, layout.ASSETS):
        tally = result["budgets"][name]
        verdict = (t("cli.budget_over", over=", ".join(tally["over"])) if tally["over"]
                   else t("cli.budget_ok"))
        lines.append(t("cli.budget_line", name=name, files=tally["files"],
                       size=_size(tally["bytes"]), max_files=tally["max_files"],
                       max_mb=tally["max_mb"]) + f"  {verdict}")
    if result["ignored"]:
        lines.append(t("cli.budget_ignored", count=len(result["ignored"]),
                       paths=", ".join(result["ignored"][:6])
                       + (", …" if len(result["ignored"]) > 6 else "")))
    return "\n".join(lines)


def render(result: dict) -> str:
    """The human reading: the mode, both allowances, what changed, what was ignored, the verdict."""
    lines = [f"{result['path']}"]
    if result["folded_top"]:
        lines.append(t("cli.budget_project", slug=result["slug"]))
    lines.append(t("cli.diff_mode", mode=result["mode"],
                   folder=result.get("existing") or "—"))
    lines.extend(render_diff(result["diff"]))
    for name in (layout.ARTIFACTS, layout.ASSETS):
        tally = result["budgets"][name]
        verdict = (t("cli.budget_over", over=", ".join(tally["over"])) if tally["over"]
                   else t("cli.budget_ok"))
        lines.append(t("cli.budget_line", name=name, files=tally["files"],
                       size=_size(tally["bytes"]), max_files=tally["max_files"],
                       max_mb=tally["max_mb"]) + f"  {verdict}")
    if result["ignored"]:
        lines.append(t("cli.budget_ignored", count=len(result["ignored"]),
                       paths=", ".join(result["ignored"][:6])
                       + (", …" if len(result["ignored"]) > 6 else "")))
    if result["importable"]:
        lines.append(t("cli.budget_importable"))
    else:
        lines.append(t("cli.budget_not_importable"))
        lines.append(t("cli.budget_reason", message=result["reason"]))
    return "\n".join(lines)
