"""Feature 049: `bizview import --dry-run` measures a folder or a zip the way the server does."""
import io
import json
import zipfile
from pathlib import Path

from bizview_cli.__main__ import main
from bizview_cli.importer import measure, render

SPEC = "---\n**Tipo**: reporte\n**Status**: Approved\n**Resumen**: ventas\n"


def _project(root: Path, images: int = 0, extra: dict[str, bytes] | None = None) -> Path:
    (root / "specs" / "001-ventas").mkdir(parents=True)
    (root / "project.yaml").write_text("name: Ventas\nslug: ventas\n", "utf-8")
    (root / "specs" / "001-ventas" / "spec.md").write_text(SPEC, "utf-8")
    if images:
        (root / "assets" / "coins").mkdir(parents=True)
        for i in range(images):
            (root / "assets" / "coins" / f"C{i}.png").write_bytes(b"\x89PNG" + bytes(60))
    for name, data in (extra or {}).items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return root


def _zip(root: Path, inside: bool = True) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        prefix = f"{root.name}/" if inside else ""
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.writestr(prefix + path.relative_to(root).as_posix(), path.read_bytes())
    return buffer.getvalue()


def test_a_folder_is_measured_against_both_allowances(tmp_path):
    result = measure(_project(tmp_path / "ventas", images=483))
    assert result["importable"], result["reason"]
    assert result["budgets"]["artifacts"]["files"] == 2
    assert result["budgets"]["assets"]["files"] == 483
    assert result["ignored"] == []


def test_a_zip_is_measured_the_same_way_and_its_top_folder_is_folded(tmp_path):
    root = _project(tmp_path / "ventas", images=3)
    archive = tmp_path / "ventas.zip"
    archive.write_bytes(_zip(root))
    result = measure(archive)
    assert result["importable"], result["reason"]
    assert result["budgets"]["assets"]["files"] == 3
    assert result["folded_top"] is True
    assert result["slug"] == "ventas"


def test_over_the_image_limit_reports_the_images(tmp_path):
    result = measure(_project(tmp_path / "logos", images=2001))
    assert result["importable"] is False
    assert result["code"] == "assets_over_files"
    assert "2001" in result["reason"].replace(" 1", "1")
    assert "assets/" in result["reason"]


def test_a_pack_zipped_by_mistake_is_importable_and_lists_what_it_skips(tmp_path):
    root = _project(tmp_path / "ventas", images=2, extra={
        "PROMPT.md": b"# pack\n", "REQUEST.md": b"# request\n", "README.md": b"# readme\n",
        "request/foto.png": b"\x89PNG", "sources/ventas/structure.json": b"{}",
        ".bizview/preset/preset.yaml": b"x: 1\n", ".DS_Store": b"\x00\x01",
    })
    result = measure(root)
    assert result["importable"], result["reason"]
    assert "PROMPT.md" in result["ignored"]
    assert "request/foto.png" in result["ignored"]
    assert "sources/ventas/structure.json" in result["ignored"]
    assert ".bizview/preset/preset.yaml" in result["ignored"]


def test_a_script_anywhere_is_refused(tmp_path):
    result = measure(_project(tmp_path / "ventas", extra={"build/pack.js": b"alert(1)"}))
    assert result["importable"] is False
    assert result["code"] == "zip_disallowed"
    assert "build/pack.js" in result["reason"]


def test_the_command_exits_one_when_not_importable_and_zero_when_it_is(tmp_path, capsys):
    good = _project(tmp_path / "bueno", images=2)
    assert main(["import", "--dry-run", str(good)]) == 0
    assert "importable" in capsys.readouterr().out

    bad = _project(tmp_path / "malo", images=2001)
    assert main(["import", "--dry-run", str(bad)]) == 1
    out = capsys.readouterr().out
    assert "not importable" in out or "no importable" in out
    assert "2001" in out


def test_the_command_exits_two_for_something_that_is_not_a_project(tmp_path):
    missing = tmp_path / "nada.zip"
    assert main(["import", "--dry-run", str(missing)]) == 2


def test_json_output_carries_the_contract_fields(tmp_path, capsys):
    root = _project(tmp_path / "ventas", images=3)
    assert main(["import", "--dry-run", str(root), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload) >= {"path", "slug", "importable", "reason", "ignored", "budgets", "code"}
    assert set(payload["budgets"]) == {"artifacts", "assets"}
    assert set(payload["budgets"]["assets"]) >= {"files", "bytes", "max_files", "max_mb"}


def test_the_human_reading_names_both_allowances(tmp_path):
    text = render(measure(_project(tmp_path / "ventas", images=3)))
    assert "artifacts" in text and "assets" in text
    assert "400" in text and "2000" in text
