"""Direct-source catalogue and execution tests (feature 019, FR-004, FR-006)."""
import pytest
import yaml
from bizview_cli import validate as wsv
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.db import get_sessionmaker
from app.engine import direct, extract, report
from app.engine.direct import DirectRunner
from tests.conftest import reauth, signed_in, sql
from tests.test_vibe_reporting import apply, lock
from tests.workspace_fixture import write

PW = "Origin-Secret-9f3k"
STATIC_PG = {
    "kind": "postgresql",
    "settings": {"host": "203.0.113.9", "port": 5432, "database": "erp", "username": "bi_ro"},
    "secrets": {"password": PW},
}


def pg_body(name="ERP directo", **over):
    url = make_url(get_settings().database_url_bi)
    body = {
        "name": name,
        "kind": "postgresql",
        "description": "",
        "settings": {
            "host": url.host,
            "port": url.port or 5432,
            "database": url.database,
            "username": url.username,
            "sslmode": "disable",
            "timeout_seconds": 15,
        },
        "secrets": {"password": url.password},
    }
    body.update(over)
    return body


def rest_body(name="API", **over):
    body = {
        "name": name,
        "kind": "rest",
        "description": "",
        "settings": {"base_url": "https://203.0.113.9/api", "auth": "bearer"},
        "secrets": {"token": "tok-123456"},
    }
    body.update(over)
    return body


def static_pg(name, **over):
    return {"name": name, **STATIC_PG, **over}


JOIN_REPORT = {
    "id": "erp-ventas",
    "spec": "specs/reports/001-erp-ventas",
    "title": "Ventas ERP",
    "direct": {
        "source": "ERP directo",
        "cache_seconds": 300,
        "tables": {
            "v": {
                "table": "erp19.ventas",
                "columns": {
                    "day": {"type": "date"},
                    "amount": {"type": "numeric"},
                    "cliente_id": {"type": "integer"},
                },
            },
            "c": {
                "table": "erp19.clientes",
                "columns": {"id": {"type": "integer"}, "zona": {"type": "text"}},
            },
        },
    },
    "joins": [{"left": "v.cliente_id", "right": "c.id", "type": "inner"}],
    "date": "v.day",
    "metrics": {"total": {"label": "Total", "format": "number", "sql": "sum(v.amount)"}},
    "dimensions": {"cliente": {"label": "Zona", "sql": "c.zona"}},
    "periods": {"default": "mtd", "allowed": ["mtd", "custom"]},
    "compare": {"default": "none", "allowed": ["none", "previous_period"]},
    "views": [
        {"type": "kpis", "metrics": ["total"]},
        {"type": "ranking", "dimension": "cliente", "metric": "total", "limit": 5},
    ],
}
QUERY = "?period=custom&from=2026-09-01&to=2026-09-30&compare=none"


@pytest.fixture(autouse=True)
def _direct_log_sync(monkeypatch):
    monkeypatch.setattr(direct, "LOG_ASYNC", False)
    direct.clear_cache()
    direct._inflight.clear()
    yield
    direct.clear_cache()


@pytest.fixture
def erp_tables():
    phys = direct.physical_schema("erp19")
    sql(f'DROP SCHEMA IF EXISTS "{phys}" CASCADE')
    sql(f'CREATE SCHEMA "{phys}"')
    sql(f'CREATE TABLE "{phys}".ventas (day date, amount numeric, cliente_id integer)')
    sql(f'CREATE TABLE "{phys}".clientes (id integer primary key, zona text)')
    sql(
        f'INSERT INTO "{phys}".ventas(day, amount, cliente_id) VALUES '
        f"('2026-09-01', 10, 1), ('2026-09-02', 20, 2), ('2026-09-03', 5, 1)"
    )
    sql(f'INSERT INTO "{phys}".clientes(id, zona) VALUES (1, \'Norte\'), (2, \'Sur\')')
    yield
    sql(f'DROP SCHEMA IF EXISTS "{phys}" CASCADE')


def write_ws(root, report_data, source_line, tables_line):
    rid, folder = report_data["id"], report_data["spec"]
    write(root, "bizview.yaml", "name: cliente\ncurrency: USD\n")
    write(
        root,
        f"{folder}/spec.md",
        f"# Ventas\n\n**Spec type**: report\n\n**Status**: Implemented\n\n"
        f"**Modo**: directo\n\n**Fuente**: {source_line}\n\n**Tablas**: {tables_line}\n\n"
        f"**Mantenido por**: proceso ERP\n\n**Volumen esperado**: 3 filas\n",
    )
    write(root, f"{folder}/plan.md", "# Plan\n")
    write(root, f"{folder}/tasks.md", "- [X] T001 hecho\n")
    write(
        root,
        f"reports/{rid}/report.yaml",
        yaml.safe_dump(report_data, sort_keys=False, allow_unicode=True),
    )


