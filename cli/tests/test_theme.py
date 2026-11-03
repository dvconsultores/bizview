"""Themes as data (feature 047): the contract, its refusals, and the derived runtime roles."""
import copy
import json
from pathlib import Path

import pytest

from bizview_cli import theme as themes
from bizview_cli.theme_preview import preview_svg

ROOT = Path(__file__).resolve().parents[2]
BUILTINS = ROOT / "frontend" / "src" / "theme" / "themes"


def _builtin(name: str = "impacto") -> dict:
    return json.loads((BUILTINS / f"{name}.json").read_text(encoding="utf-8"))


def _codes(data: dict) -> set[str]:
    return {problem.code for problem in themes.validate_theme(data)}


@pytest.mark.parametrize("name", ["impacto", "clasico", "elegante", "monocromo", "contraste",
                                  "daltonico"])
def test_every_builtin_is_a_valid_theme(name):
    """The product's own themes obey the contract a customer's file is held to."""
    assert themes.validate_theme(_builtin(name)) == []


def test_the_schema_and_the_builtins_describe_the_same_tokens():
    schema = json.loads((ROOT / "cli" / "bizview_cli" / "schemas" / "theme.schema.json")
                        .read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"id", "name", "name_en", "version", "light", "dark"}
    mode = schema["properties"]["light"]
    assert mode["additionalProperties"] is False
    assert set(mode["required"]) == {*themes.COLOUR_TOKENS, "series"}
    assert (mode["properties"]["series"]["minItems"],
            mode["properties"]["series"]["maxItems"]) == (3, 8)
    assert set(schema["properties"]["shape"]["properties"]) == set(themes.SHAPE_LISTS)
    # Feature 051: the chrome tokens are optional in both modes, and every one of them is a colour.
    assert {*themes.CHROME_TOKENS} <= set(mode["properties"])
    assert not {*themes.CHROME_TOKENS} & set(mode["required"])
    for name in themes.CHROME_TOKENS:
        assert mode["properties"][name]["pattern"] == "^#[0-9A-Fa-f]{6}$"
    assert set(schema["properties"]["app"]["properties"]) == {"light", "dark"}
    # the validator's own lists are the schema's enums: one contract, not two
    for key, allowed in themes.SHAPE_LISTS.items():
        assert tuple(schema["properties"]["shape"]["properties"][key]["enum"]) == allowed
    for key, value in themes.SHAPE_DEFAULTS.items():
        assert value in themes.SHAPE_LISTS[key]


@pytest.mark.parametrize("mutate,code,needle", [
    (lambda d: d.update(css="body { background: red }"), "unknown_key", "css"),
    (lambda d: d["dark"].pop("card"), "missing_key", "dark.card"),
    (lambda d: d["light"].update(primary="#0B5FF"), "bad_hex", "primary"),
    (lambda d: d["light"].update(series=["#0B63F6", "#00897B"]), "series_length", "series"),
    (lambda d: d["shape"].update(font="Inter"), "bad_enum", "font"),
    (lambda d: d.update(id="Acme Blue"), "bad_id", "id"),
])
def test_shape_refusals(mutate, code, needle):
    data = copy.deepcopy(_builtin())
    mutate(data)
    problems = themes.validate_theme(data)
    assert code in {p.code for p in problems}
    assert any(needle in p.path or needle in p.message for p in problems)


def test_every_missing_key_is_named_in_one_pass():
    data = copy.deepcopy(_builtin())
    del data["light"]["card"]
    del data["dark"]["muted"]
    missing = [p.path for p in themes.validate_theme(data) if p.code == "missing_key"]
    assert missing == ["light.card", "dark.muted"]


def test_a_theme_that_is_too_large_is_refused():
    data = _builtin()
    text = " " * (themes.MAX_BYTES + 1) + json.dumps(data)
    parsed, problems = themes.load_theme_text(text)
    assert parsed is None
    assert [p.code for p in problems] == ["too_large"]


def test_an_unparsable_file_is_a_problem_not_an_exception():
    parsed, problems = themes.load_theme_text("id: [unclosed")
    assert parsed is None
    assert [p.code for p in problems] == ["unparsable"]


def test_the_contrast_refusal_names_the_pair_and_the_measurement():
    data = copy.deepcopy(_builtin())
    data["light"]["text"] = "#EEEEEE"
    problem = next(p for p in themes.validate_theme(data) if p.code == "contrast")
    assert problem.path == "light.text"
    assert "light.text vs light.surface" in problem.message
    assert ":1" in problem.message and "4.5" in problem.message


def test_a_series_that_looks_like_its_neighbour_is_refused():
    data = copy.deepcopy(_builtin())
    data["light"]["series"][1] = data["light"]["series"][0]
    problem = next(p for p in themes.validate_theme(data) if p.code == "series_similar")
    assert "ΔE 0.0" in problem.message


def test_positive_and_negative_must_be_distinguishable():
    data = copy.deepcopy(_builtin())
    data["light"]["positive"] = "#166534"
    data["light"]["negative"] = "#15803D"
    assert "polarity_confusion" in _codes(data)


def test_the_sequential_ramp_is_checked_on_lightness_steps():
    data = _builtin("monocromo")
    data["light"]["series"][1] = data["light"]["series"][2]     # kills the step, keeps the list
    assert "series_similar" in _codes(data)


