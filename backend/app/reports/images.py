"""Image sets of a report (044): the folder a set reads and the bytes a row key resolves to.

A report declares `images: {<set>: {folder, key, fallback}}`; a component names one with
`image: <set>`. The browser never builds a file name: the report payload carries a URL prefix per
set and the server resolves the key to the file (exact case, then case-insensitive, then the other
extensions), so an author can ship `BTC.png`, `btc.svg` or `btc.webp` without telling anyone.

The bytes come from the project folder — the same copy the editor writes — because an applied
version stores its projects as text and an image has no text form.
"""

from pathlib import Path

from app.projects import assets as asset_rules
from app.projects import fs

FALLBACKS = ("initial", "none")


def declared(ctx) -> dict:
    """The report's `images:` block, or an empty map when it declares none."""
    definition = getattr(ctx, "definition", None) or {}
    images = definition.get("images")
    return images if isinstance(images, dict) else {}


def project_slug(ctx) -> str | None:
    """The project the applied report came from; `None` for a draft preview."""
    version = getattr(ctx, "version", None)
    artifacts = getattr(version, "artifacts", None) or {}
    entry = (artifacts.get("reports") or {}).get(ctx.report_id) or {}
    slug = entry.get("project")
    return slug if isinstance(slug, str) and slug else None


def payload(ctx, base: str | None = None, cached_base: str | None = None) -> dict:
    """What the report definition carries: per set, its key, fallback and URL prefix.

    `base` is the report-scoped asset path of whichever door the client came through
    (`/api/reports/<id>/assets` or `/api/shared/<token>/assets`), so a share link reads the images
    of its report and nothing else; `cached_base` is that same door's cache path. Without them the
    sets are declarative only.
    """
    out: dict[str, dict] = {}
    slug = project_slug(ctx)
    for name, spec in declared(ctx).items():
        if not isinstance(spec, dict):
            continue
        item: dict = {"key": spec.get("key"), "fallback": spec.get("fallback") or "initial"}
        if spec.get("column"):
            item["column"] = spec["column"]
            # A cached URL is served by content hash: the row value *is* `<sha256>.<ext>`, so the
            # client appends it to this prefix and the third party is never contacted.
            if cached_base:
                item["cached_url"] = f"{cached_base}/"
        if base and slug and isinstance(spec.get("folder"), str) and spec["folder"]:
            item["url"] = f"{base}/{name}/"
        out[name] = item
    return out


def _folder(slug: str, spec: dict) -> Path:
    rel = spec.get("folder")
    if not isinstance(rel, str) or not rel:
        raise asset_rules.AssetRefused("set_has_no_folder")
    return fs.resolve(slug, rel.rstrip("/"), folder=True)


def resolve(ctx, set_name: str, key: str) -> tuple[bytes, str, str]:
    """The image of `key` in set `set_name`: (bytes, content type, sha256).

    Raises `AssetRefused` with `unknown_set`, `set_has_no_folder` or `key_not_found`.
    """
    spec = declared(ctx).get(set_name)
    if not isinstance(spec, dict):
        raise asset_rules.AssetRefused("unknown_set", set_name)
    slug = project_slug(ctx)
    if slug is None:
        raise asset_rules.AssetRefused("unknown_set", set_name)
    found = asset_rules.lookup(_folder(slug, spec), key)
    if found is None:
        raise asset_rules.AssetRefused("key_not_found", key)
    rel = f"{str(spec['folder']).rstrip('/')}/{found.name}"
    return fs.read_asset(slug, rel)


def _raster(found: Path) -> bytes | None:
    """The file's bytes when ReportLab can embed them; SVG needs a rasteriser this product does
    not ship, so an SVG-only set draws the initial circle on paper (research R3)."""
    if found.suffix.lower() == ".svg":
        return None
    try:
        return found.read_bytes()
    except OSError:
        return None


def reader(ctx) -> dict[str, dict]:
    """Per set, the column its key comes from and a memoised lookup the PDF can call.

    The resolver never raises: a set whose folder vanished or whose key has no file answers
    `None`, and the block draws the declared fallback instead of failing the document.
    """
    slug = project_slug(ctx)
    if slug is None:
        return {}
    out: dict[str, dict] = {}
    for name, spec in declared(ctx).items():
        if not isinstance(spec, dict):
            continue
        try:
            folder = _folder(slug, spec)
        except (asset_rules.AssetRefused, fs.ProjectPathError):
            continue
        seen: dict[str, bytes | None] = {}

        def load(key: object, folder: Path = folder, seen: dict = seen) -> bytes | None:
            name_ = asset_rules.normalise_key("" if key is None else str(key))
            if not name_:
                return None
            if name_ not in seen:
                found = asset_rules.lookup(folder, name_)
                seen[name_] = _raster(found) if found is not None else None
            return seen[name_]

        out[name] = {"key": spec.get("key"), "bytes": load}
    return out
