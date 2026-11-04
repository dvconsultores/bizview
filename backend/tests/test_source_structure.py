"""Feature 052 / US1: the structure tab's backend — the pack, the flags, the notes, the samples.

Everything here is metadata. The describe is faked (no origin in the suite), and the assertions are
about what a pack must contain and what it must never contain.
"""
import pytest
from bizview_cli.structure import build_pack, structure_json, structure_markdown

from app.sources import describe as describer
from app.sources import structure as structure_service
from tests.conftest import client, reauth, signed_in, sql

SECRET = "ACME-SECRET-CUSTOMER-9931"
PG = {"name": "ERP ventas", "kind": "postgresql", "settings": {
    "host": "203.0.113.9", "port": 5432, "database": "erp", "username": "bi_ro"},
      "secrets": {"password": "Origin-Secret-9f3k"}}
REST = {"name": "coinmarketcap", "kind": "rest",
        "settings": {"base_url": "https://api.coinmarketcap.test", "auth": "none"},
        "secrets": {}}

STRUCTURE = {
    "kind": "postgresql", "truncated": False,
    "tables": [
        {"schema": "ventas", "name": "orders", "kind": "table", "estimated_rows": 1200,
         "primary_key": ["id"],
         "foreign_keys": [{"column": "customer_id", "references": "customers.id"}],
         "columns": [
             {"name": "id", "type": "integer", "nullable": False},
             {"name": "created_at", "type": "timestamp with time zone", "nullable": False,
              "range": {"min": "2023-01-04", "max": "2026-11-02"}},
             {"name": "customer_email", "type": "text", "nullable": True},
             {"name": "total_amount", "type": "numeric(12,2)", "nullable": False},
         ]},
    ],
}


@pytest.fixture
def su(superuser):
    return reauth(signed_in("root@example.com"))


@pytest.fixture
def faked_describe(monkeypatch):
    """The describe the source page would run, without an origin."""
    seen = {}

    def fake(kind, settings, secrets, app, path=None, write_probe=False, date_ranges=False):
        seen["kind"], seen["path"], seen["date_ranges"] = kind, path, date_ranges
        return STRUCTURE

    monkeypatch.setattr(describer, "describe", fake)
    return seen


def create(c, body):
    r = c.post("/api/sources", json=body)
    assert r.status_code == 201, r.text
    return r.json()


# --- the download -------------------------------------------------------------------------

def test_structure_json_is_the_generator_output(su, faked_describe):
    create(su, PG)
    r = su.get("/api/sources/ERP ventas/structure")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/json")
    assert 'filename="structure.json"' in r.headers["content-disposition"]
    assert r.json()["pack"]["source"] == "ERP ventas"
    assert r.json()["pack"]["kind"] == "postgresql"
    # the describe the pack asks for is the one with date ranges (the tab shows them)
    assert faked_describe["date_ranges"] is True


def test_structure_markdown_is_a_download(su, faked_describe):
    create(su, PG)
    r = su.get("/api/sources/ERP ventas/structure?format=md")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/markdown")
    assert 'filename="structure.md"' in r.headers["content-disposition"]
    text = r.text
    assert text.startswith("# Fuente «ERP ventas» — estructura")
    assert "#### Tabla `orders` — ~1200 filas" in text
    assert "| customer_email | text | sí |  | **sí** |  |" in text
    assert "## Observaciones" in text


def test_download_is_audited_as_a_describe(su, faked_describe):
    create(su, PG)
    su.get("/api/sources/ERP ventas/structure?format=md")
    kinds = [k for (k,) in sql("SELECT kind FROM audit_event WHERE kind = 'source_described'")]
    assert kinds == ["source_described"]
    detail = str(sql("SELECT detail FROM audit_event WHERE kind = 'source_described'"))
    assert "md" in detail and "ERP ventas" in detail


def test_structure_requires_a_super_user(admin, user, faked_describe):
    assert client().get("/api/sources/x/structure").status_code == 401
    for who in (admin, user):
        assert signed_in(who.email).get("/api/sources/x/structure").status_code == 403


def test_unknown_source_is_404(su, faked_describe):
    assert su.get("/api/sources/nope/structure").status_code == 404


def test_describe_failure_is_a_typed_error_without_the_host(su, monkeypatch):
    from app.engine.extract import ExtractError

    create(su, PG)

    def boom(*_a, **_kw):
        raise ExtractError("no se pudo conectar")

    monkeypatch.setattr(describer, "describe", boom)
    r = su.get("/api/sources/ERP ventas/structure")
    assert r.status_code == 502 and r.json()["error"]["code"] == "source_error"
    assert "203.0.113.9" not in r.text


