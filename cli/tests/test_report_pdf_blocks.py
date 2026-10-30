"""044: los bloques visuales del PDF (gauge, index, share, asset) en el validador."""

import shutil
from pathlib import Path

import yaml

from bizview_cli import authoring, validate

P = "projects/ejemplo"
REPORT = f"{P}/reports/facturas-dia/report.yaml"


def ws(tmp_path: Path) -> Path:
    dst = tmp_path / "ws"
    shutil.copytree(Path(str(authoring.golden_root("golden"))), dst)
    return dst


def errors(result: validate.Result) -> set[str]:
    return {issue.code for issue in result.issues if issue.level == "error"}


def block(root: Path, *blocks: dict, images: dict | None = None) -> None:
    path = root / REPORT
    doc = yaml.safe_load(path.read_text())
    doc["layout"]["pdf"]["blocks"].extend(blocks)
    if images is not None:
        doc["images"] = images
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))


def test_the_four_visual_kinds_are_block_types(tmp_path):
    root = ws(tmp_path)
    block(root,
          {"id": "miedo", "type": "gauge", "view": "resumen", "metric": "total_facturado",
           "min": 0, "max": 100},
          {"id": "indice", "type": "index", "view": "resumen", "metric": "total_facturado",
           "low_label": "BTC", "high_label": "Altcoins"},
          {"id": "reparto", "type": "share", "view": "resumen",
           "items": ["total_facturado", "impuesto"], "remainder_label": "Otros"},
          {"id": "fichas", "type": "asset", "view": "detalle",
           "columns": ["estado", "moneda", "facturas", "total_facturado"]})
    assert "layout_block_unknown" not in errors(validate.validate(root))


def test_a_visual_block_needs_its_view_type(tmp_path):
    root = ws(tmp_path)
    block(root, {"id": "miedo", "type": "gauge", "view": "detalle",
                 "metric": "total_facturado"})
    issue = next(i for i in validate.validate(root).issues
                 if i.code == "layout_view_unsuitable")
    assert issue.path == "/layout/pdf/blocks/5/view"
    assert "kpis" in issue.message


def test_an_asset_block_over_a_table_view_is_fine(tmp_path):
    root = ws(tmp_path)
    folder = root / P / "assets" / "coins"
    folder.mkdir(parents=True)
    (folder / "emitida.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)
    block(root,
          {"id": "fichas", "type": "asset", "view": "detalle", "image": "coins",
           "columns": ["estado", "moneda"]},
          images={"coins": {"folder": "assets/coins", "key": "estado"}})
    assert errors(validate.validate(root)) == set()


def test_an_unknown_image_set_in_a_block_is_refused(tmp_path):
    root = ws(tmp_path)
    block(root, {"id": "fichas", "type": "asset", "view": "detalle", "image": "otro"})
    assert "layout_image_unknown" in errors(validate.validate(root))


def test_a_gauge_cannot_draw_an_image(tmp_path):
    root = ws(tmp_path)
    block(root, {"id": "miedo", "type": "gauge", "view": "resumen",
                 "metric": "total_facturado", "image": "coins"})
    assert "layout_image_not_allowed" in errors(validate.validate(root))