def _flag(source_id):
    return sql("SELECT direct_reports FROM data_source WHERE id = :id", id=source_id)[0][0]


def _flag_details():
    return [row[0] for row in sql("SELECT detail FROM audit_event "
                                  "WHERE kind = 'source_direct_reports_changed' ORDER BY id")]


def test_flag_only_postgresql(superuser):
    c = reauth(signed_in("root@example.com"))
    r = c.post("/api/sources", json=rest_body(name="API rest", direct_reports=True))
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_error"
    assert err["fields"] == {"direct_reports": "not_allowed"}
    assert err["message"] == "Solo las fuentes PostgreSQL admiten reportes directos"
    assert sql("SELECT count(*) FROM data_source")[0][0] == 0

    r = c.post("/api/sources", json=static_pg("ERP pg", direct_reports=True))
    assert r.status_code == 201, r.text
    pg_id = r.json()["id"]
    assert r.json()["direct_reports"] is True

    audit_rows = sql("SELECT kind, detail FROM audit_event ORDER BY id")
    kinds = [row[0] for row in audit_rows]
    assert kinds[-2:] == ["source_created", "source_direct_reports_changed"]
    assert audit_rows[-1][1] == {"source": "ERP pg", "before": False, "value": True}

    r = c.post("/api/sources", json=rest_body(name="API rest 2"))
    assert r.status_code == 201, r.text
    rest_id = r.json()["id"]
    assert r.json()["direct_reports"] is False

    r = c.patch(f"/api/sources/{rest_id}", json={"direct_reports": True})
    assert r.status_code == 422
    assert r.json()["error"]["fields"] == {"direct_reports": "not_allowed"}
    assert _flag(rest_id) is False

    items = {s["id"]: s for s in c.get("/api/sources").json()["items"]}
    assert items[pg_id]["direct_reports"] is True and items[rest_id]["direct_reports"] is False
    assert c.get(f"/api/sources/{pg_id}").json()["direct_reports"] is True


def test_step_up_required_for_flag_change(superuser):
    c = reauth(signed_in("root@example.com"))
    r = c.post("/api/sources", json=static_pg("ERP ventas"))
    assert r.status_code == 201, r.text
    source_id = r.json()["id"]

    c2 = signed_in("root@example.com")          # new session: no step-up yet
    r = c2.patch(f"/api/sources/{source_id}", json={"direct_reports": True})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "reauth_required"
    assert _flag(source_id) is False
    assert _flag_details() == []

    r = reauth(c2).patch(f"/api/sources/{source_id}", json={"direct_reports": True})
    assert r.status_code == 200
    assert r.json()["direct_reports"] is True
    assert _flag(source_id) is True


def test_audit_row_on_flag_changes(superuser):
    c = reauth(signed_in("root@example.com"))
    r = c.post("/api/sources", json=static_pg("ERP ventas"))
    assert r.status_code == 201, r.text
    source_id = r.json()["id"]

    assert c.patch(f"/api/sources/{source_id}", json={"direct_reports": True}).status_code == 200
    assert _flag_details() == [{"source": "ERP ventas", "before": False, "value": True}]

    assert c.patch(f"/api/sources/{source_id}", json={"direct_reports": True}).status_code == 200
    assert len(_flag_details()) == 1

    r = c.patch(f"/api/sources/{source_id}", json={"direct_reports": False, "name": "ERP 2"})
    assert r.status_code == 200
    details = _flag_details()
    assert len(details) == 2
    assert details[-1] == {"source": "ERP 2", "before": True, "value": False}
    assert PW not in str(details)
    assert "host" not in str(details) and "203.0.113.9" not in str(details)


def test_kind_change_reset_and_check_constraint(superuser):
    c = reauth(signed_in("root@example.com"))
    r = c.post("/api/sources", json=static_pg("ERP ventas", direct_reports=True))
    assert r.status_code == 201, r.text
    source_id = r.json()["id"]

    r = c.patch(f"/api/sources/{source_id}", json={"kind": "rest", "direct_reports": True})
    assert r.status_code == 422
    assert "kind" in r.json()["error"]["fields"]
    assert _flag(source_id) is True
    assert sql("SELECT kind FROM data_source WHERE id = :id", id=source_id)[0][0] == "postgresql"

    assert c.post("/api/sources", json=rest_body(name="REST check")).status_code == 201
    with pytest.raises(IntegrityError):
        sql("UPDATE data_source SET direct_reports = true WHERE kind = 'rest'")


