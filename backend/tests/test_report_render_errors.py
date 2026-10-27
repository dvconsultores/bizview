"""Feature 038: a report that cannot render names the piece that failed.

The production defect (2026-10-26, project `coinmarketcap`, version 22 just applied): the preview
links stayed on the page after the apply dropped the preview schemas, so pressing `panorama-cripto`
answered the generic «Ocurrió un error inesperado (referencia …)». The fixture is that project:
one integration with four datasets joined on `snapshot_at` and a report that uses all four.
"""
from datetime import UTC, datetime, timedelta

import pytest

from app.config import get_settings
from app.db import get_engine
from app.engine import datasets, render_errors
from app.engine import report as engine
from app.reports import pdf_layout
from tests.coinmarketcap_fixture import (
    create_project,
    crypto_origin_data,
    fixture_files,
    integration_definition,
    preview_schema,
    project_id,
    put_files,
    report_definition,
    run_preview,
    validate_project,
)
from tests.conftest import reauth, signed_in, sql
from tests.test_runner import pg_source as pg_source
from tests.test_vibe_reporting import run_worker_requests


@pytest.fixture(autouse=True)
def projects_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "projects_dir", str(tmp_path / "projects"))


@pytest.fixture
def crypto_origin(pg_source):
    with crypto_origin_data():
        yield


# --- The regression: panorama-cripto renders in every data condition ---------------------------

def _yesterday_query(extra: str = "") -> str:
    """A one-day window (yesterday) so the expected figures do not depend on today's date."""
    day = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
    return f"?period=custom&from={day}&to={day}{extra}"


def test_panorama_cripto_renders_from_preview_with_full_empty_and_no_compare_data(
        db, superuser, crypto_origin):
    c = reauth(signed_in("root@example.com"))
    slug = create_project(c)
    put_files(c, slug, fixture_files())
    assert validate_project(c, slug)["validation"]["valid"] is True
    run_preview(c, slug)

    data = c.get(f"/api/projects/{slug}/preview/report/panorama-cripto/data"
                 + _yesterday_query())
    assert data.status_code == 200, data.text
    body = data.json()
    assert [v["type"] for v in body["views"]] == ["kpis", "trend", "ranking", "table"]
    assert not [v for v in body["views"] if v.get("error")]
    kpis = body["views"][0]["items"]
    assert next(i for i in kpis if i["metric"] == "market_cap")["value"] == 1603
    assert next(i for i in kpis if i["metric"] == "altseason_index")["value"] == 31
    assert body["render_reference"]

    content = c.post(f"/api/projects/{slug}/preview/report/panorama-cripto/pdf"
                     + _yesterday_query())
    assert content.status_code == 200, content.text
    assert content.content.startswith(b"%PDF")

    # (b) one dataset with no rows at all: the tiles say «Sin datos», nothing fails.
    session_id = sql("SELECT preview FROM project WHERE id = :p", p=project_id(slug))[0][0]
    schema = preview_schema(session_id["session_id"])
    sql(f'DELETE FROM "{schema}".altcoin_season')
    empty = c.get(f"/api/projects/{slug}/preview/report/panorama-cripto/data"
                  + _yesterday_query())
    assert empty.status_code == 200, empty.text
    assert not [v for v in empty.json()["views"] if v.get("error")]
    altseason = next(i for i in empty.json()["views"][0]["items"]
                     if i["metric"] == "altseason_index")
    assert altseason["value"] is None
    assert c.post(f"/api/projects/{slug}/preview/report/panorama-cripto/pdf"
                  + _yesterday_query()).status_code == 200

    # (c) no comparison period: the same views without the previous series.
    plain = c.get(f"/api/projects/{slug}/preview/report/panorama-cripto/data"
                  + _yesterday_query("&compare=none"))
    assert plain.status_code == 200, plain.text
    assert plain.json()["selection"]["previous"] is None
    assert not [v for v in plain.json()["views"] if v.get("error")]


