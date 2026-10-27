"""Feature 020 T005: project layout and spec kind."""

import pytest

from bizview_cli.layout import ALLOWED_TEXT, is_allowed, is_allowed_folder, spec_kind


@pytest.mark.parametrize(
    "path",
    [
        "project.yaml",
        ".specify/memory/constitution.md",
        "specs/001-facturas/spec.md",
        "specs/001-facturas/plan.md",
        "specs/001-facturas/tasks.md",
        "specs/001-facturas/research.md",
        "specs/001-facturas/data-model.md",
        "specs/001-facturas/quickstart.md",
        "specs/001-facturas/run-report.md",
        "specs/001-facturas/checklists/requirements.md",
        "integrations/abc/integration.yaml",
        "integrations/abc/queries/facturas.sql",
        "integrations/abc/requests/pedidos.yaml",
        "reports/abc/report.yaml",
        "distributions/envio-semanal.yaml",
    ],
)
def test_allowed_paths(path: str) -> None:
    assert is_allowed(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/project.yaml",
        "../x",
        "specs/1-x/spec.md",
        "specs/001-Facturas/spec.md",
        "specs/001-x/notes.md",
        "integrations/X/integration.yaml",
        "reports/a/report.yml",
        "bizview.yaml",
        "integrations/abc/queries/a.txt",
        "secrets/.env",
    ],
)
def test_refused_paths(path: str) -> None:
    assert is_allowed(path) is False


@pytest.mark.parametrize(
    "path", ["specs", "specs/001-x/", "integrations/abc/queries", ".specify/memory"]
)
def test_allowed_folders(path: str) -> None:
    assert is_allowed_folder(path) is True


@pytest.mark.parametrize("path", ["specs/xx", "other", "integrations/abc/other"])
def test_refused_folders(path: str) -> None:
    assert is_allowed_folder(path) is False


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("**Tipo**: integración", "integracion"),
        ("- **Type**: Report", "reporte"),
        ("**Spec type**: integration", "integracion"),
        ("**Tipo**: distribución", "distribucion"),
        ("**Tipo**: fuente", "fuente"),
        ("**Type**: source", "fuente"),
        ("**Tipo**: otro", None),
        ("sin línea", None),
    ],
)
def test_spec_kind(text: str, expected: str | None) -> None:
    assert spec_kind(text) == expected


def test_allowed_text_has_no_newline() -> None:
    assert "\n" not in ALLOWED_TEXT
