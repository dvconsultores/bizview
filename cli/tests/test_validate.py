"""Validator: spec discipline, schemas, SQL safety, references, lock (feature 005)."""
import json
from pathlib import Path

import pytest
import yaml

from bizview_cli import sqlsafety
from bizview_cli.__main__ import main
from bizview_cli.validate import lock_differences, read_lock, validate, write_lock
from tests.conftest import SPEC, spec_folder, write


def codes(root: Path, **kw) -> set[str]:
    return {i.code for i in validate(root, **kw).issues}


def test_valid_workspace(ws):
    result = validate(ws)
    assert result.ok, [str(i) for i in result.issues]
    assert set(result.integrations) == {"ventas"} and set(result.reports) == {"resumen"}
    entry = result.lock["entries"]["integrations/ventas"]
    assert entry["spec"]["status"] == "Implemented"
    assert set(entry["artifacts"]) == {"integrations/ventas/integration.yaml",
                                       "integrations/ventas/queries/sale_lines.sql",
                                       "integrations/ventas/queries/products.sql"}


@pytest.mark.parametrize("change,code", [
    (lambda r: (r / "specs/integrations/001-ventas/plan.md").unlink(), "spec_incomplete"),
    (lambda r: spec_folder(r, "integration", "001-ventas", status="Draft"), "spec_not_approved"),
    (lambda r: spec_folder(r, "integration", "001-ventas", open_task=True), "open_tasks"),
    (lambda r: write(r, "specs/integrations/001-ventas/spec.md",                 # wrong type
                     SPEC.format(title="x", kind="report", status="Approved")), "spec_incomplete"),
    (lambda r: write(r, "integrations/ventas/integration.yaml",
                     (r / "integrations/ventas/integration.yaml").read_text()
                     .replace("specs/integrations/001-ventas", "specs/integrations/404")),
     "missing_spec"),
])
def test_no_spec_no_run(ws, change, code):
    change(ws)
    assert code in codes(ws)


@pytest.mark.parametrize("sql", [
    "DELETE FROM documentos WHERE fecha >= :window_start AND fecha < :window_end",
    "SELECT pg_read_file('/etc/passwd') WHERE 1 = :window_start AND 1 = :window_end",
    "SELECT 1 WHERE 1 = :window_start AND 1 = :window_end; DROP TABLE x",
    "SELECT * INTO copia FROM documentos WHERE 1 = :window_start AND 1 = :window_end",
    "SELECT * FROM documentos WHERE 1 = :window_start AND 1 = :window_end FOR UPDATE",
    "SELECT * FROM documentos WHERE 1 = :window_start AND 1 = :window_end AND x = :other",
])
def test_unsafe_integration_sql(ws, sql):
    write(ws, "integrations/ventas/queries/sale_lines.sql", sql)
    assert "unsafe_sql" in codes(ws)


@pytest.mark.parametrize("sql", [
    'SELECT "pg_read_file"(\'/etc/passwd\')',
    'SELECT pg_catalog."pg_read_file"(\'/etc/passwd\')',
    'SELECT * FROM "pg_read_file"(\'/etc/passwd\')',
    'SELECT "pg_read_binary_file"(\'/etc/passwd\')',
    'SELECT "pg_ls_dir"(\'/\')',
    'SELECT "pg_terminate_backend"(pg_backend_pid())',
    'SELECT "dblink"(\'dbname=x\',\'select 1\')',
    'SELECT "set_config"(\'statement_timeout\', \'0\', false)',
    'SELECT lo_import(\'/etc/passwd\')',
])
def test_quoted_function_name_cannot_bypass_the_block_list(sql):
    problems = sqlsafety.check_query(sql)
    assert [p.code for p in problems] == ["unsafe_sql"], problems
    assert all("no permitida" in p.message for p in problems), problems


@pytest.mark.parametrize("sql", [
    'SELECT "sum"(amount) FROM sales',
    'SELECT "lower"(name) FROM sales',
    'SELECT amount FROM sales',
])
def test_quoted_harmless_names_are_not_over_rejected(sql):
    assert sqlsafety.check_query(sql) == []


