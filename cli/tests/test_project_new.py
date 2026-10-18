"""`bizview project new` (feature 020 T074), without Spec Kit."""
from bizview_cli.__main__ import main
from bizview_cli.init import init
from bizview_cli.project import new_project, slug_for
from bizview_cli.validate import validate


def workspace(tmp_path):
    ws = tmp_path / "ws"
    assert init(ws, "acme", git=False) == 0
    return ws


def test_new_project_without_speckit(tmp_path):
    ws = workspace(tmp_path)
    assert new_project(ws, "Ventas Caracas", speckit_init=False) == 0
    base = ws / "projects/ventas-caracas"
    manifest = (base / "project.yaml").read_text()
    assert 'name: "Ventas Caracas"' in manifest
    assert "slug: ventas-caracas" in manifest
    constitution = (base / ".specify/memory/constitution.md").read_text()
    assert "Ventas Caracas" in constitution
    # Feature 021 T005: the installation rules block that commands must keep intact.
    assert "<!-- bizview:reglas-instalacion -->" in constitution
    assert "<!-- /bizview:reglas-instalacion -->" in constitution
    for folder in ("specs", "integrations", "reports", "distributions"):
        assert (base / folder).is_dir()
    result = validate(ws)
    assert result.ok, [str(i) for i in result.issues]
    assert result.layout == "v2"
    assert "ventas-caracas" in result.projects


def test_refusals(tmp_path):
    assert new_project(tmp_path, "X", speckit_init=False) == 2
    ws = workspace(tmp_path)
    assert new_project(ws, "Ventas", speckit_init=False) == 0
    assert new_project(ws, "Ventas", speckit_init=False) == 2
    assert new_project(ws, "Otro", slug="Bad Slug", speckit_init=False) == 2
    assert new_project(ws, "   ", speckit_init=False) == 2
    assert slug_for("Ñandú 2024!") == "nandu-2024"
    assert slug_for("2024 ventas") == "ventas"


def test_main_project_new(tmp_path, capsys):
    ws = workspace(tmp_path)
    assert main(["project", "new", "Ventas", "--path", str(ws), "--no-speckit"]) == 0
    assert (ws / "projects/ventas/project.yaml").exists()
    assert main(["validate", str(ws), "--write-lock"]) == 0
    assert "ventas" in capsys.readouterr().out
