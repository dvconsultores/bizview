"""Feature 048 (US1): the BI-ready declaration, its bounds, and the proof it is read-only."""
import pytest

from app.sources import bi_ready
from tests.conftest import reauth, signed_in, sql


@pytest.fixture
def client(superuser):
    return signed_in("root@example.com")


def make_source(client, *, kind="postgresql", **extra):
    settings = ({"base_url": "https://api.example.test", "username": "lector"}
                if kind == "rest" else
                {"host": "203.0.113.9", "port": 5432, "database": "bi", "username": "lector"})
    body = {"name": "Almacén ventas", "kind": kind, "settings": settings,
            "secrets": {"password": "secreto-de-prueba-123"}, **extra}
    r = reauth(client).post("/api/sources", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def patch_ready(client, source_id, **declaration):
    return reauth(client).patch(f"/api/sources/{source_id}",
                                json={"bi_ready": {"enabled": True, **declaration}})


# --- the declaration is data, and it is checked before it is stored ---------------------------


def test_a_valid_declaration_is_stored_and_audited(client, monkeypatch):
    src = make_source(client)
    monkeypatch.setattr("app.sources.describe.postgresql",
                        lambda settings, secrets, app, write_probe=False: {
                            "kind": "postgresql", "tables": [], "truncated": False,
                            "write_allowed": False})
    r = patch_ready(client, src["id"], schemas=["reporting"], objects=["reporting.v_ventas_dia"],
                    timeout_s=45, cache_ttl_s=120, max_rows=1000, max_parallel=3,
                    timezone="America/Caracas")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["bi_ready_enabled"] is True
    assert body["bi_ready"]["schemas"] == ["reporting"]
    assert body["bi_ready"]["timeout_s"] == 45
    assert body["bi_ready"]["verified_ok"] is True
    assert body["direct_reports"] is True          # the 019 switch follows the declaration
    assert sql("SELECT detail FROM audit_event WHERE kind = 'source_bi_ready_changed'")[-1][0][
        "value"] == {"enabled": True, "schemas": ["reporting"], "objects": 1,
                     "limits": {"timeout_s": 45, "cache_ttl_s": 120, "max_rows": 1000,
                                "max_parallel": 3}}


def test_a_writable_credential_is_refused_and_nothing_is_stored(client, monkeypatch):
    src = make_source(client)
    monkeypatch.setattr("app.sources.describe.postgresql",
                        lambda settings, secrets, app, write_probe=False: {
                            "kind": "postgresql", "tables": [], "truncated": False,
                            "write_allowed": True})
    r = patch_ready(client, src["id"], schemas=["reporting"])
    assert r.status_code == 422, r.text
    assert r.json()["error"]["message"].startswith("Esa credencial puede escribir")
    assert sql("SELECT bi_ready FROM data_source WHERE id = :i", i=src["id"]) == [({},)]
    assert sql("SELECT count(*) FROM audit_event WHERE kind = 'source_bi_ready_changed'") == [(0,)]


def test_only_postgresql_can_be_declared(client):
    src = make_source(client, kind="rest")
    r = patch_ready(client, src["id"], schemas=["reporting"])
    assert r.status_code == 422
    assert r.json()["error"]["fields"] == {"bi_ready": "invalid"} or \
        r.json()["error"]["fields"] == {"bi_ready": "not_allowed"}
    assert r.json()["error"]["message"].startswith("Solo una fuente PostgreSQL")


@pytest.mark.parametrize("declaration,field", [
    ({"schemas": "reporting"}, "bi_ready.schemas"),
    ({"schemas": ["pg_catalog"]}, "bi_ready.schemas"),
    ({"schemas": ["app_test_0000"]}, "bi_ready.schemas"),
    ({"schemas": ["public"], "objects": ["v_ventas"]}, "bi_ready.objects"),
    ({"schemas": ["public"], "objects": ["pg_catalog.pg_class"]}, "bi_ready.objects"),
    ({"schemas": ["public"], "timeout_s": 0}, "bi_ready.timeout_s"),
    ({"schemas": ["public"], "max_rows": 5_000_000}, "bi_ready.max_rows"),
    ({"schemas": ["public"], "timezone": "  "}, "bi_ready.timezone"),
    ({"schemas": ["public"], "nonsense": 1}, "bi_ready"),
])
def test_a_declaration_outside_the_rules_is_refused_naming_the_field(client, declaration, field):
    src = make_source(client)
    r = patch_ready(client, src["id"], **declaration)
    assert r.status_code == 422, r.text
    assert field in r.json()["error"]["fields"], r.text


# --- the scope answers one question, for everybody ---------------------------------------------


class Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_an_undeclared_source_answers_from_the_019_switch():
    assert bi_ready.enabled(Row(bi_ready={}, direct_reports=True)) is True
    assert bi_ready.enabled(Row(bi_ready={}, direct_reports=False)) is False
    assert bi_ready.permitted(Row(bi_ready={}, direct_reports=True), "reporting", "v_ventas")
    assert not bi_ready.permitted(Row(bi_ready={}, direct_reports=True), "pg_catalog", "pg_class")


def test_a_declared_source_answers_from_its_scope():
    src = Row(bi_ready={"enabled": True, "schemas": ["reporting"], "objects": []},
              direct_reports=True)
    assert bi_ready.enabled(src) is True
    assert bi_ready.permitted(src, "reporting", "cualquiera")
    assert bi_ready.permitted(src, "Reporting", "cualquiera")       # case-insensitive
    assert not bi_ready.permitted(src, "public", "ventas")


def test_named_objects_narrow_the_schema():
    src = Row(bi_ready={"enabled": True, "schemas": ["reporting"],
                        "objects": ["reporting.v_ventas_dia"]}, direct_reports=True)
    assert bi_ready.permitted(src, "reporting", "v_ventas_dia")
    assert not bi_ready.permitted(src, "reporting", "otra")


def test_an_empty_scope_means_nothing_never_everything():
    src = Row(bi_ready={"enabled": True, "schemas": []}, direct_reports=True)
    assert bi_ready.permitted(src, "reporting", "v_ventas_dia") is False


def test_the_deny_list_is_never_overridable():
    src = Row(bi_ready={"enabled": True, "schemas": ["reporting"], "objects": []},
              direct_reports=True)
    for schema in ("pg_catalog", "information_schema", "pg_toast_x", "app_test_abc",
                   "preview_1"):
        assert not bi_ready.permitted(src, schema, "x"), schema


def test_a_disabled_declaration_reads_nothing():
    src = Row(bi_ready={"enabled": False, "schemas": ["reporting"]}, direct_reports=True)
    assert bi_ready.enabled(src) is False
    assert bi_ready.permitted(src, "reporting", "x") is False


# --- the limits ---------------------------------------------------------------------------------


def test_the_limits_come_from_the_declaration_then_the_installation():
    declared = Row(bi_ready={"enabled": True, "timeout_s": 90, "max_rows": 100},
                   direct_reports=True)
    assert bi_ready.limits(declared)["timeout_s"] == 90
    assert bi_ready.limits(declared)["cache_ttl_s"] == 300
    plain = Row(bi_ready={}, direct_reports=True)
    assert bi_ready.limits(plain)["max_parallel"] == 2


# --- the health summary -------------------------------------------------------------------------


def test_health_summarises_the_last_day_from_the_log():
    rows = [{"duration_ms": 10, "outcome": "ok", "stale_served": False},
            {"duration_ms": 30, "outcome": "ok", "stale_served": True},
            {"duration_ms": 20, "outcome": "timeout", "stale_served": False}]
    summary = bi_ready.health_summary(rows)
    assert summary["runs"] == 3
    assert summary["failures"] == 1
    assert summary["p50_ms"] == 20
    assert summary["served_from_cache"] == 1
    assert bi_ready.health_summary([]) == {"runs": 0, "failures": 0, "p50_ms": None,
                                           "p95_ms": None, "served_from_cache": 0,
                                           "cache_share": None}
