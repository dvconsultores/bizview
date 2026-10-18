"""Supabase sources (feature 016): the project's REST API (PostgREST) at <url>/rest/v1/.

Stored as the two values Supabase gives (SUPABASE_URL, SUPABASE_SERVICE_KEY) and run through the
REST connector: the key goes in both the `apikey` header and the Bearer token, as Supabase
requires. Requests are GETs only (tests, descriptions, extraction).
"""
from app.config import Settings
from app.sources.connectors import rest
from app.sources.connectors.base import TestResult
from app.sources.schemas import header_secret_key

API_PATH = "/rest/v1/"


def api_base(url: str) -> str:
    base = url.strip().rstrip("/")
    if base.endswith("/rest/v1"):   # the API address pasted instead of the project URL
        base = base[: -len("/rest/v1")]
    return base + API_PATH


def rest_settings(settings: dict) -> dict:
    return {"base_url": api_base(settings["url"]), "test_path": "/", "auth": "bearer",
            "headers": [{"name": "apikey", "secret": True}],
            "timeout_seconds": settings.get("timeout_seconds")}


def rest_secrets(secrets: dict) -> dict:
    key = secrets.get("service_key")
    return {"token": key, header_secret_key("apikey"): key} if key else {}


def test(settings: dict, secrets: dict, app: Settings) -> TestResult:
    return rest.test(rest_settings(settings), rest_secrets(secrets), app)