def test_reserved_name_bi(superuser):
    c = reauth(signed_in("root@example.com"))
    for name in ("BI", " bi ", "Bi"):
        r = c.post("/api/sources", json=static_pg(name))
        assert r.status_code == 422
        assert r.json()["error"]["fields"] == {"name": "reserved"}
        assert "reservado" in r.json()["error"]["message"]

    r = c.post("/api/sources", json=static_pg("bi-ventas"))
    assert r.status_code == 201, r.text
    source_id = r.json()["id"]
    assert c.post("/api/sources", json=static_pg("BI ventas")).status_code == 201

    r = c.patch(f"/api/sources/{source_id}", json={"name": "bi"})
    assert r.status_code == 422
    assert r.json()["error"]["fields"] == {"name": "reserved"}


@pytest.mark.parametrize("kind", ["rest", "soap", "supabase"])
def test_validation_refuses_non_direct_kinds(tmp_path, kind):
    root = tmp_path / "ws"
    root.mkdir()
    ctx = wsv.DirectContext(
        sources={
            "demo": {"name": "Demo", "kind": kind, "enabled": True, "direct": True, "bi": False}
        },
        bi_enabled=True,
        product_tables=direct.product_tables(),
        structure=lambda s, t: {"error": "no"},
        personal_kind=lambda c: None,
        warn_rows=100000,
    )
    rep = {**JOIN_REPORT, "direct": {**JOIN_REPORT["direct"], "source": "Demo"}}
    write_ws(root, rep, "Demo", "erp19.ventas, erp19.clientes")
    result = wsv.validate(root, direct=ctx)
    direct_issues = [i for i in result.issues if i.code == "direct_not_allowed"]
    assert direct_issues
    assert "crea una integración" in direct_issues[0].fix
    assert "no admiten reportes directos" in direct_issues[0].message


def test_validation_refuses_flag_off_and_disabled(superuser, tmp_path):
    c = reauth(signed_in("root@example.com"))
    assert c.post("/api/sources", json=pg_body(name="ERP off")).status_code == 201
    dis = c.post("/api/sources", json=pg_body(name="ERP off2", direct_reports=True)).json()
    assert c.patch(f"/api/sources/{dis['id']}", json={"enabled": False}).status_code == 200

    db = get_sessionmaker()()
    try:
        ctx = direct.validation_context(db)
        for folder, name, expected in (("ws-off", "ERP off", "no permite reportes directos"),
                                       ("ws-disabled", "ERP off2", "está desactivada")):
            root = tmp_path / folder
            root.mkdir()
            rep = {**JOIN_REPORT, "direct": {**JOIN_REPORT["direct"], "source": name}}
            write_ws(root, rep, name, "erp19.ventas, erp19.clientes")
            result = wsv.validate(root, direct=ctx)
            direct_issues = [i for i in result.issues if i.code == "direct_not_allowed"]
            assert direct_issues, name
            assert "crea una integración" in direct_issues[0].fix
            assert expected in direct_issues[0].message
    finally:
        db.close()


