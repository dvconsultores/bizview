"""Feature 011: spec archive."""
import hashlib
import types

from bizview_cli import validate as wsv

from app.db import get_sessionmaker
from app.workspace import service
from tests.conftest import client, reauth, signed_in, sql
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import apply, lock
from tests.test_vibe_reporting import workspace as workspace  # fixture
from tests.workspace_fixture import write


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_apply_stores_documents_matching_lock(workspace, superuser):
    write(workspace, "specs/reports/001-ventas/notes.md", "# Notas\n")
    lock(workspace)
    c = signed_in("root@example.com")
    apply(c)
    row = sql("SELECT lock, specs FROM workspace_version WHERE state = 'active'")[0]
    lock_json, specs = row[0], row[1]
    for key, entry in lock_json["entries"].items():
        documents = specs[key]["documents"]
        assert set(documents) == set(wsv.SPEC_FILES)
        for name in wsv.SPEC_FILES:
            assert _text_hash(documents[name]) == entry["spec"]["sha256"][name]
    assert "notes.md" not in specs["reports/ventas"]["documents"]


def test_workspace_lists_specs_without_documents(workspace, superuser):
    lock(workspace)
    c = signed_in("root@example.com")
    apply(c)
    r = c.get("/api/workspace")
    assert r.status_code == 200
    specs = {item["key"]: item for item in r.json()["active"]["specs"]}
    assert set(specs) == {"integrations/ventas-prueba", "reports/ventas",
                          "reports/ventas-layout"}
    assert specs["integrations/ventas-prueba"]["kind"] == "integration"
    assert specs["reports/ventas"]["kind"] == "report"
    assert specs["integrations/ventas-prueba"]["title"] == "001-ventas-prueba"
    assert specs["reports/ventas"]["title"] == "001-ventas"
    assert specs["integrations/ventas-prueba"]["status"] == "Implemented"
    assert specs["reports/ventas"]["status"] == "Implemented"
    for item in specs.values():
        assert "documents" not in item
    assert "documents" not in r.text


def test_get_spec_returns_applied_text(workspace, superuser):
    lock(workspace)
    c = signed_in("root@example.com")
    apply(c)
    first = c.get("/api/workspace/specs", params={"key": "reports/ventas"}).json()
    assert "**Spec type**: report" in first["documents"]["spec.md"]
    write(workspace, "specs/reports/001-ventas/spec.md", "# Otro\n")
    r = c.get("/api/workspace/specs", params={"key": "reports/ventas"})
    assert r.status_code == 200
    assert r.json() == first


