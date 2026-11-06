"""Feature 056: `labels` is the only key the layout gained; the validator must accept it and
refuse a value outside its enum."""
import shutil
from pathlib import Path

import yaml

from bizview_cli.validate import validate

ROOT = Path(__file__).resolve().parents[1]


def workspace(tmp_path: Path) -> Path:
    src = ROOT / "bizview_cli" / "golden"
    shutil.copytree(src, tmp_path / "ws")
    return tmp_path / "ws"


def component(ws: Path, **extra) -> dict:
    report = ws / "projects" / "ejemplo" / "reports" / "facturas-dia" / "report.yaml"
    data = yaml.safe_load(report.read_text())
    data["layout"]["web"]["components"].append({"id": "barras", "type": "bar", "view": "estados",
                                                "x": "estado", "series": ["total_facturado"], **extra})
    report.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    return data


def test_true_is_accepted(tmp_path):
    ws = workspace(tmp_path)
    component(ws, labels=True)
    result = validate(ws)
    assert result.ok, [str(i) for i in result.issues]


def test_a_mode_is_accepted(tmp_path):
    ws = workspace(tmp_path)
    component(ws, type="pie", category="estado", value="total_facturado", labels="both")
    result = validate(ws)
    assert result.ok, [str(i) for i in result.issues]


def test_an_unknown_value_is_refused(tmp_path):
    ws = workspace(tmp_path)
    component(ws, labels="sometimes")
    result = validate(ws)
    assert not result.ok
    assert any(i.code == "schema_error" for i in result.issues)
