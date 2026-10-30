"""Feature 044: an image set resolved on the server, so the browser never builds a file name."""
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.api import reports
from app.config import get_settings
from app.engine import report as engine
from app.models import AppUser
from app.projects import assets as asset_rules
from app.projects import fs
from app.projects import service as project_service
from app.reports import images as report_images
from app.reports import pdf


def _png() -> bytes:
    """A real 8x8 PNG: ReportLab reads it with PIL, so a hand-made header would fail."""
    import io

    from PIL import Image as Pillow

    buffer = io.BytesIO()
    Pillow.new("RGB", (8, 8), (200, 30, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


PNG = _png()
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>'

ACTOR = {"kind": "user", "user_id": None, "session_id": None, "command": "edit"}


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))
    return tmp_path / "projects"


@pytest.fixture
def project(db, superuser):
    p = project_service.create(db, db.get(AppUser, superuser.id), "Con logos")
    db.commit()
    actor = {**ACTOR, "user_id": superuser.id}
    fs.apply_asset(p.id, "assets/coins/BTC.png", PNG, actor)
    fs.apply_asset(p.id, "assets/coins/eth.svg", SVG, actor)
    return p


def ctx_for(project, *, images=None, report_id="cripto-panorama"):
    definition = {
        "title": "Panorama",
        "metrics": {"btc": {"label": "BTC", "format": "number"}},
        "dimensions": {"symbol": {"label": "Símbolo"}},
        "views": {},
        "layout": {"web": {"components": []}},
    }
    if images is not None:
        definition["images"] = images
    # The bits of engine.Context that definition_json reads, and no runner: these tests never
    # execute a query.
    return SimpleNamespace(
        report_id=report_id, definition=definition, direct=None, tables={}, columns={},
        integrations=[], version=SimpleNamespace(id=1, artifacts={
            "reports": {report_id: {"project": project.slug, "definition": definition}},
        }),
    )