# --- notes and flags ----------------------------------------------------------------------

def test_notes_round_trip_into_the_pack(su, faked_describe):
    src = create(su, PG)
    r = su.put("/api/sources/ERP ventas/structure/notes",
               json={"notes": "Plan free: 333 llamadas al día."})
    assert r.status_code == 200 and r.json()["notes"] == "Plan free: 333 llamadas al día."
    assert "Plan free: 333 llamadas al día." in su.get(
        "/api/sources/ERP ventas/structure?format=md").text
    detail = str(sql("SELECT detail FROM audit_event "
                     "WHERE kind = 'source_structure_notes_updated'"))
    assert "chars" in detail and "Plan free" not in detail
    assert src["id"]


def test_notes_need_step_up(superuser, faked_describe):
    create(reauth(signed_in("root@example.com")), PG)
    fresh = signed_in("root@example.com")
    assert fresh.put("/api/sources/ERP ventas/structure/notes",
                     json={"notes": "x"}).status_code == 403


def test_personal_flag_can_be_overridden_and_travels(su, faked_describe):
    create(su, PG)
    r = su.put("/api/sources/ERP ventas/structure/columns", json={
        "schema_name": "ventas", "table": "orders", "column": "customer_email",
        "personal": False})
    assert r.status_code == 200, r.text
    pack = su.get("/api/sources/ERP ventas/structure").json()
    columns = {c["name"]: c for c in pack["structure"]["tables"][0]["columns"]}
    assert columns["customer_email"]["personal"] is False
    markdown = su.get("/api/sources/ERP ventas/structure?format=md").text
    assert "| customer_email | text | sí |  |  |  |" in markdown


def test_flag_for_an_unknown_column_is_refused(su, faked_describe):
    create(su, PG)
    r = su.put("/api/sources/ERP ventas/structure/columns", json={
        "schema_name": "ventas", "table": "orders", "column": "nope", "personal": True})
    assert r.status_code == 422 and r.json()["error"]["fields"] == {"column": "unknown"}


# --- sample requests ----------------------------------------------------------------------

def test_sample_crud_keeps_the_path_relative(su, faked_describe):
    create(su, REST)
    r = su.post("/api/sources/coinmarketcap/samples", json={
        "name": "listados", "path": "v1/cryptocurrency/listings/latest",
        "params": {"limit": "100"}})
    assert r.status_code == 201, r.text
    sample = r.json()
    assert sample["method"] == "GET" and sample["params"] == {"limit": "100"}
    listed = su.get("/api/sources/coinmarketcap/samples").json()["items"]
    assert [s["name"] for s in listed] == ["listados"]
    assert su.post("/api/sources/coinmarketcap/samples", json={
        "name": "LISTADOS", "path": "otra"}).status_code == 409
    assert su.delete(f"/api/sources/coinmarketcap/samples/{sample['id']}").status_code == 204
    assert su.get("/api/sources/coinmarketcap/samples").json()["items"] == []


@pytest.mark.parametrize("path", ["https://evil.test/x", "/absolute", "a/../../etc", ""])
def test_sample_refuses_an_absolute_or_escaping_path(su, faked_describe, path):
    create(su, REST)
    r = su.post("/api/sources/coinmarketcap/samples", json={"name": "x", "path": path})
    assert r.status_code == 422 and r.json()["error"]["fields"] == {"path": "invalid"}


def test_samples_only_on_rest_or_supabase(su, faked_describe):
    create(su, PG)
    r = su.post("/api/sources/ERP ventas/samples", json={"name": "x", "path": "orders"})
    assert r.status_code == 422 and r.json()["error"]["fields"] == {"kind": "unsupported"}


