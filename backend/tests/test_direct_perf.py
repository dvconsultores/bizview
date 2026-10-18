"""SC-002 slow direct-report performance test (opt-in).

Run with BIZVIEW_SLOW_TESTS=1 and a DATABASE_URL_BI close to the backend. The cached
path still reads report_cache from the BI database, so a remote database with ~200 ms
round trips cannot meet the 200 ms p95 target.
"""

import math
import os
import time

import pytest
import yaml

from app.config import get_settings
from app.engine import direct, report
from tests.conftest import signed_in, sql
from tests.test_vibe_reporting import apply, lock
from tests.workspace_fixture import write

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("BIZVIEW_SLOW_TESTS") != "1",
        reason="opt-in: 1 M rows on DATABASE_URL_BI; set BIZVIEW_SLOW_TESTS=1",
    ),
]


@pytest.fixture
def perf_workspace(tmp_path, monkeypatch):
    phys = direct.physical_schema("public")
    sql(f'CREATE SCHEMA IF NOT EXISTS "{phys}"')
    sql(f'DROP TABLE IF EXISTS "{phys}".bi_ventas_perf')
    sql(
        f'CREATE TABLE "{phys}".bi_ventas_perf '
        "(fecha date, sucursal text, producto text, monto numeric, unidades integer)"
    )
    sql(
        f"""
        INSERT INTO "{phys}".bi_ventas_perf (fecha, sucursal, producto, monto, unidades)
        SELECT
            DATE '2025-01-01' + (g % 638),
            CASE (g / 20)::int % 8
                WHEN 0 THEN 'Centro' WHEN 1 THEN 'Este' WHEN 2 THEN 'Oeste' WHEN 3 THEN 'Norte'
                WHEN 4 THEN 'Sur' WHEN 5 THEN 'Plaza' WHEN 6 THEN 'Terminal' ELSE 'Aeropuerto'
            END,
            'Producto ' || (g % 20 + 1),
            (g % 997 + 1) * 1.25,
            g % 50 + 1
        FROM generate_series(0, 999999) AS g
        """
    )
    sql(f'CREATE INDEX ON "{phys}".bi_ventas_perf (fecha)')
    sql(f'ANALYZE "{phys}".bi_ventas_perf')

    root = tmp_path / "workspace"
    try:
        write(root, "bizview.yaml", "name: perf\ncurrency: USD\n")
        write(
            root,
            "specs/reports/001-ventas-perf/spec.md",
            "# Ventas perf\n\n**Spec type**: report\n\n**Status**: Implemented\n\n"
            "**Modo**: directo\n\n**Fuente**: bi\n\n**Tablas**: public.bi_ventas_perf\n\n"
            "**Mantenido por**: proceso ERP\n\n**Volumen esperado**: 1 M filas\n",
        )
        write(root, "specs/reports/001-ventas-perf/plan.md", "# Plan\n")
        write(root, "specs/reports/001-ventas-perf/tasks.md", "- [X] T001 hecho\n")

        report_dict = {
            "id": "ventas-perf",
            "spec": "specs/reports/001-ventas-perf",
            "title": "Ventas perf",
            "direct": {
                "source": "bi",
                "cache_seconds": 3600,
                "timeout_seconds": 15,
                "tables": {
                    "v": {
                        "table": "public.bi_ventas_perf",
                        "columns": {
                            "fecha": {"type": "date"},
                            "sucursal": {"type": "text"},
                            "producto": {"type": "text"},
                            "monto": {"type": "numeric"},
                            "unidades": {"type": "integer"},
                        },
                    }
                },
            },
            "date": "v.fecha",
            "metrics": {
                "total": {"label": "Total", "format": "number", "sql": "sum(v.monto)"},
                "unidades": {
                    "label": "Unidades",
                    "format": "integer",
                    "sql": "sum(v.unidades)",
                },
            },
            "dimensions": {
                "producto": {"label": "Producto", "sql": "v.producto"},
                "sucursal": {"label": "Sucursal", "sql": "v.sucursal"},
            },
            "periods": {"default": "mtd", "allowed": ["mtd", "custom"]},
            "compare": {"default": "none", "allowed": ["none", "previous_period"]},
            "views": [
                {"type": "kpis", "metrics": ["total", "unidades"]},
                {"type": "trend", "metric": "total", "grain": "day"},
                {"type": "ranking", "dimension": "producto", "metric": "total", "limit": 10},
                {
                    "type": "table",
                    "dimensions": ["sucursal", "producto"],
                    "metrics": ["total"],
                    "limit": 100,
                },
            ],
            "filters": ["producto"],
            "pdf": {"enabled": True},
        }
        write(
            root,
            "reports/ventas-perf/report.yaml",
            yaml.safe_dump(report_dict, sort_keys=False, allow_unicode=True),
        )

        lock(root)
        monkeypatch.setattr(get_settings(), "workspace_path", str(root))
        yield root
    finally:
        sql(f'DROP TABLE IF EXISTS "{phys}".bi_ventas_perf')


def test_direct_report_cold_within_timeout_and_cached_p95(perf_workspace, superuser, monkeypatch):
    monkeypatch.setattr(direct, "LOG_ASYNC", False)
    direct.clear_cache()
    direct._inflight.clear()
    monkeypatch.setattr(report, "_epoch", lambda: 1_700_000_000.0)

    client = signed_in("root@example.com")
    apply(client)

    params = {
        "period": "custom",
        "from": "2026-07-01",
        "to": "2026-09-30",
        "compare": "previous_period",
    }
    url = "/api/reports/ventas-perf/data"

    start = time.perf_counter()
    r = client.get(url, params=params)
    cold_elapsed = time.perf_counter() - start
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["freshness"]["mode"] == "direct"
    assert body["freshness"]["stale"] is False
    assert cold_elapsed < 15, f"cold {cold_elapsed:.3f}s >= 15s"

    latencies = []
    for _ in range(30):
        t0 = time.perf_counter()
        r = client.get(url, params=params)
        latencies.append(time.perf_counter() - t0)
        assert r.status_code == 200
    latencies.sort()
    p50 = latencies[math.ceil(0.50 * len(latencies)) - 1]
    p95 = latencies[math.ceil(0.95 * len(latencies)) - 1]
    assert p95 < 0.200, (
        f"cached p50={p50*1000:.1f}ms p95={p95*1000:.1f}ms (want p95 < 200ms)"
    )

    filtered = dict(params)
    filtered["filter.producto"] = "Producto 3"
    start = time.perf_counter()
    r = client.get(url, params=filtered)
    assert time.perf_counter() - start < 15
    assert r.status_code == 200
    assert r.json()["freshness"]["mode"] == "direct"