def request(**headers) -> Request:
    raw = [(k.lower().replace("_", "-").encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": raw})


COINS = {"coins": {"folder": "assets/coins", "key": "symbol", "fallback": "initial"}}


def test_the_payload_carries_a_url_prefix_it_never_builds_a_file_name(project):
    ctx = ctx_for(project, images=COINS)
    assert report_images.payload(ctx, "/api/reports/x/assets") == {
        "coins": {"key": "symbol", "fallback": "initial", "url": "/api/reports/x/assets/coins/"},
    }
    # Without a base (a PDF or an email) the set stays declarative: no URL to a door it lacks.
    assert "url" not in report_images.payload(ctx)["coins"]


def test_a_set_without_images_declared_says_nothing(project):
    assert report_images.payload(ctx_for(project)) == {}


def test_the_key_resolves_in_any_case_and_in_any_extension(project):
    ctx = ctx_for(project, images=COINS)
    assert report_images.resolve(ctx, "coins", "BTC")[0] == PNG
    assert report_images.resolve(ctx, "coins", "btc")[0] == PNG
    # The SVG is sanitised on the way in, so it is not byte-identical to what was written.
    data, content_type, digest = report_images.resolve(ctx, "coins", "ETH")
    assert data.startswith(b"<svg") and content_type == "image/svg+xml" and len(digest) == 64


def test_a_missing_key_or_set_is_refused(project):
    ctx = ctx_for(project, images=COINS)
    with pytest.raises(asset_rules.AssetRefused) as exc:
        report_images.resolve(ctx, "coins", "HYPE")
    assert exc.value.reason == "key_not_found"
    with pytest.raises(asset_rules.AssetRefused) as exc:
        report_images.resolve(ctx, "nope", "BTC")
    assert exc.value.reason == "unknown_set"


def test_a_column_set_has_no_folder_to_read(project):
    ctx = ctx_for(project, images={"logos": {"column": "l.logo_url", "key": "symbol"}})
    with pytest.raises(asset_rules.AssetRefused) as exc:
        report_images.resolve(ctx, "logos", "BTC")
    assert exc.value.reason == "set_has_no_folder"
    # Nothing to fetch yet, so the client is told the key and the fallback and nothing else.
    assert report_images.payload(ctx, "/api/reports/x/assets") == {
        "logos": {"key": "symbol", "fallback": "initial", "column": "l.logo_url"},
    }


def test_the_definition_carries_the_sets_only_when_there_are_some(project):
    ctx = ctx_for(project, images=COINS)
    out = engine.definition_json(ctx, assets_base="/api/reports/r/assets")
    assert out["images"]["coins"]["url"] == "/api/reports/r/assets/coins/"
    assert "images" not in engine.definition_json(ctx_for(project))


def test_the_response_is_bytes_with_an_etag_and_a_year_of_cache(project):
    ctx = ctx_for(project, images=COINS)
    r = reports.asset_response(ctx, "/api/reports/r/assets", "coins", "btc", request())
    assert r.status_code == 200 and r.body == PNG
    assert r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert r.headers["x-content-type-options"] == "nosniff"

    again = reports.asset_response(ctx, "/api/reports/r/assets", "coins", "btc",
                                   request(if_none_match=r.headers["etag"]))
    assert again.status_code == 304 and again.body == b""


def test_a_key_that_is_not_there_is_a_404_the_client_turns_into_a_fallback(project):
    ctx = ctx_for(project, images=COINS)
    with pytest.raises(engine.ApiError) as exc:
        reports.asset_response(ctx, "/api/reports/r/assets", "coins", "HYPE", request())
    assert exc.value.status == 404

def _pdf_definition(blocks: list[dict]) -> dict:
    return {
        "title": "Panorama",
        "description": "Cripto",
        "currency": "USD",
        "metrics": {"btc": {"label": "BTC", "format": "number", "sql": "1"}},
        "dimensions": {"symbol": {"label": "Símbolo", "sql": "s"},
                       "name": {"label": "Nombre", "sql": "n"}},
        "images": COINS,
        "views": [{"id": "monedas", "type": "table",
                   "dimensions": ["symbol", "name"], "metrics": ["btc"]}],
        "layout": {"pdf": {"blocks": blocks}},
    }


def _pdf_payload(symbols: list[str]) -> dict:
    return {
        "selection": {"period": "mtd", "current": {"from": "2026-10-01", "to": "2026-10-31"},
                      "previous": None, "compare": "none", "partial": False, "grain": "day"},
        "filters": {},
        "freshness": {"updated_at": None, "data_version": "v1"},
        "views": [{"id": "monedas", "type": "table",
                   "columns": [{"id": "symbol", "label": "Símbolo", "kind": "dimension"},
                               {"id": "name", "label": "Nombre", "kind": "dimension"},
                               {"id": "btc", "label": "BTC", "kind": "metric"}],
                   "rows": [{"symbol": s, "name": s.title(), "btc": 100} for s in symbols]}],
    }


def _render_pdf(project, symbols: list[str], columns: list) -> bytes:
    ctx = ctx_for(project, images=COINS)
    definition = _pdf_definition([{"id": "fichas", "type": "asset", "view": "monedas",
                                   "columns": columns, "image": "coins"}])
    return pdf.render(definition, _pdf_payload(symbols), organization="Acme", product="Bizview",
                      viewer="Ana", locale="es", images=report_images.reader(ctx))


def test_the_pdf_embeds_the_project_file_the_key_names(project):
    content = _render_pdf(project, ["BTC"], ["symbol", "name", None, "btc"])
    assert b"/Subtype /Image" in content


def test_an_svg_or_missing_key_draws_the_initial_circle_instead(project):
    """ReportLab cannot embed SVG, and a key with no file has nothing to embed: both fall back."""
    for symbol in ("ETH", "HYPE"):
        content = _render_pdf(project, [symbol], ["symbol", "name", None, "btc"])
        assert b"/Subtype /Image" not in content, symbol
