"""Fix hints with valid names and schema-invalid dependencies (feature 017, FR-003)."""

from pathlib import Path

import pytest

from bizview_cli.validate import _names, validate
from tests.conftest import spec_folder


def _edit(ws: Path, rel: str, old: str, new: str) -> None:
    path = ws / rel
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not found in {rel}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _issue(result, code, path):
    matches = [i for i in result.issues if i.code == code and i.path == path]
    assert matches, f"ningún issue {code} en {path}: {result.issues}"
    return matches[0]


def test_schema_invalid_integration_message(ws):
    _edit(ws, "integrations/ventas/integration.yaml",
          "schedule: \"*/30 * * * *\"", "schedule: cada media hora")
    result = validate(ws)
    issue = _issue(result, "unknown_dataset", "/uses/lines")
    assert "la integración ventas tiene errores de esquema; corrígela primero" in issue.message
    assert "no existe" not in issue.message
    assert issue.file == "reports/resumen/report.yaml"
    assert "integrations/ventas/integration.yaml" in (issue.fix or "")
    assert all("no existe la integración ventas" not in i.message for i in result.issues)


def test_missing_dataset_and_integration(ws):
    _edit(ws, "reports/resumen/report.yaml",
          "lines: ventas.sale_lines", "lines: otra.sale_lines")
    result = validate(ws)
    issue = _issue(result, "unknown_dataset", "/uses/lines")
    assert "no existe la integración otra" in issue.message
    assert "ventas" in (issue.fix or "")

    _edit(ws, "reports/resumen/report.yaml",
          "lines: otra.sale_lines", "lines: ventas.nope")
    result = validate(ws)
    issue = _issue(result, "unknown_dataset", "/uses/lines")
    assert "ventas no tiene el conjunto nope" in issue.message
    assert "sale_lines" in (issue.fix or "")
    assert "products" in (issue.fix or "")


def test_id_mismatch_runs_spec_check(ws):
    _edit(ws, "integrations/ventas/integration.yaml", "id: ventas", "id: otro")
    spec_folder(ws, "integration", "001-ventas", status="Draft", open_task=True)
    result = validate(ws)

    id_issue = _issue(result, "schema_error", "/id")
    assert "id 'otro' debe coincidir con la carpeta 'ventas'" in id_issue.message
    assert id_issue.fix == "usa id: ventas"

    spec_issue = [
        i for i in result.issues
        if i.code == "spec_not_approved"
        and i.file == "specs/integrations/001-ventas/spec.md"
    ]
    assert spec_issue
    tasks_issue = [
        i for i in result.issues
        if i.code == "open_tasks" and i.file == "specs/integrations/001-ventas/tasks.md"
    ]
    assert tasks_issue

    report_issue = _issue(result, "unknown_dataset", "/uses/lines")
    assert "la integración ventas tiene errores de esquema" in report_issue.message


def test_unknown_source_fix(ws):
    result = validate(ws, known_sources={"Otra fuente", "Tercera"})
    issue = _issue(result, "unknown_source", "/source")
    assert "la fuente 'Origen ERP' no existe en la instalación" in issue.message
    assert "Otra fuente" in issue.fix
    assert "Tercera" in issue.fix

    result = validate(ws, known_sources=set())
    issue = _issue(result, "unknown_source", "/source")
    assert issue.fix == "registra primero la fuente en la instalación"


def test_primary_key_fix(ws):
    _edit(ws, "integrations/ventas/integration.yaml",
          "primary_key: [product_code]", "primary_key: [codigo]")
    result = validate(ws)
    issue = _issue(result, "invalid_reference", "/datasets/products/primary_key")
    assert issue.message == "primary_key: no existe codigo"
    assert "product_code" in issue.fix
    assert "name" in issue.fix


def test_bad_date_column_fix(ws):
    _edit(ws, "integrations/ventas/integration.yaml",
          "date_column: local_date", "date_column: product_code")
    result = validate(ws)
    issue = _issue(result, "invalid_reference", "/datasets/sale_lines/date_column")
    assert "local_date" in issue.fix
    assert "product_code" not in issue.fix