def test_incremental_query_must_use_window(ws):
    write(ws, "integrations/ventas/queries/sale_lines.sql", "SELECT 1 AS document_id")
    assert "invalid_reference" in codes(ws)


@pytest.mark.parametrize("old,new,code", [
    ('sql: "sum(lines.net_amount)"', 'sql: "sum(lines.missing)"', "invalid_reference"),
    ('sql: "sum(lines.net_amount)"', 'sql: "sum(net_amount)"', "invalid_reference"),
    ('sql: "sum(lines.net_amount)"', 'sql: "pg_sleep(10)"', "unsafe_sql"),
    ('sql: "sum(lines.net_amount)"', 'sql: "sum(lines.net_amount) + (select 1)"', "unsafe_sql"),
    ("formula: net_sales / orders", "formula: net_sales / ghost", "invalid_reference"),
    ("lines: ventas.sale_lines", "lines: ventas.nope", "unknown_dataset"),
    ("lines: ventas.sale_lines", "lines: otra.sale_lines", "unknown_dataset"),
    ("date: lines.local_date", "date: lines.document_id", "invalid_reference"),
    ("inputs: [net_sales, orders]", "inputs: [net_sales, secreto]", "invalid_reference"),
    ("metric: net_sales, limit: 10", "metric: ghost, limit: 10", "invalid_reference"),
])
def test_report_references(ws, old, new, code):
    path = ws / "reports/resumen/report.yaml"
    path.write_text(path.read_text().replace(old, new))
    assert code in codes(ws)


def test_schema_errors_and_id_mismatch(ws):
    path = ws / "reports/resumen/report.yaml"
    path.write_text(path.read_text().replace("id: resumen", "id: otro"))
    assert "schema_error" in codes(ws)
    path.write_text(path.read_text().replace("id: otro", "id: resumen") + "unexpected: 1\n")
    assert "schema_error" in codes(ws)


def test_unknown_source_with_catalogue(ws):
    assert "unknown_source" in codes(ws, known_sources={"Otra"})
    assert validate(ws, known_sources={"origen ERP"}).ok


def test_lock_detects_changes(ws):
    write_lock(ws, validate(ws).lock)
    lock = read_lock(ws)
    assert lock_differences(lock, validate(ws).lock) == []
    path = ws / "integrations/ventas/queries/products.sql"
    path.write_text(path.read_text() + " -- cambio\n")
    assert lock_differences(lock, validate(ws).lock) == ["integrations/ventas"]
    (ws / "specs/reports/001-resumen/spec.md").write_text(
        (ws / "specs/reports/001-resumen/spec.md").read_text() + "\nMás texto.\n")
    assert "reports/resumen" in lock_differences(lock, validate(ws).lock)


def test_cli_exit_codes(ws, capsys):
    assert main(["validate", str(ws)]) == 1                 # no lock yet
    assert main(["validate", str(ws), "--write-lock"]) == 0
    assert main(["validate", str(ws)]) == 0
    spec_folder(ws, "report", "001-resumen", open_task=True)
    assert main(["validate", str(ws)]) == 1
    assert "open_tasks" in capsys.readouterr().err


@pytest.mark.parametrize("tz", ["UTC -c default_transaction_read_only=off", "Mars/Olympus",
                                "../etc/passwd"])
def test_timezone_must_be_iana(ws, tz):
    path = ws / "integrations/ventas/integration.yaml"
    path.write_text(path.read_text().replace("timezone: America/Caracas", f"timezone: '{tz}'"))
    assert "schema_error" in codes(ws)


@pytest.mark.parametrize("req_path", ["https://evil.example/x", "//evil.example/x"])
def test_request_path_must_be_relative(ws, req_path):
    path = ws / "integrations/ventas/integration.yaml"
    path.write_text(path.read_text().replace("query: queries/products.sql",
                                             "request: requests/products.yaml"))
    write(ws, "integrations/ventas/requests/products.yaml",
          f"path: '{req_path}'\nrecords: $.items\nfields: {{product_code: code, name: name}}\n")
    assert "unsafe_sql" in codes(ws)


