"""Tests for multi-value report filters and the filter-options search (feature 012, task 002)."""
import re
from urllib.parse import quote

from app.ai import AIReply
from app.config import get_settings
from app.engine import narrative
from app.engine import report as engine
from app.reports import pdf
from tests.conftest import sql
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_vibe_reporting import SELECTION
from tests.test_vibe_reporting import applied as applied  # fixture
from tests.test_vibe_reporting import workspace as workspace  # fixture


def test_two_values_equal_the_sum_of_each(applied):
    r = applied.get(
        f"/api/reports/ventas/data?{SELECTION}&filter.product=P1&filter.product=P2")
    assert r.status_code == 200
    body = r.json()
    assert body["views"][0]["items"][0]["value"] == 11.75
    assert body["filters"] == {"product": ["P1", "P2"]}
    ranking = body["views"][2]["items"]
    keys = {row["key"] for row in ranking}
    assert {"P1", "P2"} <= keys


def test_single_value_link_still_works(applied):
    r = applied.get(f"/api/reports/ventas/data?{SELECTION}&filter.product=P1")
    assert r.status_code == 200
    body = r.json()
    assert body["views"][0]["items"][0]["value"] == 7.5
    assert body["filters"] == {"product": ["P1"]}

    r_dup = applied.get(
        f"/api/reports/ventas/data?{SELECTION}&filter.product=P1&filter.product=P1")
    assert r_dup.status_code == 200
    assert r_dup.headers["ETag"] == r.headers["ETag"]

    r_empty = applied.get(f"/api/reports/ventas/data?{SELECTION}&filter.product=")
    assert r_empty.status_code == 200
    body = r_empty.json()
    assert body["views"][0]["items"][0]["value"] == 11.75
    assert body["filters"] == {}


def test_unknown_filter_ignored(applied):
    r = applied.get(f"/api/reports/ventas/data?{SELECTION}&filter.nope=x")
    assert r.status_code == 200
    body = r.json()
    assert body["views"][0]["items"][0]["value"] == 11.75
    assert body["filters"] == {}


def test_too_many_values(applied):
    qs = "".join(f"&filter.product=P{i}" for i in range(51))
    r = applied.get(f"/api/reports/ventas/data?{SELECTION}{qs}")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "too_many_values"

    qs = "".join(f"&filter.product=P{i}" for i in range(50))
    r = applied.get(f"/api/reports/ventas/data?{SELECTION}{qs}")
    assert r.status_code == 200


def test_values_are_bound(applied):
    bad1 = "P1'; DROP TABLE dashboard;--"
    bad2 = 'x" OR 1=1'
    r = applied.get(f"/api/reports/ventas/data?{SELECTION}"
                    f"&filter.product={quote(bad1)}"
                    f"&filter.product={quote(bad2)}"
                    f"&filter.product=P2")
    assert r.status_code == 200
    body = r.json()
    assert body["views"][0]["items"][0]["value"] == 4.25
    assert body["filters"] == {"product": sorted([bad1, bad2, "P2"])}
    assert sql("SELECT count(*) FROM dashboard")[0][0] >= 1


def test_filter_search(applied, monkeypatch):
    base = f"/api/reports/ventas/filters/product?{SELECTION}"

    r = applied.get(f"{base}&q=p1")
    assert r.status_code == 200
    assert r.json() == {"items": ["P1"], "truncated": False}

    r = applied.get(f"{base}&q={quote('%')}")
    assert r.status_code == 200
    assert r.json() == {"items": [], "truncated": False}

    r = applied.get(f"{base}&q={quote('_')}")
    assert r.status_code == 200
    assert r.json() == {"items": [], "truncated": False}

    r = applied.get(f"{base}&q=P_")
    assert r.status_code == 200
    assert r.json() == {"items": [], "truncated": False}

    r = applied.get(f"{base}&q=")
    assert r.status_code == 200
    assert r.json() == {"items": ["P1", "P2"], "truncated": False}

    monkeypatch.setattr(engine, "FILTER_OPTIONS_LIMIT", 1)
    r = applied.get(f"{base}&q=")
    assert r.status_code == 200
    assert r.json() == {"items": ["P1"], "truncated": True}
    monkeypatch.undo()

    r = applied.get(f"{base}&q={quote('P1\'')}")
    assert r.status_code == 200
    assert r.json() == {"items": [], "truncated": False}


def test_pdf_honours_multi_values(applied):
    r = applied.post(f"/api/reports/ventas/pdf?{SELECTION}"
                     f"&filter.product=P1&filter.product=P2")
    assert r.status_code == 200
    text = r.content.decode("latin-1")
    assert "(11,75 USD)" in text
    assert "Producto: P1, P2" in text

    r = applied.post(f"/api/reports/ventas/pdf?{SELECTION}&filter.product=P2")
    assert r.status_code == 200
    text = r.content.decode("latin-1")
    assert "(4,25 USD)" in text
    assert "(11,75 USD)" not in text


