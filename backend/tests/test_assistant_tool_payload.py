"""Tool payloads are JSON data (regression: an Auto apply died with `TypeError`).

`assistant_message.tool_payload` is a JSONB column and psycopg dumps it with a plain
`json.dumps`. A tool result holding a datetime (the applied version's `applied_at`) raised
`TypeError: Object of type datetime is not JSON serializable` at insert time, *after* the apply
had run, so every assistant-driven apply ended with "Ocurrió un error inesperado (TypeError)".
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.assistant import tools
from app.assistant.service import _json_safe
from app.i18n import use_locale


def _version() -> SimpleNamespace:
    """The attributes `workspace.service.version_json` reads from an applied version."""
    return SimpleNamespace(
        id=7,
        commit=None,
        checksum="abc123",
        applied_at=datetime(2026, 10, 24, 20, 39, 51, tzinfo=UTC),
        applied_by=1,
        lock={"workspace": {"slug": "acme"}},
        artifacts={"integrations": {"mercado-cripto": {}},
                   "reports": {"panorama-cripto": {}}, "distributions": {}},
        specs={},
        projects={"coinmarketcap": {"project_id": 14, "name": "CoinmarketCap",
                                    "origin": "app"}},
    )


def test_json_safe_encodes_product_types():
    payload = {
        "when": datetime(2026, 10, 24, 20, 39, 51, tzinfo=UTC),
        "day": date(2026, 10, 24),
        "amount": Decimal("10.50"),
        "id": UUID("6f1c4b76-8bd6-4b4f-9a52-0f0f04a2e0e7"),
        "items": [{"nested": datetime(2026, 1, 1)}],
        "plain": [1, True, None, "x"],
    }
    safe = _json_safe(payload)
    assert json.loads(json.dumps(safe)) == safe
    assert safe["when"] == "2026-10-24T20:39:51+00:00"
    assert safe["day"] == "2026-10-24"
    assert safe["items"][0]["nested"] == "2026-01-01T00:00:00"
    assert safe["plain"] == [1, True, None, "x"]


def test_json_safe_survives_circular_values():
    loop: dict = {}
    loop["self"] = loop
    assert isinstance(_json_safe(loop), dict)      # a lost payload never loses the turn


def test_apply_draft_payload_needs_json_safe(monkeypatch):
    """The `apply_draft` result is what used to break the JSONB insert."""
    use_locale("es")
    version = _version()
    monkeypatch.setattr("app.assistant.service.apply_draft", lambda *a, **k: (version, False))

    payload, summary = tools._apply_draft(
        None, SimpleNamespace(id=1), SimpleNamespace(id=23, auto_run=None), None, None
    )

    assert payload["id"] == 7 and payload["revalidated"] is False
    assert summary
    with pytest.raises(TypeError):                 # the old behaviour: the round died here
        json.dumps(payload)
    safe = _json_safe(payload)
    assert json.loads(json.dumps(safe)) == safe
    assert safe["applied_at"] == "2026-10-24T20:39:51+00:00"
