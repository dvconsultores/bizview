"""`bizview describe "<source>"`: the STRUCTURE of a data source of the installation (tables and
columns, REST response shape, SOAP operations) — never its data — so the author and the AI agent
can write integration specs. Needs BIZVIEW_URL and BIZVIEW_TOKEN (a `describe` token created by
the super user in Administración → Tokens).

`--pack` writes `sources/<name>/structure.md` + `structure.json` (feature 052) using the same
generator the API uses, so the two cannot drift."""
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

import httpx
import yaml

from bizview_cli.i18n import t

EXIT_USAGE, EXIT_NETWORK = 2, 3


class DescribeError(Exception):
    def __init__(self, message: str, exit_code: int):
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code

    def __str__(self) -> str:
        return self.message


def _get_json(path: str, params: dict | None = None) -> dict:
    url, token = os.environ.get("BIZVIEW_URL", "").rstrip("/"), os.environ.get("BIZVIEW_TOKEN")
    if not url or not token:
        raise DescribeError(t("describe.need_config"), EXIT_USAGE)
    try:
        r = httpx.get(f"{url}{path}", params=params,
                      headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                      timeout=60, follow_redirects=False)
    except httpx.HTTPError as e:
        raise DescribeError(t("describe.connect_failed", url=url, exc=type(e).__name__),
                            EXIT_NETWORK) from e
    if r.status_code in (401, 403):
        raise DescribeError(t("describe.token_rejected"), EXIT_NETWORK)
    if r.status_code >= 300:
        try:
            message = r.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            message = f"HTTP {r.status_code}"
        raise DescribeError(t("describe.source_error", message=message), EXIT_NETWORK)
    return r.json()


def fetch(source: str, path: str | None = None) -> dict:
    return _get_json(f"/api/sources/{quote(source, safe='')}/describe",
                     {"path": path} if path else None)


def fetch_pack(source: str, path: str | None = None) -> dict:
    """The pack the installation builds (notes, personal flags and the BI-ready flag included)."""
    return _get_json(f"/api/sources/{quote(source, safe='')}/structure",
                     {"path": path} if path else None)


def write_pack(pack: dict, out_dir: str | Path = ".") -> list[Path]:
    """`sources/<name>/structure.md` + `structure.json`, the layout the authoring pack expects."""
    from bizview_cli.structure import structure_json, structure_markdown

    name = str(pack.get("pack", {}).get("source") or "source")
    folder = Path(out_dir) / "sources" / re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")
    folder.mkdir(parents=True, exist_ok=True)
    markdown, data = folder / "structure.md", folder / "structure.json"
    markdown.write_text(structure_markdown(pack), encoding="utf-8")
    data.write_text(structure_json(pack), encoding="utf-8")
    return [markdown, data]


def describe(source: str, *, path: str | None = None, as_json: bool = False,
             pack: bool = False, out: str = ".") -> int:
    if pack:
        try:
            data = fetch_pack(source, path=path)
            written = write_pack(data, out)
        except DescribeError as e:
            print(e.message, file=sys.stderr)
            return e.exit_code
        for path_written in written:
            print(t("describe.pack_written", path=str(path_written)))
        return 0
    try:
        data = fetch(source, path=path)
    except DescribeError as e:
        print(e.message, file=sys.stderr)
        return e.exit_code
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), end="")
    return 0


def structure_from(data: dict, tables: list[str]) -> dict:
    requested = set(tables)
    if isinstance(data, dict) and isinstance(data.get("pack"), dict):
        data = data.get("structure") or {}
    if not isinstance(data, dict) or data.get("kind") != "postgresql":
        return {"tables": {}, "error": "la descripción no es de una fuente PostgreSQL"}
    result: dict[str, dict] = {}
    truncated = bool(data.get("truncated"))
    for item in data.get("tables") or []:
        if not isinstance(item, dict) or "schema" not in item or "name" not in item:
            continue
        key = f"{item['schema']}.{item['name']}".lower()
        if key not in requested:
            continue
        columns = {str(c["name"]).lower(): str(c.get("type", "")).lower()
                   for c in item.get("columns") or []
                   if isinstance(c, dict) and "name" in c}
        result[key] = {"columns": columns, "product_dependency": False}
    if truncated and len(result) != len(requested):
        return {"tables": {}, "error": "la descripción está truncada y no incluye todas las "
                                      "tablas"}
    return {"tables": result, "error": None}