def test_narrative_honours_multi_values(applied, monkeypatch):
    captured = {}

    class Fake:
        def complete(self, prompt, *, system=None, max_tokens=1024, effort=None):
            captured["prompt"], captured["system"] = prompt, system
            return AIReply("Las ventas subieron.", "fake")

    monkeypatch.setattr(get_settings(), "ai_provider", "anthropic")
    monkeypatch.setattr(get_settings(), "ai_api_key", "k")
    monkeypatch.setattr(narrative, "get_provider", lambda s: Fake())

    r = applied.get(f"/api/reports/ventas/narrative?{SELECTION}"
                    f"&filter.product=P1&filter.product=P2")
    assert r.status_code == 200
    prompt = captured["prompt"]
    assert "Ventas netas: 11.75" in prompt
    assert "Filtrado por: Producto (2 valores seleccionados)" in prompt
    assert "P1" not in prompt and "P2" not in prompt

    captured.clear()
    r = applied.get(f"/api/reports/ventas/narrative?{SELECTION}&filter.product=P2")
    assert r.status_code == 200
    assert "Ventas netas: 4.25" in captured["prompt"]


def test_cache_distinguishes_selections(applied):
    urls = {
        "none": f"/api/reports/ventas/data?{SELECTION}",
        "P1": f"/api/reports/ventas/data?{SELECTION}&filter.product=P1",
        "P2": f"/api/reports/ventas/data?{SELECTION}&filter.product=P2",
        "both": f"/api/reports/ventas/data?{SELECTION}&filter.product=P1&filter.product=P2",
        "both_rev": f"/api/reports/ventas/data?{SELECTION}&filter.product=P2&filter.product=P1",
    }
    etags = {name: applied.get(url).headers["ETag"] for name, url in urls.items()}
    assert len({etags["none"], etags["P1"], etags["P2"], etags["both"]}) == 4
    assert etags["both"] == etags["both_rev"]

    r = applied.get(urls["both_rev"])
    assert r.json()["views"][0]["items"][0]["value"] == 11.75

    r = applied.get(urls["both"], headers={"If-None-Match": etags["P1"]})
    assert r.status_code == 200
    assert r.headers["ETag"] == etags["both"]


def test_pdf_escapes_filter_values(applied):
    r = applied.post(f"/api/reports/ventas/pdf?{SELECTION}"
                     f"&filter.product=%3Cb&filter.product=a%26b")
    assert r.status_code == 200
    text = r.content.decode("latin-1")
    joined = "".join(re.findall(r"\((.*?)\) Tj", text))
    assert "Producto: <b, a&b" in joined


def _pdf_lines(content: bytes) -> list[str]:
    """Text of each visual line in an uncompressed ReportLab PDF, unescaped."""

    def unescaped(raw: bytes) -> str:
        return re.sub(
            rb"\\([0-7]{1,3}|.)",
            lambda m: bytes([int(m.group(1), 8)])
            if m.group(1)[:1] in b"01234567"
            else m.group(1),
            raw,
        ).decode("cp1252")

    out = []
    current = ""
    token = rb"\(((?:\\.|[^\\)])*)\) Tj|\bT\*|\bT[dDm]\b|\bET\b"
    for match in re.finditer(token, content):
        if match.group(0).endswith(b"Tj"):
            current += unescaped(match.group(1))
        else:
            if current:
                out.append(current)
                current = ""
    if current:
        out.append(current)
    return out


def test_pdf_meta_matches_context_block(applied):
    r = applied.post(f"/api/reports/ventas/pdf?{SELECTION}")
    assert r.status_code == 200
    lines = _pdf_lines(r.content)
    assert "Período: Personalizado (27 sep 2026 \u2013 28 sep 2026)" in lines
    assert "Comparado con: 25 sep 2026 \u2013 26 sep 2026" in lines
    full_name = applied.get("/api/me").json()["full_name"]
    assert f"Consultado por: {full_name}" in lines


def test_pdf_meta_without_comparison(applied):
    selection = SELECTION.replace("compare=previous_period", "compare=none")
    r = applied.post(f"/api/reports/ventas/pdf?{selection}")
    assert r.status_code == 200
    lines = _pdf_lines(r.content)
    assert "Comparado con: Sin comparación" in lines


def test_render_meta_matches_context_block_and_escapes_viewer():
    definition = {"title": "T", "dimensions": {}, "currency": "USD"}
    payload = {
        "selection": {
            "period": "mtd",
            "current": {"from": "2026-10-01", "to": "2026-10-02"},
            "previous": None,
            "partial": True,
        },
        "views": [],
        "filters": {},
    }
    content = pdf.render(
        definition,
        payload,
        organization="ACME",
        product="Customer A Reports",
        viewer="Ana <b>&",
    )
    lines = _pdf_lines(content)
    assert "Período: Mes en curso (01 oct 2026 \u2013 02 oct 2026, en curso)" in lines
    assert "Comparado con: Sin comparación" in lines
    assert "Consultado por: Ana <b>&" in lines
    assert not any(line.startswith("Consultado por: <b>") for line in lines)


def test_render_meta_omits_viewer_when_none():
    definition = {"title": "T", "dimensions": {}, "currency": "USD"}
    payload = {
        "selection": {
            "period": "mtd",
            "current": {"from": "2026-10-01", "to": "2026-10-02"},
            "previous": None,
            "partial": False,
        },
        "views": [],
        "filters": {},
    }
    content = pdf.render(
        definition,
        payload,
        organization="ACME",
        product="Customer A Reports",
    )
    lines = _pdf_lines(content)
    assert not any(line.startswith("Consultado por") for line in lines)
