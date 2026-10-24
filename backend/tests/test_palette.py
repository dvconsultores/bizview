"""Feature 030 T033: the palette presets and how the PDF resolves them."""
from typing import Any

import pytest

from app.reports import palette as palettes

ROLES = (
    "primary", "series1", "series2", "series3", "series4", "series5", "series6", "series7",
    "series8", "positive", "negative", "neutral", "grid", "surface", "kpi_text",
)


def _hex(color: Any) -> str:
    red, green, blue = (round(channel * 255) for channel in (color.red, color.green, color.blue))
    return f"#{red:02X}{green:02X}{blue:02X}"


def test_preset_ids_are_the_contract_order():
    assert palettes.PRESET_IDS == ("impacto", "clasico", "monocromo", "contraste", "daltonico")
    assert palettes.DEFAULT_PRESET == "impacto"


def test_every_preset_loads_with_both_themes_complete():
    for preset_id in palettes.PRESET_IDS:
        data = palettes.load_preset(preset_id)
        assert data["id"] == preset_id
        assert data["label_key"] == f"palette.{preset_id}"
        assert data["strategy"] in ("categorical", "sequential")
        for theme in ("light", "dark"):
            missing = [role for role in ROLES if role not in data[theme]]
            assert not missing, f"{preset_id}/{theme} misses {missing}"
            assert set(data[theme]["kpi_delta_bg"]) == {"positive", "negative"}
            values = [data[theme][role] for role in ROLES]
            values += [data[theme]["kpi_delta_bg"]["positive"],
                       data[theme]["kpi_delta_bg"]["negative"]]
            for value in values:
                assert value == value.upper() and len(value) == 7, f"{preset_id}/{theme}: {value}"


def test_unknown_preset_raises_key_error():
    with pytest.raises(KeyError):
        palettes.load_preset("neon")
    assert palettes.is_preset("daltonico")
    assert not palettes.is_preset("neon")
    assert not palettes.is_preset(None)


def test_override_wins_over_the_installation():
    definition = {"layout": {"theme": {"palette": "contraste"}}}
    assert palettes.resolve(definition, "monocromo").preset == "contraste"


def test_installation_applies_when_the_report_declares_none():
    assert palettes.resolve({}, "daltonico").preset == "daltonico"
    assert palettes.resolve({"layout": {"pdf": {"blocks": []}}}, "clasico").preset == "clasico"
    assert palettes.resolve({"layout": {"theme": {}}}, "clasico").preset == "clasico"


def test_default_applies_last():
    assert palettes.resolve().preset == "impacto"
    assert palettes.resolve(None).preset == "impacto"
    assert palettes.resolve({}, None).preset == "impacto"


def test_unknown_ids_fall_back_to_the_default():
    # The declaration and the installation are both untrusted input to the renderer.
    assert palettes.resolve({"layout": {"theme": {"palette": "neon"}}}).preset == "impacto"
    assert palettes.resolve({}, "neon").preset == "impacto"
    assert palettes.resolve({"layout": {"theme": {"palette": "neon"}}}, "neon").preset == "impacto"


def test_resolution_always_returns_the_light_variant():
    for preset_id in palettes.PRESET_IDS:
        data = palettes.load_preset(preset_id)
        palette = palettes.resolve({"layout": {"theme": {"palette": preset_id}}})
        assert _hex(palette.primary) == data["light"]["primary"]
        assert _hex(palette.surface) == data["light"]["surface"]
        assert _hex(palette.kpi_text) == data["light"]["kpi_text"]
        assert tuple(_hex(c) for c in palette.series) == tuple(
            data["light"][f"series{i}"] for i in range(1, 9))
        assert _hex(palette.ink) == data["light"]["kpi_text"]
        assert _hex(palette.muted) == data["light"]["neutral"]
        assert _hex(palette.line) == data["light"]["grid"]
        assert _hex(palette.kpi_delta_bg_positive) == data["light"]["kpi_delta_bg"]["positive"]
        assert _hex(palette.kpi_delta_bg_negative) == data["light"]["kpi_delta_bg"]["negative"]


def test_role_resolves_declared_roles_and_falls_back_to_the_series_order():
    palette = palettes.resolve(None)
    assert palette.role("positive") is palette.positive
    assert palette.role("muted") is palette.muted
    assert palette.role("series3") is palette.series[2]
    assert palette.role(None, 2) is palette.series[2]
    assert palette.role("unknown", 8) is palette.series[0]
    assert palette.role("series9", 1) is palette.series[1]


def test_preset_ids_match_the_model_when_it_exists():
    models = pytest.importorskip("app.models")
    declared = getattr(models, "PALETTE_PRESET_IDS", None)
    if declared is None:
        pytest.skip("app.models.PALETTE_PRESET_IDS not landed yet")
    assert set(palettes.PRESET_IDS) == set(declared)
