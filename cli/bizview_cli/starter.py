"""The starter pack (feature 057): one template, rendered three ways.

The pack lives at `pack/bizview-starter-pack/` in the repository. `render()` applies the project
name, its slug, the language, the first-spec kind and (optionally) a source's structure, and returns
the text files of the zip. The server serves it, `bizview init project` writes it, and
`make starter-template` commits the version with placeholders — all through this module, so the
three cannot drift.
"""
from __future__ import annotations

import io
import os
import zipfile
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

from . import layout

LANGS = ("es", "en")
KINDS = ("integration", "direct")
TEMPLATE_NAME = "bizview-starter-template.zip"
TEMPLATE_SLUG = "<slug>"
TEMPLATE_PROJECT = "<nombre>"
SOURCE_PLACEHOLDER = "<fuente>"

#: Documents written for a reader. The chosen language keeps the canonical name; the other one
#: travels beside it with its suffix, so a chat-based author can read both.
BILINGUAL = ("PROMPT.md", "REQUEST.md", "README.md")
#: Documents that always ship in both languages under their own names (one per language).
FIXED = {"es": {"CONTENIDO.md": "CONTENIDO.md", "QUE-HACE-BIZVIEW.md": "QUE-HACE-BIZVIEW.md",
                  "COMO-SE-DIBUJA.md": "COMO-SE-DIBUJA.md"},
         "en": {"CONTENTS.md": "CONTENTS.md", "WHAT-BIZVIEW-DOES.md": "WHAT-BIZVIEW-DOES.md",
                "HOW-IT-RENDERS.md": "HOW-IT-RENDERS.md"}}
#: Agentic tools read a fixed name; it carries the prompt's text.
AGENT_FILES = ("CLAUDE.md", "AGENTS.md")
#: Skeletons shared by both kinds, then the ones each kind adds.
COMMON = "common"
FLAVOURS = {"integration": ("integration",), "direct": ("direct",)}

ZIP_DATE = (1980, 1, 1, 0, 0, 0)


class PackError(Exception):
    """The pack is missing or a selection is invalid."""


def plain_slug(name: str) -> str:
    """The slug a name derives to (one implementation for the CLI and the server)."""
    return layout.plain_slug(name)


def pack_dir() -> Path:
    """The pack source: an explicit path, the copy inside the wheel, or the repository's folder."""
    override = os.environ.get("BIZVIEW_STARTER_PACK", "").strip()
    if override:
        path = Path(override).expanduser()
        if not (path / "files").is_dir():
            raise PackError(f"BIZVIEW_STARTER_PACK does not hold a starter pack: {path}")
        return path
    packaged = resources.files("bizview_cli") / "starter_pack"
    if (packaged / "files").is_dir():
        return Path(str(packaged))
    here = Path(__file__).resolve().parent
    for parent in here.parents:
        candidate = parent / "pack" / "bizview-starter-pack"
        if (candidate / "files").is_dir():
            return candidate
    raise PackError("the starter pack was not found; set BIZVIEW_STARTER_PACK")


def _walk(root: Path, prefix: str = "") -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    for item in sorted(root.iterdir()):
        rel = f"{prefix}{item.name}"
        if item.is_dir():
            out.extend(_walk(item, f"{rel}/"))
        elif item.is_file():
            out.append((rel, item.read_bytes()))
    return out


def _apply(text: bytes, values: dict[str, str]) -> str:
    out = text.decode("utf-8")
    for key, value in values.items():
        out = out.replace("{{" + key + "}}", value)
    return out


def _skeletons(kind: str, values: dict[str, str]) -> dict[str, str]:
    root = pack_dir() / "files"
    files: dict[str, str] = {}
    for part in (COMMON, *FLAVOURS[kind]):
        for rel, data in _walk(root / part):
            path = _apply(rel.encode("utf-8"), values)
            files[path] = _apply(data, values)
    return files


def _documents(lang: str, values: dict[str, str]) -> dict[str, str]:
    """The prose: the chosen language at its name, the other one with its suffix, the fixed ones."""
    root = pack_dir()
    files: dict[str, str] = {}
    other = "en" if lang == "es" else "es"
    for name in BILINGUAL:
        files[name] = _apply((root / lang / name).read_bytes(), values)
        files[f"{name[:-3]}.{other}.md"] = _apply((root / other / name).read_bytes(), values)
    for source, target in FIXED[lang].items():
        files[target] = _apply((root / lang / source).read_bytes(), values)
    for source, target in FIXED[other].items():
        files[target] = _apply((root / other / source).read_bytes(), values)
    prompt = files["PROMPT.md"]
    for name in AGENT_FILES:
        files[name] = prompt
        files[f"{name[:-3]}.{other}.md"] = files[f"PROMPT.{other}.md"]
    return files


def schemas() -> dict[str, str]:
    """The JSON Schemas the validator reads, from the one place the product keeps them."""
    root = resources.files("bizview_cli") / "schemas"
    return {f".bizview/schemas/{item.name}": item.read_text(encoding="utf-8")
            for item in sorted(root.iterdir())
            if item.name.endswith(".json")}


def render(*, name: str | None = None, slug: str | None = None, lang: str = "es",
           kind: str = "integration", source: str | None = None,
           template: bool = False, date: str | None = None) -> dict[str, str]:
    """Every text file of one starter zip, keyed by its path inside the zip.

    `template=True` keeps the placeholders (`<slug>`, `<nombre>`): that is the public template, not
    a project. A rendered project always gets a real slug, because the validator and the import
    both read it as identity."""
    if lang not in LANGS:
        raise PackError(f"lang must be one of {LANGS}: {lang!r}")
    if kind not in KINDS:
        raise PackError(f"kind must be one of {KINDS}: {kind!r}")
    if template:
        slug = TEMPLATE_SLUG
        display = TEMPLATE_PROJECT
        source_name = SOURCE_PLACEHOLDER
    else:
        display = (name or "").strip()
        if not display:
            raise PackError("a project name is required")
        slug = slug or plain_slug(display)
        if not layout.ID_RE.match(slug):
            raise PackError(f"the name does not yield a usable slug: {slug!r}")
        source_name = (source or SOURCE_PLACEHOLDER).strip() or SOURCE_PLACEHOLDER
    values = {"name": display, "slug": slug, "source": source_name,
              "dataset": slug.replace("-", "_")[:40].strip("_") or "dataset",
              "date": date or ("<fecha>" if template else datetime.now(UTC).date().isoformat())}
    files = {**_skeletons(kind, values), **_documents(lang, values), **schemas()}
    return dict(sorted(files.items()))


def zip_bytes(files: dict[str, bytes | str]) -> bytes:
    """A deterministic zip: sorted names, fixed timestamp, no directory entries."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(files):
            data = files[name]
            if isinstance(data, str):
                data = data.encode("utf-8")
            info = zipfile.ZipInfo(name, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)
    return buffer.getvalue()


def filename(slug: str) -> str:
    return f"bizview-starter-{slug}.zip"
