"""Readiness gate: a personal column the integration spec names under **Datos personales** is
allowed (feature 017 records the confirmation there; feature 045 removed the conversation state
that used to carry it separately)."""
from types import SimpleNamespace

from app.projects import readiness

REQUEST = "method: GET\npath: v1/listings\nrecords: $.data\nfields: {name: $.name}\n"

INTEGRATION = """id: mercado
spec: specs/001-mercado
source: CoinMarketCap
datasets:
  listings:
    extract:
      request: requests/listings.yaml
    primary_key: [id]
    incremental: {mode: full}
    checks: [{type: row_count, min: 1}]
    columns:
      id: {type: integer}
      name: {type: text}
"""


def session(files: dict[str, str], checks: dict | None = None):
    return SimpleNamespace(
        draft={"files": files},
        validation={"valid": True, "composed_valid": True, "errors": [], "warnings": [],
                    "other_projects": {}, "workspace_errors": 0},
        query_checks=checks or {},
        working_state={},
    )


def integration_files(extra_dataset: str = "", spec_personal: str = "ninguno"):
    request_path = "integrations/mercado/requests/listings.yaml"
    files = {
        "integrations/mercado/integration.yaml": INTEGRATION + extra_dataset,
        request_path: REQUEST,
        "specs/001-mercado/spec.md": f"**Datos personales**: {spec_personal}\n",
    }
    return files, {request_path: {"ok": True, "sha256": readiness.file_sha(REQUEST)}}


def test_personal_column_named_in_the_spec_is_allowed():
    files, checks = integration_files(
        spec_personal="name (nombre de la moneda, dato público)")
    assert readiness.compute(session(files, checks)) == {"ready": True, "pending": []}


def test_personal_column_absent_from_the_spec_blocks_once():
    files, checks = integration_files(extra_dataset="""  season:
    primary_key: [id]
    incremental: {mode: full}
    checks: [{type: row_count, min: 1}]
    columns:
      id: {type: integer}
      name: {type: text}
""")
    result = readiness.compute(session(files, checks))
    assert result["ready"] is False
    personal = [p for p in result["pending"] if p["code"] == "personal_data"]
    assert len(personal) == 1
    assert "name" in personal[0]["message"]


def test_report_without_filters_is_pending():
    files = {
        "reports/ventas/report.yaml": (
            "source: l\n"
            "dimensions:\n  estado: {label: Estado, sql: l.estado}\n"
            "metrics:\n  total: {label: Total, sql: sum(l.total)}\n"
            "views:\n  - {type: kpis, id: resumen, metrics: [total]}\n"
            "filters: []\n"
            "pdf: {enabled: true}\n"
        ),
        "specs/001-ventas/spec.md": "# Ventas\n",
    }
    result = readiness.compute(session(files))
    assert result["ready"] is False
    assert [p["code"] for p in result["pending"]] == ["report_dimensions"]
    assert "filters" in result["pending"][0]["message"]