def test_symlinked_spec_file_rejected(ws):
    plan = ws / "specs/integrations/001-ventas/plan.md"
    plan.unlink()
    outside = ws.parent / "stolen-plan.md"
    outside.write_text("# Plan\n", encoding="utf-8")
    plan.symlink_to(outside)
    result = validate(ws)
    assert not result.ok
    assert any(i.code == "spec_incomplete" and i.entry == "integrations/ventas"
               and "enlace" in i.message for i in result.issues)
    assert all(not p.endswith("specs/integrations/001-ventas/plan.md")
               for entry in {**result.integrations, **result.reports}.values()
               for p in entry.files)
    outside.unlink()
    plan.unlink()
    write(ws, "specs/integrations/001-ventas/plan.md", "# Plan\n")
    sibling = ws / "specs/integrations/001-ventas/notes.md"
    write(ws, "specs/integrations/001-ventas/notes.md", "# Notes\n")
    plan.unlink()
    plan.symlink_to(sibling)
    result = validate(ws)
    assert not result.ok
    assert any(i.code == "spec_incomplete" and i.entry == "integrations/ventas"
               and "enlace" in i.message for i in result.issues)


def test_spec_path_with_dotdot_rejected(ws):
    artifact = ws / "integrations/ventas/integration.yaml"
    text = artifact.read_text()
    text = text.replace("spec: specs/integrations/001-ventas",
                        "spec: specs/integrations/../integrations/001-ventas")
    artifact.write_text(text)
    result = validate(ws)
    assert "missing_spec" in {i.code for i in result.issues}
    assert any(".." in i.message or "barras invertidas" in i.message for i in result.issues)


def test_non_utf8_spec_file_rejected(ws):
    plan = ws / "specs/integrations/001-ventas/plan.md"
    plan.write_bytes(b"# Plan\n\xff\xfe\n")
    result = validate(ws)
    assert not result.ok
    assert any(i.code == "spec_incomplete" and i.entry == "integrations/ventas"
               and "UTF-8" in i.message for i in result.issues)


def test_nul_byte_spec_file_rejected(ws):
    plan = ws / "specs/integrations/001-ventas/plan.md"
    plan.write_bytes(b"# Plan\n\x00\n")
    result = validate(ws)
    assert not result.ok
    assert any(i.code == "spec_incomplete" and i.entry == "integrations/ventas"
               and "nulos" in i.message for i in result.issues)


def test_spec_file_size_limit(ws):
    plan = ws / "specs/integrations/001-ventas/plan.md"
    plan.write_bytes(b"a" * (512 * 1024 + 1))
    result = validate(ws)
    assert not result.ok
    assert any(i.code == "spec_incomplete" and i.entry == "integrations/ventas"
               and "512 KB" in i.message for i in result.issues)
    plan.write_bytes(b"a" * (512 * 1024))
    result = validate(ws)
    assert result.ok


def test_symlinked_artifact_rejected(ws):
    artifact = ws / "reports/resumen/report.yaml"
    outside = ws.parent / "report-outside.yaml"
    outside.write_bytes(artifact.read_bytes())
    artifact.unlink()
    artifact.symlink_to(outside)
    result = validate(ws)
    assert not result.ok
    assert any(i.code == "schema_error" and i.entry == "reports/resumen"
               and "enlace" in i.message for i in result.issues)


def test_crlf_bom_nonascii_valid_and_sha_matches_bytes(ws):
    tasks = ws / "specs/integrations/001-ventas/tasks.md"
    raw = b"\xef\xbb\xbf- [X] T001 hecho \xc3\xb1and\xc3\xba\r\n"
    tasks.write_bytes(raw)
    result = validate(ws)
    assert result.ok
    assert result.integrations["ventas"].files["specs/integrations/001-ventas/tasks.md"] == raw


