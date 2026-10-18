"""SC-001 live eval for feature 024: a mockup attached to the chat must reach the model *as an
image* and come back as a report proposal.

Run with:

    AI_LIVE_TESTS=1 AI_LIVE_API_KEY=... [AI_LIVE_BASE_URL=https://api.deepseek.com] \
    [AI_LIVE_MODEL=deepseek-chat] uv run pytest tests/live/test_brief_eval.py -s

WARNING: this contacts the live provider, costs tokens and may be slow. Never run it against real
customer data: the briefs below are generated in memory.

The briefs are *synthetic* (flat bands and bars): they prove the plumbing — the picture reaches the
model and the answer uses it — not the fidelity of a designer's mockup. Replace them with real
mockups (or screenshots of a de-identified dashboard) before quoting SC-001 to a customer.
"""
import os
import struct
import zlib
from dataclasses import dataclass

import pytest

from app.ai import ChatMessage, ImagePart, get_provider
from app.config import get_settings

pytestmark = pytest.mark.skipif(
    os.environ.get("AI_LIVE_TESTS") != "1",
    reason="contacts the live AI provider; set AI_LIVE_TESTS=1",
)

RUNS = 10
REQUIRED = 8
PROMPT = ("Mira el boceto adjunto y responde en una sola línea en español, con estas dos partes: "
          "«Leo:» lo que muestra el boceto, y «Reporte:» el título y la métrica del reporte que "
          "propondrías para que quede igual.")


def _png(width: int, height: int, rows: list[tuple[int, tuple[int, int, int]]]) -> bytes:
    """A minimal PNG: full-width bands of colour (no library, no dependency)."""
    raw = b"".join(b"\x00" + bytes(colour) * width for _, colour in rows for _ in range(height))
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _brief(kind: str) -> bytes:
    """A flat “mockup”: a title band, a chart area with 3-4 bars, and a footer band."""
    white, ink, bar = (255, 255, 255), (230, 230, 230), (60, 90, 160)
    if kind == "pie":
        rows = [(40, ink), (60, white), (60, bar), (20, white)]
    elif kind == "table":
        rows = [(30, ink), (12, bar)] * 5
    elif kind == "line":
        rows = [(20, white), (6, bar), (24, white), (6, bar), (20, white)]
    else:                                     # bars
        rows = [(35, ink), (25, white), (50, bar), (35, white)]
    return _png(160, sum(height for height, _ in rows), rows)


@dataclass(frozen=True)
class Brief:
    kind: str
    expect: tuple[str, ...]                   # case-insensitive keywords in the answer


BRIEFS = (Brief("bars", ("barra",)), Brief("bars", ("columna", "barra")),
          Brief("pie", ("circular", "torta", "pastel", "pie")),
          Brief("table", ("tabla",)), Brief("line", ("línea", "linea", "serie")),
          Brief("bars", ("barra", "mes")), Brief("table", ("tabla", "columna")),
          Brief("pie", ("distribución", "distribucion", "porcentaje")),
          Brief("line", ("tendencia", "línea", "linea")),
          Brief("bars", ("barra", "categoría", "categoria")))


@pytest.fixture
def live_provider(monkeypatch):
    if not os.environ.get("AI_LIVE_API_KEY"):
        pytest.skip("set AI_LIVE_API_KEY for the live eval")
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_BASE_URL", os.environ.get("AI_LIVE_BASE_URL", "https://api.deepseek.com"))
    monkeypatch.setenv("AI_MODEL", os.environ.get("AI_LIVE_MODEL", "deepseek-chat"))
    monkeypatch.setenv("AI_API_KEY", os.environ["AI_LIVE_API_KEY"])
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", "120")
    get_settings.cache_clear()
    yield get_provider(get_settings())
    get_settings.cache_clear()


def test_a_brief_reaches_the_model_and_comes_back_as_a_report(live_provider):
    """At least `REQUIRED` of the `RUNS` briefs are described and turned into a proposal."""
    results: list[tuple[str, bool, str]] = []
    for brief in BRIEFS[:RUNS]:
        image = ImagePart("image/png", _brief(brief.kind))
        reply = live_provider.chat(
            [ChatMessage("user", PROMPT, images=(image,))],
            system="Eres un asistente de BI. Responde solo con la línea pedida.", max_tokens=200)
        text = reply.text.strip().replace("\n", " ")
        lowered = text.lower()
        ok = "reporte:" in lowered and any(word in lowered for word in brief.expect)
        results.append((brief.kind, ok, text[:120]))

    for kind, ok, text in results:
        print(f"{'OK ' if ok else 'KO '} {kind:6} {text}")
    passed = sum(1 for _, ok, _ in results if ok)
    assert passed >= REQUIRED, f"{passed}/{len(results)} briefs described and turned into a report"