def test_running_a_sample_stores_the_shape_and_never_a_value(su, faked_describe, monkeypatch):
    from app.sources import samples as sample_service

    calls = {}

    def fake_run(source, secrets, app, path, params, timeout=20):
        calls.update(path=path, params=params)
        return {"status": 200, "shape": {"data": [{"id": "integer", "when": "string"}]},
                "records": "$.data", "fields": {"id": "$.id", "when": "$.when"},
                "types": {"id": "integer", "when": "string"},
                "timestamp_units": "iso8601", "pagination": None, "duration_ms": 12}

    monkeypatch.setattr(sample_service, "run", fake_run)
    create(su, REST)
    sample = su.post("/api/sources/coinmarketcap/samples", json={
        "name": "listados", "path": "v1/listings", "params": {"limit": "5"}}).json()
    r = su.post(f"/api/sources/coinmarketcap/samples/{sample['id']}/run")
    assert r.status_code == 200, r.text
    assert r.json()["records"] == "$.data" and r.json()["timestamp_units"] == "iso8601"
    assert calls["path"] == "v1/listings"
    stored = sql("SELECT last_shape::text, last_suggestions::text, last_status "
                 "FROM source_sample_request")[0]
    assert SECRET not in stored[0] + stored[1] and stored[2] == 200
    assert "iso8601" in stored[1]


def test_running_a_sample_that_fails_keeps_the_line_without_secrets(su, faked_describe,
                                                                   monkeypatch):
    from app.engine.extract import ExtractError
    from app.sources import samples as sample_service

    def boom(*_a, **_kw):
        raise ExtractError("la fuente respondió HTTP 403")

    monkeypatch.setattr(sample_service, "run", boom)
    create(su, REST)
    sample = su.post("/api/sources/coinmarketcap/samples",
                     json={"name": "listados", "path": "v1/listings"}).json()
    r = su.post(f"/api/sources/coinmarketcap/samples/{sample['id']}/run")
    assert r.status_code == 502 and r.json()["error"]["code"] == "source_error"
    assert sql("SELECT last_error FROM source_sample_request")[0][0]


# --- the parser the tab relies on ---------------------------------------------------------

def test_pack_of_a_rest_source_lists_its_samples(su, faked_describe):
    monkeypatch_structure = {"kind": "rest", "path": "/v1/listings",
                             "shape": {"data": [{"id": "integer"}]}, "truncated": False}
    faked_describe["kind"] = "rest"
    pack = build_pack(monkeypatch_structure, source="coinmarketcap", kind="rest",
                      samples=[{"name": "listados", "method": "GET", "path": "v1/listings",
                                "params": {"limit": "100"}, "records": "$.data",
                                "fields": {"id": "$.id"}, "types": {"id": "integer"}}])
    text = structure_markdown(pack)
    assert "### Petición `listados` — GET `v1/listings`" in text
    assert '`records: "$.data"`.' in text


def test_pack_never_carries_the_credential_or_the_host(su, faked_describe):
    create(su, PG)
    markdown = su.get("/api/sources/ERP ventas/structure?format=md").text
    data = su.get("/api/sources/ERP ventas/structure").text
    for secret in ("Origin-Secret-9f3k", "203.0.113.9", "bi_ro", SECRET):
        assert secret not in markdown and secret not in data


def test_json_and_markdown_come_from_the_same_generator(su, faked_describe):
    create(su, PG)
    data = su.get("/api/sources/ERP ventas/structure").json()
    served_json = su.get("/api/sources/ERP ventas/structure").json()
    served_markdown = su.get("/api/sources/ERP ventas/structure?format=md").text
    # `generated_at` moves between two reads; everything else must be identical.
    data["pack"]["generated_at"] = served_json["pack"]["generated_at"] = "X"
    assert structure_json(data) == structure_json(served_json)
    assert structure_markdown(data) == served_markdown


def test_flags_are_read_per_source(su, faked_describe):
    create(su, PG)
    create(su, {**PG, "name": "otra"})
    su.put("/api/sources/ERP ventas/structure/columns", json={
        "schema_name": "ventas", "table": "orders", "column": "total_amount", "personal": True})
    mine = su.get("/api/sources/ERP ventas/structure").json()
    other = su.get("/api/sources/otra/structure").json()
    columns = {c["name"]: c for c in mine["structure"]["tables"][0]["columns"]}
    other_columns = {c["name"]: c for c in other["structure"]["tables"][0]["columns"]}
    assert columns["total_amount"]["personal"] is True
    assert other_columns["total_amount"]["personal"] is False


def test_set_flag_creates_and_updates_one_row(su, faked_describe, db):
    src = create(su, PG)
    from app.sources import service

    source = service.get(db, src["id"])
    structure_service.set_flag(db, source, schema="ventas", table="orders",
                               column="total_amount", personal=True)
    db.commit()
    structure_service.set_flag(db, source, schema="ventas", table="orders",
                               column="total_amount", personal=False)
    db.commit()
    assert structure_service.flags(db, source) == {"ventas.orders.total_amount": False}
