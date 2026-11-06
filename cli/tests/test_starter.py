"""Feature 057: the starter pack renders into a project that validates, for every combination.

The pack is the product's front door. If a rendered zip does not validate, every author starts from
a tree that is already wrong and cannot tell their mistakes from ours; if the contents document does
not list a file, the author cannot know what to do with it.
"""
import re
import zipfile
from fnmatch import fnmatch
from pathlib import Path

import pytest

from bizview_cli import starter
from bizview_cli.validate import validate

COMBINATIONS = [(kind, lang, source)
                for kind in starter.KINDS
                for lang in starter.LANGS
                for source in (None, "Origen ERP")]

ROOT = Path(__file__).resolve().parents[2]
LISTS = {"es": "CONTENIDO.md", "en": "CONTENTS.md"}


def rendered(tmp_path: Path, *, kind: str, lang: str, source: str | None,
             name: str = "Ventas de prueba") -> dict[str, str]:
    return starter.render(name=name, lang=lang, kind=kind, source=source)


def workspace(tmp_path: Path, files: dict[str, str], slug: str = "ventas-de-prueba") -> Path:
    """The pack as a v2 workspace: `bizview.yaml` at the root, the project under `projects/`."""
    project = tmp_path / "projects" / slug
    for path, text in files.items():
        target = (tmp_path / path) if path == "bizview.yaml" else (project / path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("kind,lang,source", COMBINATIONS)
def test_every_combination_is_a_valid_project(tmp_path, kind, lang, source):
    result = validate(workspace(tmp_path, rendered(
        tmp_path, kind=kind, lang=lang, source=source)))
    assert result.ok, [str(i) for i in result.issues]
    assert (result.integrations or []) if kind == "integration" else True
    assert result.reports


def test_a_direct_report_carries_no_integration(tmp_path):
    files = rendered(tmp_path, kind="direct", lang="es", source=None)
    assert not any(path.startswith("integrations/") for path in files)
    assert any(path.startswith("reports/") for path in files)


def test_prompt_is_self_contained_and_short(tmp_path):
    for lang in starter.LANGS:
        files = rendered(tmp_path, kind="integration", lang=lang, source=None)
        prompt = files["PROMPT.md"]
        assert len(prompt.split()) < 1500, lang
        for needle in ("zip", "[X]", "CAST(strftime", "dimension", "metric", "series",
                       "Datos personales", "400", "2 000" if lang == "es" else "2 000"):
            assert needle in prompt, f"{lang}: {needle}"


def test_agent_files_carry_the_prompt(tmp_path):
    files = rendered(tmp_path, kind="integration", lang="es", source=None)
    assert files["CLAUDE.md"] == files["PROMPT.md"]
    assert files["AGENTS.md"] == files["PROMPT.md"]
    assert files["CLAUDE.en.md"] == files["PROMPT.en.md"]


def test_both_explanations_ship_in_every_zip(tmp_path):
    for lang in starter.LANGS:
        files = rendered(tmp_path, kind="integration", lang=lang, source=None)
        for name in ("CONTENIDO.md", "CONTENTS.md", "QUE-HACE-BIZVIEW.md", "WHAT-BIZVIEW-DOES.md"):
            assert name in files, f"{lang}: {name}"
        # The fixed pair is always in its own language, whatever the dialog chose.
        assert "Contenido del paquete" in files["CONTENIDO.md"]
        assert "What the pack contains" in files["CONTENTS.md"]


def documented_rows(text: str) -> list[str]:
    """Every path a table row names: a row may document two files in one cell."""
    rows: list[str] = []
    for line in text.splitlines():
        if not line.startswith("| `"):
            continue
        first = line.split("|")[1]
        rows.extend(re.findall(r"`([^`]+)`", first))
    return rows


def normalize(path: str, slug: str, source: str | None) -> str:
    out = path.replace(f"002-{slug}-reporte", "002-<slug>-reporte").replace(slug, "<slug>")
    out = out.replace("<slug>", "<id>") if out.startswith(("reports/", "integrations/")) else out
    if source:
        out = out.replace(starter.plain_slug(source), "<source>")
    return out


@pytest.mark.parametrize("kind,lang,source", COMBINATIONS)
def test_every_zip_file_is_documented(tmp_path, kind, lang, source):
    files = rendered(tmp_path, kind=kind, lang=lang, source=source)
    rows = documented_rows(files[LISTS[lang]])
    missing = []
    for path in files:
        short = normalize(path, "ventas-de-prueba", source or starter.SOURCE_PLACEHOLDER)
        if not any(fnmatch(short, pattern) for pattern in rows):
            missing.append(path)
    assert missing == [], f"{lang}: undocumented files {missing}"


def test_the_contents_list_documents_nothing_absent(tmp_path):
    """The other direction: a row for a file the zip does not carry is a lie too."""
    files = rendered(tmp_path, kind="integration", lang="es", source=None)
    rows = documented_rows(files["CONTENIDO.md"])
    absent = [row for row in rows
              if not any(fnmatch(normalize(path, "ventas-de-prueba", None), row) for path in files)]
    # `assets/**` and `bizview.lock` are optional by design: the author adds them.
    assert set(absent) <= {"assets/**", "bizview.lock", "sources/<source>/*",
                           "integrations/<id>/requests/*.yaml"}, absent


def test_the_zip_is_deterministic(tmp_path):
    first = rendered(tmp_path, kind="integration", lang="es", source=None)
    second = starter.render(name="Ventas de prueba", lang="es", kind="integration",
                            date="2026-01-01")
    third = starter.render(name="Ventas de prueba", lang="es", kind="integration",
                           date="2026-01-01")
    assert starter.zip_bytes(first) != starter.zip_bytes(second)   # the date is the only difference
    assert starter.zip_bytes(second) == starter.zip_bytes(third)


def test_the_committed_template_is_what_the_pack_renders():
    committed = ROOT / starter.TEMPLATE_NAME
    assert committed.is_file(), "run `make starter-template`"
    assert committed.read_bytes() == starter.zip_bytes(starter.render(template=True, lang="es"))


def test_the_template_keeps_its_placeholders(tmp_path):
    files = starter.render(template=True, lang="es")
    assert "<slug>" in files["project.yaml"]
    assert "<nombre>" in files["project.yaml"]
    assert "<slug>" in " ".join(files)      # the folder names keep the placeholder


def test_a_name_with_no_letters_still_yields_a_slug():
    assert starter.plain_slug("---") == "proyecto"
    assert starter.plain_slug("Ventas 2026") == "ventas-2026"
    assert starter.plain_slug("Añ o") == "an-o"


def test_the_pack_comes_from_the_repository(monkeypatch):
    monkeypatch.delenv("BIZVIEW_STARTER_PACK", raising=False)
    path = starter.pack_dir()
    assert (path / "files" / "common" / "project.yaml").is_file()
    assert (path / "es" / "PROMPT.md").is_file()


def test_a_missing_pack_says_so(monkeypatch, tmp_path):
    monkeypatch.setenv("BIZVIEW_STARTER_PACK", str(tmp_path))
    with pytest.raises(starter.PackError):
        starter.pack_dir()


def test_a_bad_selection_is_refused():
    with pytest.raises(starter.PackError):
        starter.render(name="Ventas", lang="fr")
    with pytest.raises(starter.PackError):
        starter.render(name="Ventas", kind="model")
    with pytest.raises(starter.PackError):
        starter.render(name="   ")


def test_init_project_writes_the_pack(tmp_path, monkeypatch):
    from bizview_cli.init import init_project

    monkeypatch.chdir(tmp_path)
    assert init_project("Ventas Caracas", lang="es") == 0
    base = tmp_path / "ventas-caracas"
    for rel in ("project.yaml", "bizview.yaml", "PROMPT.md", "CONTENIDO.md", "CONTENTS.md",
                "specs/001-ventas-caracas/spec.md", "reports/ventas-caracas/report.yaml",
                "integrations/ventas-caracas/integration.yaml"):
        assert (base / rel).is_file(), rel
    # The pack is the project; the validator expects a workspace, which is what `init workspace`
    # writes and what the README of the pack points at.
    workspace = tmp_path / "ws"
    target = workspace / "projects" / "ventas-caracas"
    target.parent.mkdir(parents=True)
    base.rename(target)
    (workspace / "bizview.yaml").write_text("name: acme\nproduct: bizview\n", encoding="utf-8")
    assert validate(workspace).ok


def test_init_project_refuses_a_used_folder(tmp_path, monkeypatch):
    from bizview_cli.init import init_project

    monkeypatch.chdir(tmp_path)
    assert init_project("Ventas") == 0
    assert init_project("Ventas") == 2


def test_zip_entries_have_no_directories_and_no_timestamps(tmp_path):
    files = rendered(tmp_path, kind="integration", lang="es", source=None)
    with zipfile.ZipFile(__import__("io").BytesIO(starter.zip_bytes(files))) as zf:
        assert all(not info.is_dir() for info in zf.infolist())
        assert {info.date_time for info in zf.infolist()} == {(1980, 1, 1, 0, 0, 0)}