def test_latin1_query_rejected(ws):
    query = ws / "integrations/ventas/queries/products.sql"
    query.write_bytes(b"-- caf\xe9\n" + query.read_bytes())
    result = validate(ws)
    assert not result.ok
    assert any(i.code == "schema_error" and i.entry == "integrations/ventas"
               and "UTF-8" in i.message for i in result.issues)
    assert result.lock is None


def test_nul_byte_query_rejected(ws):
    query = ws / "integrations/ventas/queries/products.sql"
    query.write_bytes(b"SELECT 1;\n\x00\n" + query.read_bytes())
    result = validate(ws)
    assert not result.ok
    assert any(i.code == "schema_error" and i.entry == "integrations/ventas"
               and "nulos" in i.message for i in result.issues)


def test_query_size_limit(ws):
    query = ws / "integrations/ventas/queries/products.sql"
    query.write_bytes(b"x" * (512 * 1024 + 1))
    result = validate(ws)
    assert not result.ok
    assert any(i.code == "schema_error" and i.entry == "integrations/ventas"
               and "512 KB" in i.message for i in result.issues)


@pytest.mark.parametrize("target,entry", [
    ("report", "reports/resumen"),
    ("manifest", "bizview.yaml"),
])
def test_yaml_nul_escape_rejected(ws, target, entry):
    if target == "report":
        path = ws / "reports/resumen/report.yaml"
        original = path.read_text(encoding="utf-8")
        replaced = original.replace("title: Ventas", 'title: "Ven\\0tas"')
        assert replaced != original
        path.write_text(replaced, encoding="utf-8")
    else:
        path = ws / "bizview.yaml"
        original = path.read_text(encoding="utf-8")
        replaced = original.replace("name: cliente-b", 'name: "clie\\0ente-b"')
        assert replaced != original
        path.write_text(replaced, encoding="utf-8")
    result = validate(ws)
    assert not result.ok
    assert any(i.code == "schema_error" and i.entry == entry
               and "nulos" in i.message for i in result.issues)


def test_yaml_surrogate_escape_rejected(ws):
    report = ws / "reports/resumen/report.yaml"
    original = report.read_text(encoding="utf-8")
    replaced = original.replace("title: Ventas", 'title: "Ven\\ud800tas"')
    assert replaced != original
    report.write_text(replaced, encoding="utf-8")
    result = validate(ws)
    assert not result.ok
    assert any(i.code == "schema_error" and i.entry == "reports/resumen"
               and "no válidos" in i.message for i in result.issues)


def _edit(ws: Path, rel: str, old: str, new: str) -> None:
    path = ws / rel
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not found in {rel}"
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_all_schema_errors_in_one_pass_with_hints(ws: Path) -> None:
    rel = "integrations/ventas/integration.yaml"
    _edit(ws, rel, 'schedule: "*/30 * * * *"', "schedule: cada media hora")
    _edit(ws, rel, "incremental: {mode: full}", "incremental: {mode: parcial}")
    _edit(
        ws,
        rel,
        "- {type: not_null, columns: [document_id]}",
        "- {type: notnull}",
    )
    _edit(ws, rel, "quantity: {type: numeric}", "quantity: {type: decimal}")
    path = ws / rel
    text = path.read_text(encoding="utf-8")
    assert "extra: 1" not in text
    path.write_text(text + "extra: 1\n", encoding="utf-8")

    result = validate(ws)
    issues = [i for i in result.issues if i.code == "schema_error"
              and i.file == rel]
    assert len(issues) >= 5
    for issue in issues:
        assert issue.file == rel
        assert issue.path == "" or issue.path.startswith("/")
        assert issue.fix
        assert isinstance(issue.expected, dict)
        packed = json.dumps(issue.expected, ensure_ascii=False).encode("utf-8")
        assert len(packed) <= 1024
        assert str(issue).startswith("[schema_error] integrations/ventas: ")

    by_path = {i.path: i for i in issues}
    assert "0 * * * *" in by_path["/schedule"].fix
    assert by_path["/datasets/products/incremental/mode"].fix == "usa `full`"
    assert "timestamptz" in by_path["/datasets/sale_lines/columns/quantity/type"].fix
    assert by_path[""].fix.startswith("quita `extra`; permitidas:")
    assert by_path["/datasets/sale_lines/checks/0/type"].fix \
        == "usa type: row_count | not_null | reconcile"


