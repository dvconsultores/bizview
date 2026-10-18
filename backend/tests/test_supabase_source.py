"""Feature 016: Supabase data sources (SUPABASE_URL + SUPABASE_SERVICE_KEY over its REST API)."""
import httpx
import pytest

from app.sources.connectors import rest
from app.sources.connectors import supabase as sb
from app.sources.describe import openapi_tables
from tests.conftest import reauth, signed_in

KEY = "sb-service-SECRET-123"


@pytest.fixture
def su(superuser):
    return reauth(signed_in("root@example.com"))


def test_api_base_accepts_project_or_api_url():
    assert sb.api_base("https://abcd.supabase.co") == "https://abcd.supabase.co/rest/v1/"
    assert sb.api_base("https://abcd.supabase.co/") == "https://abcd.supabase.co/rest/v1/"
    assert sb.api_base("https://abcd.supabase.co/rest/v1/") == "https://abcd.supabase.co/rest/v1/"


def test_key_goes_in_apikey_header_and_bearer_token():
    settings = sb.rest_settings({"url": "https://abcd.supabase.co"})
    with httpx.Client() as client:
        headers, params, auth = rest.build_request(settings, sb.rest_secrets({"service_key": KEY}),
                                                   client)
    assert headers["apikey"] == KEY
    assert headers["Authorization"] == f"Bearer {KEY}"
    assert params == {} and auth is None


def test_openapi_tables_structure_only():
    spec = {"definitions": {
        "ventas": {"required": ["id", "fecha"], "properties": {
            "id": {"type": "integer", "format": "bigint",
                   "description": "Note:\nThis is a Primary Key.<pk/>"},
            "fecha": {"type": "string", "format": "timestamp with time zone"},
            "total": {"type": "number", "format": "numeric", "default": 0,
                      "description": "monto con IVA"}}},
        "marca": {"properties": {"nombre": {"type": "string", "format": "text"}}}}}
    out = openapi_tables(spec)
    assert [t["name"] for t in out["tables"]] == ["marca", "ventas"]
    ventas = out["tables"][1]
    assert ventas["primary_key"] == ["id"]
    assert ventas["columns"][1] == {"name": "fecha", "type": "timestamp with time zone",
                                    "nullable": False}
    assert "monto con IVA" not in str(out) and "default" not in str(out)
    assert out["truncated"] is False


def test_create_supabase_source_secret_is_write_only(su):
    r = su.post("/api/sources", json={
        "name": "Supabase Customer B", "kind": "supabase",
        "settings": {"url": "https://203.0.113.9"}, "secrets": {"service_key": KEY}})
    assert r.status_code in (200, 201), r.text
    src = r.json()
    assert src["kind"] == "supabase"
    assert src["secret_fields"] == ["service_key"]
    assert KEY not in r.text
    types = su.get("/api/sources/types").json()
    assert [f["name"] for f in types["supabase"]["fields"]][:2] == ["url", "service_key"]


def test_supabase_source_requires_url_and_key(su):
    r = su.post("/api/sources", json={"name": "Incompleta", "kind": "supabase",
                                      "settings": {}, "secrets": {}})
    assert r.status_code == 422
    fields = r.json()["error"]["fields"]
    assert "settings.url" in fields and "secrets.service_key" in fields