def test_check_column_fix(ws):
    _edit(ws, "integrations/ventas/integration.yaml",
          "- {type: not_null, columns: [document_id]}",
          "- {type: not_null, columns: [ghost]}")
    result = validate(ws)
    issue = _issue(result, "invalid_reference", "/datasets/sale_lines/checks/0")
    assert issue.message == "check: no existe ghost"
    assert "document_id" in issue.fix
    assert "net_amount" in issue.fix


@pytest.mark.parametrize("source,target,path,substr,names", [
    ("metric: net_sales, limit: 10",
     "metric: ghost, limit: 10",
     "/views/2", "views[2]: métrica ghost", ("net_sales", "orders", "ticket")),
    ("dimension: product, metric",
     "dimension: ghost, metric",
     "/views/2", "views[2]: dimensión ghost", ("product",)),
    ("filters: [product]", "filters: [ghost]",
     "/filters/0", "filters: dimensión ghost", ("product",)),
    ("inputs: [net_sales, orders]", "inputs: [net_sales, ghost]",
     "/ai_narrative/inputs/1", "ai_narrative: métrica ghost", ("net_sales",)),
    ("date: lines.local_date", "date: lines.document_id",
     "/date", "debe ser una columna date/timestamptz", ("lines.local_date",)),
    ("formula: net_sales / orders", "formula: net_sales / ticket",
     "/metrics/ticket", "métricas con sql: ticket", ("net_sales", "orders")),
])
def test_report_reference_fix(ws, source, target, path, substr, names):
    _edit(ws, "reports/resumen/report.yaml", source, target)
    result = validate(ws)
    issue = _issue(result, "invalid_reference", path)
    assert substr in issue.message
    for name in names:
        assert name in issue.fix


def test_names_sort_dedup_empty_truncation():
    assert _names(["b", "a", "a"]) == "a, b"
    assert _names([]) == "(ninguno)"
    assert _names(["c", "a", "b", "d"], limit=2) == "a, b, … (y 2 más)"


def test_pdf_views_index_out_of_range(ws):
    _edit(
        ws, "reports/resumen/report.yaml",
        "ai_narrative: {enabled: true, inputs: [net_sales, orders]}",
        "ai_narrative: {enabled: true, inputs: [net_sales, orders]}\n"
        "pdf: {enabled: true, views: [0, 3, 2, 7]}",
    )
    result = validate(ws)
    assert result.ok is False
    for i, idx in [(1, 3), (3, 7)]:
        issue = _issue(result, "invalid_reference", f"/pdf/views/{i}")
        assert issue.file == "reports/resumen/report.yaml"
        assert f"no existe la vista {idx}" in issue.message
        assert issue.fix == "usa un índice de vista válido: 0, 1, 2"
    for path in ("/pdf/views/0", "/pdf/views/2"):
        assert not any(
            i.code == "invalid_reference" and i.path == path for i in result.issues
        )


def test_pdf_views_valid_indexes_pass(ws):
    _edit(
        ws, "reports/resumen/report.yaml",
        "ai_narrative: {enabled: true, inputs: [net_sales, orders]}",
        "ai_narrative: {enabled: true, inputs: [net_sales, orders]}\n"
        "pdf: {enabled: true, views: [2, 0, 1]}",
    )
    result = validate(ws)
    assert result.ok is True
    assert not any(i.path and i.path.startswith("/pdf") for i in result.issues)


def test_pdf_views_reported_with_dataset_problem(ws):
    _edit(
        ws, "reports/resumen/report.yaml",
        "lines: ventas.sale_lines",
        "lines: otra.sale_lines",
    )
    _edit(
        ws, "reports/resumen/report.yaml",
        "ai_narrative: {enabled: true, inputs: [net_sales, orders]}",
        "ai_narrative: {enabled: true, inputs: [net_sales, orders]}\n"
        "pdf: {enabled: true, views: [5]}",
    )
    result = validate(ws)
    assert result.ok is False
    _issue(result, "unknown_dataset", "/uses/lines")
    issue = _issue(result, "invalid_reference", "/pdf/views/0")
    assert issue.file == "reports/resumen/report.yaml"
    assert "no existe la vista 5" in issue.message
    assert issue.fix == "usa un índice de vista válido: 0, 1, 2"