@pytest.mark.parametrize(
    ("rel", "old", "new", "expected_path", "fix_fragment"),
    [
        (
            "integrations/ventas/integration.yaml",
            "extract: {query: queries/products.sql}",
            "extract: {query: products.sql}",
            "/datasets/products/extract/query",
            "queries/facturas.sql",
        ),
        (
            "integrations/ventas/integration.yaml",
            "extract: {query: queries/products.sql}",
            "extract: {query: queries/products.sql, request: requests/p.yaml}",
            "/datasets/products/extract",
            "usa solo una de: query, request",
        ),
        (
            "integrations/ventas/integration.yaml",
            'incremental: {window_days: 7, full_rebuild_cron: "0 3 * * *", slice: month}',
            "incremental: {window_days: 0}",
            "/datasets/sale_lines/incremental/window_days",
            "el valor mínimo es 1",
        ),
        (
            "integrations/ventas/integration.yaml",
            "incremental: {mode: full}",
            "incremental: {}",
            "/datasets/products/incremental",
            "añade una de: mode, window_days",
        ),
        (
            "integrations/ventas/integration.yaml",
            "- {type: not_null, columns: [document_id]}",
            "- {type: notnull, columns: [document_id]}",
            "/datasets/sale_lines/checks/0/type",
            "usa `not_null`",
        ),
        (
            "reports/resumen/report.yaml",
            "- {type: trend, metric: net_sales}",
            "- {type: pie}",
            "/views/1/type",
            "usa type: kpis | trend | ranking | table",
        ),
        (
            "reports/resumen/report.yaml",
            "- {type: trend, metric: net_sales}",
            "- {type: trend, metric: net_sales, color: red}",
            "/views/1",
            "quita `color`; permitidas:",
        ),
        (
            "reports/resumen/report.yaml",
            "ticket: {label: Ticket, formula: net_sales / orders, format: currency}",
            'ticket: {label: Ticket, formula: net_sales / orders, sql: "sum(lines.net_amount)"}',
            "/metrics/ticket",
            "usa solo una de: formula, sql",
        ),
        (
            "reports/resumen/report.yaml",
            "ticket: {label: Ticket, formula: net_sales / orders, format: currency}",
            "ticket: {label: Ticket, format: currency}",
            "/metrics/ticket",
            "añade una de: formula, sql",
        ),
    ],
)
def test_oneof_branch_selection(
    ws: Path, rel: str, old: str, new: str, expected_path: str, fix_fragment: str
) -> None:
    _edit(ws, rel, old, new)
    issues = [i for i in validate(ws).issues if i.code == "schema_error"]
    assert issues, "expected schema errors"
    matching = [i for i in issues if i.path == expected_path]
    assert matching, f"no issue at {expected_path}: {[(i.path, i.fix) for i in issues]}"
    issue = matching[0]
    assert fix_fragment in issue.fix
    assert isinstance(issue.expected, dict)


def test_spec_problems_reported_with_schema_errors(ws: Path) -> None:
    rel = "integrations/ventas/integration.yaml"
    _edit(ws, rel, 'schedule: "*/30 * * * *"', "schedule: cada media hora")
    spec_folder(ws, "integration", "001-ventas", status="Draft", open_task=True)

    result = validate(ws)
    assert "ventas" not in result.integrations
    assert any(i.code == "schema_error" for i in result.issues)
    assert any(
        i.code == "spec_not_approved"
        and i.file == "specs/integrations/001-ventas/spec.md"
        for i in result.issues
    )
    assert any(
        i.code == "open_tasks"
        and i.file == "specs/integrations/001-ventas/tasks.md"
        for i in result.issues
    )


