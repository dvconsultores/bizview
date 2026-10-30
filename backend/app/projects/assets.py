"""Project assets: the images an author ships inside a project (feature 044).

An asset is a file under `assets/` of a project folder. This module is the single place that decides
what an asset may be: the magic bytes (never the extension alone), the size, and — for SVG — the
allowlist that makes the stored file safe to serve and to embed in a PDF.

Nothing here talks to a database or to the network: it reads and writes files under a project root
that the caller resolved with `fs.resolve_project_path`, so the path rules of feature 037 apply
unchanged.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_KB = 300
MAX_FILES = 2000
EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".svg")
CONTENT_TYPES = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "svg": "image/svg+xml",
}

# SVG survivors: shapes and groups a drawing needs, nothing that can run or fetch.
SVG_ELEMENTS = frozenset({
    "svg", "g", "defs", "title", "desc", "symbol", "use", "switch",
    "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
    "text", "tspan", "textPath",
    "linearGradient", "radialGradient", "stop", "pattern", "clipPath", "mask", "filter",
    "feGaussianBlur", "feOffset", "feBlend", "feColorMatrix", "feMerge", "feMergeNode",
    "feFlood", "feComposite", "feMorphology",
})
# Attributes that can execute or reach outside the document.
SVG_FORBIDDEN_ATTRS = frozenset({"href", "xlink:href", "src", "action", "formaction"})
SVG_URL_ATTRS = ("fill", "stroke", "filter", "clip-path", "mask", "marker-start", "marker-mid",
                 "marker-end")

_KEY_SAFE = re.compile(r"[^A-Za-z0-9._-]+")

# Keep the stored SVG readable: without this, ElementTree writes `ns0:svg` prefixes and a human
# reviewing an asset sees noise instead of the artwork.
ET.register_namespace("", "http://www.w3.org/2000/svg")
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")


class AssetRefused(Exception):
    """The bytes are not an asset this product will store."""

    def __init__(self, reason: str, detail: str = ""):
        self.reason = reason          # too_large | not_image | svg_refused | too_many
        self.detail = detail
        super().__init__(reason if not detail else f"{reason}: {detail}")


def normalise_key(key: str) -> str:
    """A row key as a file stem: `/` and spaces become `_`, everything else unsafe goes too."""
    cleaned = _KEY_SAFE.sub("_", (key or "").strip())
    return cleaned.strip("._-")


def sniff(data: bytes, name: str, *, strict: bool = True) -> str:
    """The real type of `data`; raises when it is not one of the four, or disagrees with `name`.

    `strict=False` is for a body fetched from a URL, where the path carries no usable extension
    (`/logos/1234`, `/logo.png?v=2`): the magic bytes are then the only evidence, and they are
    enough — the name a file gets is the hash, not the one the address claimed.
    """
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        kind = "png"
    elif data.startswith(b"\xff\xd8\xff"):
        kind = "jpeg"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        kind = "webp"
    elif _looks_like_svg(data):
        kind = "svg"
    else:
        raise AssetRefused("not_image", name)

    if not strict:
        return kind
    suffix = Path(name).suffix.lower()
    if suffix == ".svg" and kind != "svg":
        raise AssetRefused("not_image", name)
    if suffix in (".png", ".jpg", ".jpeg", ".webp") and kind == "svg":
        raise AssetRefused("not_image", name)
    if kind == "jpeg" and suffix not in (".jpg", ".jpeg"):
        raise AssetRefused("not_image", name)
    if kind in ("png", "webp") and suffix != f".{kind}":
        raise AssetRefused("not_image", name)
    return kind


def _looks_like_svg(data: bytes) -> bool:
    head = data[:1024].lstrip(b"\xef\xbb\xbf \t\r\n")
    return head.startswith(b"<") and b"<svg" in data[:4096]


def check_size(data: bytes, name: str) -> None:
    if len(data) > MAX_KB * 1024:
        raise AssetRefused("too_large", name)


def sanitise_svg(data: bytes, name: str) -> bytes:
    """Parse, drop everything dangerous, and return the bytes to store (never the original)."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise AssetRefused("svg_refused", f"{name}: {exc}") from None
    _clean(root, name)
    return ET.tostring(root, encoding="utf-8", xml_declaration=False)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _clean(node: ET.Element, name: str) -> None:
    if _local(node.tag) not in SVG_ELEMENTS:
        raise AssetRefused("svg_refused", f"{name}: <{_local(node.tag)}>")
    for attr in list(node.attrib):
        local = _local(attr)
        if local.lower().startswith("on") or local in {_local(a) for a in SVG_FORBIDDEN_ATTRS}:
            raise AssetRefused("svg_refused", f"{name}: {local}")
        if local in {_local(a) for a in SVG_URL_ATTRS} and "url(" in node.attrib[attr]:
            raise AssetRefused("svg_refused", f"{name}: {local}=url(…)")
    for child in list(node):
        if isinstance(child.tag, str):
            _clean(child, name)


def prepare(data: bytes, name: str) -> tuple[bytes, str, str]:
    """Validate `data` and return what to store: (bytes, kind, content type).

    SVG comes back sanitised; everything else comes back untouched.
    """
    kind = sniff(data, name)
    check_size(data, name)
    stored = sanitise_svg(data, name) if kind == "svg" else data
    return stored, kind, CONTENT_TYPES[kind]


def lookup(folder: Path, key: str) -> Path | None:
    """Find the file for `key` in `folder`, in the order the contract publishes.

    Exact case first, then a case-insensitive match, then the other extensions in the same order.
    """
    stem = normalise_key(key)
    if not stem or not folder.is_dir():
        return None
    try:
        entries = {entry.name: entry for entry in folder.iterdir()
                   if entry.is_file() and not entry.is_symlink()}
    except OSError:
        return None
    for ext in ("png", "svg", "webp", "jpg", "jpeg"):
        exact = f"{stem}.{ext}"
        if exact in entries:
            return entries[exact]
    lowered = {name.lower(): entry for name, entry in entries.items()}
    for ext in ("png", "svg", "webp", "jpg", "jpeg"):
        found = lowered.get(f"{stem}.{ext}".lower())
        if found is not None:
            return found
    return None
