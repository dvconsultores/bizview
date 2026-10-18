"""Direct-source report tests: schema oneOf, product deny-list, spec lines, live structure,
personal columns, and the CLI --describe/--live wiring."""
import copy
import json
from pathlib import Path

import pytest
import yaml

from bizview_cli.__main__ import main
from bizview_cli.describe import structure_from
from bizview_cli.validate import DIRECT_TYPE_COMPAT, DirectContext, validate
from tests.conftest import write

LIVE = {
    "public.bi_ventas": {
        "columns": {"fecha": "date", "cliente_id": "integer", "monto": "numeric"},
        "product_dependency": False,
    },
    "public.bi_clientes": {
        "columns": {"id": "integer", "nombre": "character varying", "email": "text"},
        "product_dependency": False,
    },
}


def fake_structure(live=None, error=None, calls=None):
    live = LIVE if live is None else live

    def structure(source, tables):
        if calls is not None:
            calls.append((source, list(tables)))
        if error:
            return {"tables": {}, "error": error}
        return {"tables": {t: live[t] for t in tables if t in live}, "error": None}

    return structure


def direct_spec(root: Path, *, drop=(), extra: str = "") -> None:
    lines = [
        "# Ventas directo",
        "",
        "**Spec type**: report",
        "",
        "**Status**: Approved",
        "",
        "**Modo**: directo",
        "",
        "**Fuente**: bi",
        "",
        "**Tablas**: public.bi_ventas, public.bi_clientes",
        "",
        "**Mantenido por**: proceso nocturno del ERP",
        "",
        "**Volumen esperado**: 200 mil filas, +5 mil por mes",
    ]
    dropped = tuple(drop)
    lines = [line for line in lines if not line.startswith(dropped)]
    spec = "\n".join(lines) + (f"\n{extra}\n" if extra else "")
    write(root, "specs/reports/001-ventas-directo/spec.md", spec)
    write(root, "specs/reports/001-ventas-directo/plan.md", "# Plan\n")
    write(root, "specs/reports/001-ventas-directo/tasks.md", "- [X] T001 hecho\n")