def test_derive_tokens_reproduces_the_roles_the_renderers_paint_with():
    theme = _builtin()
    light = themes.derive_tokens(theme, "light")
    assert light["kpi_text"] == theme["light"]["text"]
    assert light["kpi_delta_bg"] == {"positive": theme["light"]["delta_positive"],
                                     "negative": theme["light"]["delta_negative"]}
    assert light["series1"] == theme["light"]["series"][0]
    assert light["surface"] == theme["light"]["surface"]


def test_a_three_series_theme_fills_the_eight_roles_with_its_last_colour():
    data = copy.deepcopy(_builtin())
    for mode in ("light", "dark"):
        data[mode]["series"] = data[mode]["series"][:3]
    assert themes.validate_theme(data) == [] or {p.code for p in themes.validate_theme(data)} \
        <= {"series_similar", "contrast"}
    derived = themes.derive_tokens(data, "light")
    assert derived["series3"] == derived["series8"] == data["light"]["series"][2]


def test_theme_to_preset_keeps_the_030_shape():
    preset = themes.theme_to_preset(_builtin())
    assert preset["id"] == "impacto"
    assert preset["label_key"] == "palette.impacto"
    assert preset["strategy"] == "categorical"
    assert set(preset["light"]) >= {"primary", "series1", "series8", "kpi_text", "kpi_delta_bg"}


def test_the_preview_draws_both_modes_with_the_theme_colours():
    theme = _builtin()
    svg = preview_svg(theme)
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert theme["light"]["surface"] in svg and theme["dark"]["surface"] in svg
    assert theme["light"]["series"][0] in svg
    assert "light · text" in svg and "dark · text" in svg


def test_the_command_exits_zero_on_a_builtin_and_writes_the_preview(tmp_path):
    import json

    from bizview_cli.__main__ import main

    created = tmp_path / "theme.json"
    created.write_text(json.dumps(_builtin()), encoding="utf-8")
    assert main(["theme", "validate", str(created)]) == 0
    out = tmp_path / "preview.svg"
    assert main(["theme", "preview", str(created), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("<svg")


def test_the_command_exits_one_naming_every_problem(tmp_path, capsys):
    import json

    from bizview_cli.__main__ import main

    data = copy.deepcopy(_builtin())
    del data["dark"]["card"]
    data["light"]["primary"] = "blue"
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(data), encoding="utf-8")
    assert main(["theme", "validate", str(broken)]) == 1
    errors = capsys.readouterr().err
    assert "dark.card" in errors and "light.primary" in errors


def test_the_command_refuses_an_image_extension_instead_of_writing_svg_bytes_as_png(tmp_path):
    import json

    from bizview_cli.__main__ import main

    created = tmp_path / "theme.json"
    created.write_text(json.dumps(_builtin()), encoding="utf-8")
    out = tmp_path / "preview.png"
    assert main(["theme", "preview", str(created), "--out", str(out)]) == 2
    assert not out.exists()


def test_the_command_exits_two_when_the_file_cannot_be_read(tmp_path):
    from bizview_cli.__main__ import main

    assert main(["theme", "validate", str(tmp_path / "absent.yaml")]) == 2

# --- feature 051: the application's own chrome ------------------------------------------------

def test_a_theme_from_before_051_is_still_accepted():
    """The chrome tokens are additive: a file written against 047 keeps working untouched."""
    data = copy.deepcopy(_builtin("clasico"))
    data.pop("app", None)
    for mode in themes.MODES:
        for name in themes.CHROME_TOKENS:
            data[mode].pop(name, None)
    assert themes.validate_theme(data) == []


def test_the_chrome_tokens_are_accepted_and_checked():
    data = copy.deepcopy(_builtin("clasico"))
    data["light"].update(accent="#123456", chrome="#111111", chrome_text="#FFFFFF")
    assert themes.validate_theme(data) == []


@pytest.mark.parametrize("mutate,code,needle", [
    (lambda d: d["light"].update(chrome_text="#101010"), "contrast", "chrome_text"),
    (lambda d: d["light"].update(accent="#FEFEFE"), "contrast", "accent"),
    (lambda d: d["light"].update(canvas="#777777"), "contrast", "canvas"),
    (lambda d: d["light"].update(field="#000000"), "contrast", "field"),
])
def test_a_chrome_pair_that_cannot_be_read_is_refused(mutate, code, needle):
    data = copy.deepcopy(_builtin("clasico"))
    mutate(data)
    problems = themes.validate_theme(data)
    assert code in {p.code for p in problems}
    assert any(needle in p.path or needle in p.message for p in problems)


def test_the_app_block_may_only_pin_known_tokens():
    data = copy.deepcopy(_builtin("clasico"))
    data["app"]["light"]["mystery"] = "#123456"
    problems = themes.validate_theme(data)
    assert [(p.path, p.code) for p in problems] == [("app.light.mystery", "unknown_key")]


def test_the_app_block_is_held_to_the_pairs_it_declares():
    data = copy.deepcopy(_builtin("clasico"))
    data["app"]["dark"]["ink"] = data["app"]["dark"]["surface"]
    problems = themes.validate_theme(data)
    # Every declared pair the ink takes part in fails, and each is reported against the ink.
    assert {p.code for p in problems} == {"contrast"}
    assert {p.path for p in problems} == {"app.dark.ink"}


def test_clasico_pins_its_whole_chrome():
    """The appearance the installation has today is data, not a stylesheet default (FR-010)."""
    data = _builtin("clasico")
    for mode in themes.MODES:
        assert set(data["app"][mode]) >= set(themes.APP_TOKENS) - {"field-focus"}, mode