def test_applied_panorama_cripto_renders_json_and_pdf(db, superuser, crypto_origin):
    c = reauth(signed_in("root@example.com"))
    slug = create_project(c)
    put_files(c, slug, fixture_files())
    assert validate_project(c, slug)["validation"]["valid"] is True
    run_preview(c, slug)

    applied = c.post(f"/api/projects/{slug}/apply")
    assert applied.status_code == 200, applied.text
    run = reauth(c).post("/api/integrations/mercado-cripto/run", json={"kind": "full"})
    assert run.status_code == 202, run.text
    run_worker_requests()

    data = c.get("/api/reports/panorama-cripto/data?period=last_7_days&compare=none")
    assert data.status_code == 200, data.text
    assert not [v for v in data.json()["views"] if v.get("error")]
    content = c.post("/api/reports/panorama-cripto/pdf?period=last_7_days&compare=none")
    assert content.status_code == 200, content.text
    assert content.content.startswith(b"%PDF")


# --- Typed errors in the engine ----------------------------------------------------------------

def _datasets(rows: dict[str, list[tuple]] | None = None) -> None:
    """The four dataset tables of the fixture, loaded from `rows` (none → empty tables)."""
    rows = rows or {}
    definition = integration_definition()
    with get_engine().begin() as conn:
        pg = conn.connection.driver_connection
        for name, ds in definition["datasets"].items():
            datasets.ensure_table(pg, "mercado-cripto", name, ds)
    for name, values in rows.items():
        if not values:
            continue
        columns = list(integration_definition()["datasets"][name]["columns"])
        names = [*columns, "_run_id"]
        placeholders = ", ".join(f":{c}" for c in names)
        for value in values:
            sql(f'INSERT INTO "{datasets.schema_name("mercado-cripto")}".{name} '
                f'({", ".join(names)}) VALUES ({placeholders})',
                _run_id=0, **dict(zip(columns, value, strict=True)))


def _context(report: dict | None = None) -> engine.Context:
    definition = report or report_definition()
    version = engine.PreviewVersion(
        id=0,
        artifacts={"workspace": {"currency": "USD"},
                   "integrations": {"mercado-cripto": {"definition": integration_definition(),
                                                       "files": {}}},
                   "reports": {"panorama-cripto": {"definition": definition}}},
    )
    return engine.context(version, "panorama-cripto")


def _views(ctx: engine.Context, params: dict | None = None):
    today = datetime.now(UTC).date()
    sel, filters = engine.selection(ctx, params or {"period": "last_7_days",
                                                   "compare": "none"}, today)
    return engine.run_views(ctx, sel, filters, "UTC", reference="ref-038")


def _full_rows() -> dict[str, list[tuple]]:
    now = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
    rows: dict[str, list[tuple]] = {"assets": [], "global_metrics": [], "fear_greed": [],
                                    "altcoin_season": []}
    for days in (1, 2):
        when = now - timedelta(days=days)
        for symbol, cap in (("BTC", 1000), ("ETH", 500), ("SOL", 100)):
            rows["assets"].append((when, symbol, 1, cap, 10, 1))
        rows["global_metrics"].append((when, 2000, 50, 20, 100))
        rows["fear_greed"].append((when, 50, "Neutral"))
        rows["altcoin_season"].append((when, 30))
    return rows


@pytest.fixture
def loaded_datasets():
    _datasets(_full_rows())
    yield
    with get_engine().begin() as conn:
        datasets.drop_integration(conn.connection.driver_connection, "mercado-cripto")


def test_four_sets_joined_on_one_key_render(loaded_datasets):
    ctx = _context()
    views = _views(ctx)
    assert [v["type"] for v in views] == ["kpis", "trend", "ranking", "table"]
    assert not [v for v in views if v.get("error")]
    assert views[0]["items"][0]["value"] == 3200
    assert all(v.get("summary") for v in views)


def test_a_gone_dataset_names_itself_and_the_other_views_still_answer(loaded_datasets):
    with get_engine().begin() as conn:
        conn.exec_driver_sql(
            f'DROP TABLE "{datasets.schema_name("mercado-cripto")}".altcoin_season')
    views = _views(_context())
    assert len(views) == 4
    for view in views:
        assert view["error"]["code"] == render_errors.DATASET_MISSING
        assert "altcoin_season" in view["error"]["message"]
        assert view["error"]["reference"] == "ref-038"
        assert view["error"]["report"] == "panorama-cripto"


