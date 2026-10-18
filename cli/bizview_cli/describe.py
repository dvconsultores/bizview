"""`bizview describe "<source>"`: the STRUCTURE of a data source of the installation (tables and
columns, REST response shape, SOAP operations) — never its data — so the author and the AI agent
can write integration specs. Needs BIZVIEW_URL and BIZVIEW_TOKEN (a `describe` token created by
the super user in Administración → Tokens)."""
import json
import os
import sys
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


def fetch(source: str, path: str | None = None) -> dict:
    url, token = os.environ.get("BIZVIEW_URL", "").rstrip("/"), os.environ.get("BIZVIEW_TOKEN")
    if not url or not token:
        raise DescribeError(t("describe.need_config"), EXIT_USAGE)
    try:
        r = httpx.get(f"{url}/api/sources/{quote(source, safe='')}/describe",
                      params={"path": path} if path else None,
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


def describe(source: str, *, path: str | None = None, as_json: bool = False) -> int:
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
