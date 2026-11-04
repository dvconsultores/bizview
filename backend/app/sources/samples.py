"""Running a saved sample request through a REST/Supabase source's own credential (052, FR-002).

The sample is a read: `GET` only, the path relative to the base URL the source already stores, the
same guarded client and the same host checks the describe uses. What comes back is the *shape* —
keys and types — and the product's own suggestions; no response value is kept anywhere.
"""
from __future__ import annotations

import json
import time
from urllib.parse import urljoin

from app.config import Settings
from app.engine.extract import ExtractError, same_origin
from app.i18n import t
from app.security import profile
from app.security.netguard import guarded_client, policy_from_settings
from app.sources import describe as describer
from app.sources import structure as structure_service
from app.sources.connectors import rest
from app.sources.connectors import supabase as supabase_connector

MAX_PARAMS = 50


def clean_path(path: str) -> str:
    """The relative path a sample may name; absolute paths and URLs are refused, never fixed."""
    rel = (path or "").strip()
    if not rel or "://" in rel or rel.startswith("/") or ".." in rel.split("/"):
        raise ExtractError(t("sourceStructure.sample_path"))
    return rel


def clean_params(params: dict | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in list((params or {}).items())[:MAX_PARAMS]:
        if not isinstance(key, str) or not key.strip():
            raise ExtractError(t("sourceStructure.sample_path"))
        out[key.strip()] = "" if value is None else str(value)[:500]
    return out


def run(source, secrets: dict, app: Settings, path: str, params: dict | None,
        timeout: float = 20) -> dict:
    """One GET; returns the shape and the suggestions. No value is returned or kept."""
    rel = clean_path(path)
    if source.kind == "rest":
        settings, sample_secrets = source.settings, secrets
    else:
        settings = supabase_connector.rest_settings(source.settings)
        sample_secrets = supabase_connector.rest_secrets(secrets)
    if profile.url_problem(settings["base_url"], app):
        raise ExtractError(t("sources.https_required"))
    base = settings["base_url"].rstrip("/") + "/"
    url = same_origin(base, urljoin(base, rel))
    started = time.monotonic()
    with guarded_client(policy=policy_from_settings(app), timeout=timeout,
                        verify=rest._verify(settings)) as client:
        headers, extra, auth = rest.build_request(settings, sample_secrets, client)
        with client.stream("GET", url, headers=headers,
                           params={**extra, **clean_params(params)}, auth=auth) as r:
            body, status = rest._read_limited(r), r.status_code
    if status >= 300:
        raise ExtractError(t("sources.http_status", status=status))
    try:
        data = json.loads(body)
    except ValueError:
        raise ExtractError(t("sources.response_not_json")) from None
    shape = describer.shape(data)
    found = structure_service.suggestions_for(shape, _record(data))
    elapsed_ms = int((time.monotonic() - started) * 1000)
    return {"status": status, "shape": shape, "duration_ms": elapsed_ms, **found}


def _record(data):
    """The object the shape came from: its values are read for a date *format*, then dropped."""
    node = data
    for _depth in range(8):
        if isinstance(node, list):
            return node[0] if node and isinstance(node[0], dict) else None
        if not isinstance(node, dict):
            return None
        deeper = next((v for v in node.values() if isinstance(v, (list, dict)) and v), None)
        if deeper is None:
            return node
        node = deeper
    return None
