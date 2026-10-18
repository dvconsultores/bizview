"""SC-005 of spec 019: existing dataset reports must produce identical API responses before and
after feature 019. Regenerate snapshot with UPDATE_SNAPSHOT_019=1."""

import json
import os
import re
from pathlib import Path

import pytest

from tests.conftest import sql  # noqa: F401
from tests.test_reports_params import _pdf_lines
from tests.test_runner import origin as origin
from tests.test_runner import pg_source as pg_source
from tests.test_vibe_reporting import SELECTION
from tests.test_vibe_reporting import applied as applied
from tests.test_vibe_reporting import workspace as workspace

SNAPSHOT_PATH = Path(__file__).parent / "fixtures" / "report_snapshot_019.json"
SELECTION_2 = "period=custom&from=2026-09-27&to=2026-09-27&compare=none&filter.product=P1"
VOLATILE_KEYS = {
    "data_version", "updated_at", "generated_at", "queried_at", "computed_at",
    "run_id", "last_run_at", "finished_at", "started_at",
}
TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?([+-]\d{2}:\d{2}|Z)?")
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\b")


def _normalize(obj, viewer_name):
    if isinstance(obj, dict):
        # Optional English texts (`*_en`) are feature 022 additions, not part of the 019 check.
        return {
            k: ("<volatile>" if k in VOLATILE_KEYS else _normalize(v, viewer_name))
            for k, v in obj.items() if not k.endswith("_en")
        }
    if isinstance(obj, list):
        return [_normalize(v, viewer_name) for v in obj]
    if isinstance(obj, str):
        s = TS_RE.sub("<ts>", obj)
        s = TIME_RE.sub("<time>", s)
        s = s.replace(viewer_name, "<viewer>")
        if s.startswith(("Generado", "Consultado", "Datos actualizados")):
            s = "<meta>"
        return s
    return obj


def test_feature_019_response_snapshot(applied):
    definition_resp = applied.get("/api/reports/ventas")
    data_resp_1 = applied.get(f"/api/reports/ventas/data?{SELECTION}")
    data_resp_2 = applied.get(f"/api/reports/ventas/data?{SELECTION_2}")
    version_resp = applied.get("/api/reports/ventas/version")
    filters_resp = applied.get(f"/api/reports/ventas/filters/product?{SELECTION}")
    pdf_resp = applied.post(f"/api/reports/ventas/pdf?{SELECTION}")

    for resp in (definition_resp, data_resp_1, data_resp_2, version_resp, filters_resp, pdf_resp):
        assert resp.status_code == 200, f"status {resp.status_code} for {resp.request.url}"

    pdf_lines = _pdf_lines(pdf_resp.content)

    payload = {
        "definition": definition_resp.json(),
        "data": {
            SELECTION: data_resp_1.json(),
            SELECTION_2: data_resp_2.json(),
        },
        "version_keys": sorted(version_resp.json().keys()),
        "filters": filters_resp.json(),
        "pdf_lines": pdf_lines,
    }

    viewer_name = applied.get("/api/me").json()["full_name"]
    normalized = _normalize(payload, viewer_name)

    if os.environ.get("UPDATE_SNAPSHOT_019") == "1":
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
            json.dump(normalized, f, indent=1, ensure_ascii=False, sort_keys=True)
            f.write("\n")
        return

    if not SNAPSHOT_PATH.exists():
        pytest.fail(
            "Snapshot missing. Generate it on pre-019 code with UPDATE_SNAPSHOT_019=1 "
            "then run the test again."
        )

    with open(SNAPSHOT_PATH, encoding="utf-8") as f:
        snapshot = json.load(f)

    assert normalized == snapshot
