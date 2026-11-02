"""Feature 049: the two import allowances, and the classification every caller shares."""
import pytest

from bizview_cli import budgets, layout


def test_every_allowed_path_is_charged_to_exactly_one_budget():
    """The classification is the layout's, so a folder added there is counted everywhere."""
    assert layout.budget_of("project.yaml") == layout.ARTIFACTS
    assert layout.budget_of(".specify/memory/constitution.md") == layout.ARTIFACTS
    assert layout.budget_of("specs/001-ventas/spec.md") == layout.ARTIFACTS
    assert layout.budget_of("specs/001-ventas/checklists/calidad.md") == layout.ARTIFACTS
    assert layout.budget_of("integrations/carga/queries/ventas.sql") == layout.ARTIFACTS
    assert layout.budget_of("reports/ventas/report.yaml") == layout.ARTIFACTS
    assert layout.budget_of("themes/acme.yaml") == layout.ARTIFACTS
    assert layout.budget_of("distributions/correo.yaml") == layout.ARTIFACTS
    assert layout.budget_of("assets/BTC.png") == layout.ASSETS
    assert layout.budget_of("assets/coins/BTC.png") == layout.ASSETS


def test_a_path_no_pattern_owns_belongs_to_no_budget():
    for path in ("PROMPT.md", "REQUEST.md", "README.md", "request/logo.png",
                 "sources/ventas/structure.json", ".DS_Store", "__MACOSX/x.png",
                 ".bizview/preset/preset.yaml", "assets/coins/readme.txt"):
        assert layout.budget_of(path) is None, path


def test_images_do_not_spend_the_artifact_allowance():
    """The reported defect: 483 logos plus 40 artifacts were refused as '400 files'."""
    entries = [("project.yaml", 100, None)]
    entries += [(f"specs/{i:03d}-x/spec.md", 900, None) for i in range(1, 40)]
    entries += [(f"assets/coins/{i}.png", 3800, None) for i in range(483)]
    report = budgets.tally(entries)
    assert report.importable, report.refusal
    assert report["artifacts"].files == 40
    assert report["assets"].files == 483


def test_over_the_image_count_names_the_images():
    entries = [("project.yaml", 100, None)] + [(f"assets/{i}.png", 10, None) for i in range(2001)]
    refusal = budgets.tally(entries).refusal
    assert refusal.code == "assets_over_files"
    assert refusal.params["files"] == 2001
    assert refusal.params["max_files"] == 2000
    assert "assets/" in refusal.params["label"]


def test_over_the_image_total_names_the_images():
    # each image is legal on its own (300 KB); the whole set is not
    entries = [("project.yaml", 100, None)]
    entries += [(f"assets/{i}.png", 300 * 1024, None) for i in range(100)]
    refusal = budgets.tally(entries).refusal
    assert refusal.code == "assets_over_bytes"
    assert refusal.params["size_mb"] == 29       # 100 files of 300 KB, rounded to whole MB
    assert refusal.params["max_mb"] == 25


def test_over_the_artifact_count_names_the_artifacts():
    entries = [("project.yaml", 100, None)]
    entries += [(f"specs/{i:03d}-x/spec.md", 10, None) for i in range(400)]
    refusal = budgets.tally(entries).refusal
    assert refusal.code == "artifacts_over_files"
    assert refusal.params["files"] == 401
    assert "specs/" in refusal.params["label"]


def test_over_the_artifact_total_names_the_artifacts():
    # eleven 2 MB files: no file breaks the per-file rule, the set breaks the total
    entries = [(f"specs/{i:03d}-x/spec.md", 2048 * 1024, None) for i in range(11)]
    refusal = budgets.tally(entries).refusal
    assert refusal.code == "artifacts_over_bytes"
    assert refusal.params["size_mb"] == 22
    assert refusal.params["max_mb"] == 20
    assert "specs/" in refusal.params["label"]


def test_a_single_file_over_its_own_limit_names_the_file():
    over_artifact = [("specs/001-x/spec.md", 3 * 1024 * 1024, None)]
    refusal = budgets.tally(over_artifact).refusal
    assert refusal.code == "artifacts_file_too_large"
    assert refusal.params == {"path": "specs/001-x/spec.md", "max_kb": 2048}

    over_image = [("assets/BTC.png", 420 * 1024, None)]
    refusal = budgets.tally(over_image).refusal
    assert refusal.code == "assets_file_too_large"
    assert refusal.params == {"path": "assets/BTC.png", "max_kb": 300}


def test_when_both_allowances_are_over_the_author_hears_about_the_artifacts():
    entries = [("project.yaml", 100, None)]
    entries += [(f"specs/{i:03d}-x/spec.md", 10, None) for i in range(401)]
    entries += [(f"assets/{i}.png", 10, None) for i in range(2001)]
    assert budgets.tally(entries).refusal.code == "artifacts_over_files"


def test_disallowed_content_wins_over_every_count():
    entries = [("project.yaml", 100, None), ("assets/build.js", 10, None)]
    entries += [(f"assets/{i}.png", 10, None) for i in range(2001)]
    refusal = budgets.tally(entries).refusal
    assert refusal.code == "zip_disallowed"
    assert refusal.params == {"path": "assets/build.js"}


def test_a_program_hidden_behind_a_harmless_extension_is_refused_by_its_bytes():
    assert budgets.disallowed("notes.txt", b"\x7fELF\x02\x01")
    assert budgets.disallowed("run", b"#!/bin/sh\n")
    assert budgets.disallowed("setup.txt", b"MZ\x90\x00")
    assert not budgets.disallowed("notes.txt", b"just words")


def test_harmless_unknown_files_are_listed_not_refused():
    report = budgets.tally([("project.yaml", 10, None), ("PROMPT.md", 10, None),
                            ("request/foto.png", 10, b"\x89PNG"), (".DS_Store", 10, None)])
    assert report.importable
    assert report.ignored == [".DS_Store", "PROMPT.md", "request/foto.png"]


def test_the_counts_are_complete_even_when_something_is_refused():
    """An author told 'one image is too big' also wants to know how many there are."""
    entries = [("project.yaml", 10, None), ("assets/bin.js", 10, None)]
    entries += [(f"assets/{i}.png", 10, None) for i in range(7)]
    report = budgets.tally(entries)
    assert report.refusal is not None
    assert report["assets"].files == 7


def test_a_budget_over_a_stored_row_keeps_the_other_numbers():
    tight = budgets.as_budget(layout.ASSETS, {"max_files": 10, "max_kb": None, "max_mb": None})
    assert (tight.max_files, tight.max_kb, tight.max_mb) == (10, 300, 25)
    entries = [(f"assets/{i}.png", 10, None) for i in range(11)]
    assert budgets.tally(entries, {layout.ARTIFACTS: budgets.defaults()[layout.ARTIFACTS],
                                  layout.ASSETS: tight}).refusal.code == "assets_over_files"


@pytest.mark.parametrize("name", [layout.ARTIFACTS, layout.ASSETS])
def test_each_budget_publishes_its_own_label(name):
    assert budgets.defaults()[name].as_json()["label"] == budgets.LABELS[name]