def test_applied_report_with_flag_off_never_connects(superuser, erp_tables, tmp_path,
                                                     monkeypatch):
    root = tmp_path / "ws"
    root.mkdir()
    monkeypatch.setattr(get_settings(), "workspace_path", str(root))
    monkeypatch.setattr(report, "_epoch", lambda: 1_000_000 * 300 + 1)

    c = reauth(signed_in("root@example.com"))
    r = c.post("/api/sources", json=pg_body(direct_reports=True))
    assert r.status_code == 201, r.text
    source_id = r.json()["id"]

    write_ws(root, JOIN_REPORT, "ERP directo", "erp19.ventas, erp19.clientes")
    lock(root)
    apply(c)
    # 019 T050: viewed once, so the result is in report_cache before the flag goes off.
    first = c.get(f"/api/reports/erp-ventas/data{QUERY}")
    assert first.status_code == 200, first.text

    assert c.patch(f"/api/sources/{source_id}", json={"direct_reports": False}).status_code == 200
    direct.clear_cache()

    called = {"n": 0}

    def boom(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("must not connect")

    monkeypatch.setattr(extract, "_pg_connect", boom)

    r = c.get(f"/api/reports/erp-ventas/data{QUERY}")
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "direct_not_allowed"
    assert err["message"] == "Esta fuente no permite reportes directos"
    assert called["n"] == 0


def test_join_over_catalogue_source_direct_data(superuser, erp_tables, tmp_path, monkeypatch):
    root = tmp_path / "ws"
    root.mkdir()
    monkeypatch.setattr(get_settings(), "workspace_path", str(root))
    monkeypatch.setattr(report, "_epoch", lambda: 1_000_000 * 300 + 1)

    c = reauth(signed_in("root@example.com"))
    assert c.post("/api/sources", json=pg_body(direct_reports=True)).status_code == 201

    write_ws(root, JOIN_REPORT, "ERP directo", "erp19.ventas, erp19.clientes")
    lock(root)
    apply(c)

    r = c.get(f"/api/reports/erp-ventas/data{QUERY}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["freshness"]["mode"] == "direct"
    assert data["freshness"]["source"] == "ERP directo"
    assert data["views"][0]["items"][0]["value"] == 35.0
    ranking = [(i["key"], i["value"]) for i in data["views"][1]["items"]]
    assert ranking == [("Sur", 20.0), ("Norte", 15.0)]


def test_internet_profile_refuses_non_tls(superuser, monkeypatch):
    c = reauth(signed_in("root@example.com"))
    assert c.post("/api/sources", json=pg_body(direct_reports=True)).status_code == 201

    s = get_settings()
    monkeypatch.setattr(s, "security_profile", "internet")
    monkeypatch.setattr(s, "site_address", "bi.example.com")
    monkeypatch.setattr(s, "cookie_secure", True)
    direct.clear_cache()

    runner = DirectRunner(
        "ERP directo",
        report_id="r-tls",
        timeout_seconds=5,
        tables={"v": ("erp19", "ventas")},
    )
    with pytest.raises(direct.DirectError) as exc:
        with runner.session():
            pass
    assert exc.value.code == "error"
    assert "TLS" in exc.value.message

    result = direct.structure("ERP directo", ["erp19.ventas"])
    assert isinstance(result, dict)
    assert "TLS" in result.get("error", "")


def test_bi_describe_structure_only(superuser, erp_tables, admin):
    phys = direct.physical_schema("erp19")
    sql(f'CREATE VIEW "{phys}".v_ventas AS SELECT day, amount FROM "{phys}".ventas')
    sql(f'CREATE VIEW "{phys}".v_users AS SELECT id FROM app_user')

    c = signed_in("root@example.com")
    r = c.get("/api/sources/bi/describe")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "postgresql"
    tables = {(t["schema"], t["name"]): t for t in body["tables"]}
    assert ("erp19", "ventas") in tables
    assert [col["name"] for col in tables[("erp19", "ventas")]["columns"]] == [
        "day", "amount", "cliente_id",
    ]
    assert [col["type"] for col in tables[("erp19", "ventas")]["columns"]] == [
        "date", "numeric", "integer",
    ]
    assert tables[("erp19", "clientes")]["primary_key"] == ["id"]
    assert tables[("erp19", "v_ventas")]["kind"] == "view"
    assert ("erp19", "v_users") not in tables
    assert not any(
        f"{schema}.{name}".lower() in direct.product_tables()
        for schema, name in tables
    )
    assert not any(
        schema.startswith(("app_test_", "pg_")) or schema == "information_schema"
        for schema, _ in tables
    )
    assert "Norte" not in r.text
    rows = sql("SELECT detail FROM audit_event WHERE kind = 'source_described' ORDER BY id")
    assert rows[-1][0] == {"source": "bi", "key_id": None}
    assert make_url(get_settings().database_url_bi).password not in r.text

    a = signed_in("admin@example.com")
    assert a.get("/api/sources/bi/describe").status_code == 403


def test_bi_describe_disabled(superuser, monkeypatch):
    monkeypatch.setattr(get_settings(), "direct_reports_bi", False)
    c = signed_in("root@example.com")
    before = sql("SELECT count(*) FROM audit_event WHERE kind = 'source_described'")[0][0]
    r = c.get("/api/sources/bi/describe")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "direct_not_allowed"
    after = sql("SELECT count(*) FROM audit_event WHERE kind = 'source_described'")[0][0]
    assert after == before


def test_catalogue_describe_route_still_resolves_names(superuser):
    c = signed_in("root@example.com")
    r = c.get("/api/sources/no-existe/describe")
    assert r.status_code == 404
