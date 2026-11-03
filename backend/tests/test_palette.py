"""Feature 030 T033: the palette presets and how the PDF resolves them."""
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.reports import palette as palettes


@pytest.fixture
def db_row():
    """An uploaded theme in the library, with a live session: what the PDF reads it from."""
    from app.db import get_sessionmaker
    from app.services import themes as store

    themes_dir = Path(__file__).resolve().parents[2] / "frontend" / "src" / "theme" / "themes"
    tokens = json.loads((themes_dir / "impacto.json").read_text(encoding="utf-8"))
    tokens = {**tokens, "id": "acme-azul", "name": "Acme · azul", "name_en": "Acme · blue",
              "light": {**tokens["light"], "surface": "#101828", "primary": "#7DD3FC"},
              "dark": {**tokens["dark"], "surface": "#F8FAFC"}}
    session = get_sessionmaker()()
    try:
        row, _ = store.save(session, tokens, origin="upload")
        session.commit()
        session.expire_all()
        yield SimpleNamespace(session=session, id=row.id, tokens=tokens)
    finally:
        session.close()

ROLES = (
    "primary", "series1", "series2", "series3", "series4", "series5", "series6", "series7",
    "series8", "positive", "negative", "neutral", "grid", "surface", "kpi_text",
)


def _hex(color: Any) -> str:
    red, green, blue = (round(channel * 255) for channel in (color.red, color.green, color.blue))
    return f"#{red:02X}{green:02X}{blue:02X}"


def test_preset_ids_are_the_contract_order():
    assert palettes.PRESET_IDS == ("impacto", "clasico", "elegante", "monocromo", "contraste",
                                   "daltonico")
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


# --- Feature 047: the report names a theme, and a theme may live in the database ------------------


def test_the_report_names_a_theme_by_id_and_palette_is_the_deprecated_alias():
    assert palettes.declared_theme({"layout": {"theme": {"id": "acme-azul"}}}) == "acme-azul"
    assert palettes.declared_theme({"layout": {"theme": {"palette": "contraste"}}}) == "contraste"
    assert palettes.declared_theme({"layout": {"theme": {"id": "acme", "palette": "clasico"}}}) \
        == "acme"
    assert palettes.declared_theme({"layout": {"theme": {}}}) is None
    assert palettes.declared_theme({}) is None
    assert palettes.declared_theme(None) is None


def test_the_mode_defaults_to_auto():
    assert palettes.declared_mode({"layout": {"theme": {"mode": "dark"}}}) == "dark"
    assert palettes.declared_mode({"layout": {"theme": {"mode": "light"}}}) == "light"
    assert palettes.declared_mode({"layout": {"theme": {}}}) == "auto"
    assert palettes.declared_mode({"layout": {"theme": {"mode": "sepia"}}}) == "auto"
    assert palettes.declared_mode(None) == "auto"


def test_an_uploaded_theme_reaches_the_pdf_through_its_row(db_row):
    theme_id, tokens = db_row.id, db_row.tokens
    palette = palettes.resolve({"layout": {"theme": {"id": theme_id}}}, None, db_row.session)
    assert palette.preset == theme_id
    assert _hex(palette.surface) == tokens["light"]["surface"]
    assert _hex(palette.primary) == tokens["light"]["primary"]


def test_the_pdf_uses_the_light_variant_of_an_uploaded_theme(db_row):
    theme_id, tokens = db_row.id, db_row.tokens
    palette = palettes.resolve({"layout": {"theme": {"id": theme_id, "mode": "dark"}}},
                               None, db_row.session)
    assert _hex(palette.surface) == tokens["light"]["surface"]
    assert _hex(palette.surface) != tokens["dark"]["surface"]


def test_a_deleted_theme_falls_back_to_the_product_default(db_row):
    palette = palettes.resolve({"layout": {"theme": {"id": "borrado"}}}, None, db_row.session)
    assert palette.preset == "impacto"
    # And with no session at all: the PDF still renders.
    assert palettes.resolve({"layout": {"theme": {"id": "borrado"}}}).preset == "impacto"


def test_the_installation_choice_is_read_before_the_old_preset_column(db_row):
    from app.models import AppearanceSettings

    session = db_row.session
    session.merge(AppearanceSettings(id=1, palette_preset="clasico", theme_id=db_row.id))
    session.flush()
    assert palettes.installation_preset(session) == db_row.id
    row = session.get(AppearanceSettings, 1)
    row.theme_id = None
    session.flush()
    assert palettes.installation_preset(session) == "clasico"
