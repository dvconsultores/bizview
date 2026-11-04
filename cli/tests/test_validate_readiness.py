"""The two gates the server refuses to apply a project on are read here first (features 017/020):
a personal column the integration's spec does not declare, and a report with no filters. The
external AI that authors a project only learns what it must give from `bizview validate`."""
from pathlib import Path

from conftest import write

from bizview_cli import validate

CLIENTES = """
  clientes:
    primary_key: [cliente_id]
    columns:
      cliente_id: {type: text, nullable: false}
      name: {type: text}
    extract: {query: queries/clientes.sql}
    incremental: {mode: full}
"""


def codes(result: validate.Result, level: str = "error") -> set[str]:
    return {i.code for i in result.issues if i.level == level}


def add_clientes(root: Path) -> None:
    path = root / "integrations/ventas/integration.yaml"
    path.write_text(path.read_text() + CLIENTES.lstrip("\n"), encoding="utf-8")
    write(root, "integrations/ventas/queries/clientes.sql",
          "SELECT id AS cliente_id, nombre AS name FROM clientes\n")


def test_personal_column_must_be_declared_in_the_spec(ws: Path) -> None:
    add_clientes(ws)
    result = validate.validate(ws)
    assert "integration_personal_column" in codes(result)
    issue = next(i for i in result.issues if i.code == "integration_personal_column")
    assert issue.file == "integrations/ventas/integration.yaml"
    assert "**Datos personales**: name" in issue.fix

    spec = ws / "specs/integrations/001-ventas/spec.md"
    spec.write_text(spec.read_text() + "\n**Datos personales**: name\n", encoding="utf-8")
    assert "integration_personal_column" not in codes(validate.validate(ws))


def test_a_product_name_is_not_personal_data(ws: Path) -> None:
    assert "integration_personal_column" not in codes(validate.validate(ws))


def test_report_without_filters_is_a_warning(ws: Path) -> None:
    path = ws / "reports/resumen/report.yaml"
    path.write_text(path.read_text().replace("filters: [product]", "filters: []"),
                    encoding="utf-8")
    result = validate.validate(ws)
    assert "report_no_filters" in codes(result, "warning")
    assert result.ok
