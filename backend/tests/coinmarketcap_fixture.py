"""The `coinmarketcap` project of the production defect of 2026-10-26 (feature 038).

One integration with four datasets joined on `snapshot_at` and a report (`panorama-cripto`) that
uses all four, with a web layout and a PDF layout. Shared by the render-error tests and the
preview-after-apply tests; the origin rows live in the test schema, so the integration extracts
from the test database.
"""
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from app.assistant import preview
from app.db import get_engine
from app.engine import datasets
from tests.conftest import TEST_SCHEMA, sql

FIXTURE = Path(__file__).parent / "fixtures/projects/coinmarketcap"
ORIGIN_TABLES = ("origin_crypto_assets", "origin_crypto_global", "origin_crypto_fear_greed",
                 "origin_crypto_altseason")


def fixture_files() -> dict[str, str]:
    """The project as the API stores it, reading the origin through the test schema."""
    files = {}
    for path in sorted(FIXTURE.rglob("*")):
        if path.is_file() and path.name not in ("bizview.yaml", "project.yaml"):
            rel = path.relative_to(FIXTURE).as_posix()
            files[rel] = path.read_text(encoding="utf-8").replace("{schema}", TEST_SCHEMA)
    return files


def report_definition() -> dict:
    return yaml.safe_load(fixture_files()["reports/panorama-cripto/report.yaml"])


def integration_definition() -> dict:
    return yaml.safe_load(fixture_files()["integrations/mercado-cripto/integration.yaml"])


@contextmanager
def crypto_origin_data():
    """Four captures of the market: two in the current window, one a period earlier."""
    for table in ORIGIN_TABLES:
        sql(f"DROP TABLE IF EXISTS {table}")
    sql("CREATE TABLE origin_crypto_assets (snapshot_at timestamptz, symbol text, "
        "price numeric, market_cap numeric, volume_24h numeric, change_24h numeric)")
    sql("CREATE TABLE origin_crypto_global (snapshot_at timestamptz, total_market_cap numeric, "
        "btc_dominance numeric, eth_dominance numeric, volume_24h numeric)")
    sql("CREATE TABLE origin_crypto_fear_greed (snapshot_at timestamptz, value integer, "
        "classification text)")
    sql("CREATE TABLE origin_crypto_altseason (snapshot_at timestamptz, index integer)")
    snapshots = [datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
                 - timedelta(days=days) for days in (0, 1, 8)]
    for i, when in enumerate(snapshots):
        for symbol, cap in (("BTC", 1000 + i), ("ETH", 500 + i), ("SOL", 100 + i)):
            sql("INSERT INTO origin_crypto_assets VALUES (:t, :s, 1, :cap, 10, 1)",
                t=when, s=symbol, cap=cap)
        sql("INSERT INTO origin_crypto_global VALUES (:t, :total, 50, 20, 100)",
            t=when, total=2000 + i)
        sql("INSERT INTO origin_crypto_fear_greed VALUES (:t, :v, 'Neutral')", t=when, v=50 + i)
        sql("INSERT INTO origin_crypto_altseason VALUES (:t, :i)", t=when, i=30 + i)
    yield
    for table in ORIGIN_TABLES:
        sql(f"DROP TABLE IF EXISTS {table}")
    with get_engine().begin() as conn:
        datasets.drop_integration(conn.connection.driver_connection, "mercado-cripto")


def create_project(c, name: str = "CoinmarketCap") -> str:
    r = c.post("/api/projects", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["slug"]


def put_files(c, slug: str, files: dict[str, str]) -> None:
    for path, content in files.items():
        r = c.put(f"/api/projects/{slug}/file", json={"path": path, "content": content})
        assert r.status_code == 200, r.text


def project_id(slug: str) -> int:
    return sql("SELECT id FROM project WHERE slug = :s", s=slug)[0][0]


def validate_project(c, slug: str) -> dict:
    r = c.post(f"/api/projects/{slug}/validate")
    assert r.status_code == 200, r.text
    return r.json()


def run_preview(c, slug: str) -> None:
    r = c.post(f"/api/projects/{slug}/preview")
    assert r.status_code == 200, r.text
    request_id = sql("SELECT id FROM assistant_preview_request WHERE project_id = :p "
                     "ORDER BY id DESC", p=project_id(slug))[0][0]
    preview.process_request(request_id)
    state = sql("SELECT preview FROM project WHERE id = :p", p=project_id(slug))[0][0]
    assert state["status"] == "succeeded", state


def preview_schema(session_id: int) -> str:
    with datasets.preview_schemas(datasets.preview_prefix(session_id)):
        return datasets.schema_name("mercado-cripto")