def test_get_spec_unknown_key_and_access(workspace, superuser, admin):
    lock(workspace)
    c = signed_in("root@example.com")
    apply(c)
    r = c.get("/api/workspace/specs", params={"key": "reports/nope"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
    r = signed_in("admin@example.com").get("/api/workspace/specs",
                                           params={"key": "reports/ventas"})
    assert r.status_code == 403
    r = c.get("/api/workspace/specs")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_version_without_documents(workspace, superuser):
    lock(workspace)
    c = signed_in("root@example.com")
    apply(c)
    sql("UPDATE workspace_version SET specs = specs #- '{reports/ventas,documents}'")
    r = c.get("/api/workspace/specs", params={"key": "reports/ventas"})
    assert r.status_code == 200
    body = r.json()
    assert body["documents"] is None
    assert body["title"] == "001-ventas"
    assert body["status"] == "Implemented"
    assert body["sha256"]


def test_rollback_serves_previous_texts(workspace, superuser):
    lock(workspace)
    c = signed_in("root@example.com")
    apply(c)
    first_spec = c.get("/api/workspace/specs", params={"key": "reports/ventas"}).json()
    with open(workspace / "specs/reports/001-ventas/spec.md", "a", encoding="utf-8") as f:
        f.write("\nSegunda versión.\n")
    lock(workspace)
    apply(c)
    r = c.get("/api/workspace/specs", params={"key": "reports/ventas"})
    assert r.status_code == 200
    assert "Segunda versión." in r.json()["documents"]["spec.md"]
    r = reauth(c).post("/api/workspace/rollback")
    assert r.status_code == 200
    r = c.get("/api/workspace/specs", params={"key": "reports/ventas"})
    assert r.status_code == 200
    assert "Segunda versión." not in r.json()["documents"]["spec.md"]
    assert r.json() == first_spec


def _errors(r):
    body = r.json()["error"]
    return body.get("errors") or body.get("extra", {}).get("errors", [])


def test_non_utf8_spec_refused(workspace, superuser):
    lock(workspace)
    plan = workspace / "specs/reports/001-ventas/plan.md"
    plan.write_bytes(b"# Plan\n\xff\xfe\n")
    c = signed_in("root@example.com")
    r = reauth(c).post("/api/workspace/apply")
    assert r.status_code == 409
    errs = _errors(r)
    assert any(e["code"] == "spec_incomplete" and e["entry"] == "reports/ventas"
               and "UTF-8" in e["message"] for e in errs)
    assert sql("SELECT count(*) FROM workspace_version")[0][0] == 0


def test_symlinked_spec_refused(workspace, superuser):
    lock(workspace)
    plan = workspace / "specs/reports/001-ventas/plan.md"
    plan.unlink()
    outside = workspace.parent / "secreto.txt"
    outside.write_text("# Plan\n", encoding="utf-8")
    plan.symlink_to(outside)
    c = signed_in("root@example.com")
    r = reauth(c).post("/api/workspace/apply")
    assert r.status_code == 409
    errs = _errors(r)
    assert any(e["code"] == "spec_incomplete" and e["entry"] == "reports/ventas"
               and "enlace" in e["message"] for e in errs)
    assert sql("SELECT count(*) FROM workspace_version")[0][0] == 0


def test_dotdot_spec_path_refused(workspace, superuser):
    lock(workspace)
    report = workspace / "reports/ventas/report.yaml"
    report.write_text(report.read_text().replace(
        "spec: specs/reports/001-ventas", "spec: specs/reports/../reports/001-ventas"))
    c = signed_in("root@example.com")
    r = reauth(c).post("/api/workspace/apply")
    assert r.status_code == 409
    errs = _errors(r)
    assert any(e["code"] == "missing_spec" and e["entry"] == "reports/ventas" for e in errs)


def test_get_spec_anonymous_401(workspace, superuser):
    lock(workspace)
    c = signed_in("root@example.com")
    assert reauth(c).post("/api/workspace/apply").status_code == 200
    assert client().get("/api/workspace/specs",
                        params={"key": "reports/ventas"}).status_code == 401


def test_documents_byte_exact_with_bom_crlf_non_ascii(workspace, superuser):
    plan = workspace / "specs/reports/001-ventas/plan.md"
    raw = "\ufeff# Plan con ñ, acción y €\r\nLínea 2\r\n".encode()
    plan.write_bytes(raw)
    lock(workspace)
    c = signed_in("root@example.com")
    assert reauth(c).post("/api/workspace/apply").status_code == 200
    r = c.get("/api/workspace/specs", params={"key": "reports/ventas"})
    assert r.status_code == 200
    assert r.json()["documents"]["plan.md"].encode("utf-8") == raw
    row = sql("SELECT specs, lock FROM workspace_version WHERE state = 'active'")[0]
    assert row[0]["reports/ventas"]["documents"]["plan.md"].encode("utf-8") == raw
    lock_sha = row[1]["entries"]["reports/ventas"]["spec"]["sha256"]["plan.md"]
    assert hashlib.sha256(raw).hexdigest() == lock_sha


def test_latin1_query_refused(workspace, superuser):
    lock(workspace)
    query = workspace / "integrations/ventas-prueba/queries/products.sql"
    query.write_bytes(b"-- caf\xe9\n" + query.read_bytes())
    c = signed_in("root@example.com")
    r = reauth(c).post("/api/workspace/validate")
    assert r.status_code == 200
    body = r.json()
    assert not body["ok"]
    assert any(e["code"] == "schema_error" and e["entry"] == "integrations/ventas-prueba"
               and "UTF-8" in e["message"] for e in body["errors"])
    r = reauth(c).post("/api/workspace/apply")
    assert r.status_code == 409
    assert sql("SELECT count(*) FROM workspace_version")[0][0] == 0


def test_nul_query_refused(workspace, superuser):
    lock(workspace)
    query = workspace / "integrations/ventas-prueba/queries/products.sql"
    query.write_bytes(b"\x00\n" + query.read_bytes())
    c = signed_in("root@example.com")
    r = reauth(c).post("/api/workspace/validate")
    assert r.status_code == 200
    body = r.json()
    assert not body["ok"]
    assert any(e["code"] == "schema_error" and e["entry"] == "integrations/ventas-prueba"
               and "nulos" in e["message"] for e in body["errors"])
    r = reauth(c).post("/api/workspace/apply")
    assert r.status_code == 409
    assert sql("SELECT count(*) FROM workspace_version")[0][0] == 0


def test_yaml_nul_escape_refused(workspace, superuser):
    lock(workspace)
    report = workspace / "reports/ventas/report.yaml"
    original = report.read_text(encoding="utf-8")
    replaced = original.replace("title: Ventas", 'title: "Ven\\0tas"')
    assert replaced != original
    report.write_text(replaced, encoding="utf-8")
    c = signed_in("root@example.com")
    r = reauth(c).post("/api/workspace/apply")
    assert r.status_code == 409
    errs = _errors(r)
    assert any(e["code"] == "schema_error" and e["entry"] == "reports/ventas"
               and "nulos" in e["message"] for e in errs)
    assert sql("SELECT count(*) FROM workspace_version")[0][0] == 0


def test_workspace_report_details_dataset(workspace, superuser):
    lock(workspace)
    c = signed_in("root@example.com")
    apply(c)
    r = c.get("/api/workspace")
    assert r.status_code == 200
    details = r.json()["report_details"]
    assert details == [{
        "id": "ventas",
        "mode": "dataset",
        "source": "Origen prueba",
        "tables": ["ventas-prueba.sale_lines", "ventas-prueba.products"],
        "status": None,
        "last_read_at": None,
    }, {
        "id": "ventas-layout",
        "mode": "dataset",
        "source": "Origen prueba",
        "tables": ["ventas-prueba.sale_lines", "ventas-prueba.products"],
        "status": None,
        "last_read_at": None,
    }]


def test_workspace_report_details_empty(superuser):
    c = signed_in("root@example.com")
    r = c.get("/api/workspace")
    assert r.status_code == 200
    assert r.json()["report_details"] == []


def _log(report_id: str, outcome: str, minutes_ago: int) -> None:
    sql("INSERT INTO direct_read_log (report_id, source, duration_ms, outcome, occurred_at) "
        "VALUES (:r, 'bi', 1, :o, now() - make_interval(mins => :m))",
        r=report_id, o=outcome, m=minutes_ago)


def test_report_details_direct_status():
    sql("DELETE FROM direct_read_log WHERE report_id LIKE 'rd-%'")
    try:
        direct_def = {
            "title": "x",
            "direct": {
                "source": "bi",
                "tables": {
                    "s": {"table": "public.bi_ventas", "columns": {}},
                    "c": {"table": "public.bi_clientes", "columns": {}},
                },
            },
        }
        version = types.SimpleNamespace(artifacts={
            "integrations": {},
            "reports": {
                "rd-ok": {"definition": direct_def, "files": {}},
                "rd-broken": {"definition": direct_def, "files": {}},
                "rd-failing": {"definition": direct_def, "files": {}},
                "rd-new": {"definition": direct_def, "files": {}},
            },
        })
        _log("rd-ok", "timeout", 10)
        _log("rd-ok", "ok", 1)
        _log("rd-broken", "ok", 10)
        _log("rd-broken", "structure_changed", 1)
        _log("rd-failing", "unreachable", 1)

        session = get_sessionmaker()()
        try:
            details = service.report_details(session, version)
        finally:
            session.close()

        assert [d["id"] for d in details] == ["rd-broken", "rd-failing", "rd-new", "rd-ok"]
        statuses = {d["id"]: d["status"] for d in details}
        assert statuses == {"rd-ok": "ok", "rd-broken": "broken", "rd-failing": "failing",
                            "rd-new": None}
        for d in details:
            assert d["mode"] == "direct"
            assert d["source"] == "bi"
            assert d["tables"] == ["public.bi_ventas", "public.bi_clientes"]
        assert {d["id"]: d["last_read_at"] is not None for d in details} == {
            "rd-ok": True, "rd-broken": True, "rd-failing": True, "rd-new": False}
    finally:
        sql("DELETE FROM direct_read_log WHERE report_id LIKE 'rd-%'")
