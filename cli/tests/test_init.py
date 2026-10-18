"""`bizview init`: v2 workspaces (no Spec Kit at the root) and the legacy tree (real Spec Kit,
skipped when it is not available)."""
import shutil
import subprocess

import pytest

from bizview_cli.init import init
from bizview_cli.validate import validate

needs_speckit = pytest.mark.skipif(not (shutil.which("specify") or shutil.which("uvx")),
                                   reason="Spec Kit not available")


@needs_speckit
def test_init_creates_a_valid_empty_workspace(tmp_path):
    ws = tmp_path / "acme-bizview"
    assert init(ws, "acme", git=False, layout="legacy") == 0
    for rel in ("bizview.yaml", "AGENTS.md", "CLAUDE.md", "README.md",
                ".github/copilot-instructions.md", ".specify/memory/constitution.md",
                ".bizview/schemas/report.schema.json", "specs/integrations", "specs/reports",
                "integrations", "reports"):
        assert (ws / rel).exists(), rel
    assert "name: acme" in (ws / "bizview.yaml").read_text()
    assert "No Spec, No Run" in (ws / ".specify/memory/constitution.md").read_text()
    specify = [shutil.which("specify")] if shutil.which("specify") else \
        ["uvx", "--from", "specify-cli", "specify"]
    resolved = subprocess.run([*specify, "preset", "resolve", "spec-template"], cwd=ws,
                              capture_output=True, text=True).stdout
    assert "bizview" in resolved
    extensions = subprocess.run([*specify, "extension", "list"], cwd=ws, capture_output=True,
                                text=True).stdout
    assert "bizview" in extensions.lower()
    result = validate(ws)
    assert result.ok and not result.integrations and not result.reports


def test_init_refuses_non_empty_folder(tmp_path):
    (tmp_path / "x").write_text("x")
    assert init(tmp_path, "acme", git=False) == 2
    assert init(tmp_path / "new", "Bad Name", git=False) == 2


def test_init_v2_without_speckit(tmp_path, monkeypatch):
    def no_speckit():
        raise AssertionError("Spec Kit must not run at the root of a v2 workspace")

    monkeypatch.setattr("bizview_cli.init._specify", no_speckit)
    ws = tmp_path / "acme"
    assert init(ws, "acme", git=False) == 0
    for rel in ("bizview.yaml", "AGENTS.md", "CLAUDE.md", "README.md",
                ".github/copilot-instructions.md", ".bizview/schemas/project.schema.json",
                "projects/.gitkeep"):
        assert (ws / rel).exists(), rel
    assert not (ws / "specs").exists()
    assert validate(ws).ok
