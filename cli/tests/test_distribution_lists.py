"""Feature 058: a distribution names mailing lists, never addresses.

The project lives in Git, so it cannot carry a customer's addresses (constitution II). It names the
lists the installation owns; the app resolves those names when it applies the project.
"""
import shutil
from pathlib import Path

import yaml

from bizview_cli import authoring, validate


def ws(tmp_path: Path) -> Path:
    dst = tmp_path / "ws"
    shutil.copytree(Path(str(authoring.golden_root("golden"))), dst)
    return dst


DIST = "projects/ejemplo/distributions/envio-semanal.yaml"


def errors(root: Path) -> list[dict]:
    return [{"code": i.code, "message": i.message, "path": i.path}
            for i in validate.validate(root).issues if i.level == "error"]


def recipients(root: Path) -> dict:
    doc = yaml.safe_load((root / DIST).read_text())
    return doc["subscriptions"][0]["recipients"]


def write_recipients(root: Path, value: dict) -> None:
    path = root / DIST
    doc = yaml.safe_load(path.read_text())
    doc["subscriptions"][0]["recipients"] = value
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))


def test_lists_by_name_are_valid(tmp_path: Path) -> None:
    root = ws(tmp_path)
    write_recipients(root, {"roles": ["admin"], "lists": ["Gerencia comercial"]})
    found = errors(root)
    assert found == [], found


def test_lists_alone_are_valid(tmp_path: Path) -> None:
    root = ws(tmp_path)
    write_recipients(root, {"lists": ["Comerciales", "Gerencia"]})
    assert errors(root) == []


def test_an_address_in_lists_is_refused(tmp_path: Path) -> None:
    """The whole point: a project never carries an address."""
    root = ws(tmp_path)
    write_recipients(root, {"lists": ["ana@cliente.com"]})
    found = errors(root)
    assert found, "an address inside lists: must be refused"
    assert any("distribution" in (item["path"] or "") or "lists" in item["message"]
               for item in found), found


def test_an_address_inside_roles_is_refused(tmp_path: Path) -> None:
    root = ws(tmp_path)
    write_recipients(root, {"roles": ["ana@cliente.com"]})
    assert errors(root) != []


def test_an_empty_recipients_block_is_refused(tmp_path: Path) -> None:
    root = ws(tmp_path)
    write_recipients(root, {})
    assert errors(root) != []