def test_a_metric_that_divides_by_zero_shows_its_card_and_the_row_still_renders(loaded_datasets):
    definition = report_definition()
    definition["metrics"]["dominance"]["sql"] = (
        "sum(assets.market_cap) / max(global_metrics.total_market_cap) * 100")
    definition["metrics"]["dominance"].pop("formula")
    sql(f'UPDATE "{datasets.schema_name("mercado-cripto")}".global_metrics '
        "SET total_market_cap = 0")
    views = _views(_context(definition))
    kpis = views[0]
    assert not kpis.get("error"), kpis
    failed = next(i for i in kpis["items"] if i["metric"] == "dominance")
    assert failed["error"]["code"] == render_errors.METRIC_ERROR
    assert failed["error"]["reason"] == "division_by_zero"
    assert failed["error"]["view"] == "resumen"
    # The other metrics of the same row are there.
    assert next(i for i in kpis["items"] if i["metric"] == "market_cap")["value"] == 3200


def test_a_format_outside_the_catalogue_names_the_metric(loaded_datasets):
    definition = report_definition()
    definition["metrics"]["volume"]["format"] = "moneda"
    views = _views(_context(definition))
    kpis = views[0]
    assert kpis["error"]["code"] == render_errors.FORMAT_UNKNOWN
    assert kpis["error"]["metric"] == "volume"
    assert kpis["error"]["format"] == "moneda"


def test_an_empty_period_says_which_datasets_have_no_rows():
    _datasets({})
    try:
        views = _views(_context())
        assert not [v for v in views if v.get("error")]
        assert all(v["empty"]["code"] == render_errors.EMPTY_DATASET for v in views)
        assert "mercado-cripto.altcoin_season" in views[0]["empty"]["datasets"]
    finally:
        with get_engine().begin() as conn:
            datasets.drop_integration(conn.connection.driver_connection, "mercado-cripto")


def test_the_join_builder_chains_two_three_and_four_sets():
    base = {"a": ("s", "ta"), "b": ("s", "tb"), "c": ("s", "tc"), "d": ("s", "td")}
    columns = {alias: {"k": {"type": "text"}} for alias in base}

    def context(joins, uses=("a", "b", "c", "d")):
        definition = {"date": "a.k", "uses": {u: f"i.{u}" for u in uses}, "joins": joins}
        version = engine.PreviewVersion(id=0, artifacts={})
        return engine.Context("r", definition, version,
                              {u: base[u] for u in uses},
                              {u: columns[u] for u in uses}, [])

    for count in (2, 3, 4):
        aliases = "abcd"[:count]
        joins = [{"left": f"{aliases[i]}.k", "right": f"{aliases[i + 1]}.k"}
                 for i in range(count - 1)]
        clause = engine.from_clause(context(joins, tuple(aliases))).as_string()
        assert clause.count("JOIN") == count - 1
        assert all(f' AS "{alias}"' in clause for alias in aliases)

    # Two sets without a join: the error names them instead of running a cartesian product.
    with pytest.raises(render_errors.RenderError) as caught:
        engine.from_clause(context([]))
    assert caught.value.code == render_errors.JOIN_FAILED
    assert "b, c, d" in str(caught.value.message)

    # A join whose key is not declared: a typed error naming the column, never a 500 at run time.
    with pytest.raises(render_errors.RenderError) as caught:
        engine.from_clause(context([{"left": "a.ghost", "right": "b.k"}], ("a", "b")))
    assert caught.value.code == render_errors.DATASET_MISSING
    assert caught.value.detail["column"] == "ghost"


def test_an_unknown_pdf_block_becomes_its_own_card():
    definition = {
        "id": "panorama-cripto", "title": "Panorama", "currency": "USD",
        "metrics": {}, "dimensions": {},
        "layout": {"pdf": {"blocks": [{"id": "raro", "type": "gauge"}]}},
    }
    payload = {"selection": {"current": {"from": "2026-10-01", "to": "2026-10-02"}},
               "views": [], "render_reference": "ref-038"}
    from app.reports.palette import resolve
    from app.reports.pdf import _styles

    story = pdf_layout.render_layout(definition=definition, payload=payload,
                                     styles=_styles(resolve(definition)), organization="Org",
                                     product="Biz", viewer=None, preview=False, locale="es")
    text = " ".join(getattr(flowable, "text", "") for flowable in story)
    assert render_errors.LAYOUT_COMPONENT_UNKNOWN in text
    assert "raro" in text