def edit(root: Path, fn) -> dict:
    path = root / "reports/ventas-directo/report.yaml"
    data = yaml.safe_load(path.read_text("utf-8"))
    fn(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return data


def drop_artifact(root: Path, *keys) -> dict:
    def remove(data):
        for key in keys:
            data.pop(key, None)
    return edit(root, remove)


@pytest.fixture
def dws(tmp_path):
    root = tmp_path / "direct-ws"
    write(root, "bizview.yaml", "name: demo\n")
    direct_spec(root)
    write(root, "reports/ventas-directo/report.yaml", """
        id: ventas-directo
        spec: specs/reports/001-ventas-directo
        title: Ventas directo
        direct:
          source: bi
          tables:
            v:
              table: public.bi_ventas
              columns:
                fecha: {type: date}
                cliente_id: {type: integer}
                monto: {type: numeric}
            c:
              table: public.bi_clientes
              columns:
                id: {type: integer}
                nombre: {type: text}
                email: {type: text}
        joins: [{left: v.cliente_id, right: c.id}]
        date: v.fecha
        metrics:
          ventas: {label: Ventas, sql: "sum(v.monto)", format: currency}
        dimensions:
          cliente: {label: Cliente, sql: c.nombre}
        views:
          - {type: kpis, metrics: [ventas]}
          - {type: ranking, dimension: cliente, metric: ventas}
        filters: [cliente]
    """)
    return root


def codes(result):
    return {i.code for i in result.issues}


def issues(result, code, **kw):
    out = [i for i in result.issues if i.code == code]
    for key, value in kw.items():
        out = [i for i in out if getattr(i, key, None) == value]
    return out


def test_valid_direct_workspace(dws):
    result = validate(dws)
    assert result.ok
    assert result.issues == []
    assert result.lock["entries"]["reports/ventas-directo"]["artifacts"]
    result = validate(dws, direct=DirectContext(bi_enabled=True, structure=fake_structure(),
                                                personal_kind=lambda c: None))
    assert result.ok
    assert result.issues == []


def test_oneof_direct_and_uses(dws):
    original = edit(dws, lambda data: None)["direct"]
    drop_artifact(dws, "direct")
    result = validate(dws)
    err = [i for i in result.issues if i.code == "schema_error" and i.path == ""]
    assert len(err) == 1
    assert "oneOf" in err[0].expected
    assert err[0].fix == "añade una de: direct, uses"

    edit(dws, lambda data: data.update({"direct": original,
                                        "uses": {"x": "ventas.sale_lines"}}))
    result = validate(dws)
    err = [i for i in result.issues if i.code == "schema_error" and i.path == ""]
    assert len(err) == 1
    assert err[0].fix == "usa solo una de: direct, uses"


def test_schema_branch_errors(dws):
    def set_direct_table(table, col_type="text", **extra):
        def update(data):
            data["direct"] = {"source": "bi",
                              "tables": {"v": {"table": table,
                                                "columns": {"fecha": {"type": col_type}}}},
                              **extra}
        edit(dws, update)

    set_direct_table("Public.Ventas")
    result = validate(dws)
    err = issues(result, "schema_error", path="/direct/tables/v/table")
    assert err and "public.bi_ventas" in err[0].fix
    assert err[0].expected == {"type": "string",
                                "pattern": r"^[a-z_][a-z0-9_]{0,62}\.[a-z_][a-z0-9_]{0,62}$"}

    set_direct_table("public.bi_ventas", "varchar")
    result = validate(dws)
    err = issues(result, "schema_error", path="/direct/tables/v/columns/fecha/type")
    assert err and err[0].fix.startswith("usa uno de:")

    set_direct_table("public.bi_ventas", "date", cache_seconds=30)
    result = validate(dws)
    err = issues(result, "schema_error", path="/direct/cache_seconds")
    assert err and err[0].fix == "el valor mínimo es 60"

    set_direct_table("public.bi_ventas", "date", max_rows=6000)
    result = validate(dws)
    err = issues(result, "schema_error", path="/direct/max_rows")
    assert err and err[0].fix == "el valor máximo es 5000"

    set_direct_table("public.bi_ventas", "date", schema="public")
    result = validate(dws)
    err = issues(result, "schema_error", path="/direct")
    assert err and err[0].fix.startswith("quita `schema`")

    tables = {f"t{i}": {"table": "public.t", "columns": {"a": {"type": "text"}}}
              for i in range(9)}
    edit(dws, lambda data: data.update({"direct": {"source": "bi", "tables": tables}}))
    result = validate(dws)
    assert [i for i in result.issues if i.code == "schema_error"]
    assert [i for i in result.issues if i.code == "schema_error"
            and i.path == "/direct/tables"]


@pytest.mark.parametrize("table", [
    "pg_catalog.pg_class",
    "information_schema.columns",
    "pg_toast.pg_toast_1",
    "app_test_abc.bi_ventas",
    "preview_x1.bi_ventas",
    "public.alembic_version",
])
def test_offline_deny_table(dws, table):
    edit(dws, lambda data: data["direct"]["tables"].update(
        {"v": {"table": table, "columns": {"a": {"type": "text"}}}}))

    result = validate(dws)
    issue = issues(result, "direct_product_table")[0]
    assert issue.message == "Tabla del producto: no se puede leer en un reporte directo"
    assert issue.path == "/direct/tables/v/table"

    calls = []
    ctx = DirectContext(bi_enabled=True, structure=fake_structure(calls=calls))
    validate(dws, direct=ctx)
    assert calls == [("bi", ["public.bi_clientes"])]


def test_catalogue_table_allowed_offline(dws):
    edit(dws, lambda data: data["direct"]["tables"].update(
        {"v": {"table": "ds_ventas.sale_lines", "columns": {"a": {"type": "text"}}}}))
    result = validate(dws)
    assert not issues(result, "direct_product_table")


@pytest.mark.parametrize("drop", ["**Modo**", "**Fuente**", "**Tablas**", "**Mantenido por**",
                                  "**Volumen esperado**"])
def test_missing_direct_spec_line(dws, drop):
    direct_spec(dws, drop=(drop,))
    result = validate(dws)
    found = issues(result, "direct_spec_line")
    assert len(found) == 1
    assert found[0].file == "specs/reports/001-ventas-directo/spec.md"


def test_direct_spec_english(dws):
    extra_lines = [
        "**Mode**: direct",
        "**Source**: bi",
        "**Tables**: public.bi_ventas",
        "**Maintained by**: ETL",
        "**Expected volume**: 1000 filas",
    ]
    direct_spec(dws, drop=("**Modo**", "**Fuente**", "**Tablas**", "**Mantenido por**",
                           "**Volumen esperado**"), extra="\n".join(extra_lines))
    assert not issues(validate(dws), "direct_spec_line")


def test_direct_spec_dataset_mode(dws):
    direct_spec(dws, drop=("**Modo**",), extra="**Modo**: dataset")
    found = issues(validate(dws), "direct_spec_line")
    assert len(found) == 1


def test_direct_mode_mismatch(ws):
    spec = ws / "specs/reports/001-resumen/spec.md"
    spec.write_text(spec.read_text("utf-8") + "\n**Modo**: directo\n", encoding="utf-8")
    result = validate(ws)
    assert issues(result, "direct_mode_mismatch")


@pytest.mark.parametrize("source,sources,bi,code,text", [
    ("erp", {}, True, "unknown_source", "no existe"),
    ("erp", {"erp": {"name": "ERP", "kind": "rest", "enabled": True, "direct": False}},
     True, "direct_not_allowed", "tipo rest"),
    ("erp", {"erp": {"name": "ERP", "kind": "postgresql", "enabled": False, "direct": True}},
     True, "direct_not_allowed", "desactivada"),
    ("erp", {"erp": {"name": "ERP", "kind": "postgresql", "enabled": True, "direct": False}},
     True, "direct_not_allowed", "no permite"),
    ("bi", {}, False, "direct_not_allowed", "BI"),
])
def test_direct_source_refusals(dws, source, sources, bi, code, text):
    edit(dws, lambda data: data["direct"].update({"source": source,
                                                  "tables": {"v": {"table": "public.bi_ventas",
                                                                   "columns": {
                                                                       "a": {"type": "text"}}}}}))
    calls = []
    result = validate(dws, direct=DirectContext(sources=sources, bi_enabled=bi,
                                                 structure=fake_structure(calls=calls)))
    refused = issues(result, "unknown_source") + issues(result, "direct_not_allowed")
    assert len(refused) == 1
    issue = issues(result, code)[0]
    assert issue.path == "/direct/source"
    assert text in issue.message
    assert issue.fix == ("activa «Permitir reportes directos» en la fuente o crea "
                         "una integración (integrations/<id>)")
    assert calls == []


def test_product_tables_bi(dws):
    ctx = DirectContext(bi_enabled=True, product_tables=frozenset({"public.bi_clientes"}),
                        structure=fake_structure())
    result = validate(dws, direct=ctx)
    issue = issues(result, "direct_product_table", path="/direct/tables/c/table")
    assert issue and not issues(result, "direct_product_table", path="/direct/tables/v/table")


def test_product_tables_catalogue(dws):
    edit(dws, lambda data: data["direct"].update({"source": "erp"}))
    sources = {"erp": {"name": "ERP", "kind": "postgresql", "enabled": True, "direct": True,
                       "bi": True}}
    ctx = DirectContext(sources=sources, product_tables=frozenset({"public.bi_clientes"}),
                        structure=fake_structure())
    result = validate(dws, direct=ctx)
    assert issues(result, "direct_product_table")
    sources["erp"].pop("bi")
    result = validate(dws, direct=ctx)
    assert not issues(result, "direct_product_table")


def test_no_context_no_source_issues(dws):
    edit(dws, lambda data: data["direct"].update({"source": "erp"}))
    result = validate(dws)
    assert not issues(result, "unknown_source")
    assert not issues(result, "direct_not_allowed")
    assert not issues(result, "direct_structure_unchecked")


def test_structure_missing_table(dws):
    live = {k: v for k, v in LIVE.items() if k != "public.bi_clientes"}
    result = validate(dws, direct=DirectContext(bi_enabled=True,
                                                 structure=fake_structure(live)))
    assert issues(result, "direct_table_missing", path="/direct/tables/c/table")


def test_structure_missing_column(dws):
    live = json.loads(json.dumps(LIVE))
    live["public.bi_clientes"]["columns"].pop("email")
    result = validate(dws, direct=DirectContext(bi_enabled=True,
                                                 structure=fake_structure(live)))
    assert issues(result, "direct_column_missing", path="/direct/tables/c/columns/email")


@pytest.mark.parametrize("contract,live_type",
                         [(t, live) for t, lives in DIRECT_TYPE_COMPAT.items() for live in lives])
def test_structure_compatibility_ok(dws, contract, live_type):
    live = json.loads(json.dumps(LIVE))
    live["public.bi_ventas"]["columns"]["monto"] = live_type
    edit(dws, lambda data: data["direct"]["tables"]["v"]["columns"]["monto"]
         .update({"type": contract}))
    result = validate(dws, direct=DirectContext(bi_enabled=True,
                                                 structure=fake_structure(live)))
    assert not issues(result, "direct_column_type")


@pytest.mark.parametrize("contract,live_type", [
    ("integer", "bigint"),
    ("text", "integer"),
    ("date", "timestamp with time zone"),
    ("timestamptz", "date"),
    ("boolean", "text"),
])
def test_structure_incompatible_type(dws, contract, live_type):
    live = json.loads(json.dumps(LIVE))
    live["public.bi_ventas"]["columns"]["monto"] = live_type
    edit(dws, lambda data: data["direct"]["tables"]["v"]["columns"]["monto"]
         .update({"type": contract}))
    result = validate(dws, direct=DirectContext(bi_enabled=True,
                                                 structure=fake_structure(live)))
    issue = issues(result, "direct_column_type")[0]
    assert issue.path == "/direct/tables/v/columns/monto"
    assert issue.expected == {"type": contract, "compatible": list(DIRECT_TYPE_COMPAT[contract])}
    assert live_type in issue.message


def test_structure_date_column(dws):
    live = json.loads(json.dumps(LIVE))
    live["public.bi_ventas"]["columns"]["fecha"] = "timestamp with time zone"
    result = validate(dws, direct=DirectContext(bi_enabled=True,
                                                 structure=fake_structure(live)))
    assert issues(result, "direct_column_type", path="/direct/tables/v/columns/fecha")


def test_structure_date_contract(dws):
    edit(dws, lambda data: data["direct"]["tables"]["v"]["columns"]["fecha"]
         .update({"type": "text"}))
    result = validate(dws, direct=DirectContext(bi_enabled=True,
                                                 structure=fake_structure(LIVE)))
    assert issues(result, "invalid_reference", path="/date")


def test_product_dependency_live(dws):
    live = json.loads(json.dumps(LIVE))
    live["public.bi_ventas"]["product_dependency"] = True
    result = validate(dws, direct=DirectContext(bi_enabled=True,
                                                 structure=fake_structure(live)))
    assert issues(result, "direct_product_table", path="/direct/tables/v/table")


@pytest.mark.parametrize("bad", ["timeout", "raise", "none"])
def test_structure_error_is_warning(dws, bad):
    calls = []

    def broken(source, tables):
        calls.append((source, list(tables)))
        if bad == "raise":
            raise RuntimeError("boom")
        if bad == "none":
            return None
        return {"tables": {}, "error": "timeout"}

    result = validate(dws, direct=DirectContext(bi_enabled=True, structure=broken))
    assert result.ok
    found = issues(result, "direct_structure_unchecked")
    assert len(found) == 1
    assert found[0].level == "warning"
    assert calls == [("bi", ["public.bi_ventas", "public.bi_clientes"])]


def test_structure_single_call(dws):
    calls = []
    validate(dws, direct=DirectContext(bi_enabled=True, structure=fake_structure(calls=calls)))
    assert calls == [("bi", ["public.bi_ventas", "public.bi_clientes"])]


def test_personal_column(dws):
    edit(dws, lambda data: data.update({
        "dimensions": {"cliente": {"label": "Cliente", "sql": "c.nombre"},
                       "contacto": {"label": "Contacto", "sql": "c.email"}},
        "filters": ["cliente", "contacto"],
    }))
    ctx = DirectContext(bi_enabled=True, structure=fake_structure(),
                        personal_kind=lambda c: "email" if c == "email" else None)
    result = validate(dws, direct=ctx)
    assert issues(result, "direct_personal_column", path="/dimensions/contacto/sql")
    direct_spec(dws, extra="**Datos personales**: c.email")
    result = validate(dws, direct=ctx)
    assert not issues(result, "direct_personal_column")
    offline = DirectContext(bi_enabled=True, structure=fake_structure())
    result = validate(dws, direct=offline)
    assert not issues(result, "direct_personal_column")


def test_cli_offline_summary(dws, capsys):
    assert main(["validate", str(dws), "--write-lock"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("✓ 0 integraciones y 1 reportes válidos (1 directos; estructura en "
                          "vivo no comprobada: usa --describe NOMBRE=ARCHIVO o --live)")


def test_cli_dataset_summary_unchanged(ws, capsys):
    assert main(["validate", str(ws), "--write-lock"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("✓ 1 integraciones y 1 reportes válidos")


def _describe_payload(columns):
    return {
        "kind": "postgresql",
        "truncated": False,
        "tables": [
            {"schema": "public", "name": "bi_ventas", "kind": "table", "estimated_rows": 10,
             "primary_key": [], "columns": columns["bi_ventas"]},
            {"schema": "public", "name": "bi_clientes", "kind": "table", "estimated_rows": 10,
             "primary_key": [], "columns": columns["bi_clientes"]},
        ],
    }


def _columns():
    return {"bi_ventas": [{"name": "fecha", "type": "date", "nullable": False},
                          {"name": "cliente_id", "type": "integer", "nullable": False},
                          {"name": "monto", "type": "numeric", "nullable": False}],
            "bi_clientes": [{"name": "id", "type": "integer", "nullable": False},
                            {"name": "nombre", "type": "character varying", "nullable": False},
                            {"name": "email", "type": "text", "nullable": False}]}


def test_cli_describe_json_yaml(dws, tmp_path, capsys):
    payload = _describe_payload(_columns())
    file_json = tmp_path / "bi.json"
    file_json.write_text(json.dumps(payload), encoding="utf-8")
    assert main(["validate", str(dws), "--describe", f"bi={file_json}", "--write-lock"]) == 0
    out = capsys.readouterr().out
    assert "estructura en vivo comprobada)" in out
    file_yaml = tmp_path / "bi.yaml"
    file_yaml.write_text(yaml.safe_dump(payload), encoding="utf-8")
    assert main(["validate", str(dws), "--describe", f"bi={file_yaml}", "--write-lock"]) == 0
    assert "estructura en vivo comprobada)" in capsys.readouterr().out


def test_cli_describe_missing_column(dws, tmp_path, capsys):
    cols = _columns()
    cols["bi_clientes"] = cols["bi_clientes"][:2]
    payload = _describe_payload(cols)
    file_json = tmp_path / "bi.json"
    file_json.write_text(json.dumps(payload), encoding="utf-8")
    assert main(["validate", str(dws), "--describe", f"bi={file_json}"]) == 1
    assert "direct_column_missing" in capsys.readouterr().err


def test_cli_describe_usage_errors(dws, capsys):
    assert main(["validate", str(dws), "--describe", "bi"]) == 2
    capsys.readouterr()
    assert main(["validate", str(dws), "--describe", "bi=/no/existe.yaml"]) == 2
    assert "No se pudo leer /no/existe.yaml" in capsys.readouterr().err


def test_cli_live(dws, monkeypatch, capsys):
    from bizview_cli import describe
    monkeypatch.setenv("BIZVIEW_URL", "https://bi.test")
    monkeypatch.setenv("BIZVIEW_TOKEN", "tok")
    payload = _describe_payload(_columns())
    request = {"url": None}

    def fake_get(url, **kwargs):
        request["url"] = url
        return type("Resp", (), {"status_code": 200,
                                  "json": lambda self: payload})()
    monkeypatch.setattr(describe.httpx, "get", fake_get)
    assert main(["validate", str(dws), "--live", "--write-lock"]) == 0
    assert request["url"].endswith("/api/sources/bi/describe")
    assert "estructura en vivo comprobada)" in capsys.readouterr().out


def test_cli_live_401_warning(dws, monkeypatch, capsys):
    from bizview_cli import describe
    monkeypatch.setenv("BIZVIEW_URL", "https://bi.test")
    monkeypatch.setenv("BIZVIEW_TOKEN", "tok")

    def fake_get(url, **kwargs):
        return type("Resp", (), {"status_code": 401,
                                  "json": lambda self: {"error": {"message": "bad"}}})()
    monkeypatch.setattr(describe.httpx, "get", fake_get)
    assert main(["validate", str(dws), "--live", "--write-lock"]) == 0
    captured = capsys.readouterr()
    assert "direct_structure_unchecked" in captured.err
    assert "Token rechazado" in captured.err
    assert "comprobada en parte" in captured.out


def test_cli_describe_wrong_source_is_warning(dws, tmp_path, capsys):
    payload = _describe_payload(_columns())
    file_json = tmp_path / "erp.json"
    file_json.write_text(json.dumps(payload), encoding="utf-8")
    assert main(["validate", str(dws), "--describe", f"erp={file_json}", "--write-lock"]) == 0
    assert "sin descripción de la fuente" in capsys.readouterr().err


def test_structure_from():
    payload = {"kind": "rest", "tables": []}
    assert structure_from(payload, ["public.t"])["error"]
    truncated = {"kind": "postgresql", "truncated": True, "tables": []}
    assert "truncada" in structure_from(truncated, ["public.t"])["error"]
    cols = [{"name": "EMAIL", "type": "Text"}]
    payload = {"kind": "postgresql", "truncated": False,
               "tables": [{"schema": "PUBLIC", "name": "T", "columns": cols}]}
    result = structure_from(payload, ["public.t"])
    assert result == {"tables": {"public.t": {"columns": {"email": "text"},
                                               "product_dependency": False}},
                      "error": None}


def _big_live(reltuples, date_index_columns=None, date_indexed=None):
    live = copy.deepcopy(LIVE)
    info = live["public.bi_ventas"]
    info["reltuples"] = reltuples
    if date_index_columns is not None:
        info["date_index_columns"] = date_index_columns
        info["date_indexed"] = bool(date_index_columns)
    elif date_indexed is not None:
        info["date_indexed"] = date_indexed
    return live


def test_direct_big_table_refused(dws):
    ctx = DirectContext(bi_enabled=True, structure=fake_structure(live=_big_live(10)),
                        warn_rows=5)
    result = validate(dws, direct=ctx)
    assert not result.ok
    big = issues(result, "direct_big_table")
    assert len(big) == 1
    iss = big[0]
    assert "indexa fecha" in iss.message
    assert iss.path == "/direct/tables/v/table"
    assert iss.expected == {"rows": 10, "max_rows": 5, "index": "fecha"}


def test_direct_big_table_indexed_ok(dws):
    ctx = DirectContext(bi_enabled=True,
                        structure=fake_structure(live=_big_live(10, ["fecha"])),
                        warn_rows=5)
    assert validate(dws, direct=ctx).ok


def test_direct_big_table_date_indexed_bool_ok(dws):
    ctx = DirectContext(bi_enabled=True,
                        structure=fake_structure(live=_big_live(10, date_indexed=True)),
                        warn_rows=5)
    assert validate(dws, direct=ctx).ok


def test_direct_big_table_check_disabled(dws):
    ctx = DirectContext(bi_enabled=True, structure=fake_structure(live=_big_live(10)),
                        warn_rows=None)
    assert validate(dws, direct=ctx).ok


def test_direct_big_table_only_date_alias_checked(dws):
    live = _big_live(4)
    live["public.bi_clientes"]["reltuples"] = 10
    ctx = DirectContext(bi_enabled=True, structure=fake_structure(live=live), warn_rows=5)
    assert validate(dws, direct=ctx).ok


def test_direct_big_table_under_threshold_ok(dws):
    ctx = DirectContext(bi_enabled=True, structure=fake_structure(live=_big_live(4)),
                        warn_rows=5)
    assert validate(dws, direct=ctx).ok