def test_every_issue_has_a_file(ws: Path) -> None:
    _edit(ws, "reports/resumen/report.yaml", "date: lines.local_date", "date: lines.document_id")
    _edit(
        ws,
        "integrations/ventas/queries/products.sql",
        "SELECT",
        "DELETE FROM productos",
    )
    (ws / "specs/reports/001-resumen/plan.md").unlink()

    result = validate(ws)
    assert result.issues
    assert all(i.file for i in result.issues)

    unsafe = [i for i in result.issues if i.code == "unsafe_sql"]
    assert any(i.file == "integrations/ventas/queries/products.sql" for i in unsafe)

    date_issue = next(
        i for i in result.issues
        if i.file == "reports/resumen/report.yaml" and i.path == "/date"
    )
    assert date_issue is not None
    assert any(
        i.file == "specs/reports/001-resumen/plan.md"
        and i.code == "spec_incomplete"
        for i in result.issues
    )


def test_issue_cap_per_file(ws: Path) -> None:
    rel = "reports/resumen/report.yaml"
    path = ws / rel
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    metrics = {
        f"m{i}": {"label": "M", "sql": "sum(lines.net_amount)", "format": "bad"}
        for i in range(250)
    }
    data["metrics"] = metrics
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")

    result = validate(ws)
    report_issues = [i for i in result.issues if i.file == rel and i.code == "schema_error"]
    assert len(report_issues) == 201
    assert report_issues[-1].message == "se omitieron 50 errores más"


@pytest.mark.parametrize(
    ("pdf", "expected_path", "fix_fragment", "should_pass"),
    [
        ("pdf: {enabled: true, orientation: landscape, views: [2, 0]}", None, None, True),
        (
            "pdf: {enabled: true, orientation: sideways, views: [0]}",
            "/pdf/orientation",
            "usa uno de:",
            False,
        ),
        (
            "pdf: {enabled: true, orientation: portrait, views: []}",
            "/pdf/views",
            "necesita al menos 1 elementos",
            False,
        ),
        (
            "pdf: {enabled: true, orientation: portrait, views: [0, 0]}",
            "/pdf/views",
            "no repitas elementos",
            False,
        ),
    ],
)
def test_pdf_layout_schema(
    ws: Path, pdf: str, expected_path: str | None, fix_fragment: str | None, should_pass: bool
) -> None:
    path = ws / "reports/resumen/report.yaml"
    text = path.read_text(encoding="utf-8")
    assert "\npdf:" not in text
    path.write_text(text + "\n" + pdf + "\n", encoding="utf-8")

    result = validate(ws)
    if should_pass:
        assert result.ok, result.issues
        return
    assert any(i.code == "schema_error" for i in result.issues)
    matching = [i for i in result.issues if i.path == expected_path]
    assert matching, f"no issue at {expected_path}"
    assert fix_fragment in matching[0].fix


def test_issue_as_dict(ws: Path) -> None:
    _edit(ws, "reports/resumen/report.yaml", "date: lines.local_date", "date: lines.document_id")
    issue = next(i for i in validate(ws).issues if i.code == "invalid_reference")
    assert set(issue.as_dict()) == {"entry", "code", "message", "level", "file", "path",
                                   "expected", "fix"}


def test_report_accepts_optional_english_texts(ws):
    path = ws / "reports/resumen/report.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["title_en"] = "Sales"
    doc["description_en"] = "Daily sales"
    metric = next(iter(doc["metrics"].values()))
    metric["label_en"] = "Net sales"
    metric["description_en"] = "Sales minus returns"
    dimension = next(iter((doc.get("dimensions") or {}).values()), None)
    if dimension is not None:
        dimension["label_en"] = "Product"
    for view in doc["views"]:
        if view.get("type") in ("ranking", "table"):
            view["title_en"] = "Top"
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    result = validate(ws)
    assert result.ok, [str(i) for i in result.issues]


def test_report_rejects_empty_english_title(ws):
    path = ws / "reports/resumen/report.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["title_en"] = ""
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    result = validate(ws)
    assert not result.ok
    assert any(i.code == "schema_error" for i in result.issues)
