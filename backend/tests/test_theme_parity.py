"""Feature 047 parity: one contract, three readers.

The CLI validates, the web app paints and the PDF renders the same five files. `themes.test.ts`
holds the TypeScript side to the schema, the accessibility rules and the derivation; this module
holds the Python side to the same files, byte for byte, and to the same 1:1 derivation, so a
change on one side that the other does not make fails here or there.
"""
import json
from pathlib import Path

import pytest
from bizview_cli import theme as contract

from app.reports import palette as palettes

ROOT = Path(__file__).resolve().parents[2]
TS_DIR = ROOT / "frontend" / "src" / "theme" / "themes"
SCHEMA = ROOT / "cli" / "bizview_cli" / "schemas" / "theme.schema.json"


def test_the_pdf_mirror_is_the_frontend_directory_byte_for_byte():
    assert sorted(path.name for path in TS_DIR.glob("*.json")) == \
        sorted(f"{preset}.json" for preset in palettes.PRESET_IDS)
    assert sorted(path.name for path in palettes.THEME_DIR.glob("*.json")) == \
        sorted(path.name for path in TS_DIR.glob("*.json"))
    for name in sorted(path.name for path in TS_DIR.glob("*.json")):
        assert (palettes.THEME_DIR / name).read_bytes() == (TS_DIR / name).read_bytes(), name


@pytest.mark.parametrize("preset", palettes.PRESET_IDS)
def test_every_shipped_theme_obeys_the_published_contract(preset):
    assert contract.validate_theme(palettes.load_theme(preset)) == []


def test_the_shipped_files_carry_exactly_the_tokens_the_schema_names():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    for preset in palettes.PRESET_IDS:
        data = palettes.load_theme(preset)
        assert set(schema["required"]) <= set(data) <= set(schema["properties"]), preset
        for mode in palettes.THEMES:
            assert set(data[mode]) == set(schema["properties"][mode]["required"]), (preset, mode)


@pytest.mark.parametrize("preset", palettes.PRESET_IDS)
def test_the_preset_the_pdf_uses_is_derived_from_the_theme(preset):
    assert palettes.load_preset(preset) == contract.theme_to_preset(palettes.load_theme(preset))


def test_every_runtime_role_is_the_token_of_the_same_name():
    """No arithmetic between the file and the pixels, in either theme."""
    for preset in palettes.PRESET_IDS:
        theme = palettes.load_theme(preset)
        preset_data = palettes.load_preset(preset)
        for mode in palettes.THEMES:
            tokens = theme[mode]
            derived = contract.derive_tokens(theme, mode)
            assert derived["kpi_text"] == tokens["text"]
            assert derived["kpi_delta_bg"]["positive"] == tokens["delta_positive"]
            assert derived["kpi_delta_bg"]["negative"] == tokens["delta_negative"]
            for role, value in derived.items():
                if role == "kpi_delta_bg":
                    continue
                assert preset_data[mode][role] == value, (preset, mode, role)
            for index, colour in enumerate(tokens["series"], start=1):
                assert preset_data[mode][f"series{index}"] == colour, (preset, mode, index)


def test_a_theme_with_fewer_series_repeats_the_last_one_in_the_eight_roles():
    theme = json.loads(json.dumps(palettes.load_theme("impacto")))
    for mode in palettes.THEMES:
        theme[mode]["series"] = theme[mode]["series"][:3]
    derived = contract.derive_tokens(theme, "light")
    assert derived["series3"] == derived["series8"] == theme["light"]["series"][2]
