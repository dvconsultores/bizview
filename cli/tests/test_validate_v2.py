"""Feature 020 T013: workspace layout v2 (projects, numbered specs, distributions, lock)."""

import shutil
from pathlib import Path

import yaml

from bizview_cli import authoring, validate


def ws(tmp_path: Path) -> Path:
    """Copy the golden v2 workspace to a temporary directory and return its path."""
    src = Path(str(authoring.golden_root("golden")))
    dst = tmp_path / "ws"
    shutil.copytree(src, dst)
    return dst


P = "projects/ejemplo"


def codes(result: validate.Result) -> set[str]:
    """Return error-level issue codes for a validation result."""
    return {issue.code for issue in result.issues if issue.level == "error"}


def edit(path: Path, old: str, new: str) -> None:
    """Replace a single occurrence of `old` with `new` in a text file."""
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new, 1))


def yaml_edit(path: Path, fn) -> None:
    """Load a YAML file, apply `fn` to the document, and write it back."""
    doc = yaml.safe_load(path.read_text())
    fn(doc)
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))


def test_golden_valid(tmp_path: Path) -> None:
    root = ws(tmp_path)
    result = validate.validate(root)
    assert result.ok
    assert result.layout == "v2"
    assert result.lock["layout"] == "v2"
    assert set(result.lock["entries"]) == {
        "integrations/facturas",
        "reports/facturas-dia",
        "distributions/envio-semanal",
    }
    assert result.lock["entries"]["distributions/envio-semanal"]["project"] == "ejemplo"
    specs = result.lock["projects"]["ejemplo"]["specs"]
    assert sorted(specs) == ["001-facturas", "002-facturas-dia", "003-envio-semanal"]
    assert [specs[s]["kind"] for s in sorted(specs)] == [
        "integracion",
        "reporte",
        "distribucion",
    ]


def test_legacy_fixture(tmp_path: Path) -> None:
    src = Path(__file__).parent / "fixtures" / "legacy"
    dst = tmp_path / "legacy"
    shutil.copytree(src, dst)
    result = validate.validate(dst)
    assert result.ok
    assert result.layout == "legacy"
    assert "layout" not in result.lock
    for entry in result.lock["entries"].values():
        assert "project" not in entry


def test_mixed(tmp_path: Path) -> None:
    root = ws(tmp_path)
    (root / "reports").mkdir()
    result = validate.validate(root)
    assert not result.ok
    assert "mixed_layout" in codes(result)


def test_duplicate_ids_across_projects(tmp_path: Path) -> None:
    root = ws(tmp_path)
    shutil.copytree(root / P, root / "projects" / "otro")
    edit(root / "projects" / "otro" / "project.yaml", "name: Ejemplo", "name: Otro")
    edit(root / "projects" / "otro" / "project.yaml", "slug: ejemplo", "slug: otro")
    result = validate.validate(root)
    assert not result.ok
    assert "duplicate_id" in codes(result)


def test_kind_aliases_accepted(tmp_path: Path) -> None:
    root = ws(tmp_path)
    edit(
        root / P / "specs" / "001-facturas" / "spec.md",
        "**Tipo**: integracion",
        "**Type**: integration",
    )
    result = validate.validate(root)
    assert result.ok


def test_missing_kind_line(tmp_path: Path) -> None:
    root = ws(tmp_path)
    edit(root / P / "specs" / "001-facturas" / "spec.md", "**Tipo**: integracion", "")
    result = validate.validate(root)
    assert not result.ok
    assert "spec_kind_missing" in codes(result)


def test_numbering_duplicate(tmp_path: Path) -> None:
    root = ws(tmp_path)
    shutil.copytree(
        root / P / "specs" / "001-facturas",
        root / P / "specs" / "001-otra",
    )
    result = validate.validate(root)
    assert not result.ok
    assert "spec_number_duplicate" in codes(result)


def test_numbering_invalid_folder(tmp_path: Path) -> None:
    root = ws(tmp_path)
    (root / P / "specs" / "1-x").mkdir()
    result = validate.validate(root)
    assert not result.ok
    assert "spec_folder_invalid" in codes(result)


def test_distribution_period_not_allowed(tmp_path: Path) -> None:
    root = ws(tmp_path)
    yaml_edit(
        root / P / "distributions" / "envio-semanal.yaml",
        lambda d: d["subscriptions"][0].update(period="qtd"),
    )
    result = validate.validate(root)
    assert not result.ok
    assert "invalid_reference" in codes(result)


