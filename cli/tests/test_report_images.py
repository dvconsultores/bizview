"""044: el bloque `images:` y la propiedad `image:` de los componentes."""

import shutil
from pathlib import Path

import yaml

from bizview_cli import authoring, validate

P = "projects/ejemplo"
REPORT = f"{P}/reports/facturas-dia/report.yaml"


def ws(tmp_path: Path) -> Path:
    """Copia el espacio de trabajo dorado v2 a un directorio temporal."""
    dst = tmp_path / "ws"
    shutil.copytree(Path(str(authoring.golden_root("golden"))), dst)
    return dst


def codes(result: validate.Result) -> set[str]:
    return {issue.code for issue in result.issues}


def errors(result: validate.Result) -> set[str]:
    return {issue.code for issue in result.issues if issue.level == "error"}


def images(root: Path, spec: dict, component: dict | None = None) -> None:
    """Adds sets to the ones the golden report already declares (it ships `estados`)."""
    path = root / REPORT
    doc = yaml.safe_load(path.read_text())
    doc["images"] = {**(doc.get("images") or {}), **spec}
    if component is not None:
        doc["layout"]["web"]["components"].append(component)
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))


def coins(root: Path, *names: str) -> None:
    folder = root / P / "assets" / "coins"
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)


SET = {"coins": {"folder": "assets/coins", "key": "estado"}}


def test_a_set_with_a_folder_and_a_declared_key_is_valid(tmp_path):
    root = ws(tmp_path)
    coins(root, "BTC.png", "ETH.png")
    images(root, SET, {"id": "logos", "type": "table", "view": "detalle",
                       "columns": ["estado", "moneda"], "image": "coins", "span": 12})
    result = validate.validate(root)
    assert not (codes(result) & {"image_folder_missing", "image_folder_empty",
                                 "image_svg_only", "image_key_unknown",
                                 "layout_image_not_allowed", "layout_image_unknown"}), \
        codes(result)
    assert errors(result) == set(), codes(result)


def test_a_missing_folder_is_an_error(tmp_path):
    root = ws(tmp_path)
    images(root, {"coins": {"folder": "assets/nope", "key": "estado"}})
    assert "image_folder_missing" in errors(validate.validate(root))


def test_an_empty_folder_is_an_error(tmp_path):
    root = ws(tmp_path)
    (root / P / "assets" / "coins").mkdir(parents=True)
    images(root, SET)
    assert "image_folder_empty" in errors(validate.validate(root))


def test_a_column_of_a_used_alias_works_as_the_key(tmp_path):
    root = ws(tmp_path)
    coins(root, "C-1.png")
    images(root, {"coins": {"folder": "assets/coins", "key": "cliente_id"}})
    assert "image_key_unknown" not in codes(validate.validate(root))


def test_an_undeclared_key_is_an_error(tmp_path):
    root = ws(tmp_path)
    coins(root, "BTC.png")
    images(root, {"coins": {"folder": "assets/coins", "key": "no_existe"}})
    assert "image_key_unknown" in errors(validate.validate(root))


def test_an_svg_only_set_warns_but_does_not_fail(tmp_path):
    root = ws(tmp_path)
    folder = root / P / "assets" / "coins"
    folder.mkdir(parents=True)
    (folder / "BTC.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    images(root, SET)
    result = validate.validate(root)
    issue = next(i for i in result.issues if i.code == "image_svg_only")
    assert issue.level == "warning"
    assert "image_svg_only" not in errors(result)


def test_image_on_a_component_that_cannot_draw_one_is_refused(tmp_path):
    root = ws(tmp_path)
    coins(root, "BTC.png")
    images(root, SET, {"id": "tendencia_logo", "type": "line", "view": "diaria",
                       "x": "day", "series": ["total_facturado"], "image": "coins"})
    assert "layout_image_not_allowed" in errors(validate.validate(root))


def test_an_unknown_set_name_is_refused(tmp_path):
    root = ws(tmp_path)
    coins(root, "BTC.png")
    images(root, SET, {"id": "detalle_logo", "type": "table", "view": "detalle",
                       "columns": ["estado", "moneda"], "image": "otro"})
    assert "layout_image_unknown" in errors(validate.validate(root))


def test_a_kpi_tile_may_key_the_set_by_metric_id(tmp_path):
    """A `kpi` tile has no row, so its only stable identity is the metric id."""
    root = ws(tmp_path)
    doc = yaml.safe_load((root / REPORT).read_text())
    metric = next(iter(doc["metrics"]))
    coins(root, f"{metric}.png")
    images(root, {"coins": {"folder": "assets/coins", "key": metric}},
           {"id": "cara", "type": "kpi", "view": "resumen", "metric": metric,
            "image": "coins", "span": 3})
    result = validate.validate(root)
    assert "image_key_unknown" not in codes(result), codes(result)
    assert errors(result) == set(), codes(result)