def test_attach_pdf_needs_pdf(tmp_path: Path) -> None:
    root = ws(tmp_path)
    yaml_edit(
        root / P / "reports" / "facturas-dia" / "report.yaml",
        lambda d: d["pdf"].update(enabled=False),
    )
    result = validate.validate(root)
    assert not result.ok
    assert "invalid_reference" in codes(result)


def test_nothing_to_send(tmp_path: Path) -> None:
    root = ws(tmp_path)
    yaml_edit(
        root / P / "distributions" / "envio-semanal.yaml",
        lambda d: d["subscriptions"][0].update(attach_pdf=False, link_days=None),
    )
    result = validate.validate(root)
    assert not result.ok
    assert "invalid_reference" in codes(result)


def test_link_days_above_share_max_days(tmp_path: Path) -> None:
    root = ws(tmp_path)
    yaml_edit(
        root / P / "distributions" / "envio-semanal.yaml",
        lambda d: d["subscriptions"][0].update(link_days=40),
    )
    result = validate.validate(root)
    assert not result.ok
    assert "invalid_reference" in codes(result)


def test_role_without_access_is_warning(tmp_path: Path) -> None:
    root = ws(tmp_path)
    yaml_edit(
        root / P / "reports" / "facturas-dia" / "report.yaml",
        lambda d: d["access"].update(roles=["admin"]),
    )
    yaml_edit(
        root / P / "distributions" / "envio-semanal.yaml",
        lambda d: d["subscriptions"][0]["recipients"].update(roles=["user"]),
    )
    result = validate.validate(root)
    assert result.ok
    assert any(
        issue.code == "distribution_role" and issue.level == "warning"
        for issue in result.issues
    )


def test_unknown_report(tmp_path: Path) -> None:
    root = ws(tmp_path)
    yaml_edit(
        root / P / "distributions" / "envio-semanal.yaml",
        lambda d: d.update(report="no-existe"),
    )
    result = validate.validate(root)
    assert not result.ok
    assert "unknown_report" in codes(result)


def test_fuente_spec(tmp_path: Path) -> None:
    root = ws(tmp_path)
    spec_dir = root / P / "specs" / "004-origen"
    spec_dir.mkdir()
    (spec_dir / "spec.md").write_text("# Origen\n\n**Tipo**: fuente\n\n**Status**: Approved\n")
    (spec_dir / "plan.md").write_text("# x\n")
    (spec_dir / "tasks.md").write_text("# x\n")
    result = validate.validate(root)
    assert not result.ok
    assert "source_line_missing" in codes(result)

    edit(spec_dir / "spec.md", "**Status**: Approved",
         "**Fuente**: desconocida\n\n**Status**: Approved")
    result = validate.validate(root, known_sources={"origen_ventas"})
    assert not result.ok
    assert "unknown_source" in codes(result)

    result = validate.validate(root, known_sources={"origen_ventas", "Desconocida"})
    assert result.ok


def test_ignored_files(tmp_path: Path) -> None:
    root = ws(tmp_path)
    (root / P / "notes.txt").write_text("hello\n")
    result = validate.validate(root)
    assert result.ok
    assert result.projects["ejemplo"]["ignored"] == ["notes.txt"]


def test_project_slug_mismatch(tmp_path: Path) -> None:
    root = ws(tmp_path)
    edit(root / P / "project.yaml", "slug: ejemplo", "slug: otro")
    result = validate.validate(root)
    assert not result.ok
    assert "project_slug_mismatch" in codes(result)


def test_lock_v2_differences(tmp_path: Path) -> None:
    root = ws(tmp_path)
    first = validate.validate(root).lock
    plan = root / P / "specs" / "002-facturas-dia" / "plan.md"
    plan.write_text(plan.read_text() + "\nNota.\n")
    second = validate.validate(root).lock
    diffs = validate.lock_differences(first, second)
    assert "reports/facturas-dia" in diffs
    assert validate.lock_differences(first, first) == []


def test_unquoted_created_date_accepted(tmp_path: Path) -> None:
    root = ws(tmp_path)
    edit(root / P / "project.yaml", 'created: "2026-10-01"', "created: 2026-10-01")
    result = validate.validate(root)
    assert result.ok
