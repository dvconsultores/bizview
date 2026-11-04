"""Feature 052 (converged) / US2: one button generates the pack — scan, AI, verify.

The provider is a stand-in for `app.ai.get_provider` (the pattern `test_ai.py` already uses), and
the source is never dialled: `samples.get_json` answers with recorded CoinMarketCap payloads, so the
test exercises the real scan (`formats_of`, `enums_of`, chunking) without a network.

What is asserted, in the order the owner cares about: the pack is valid and complete, the payload
carries no row value, what the model invents never reaches the pack, and a failed run loses nothing.
"""
import json

import pytest
from bizview_cli.structure import enriched_markdown, validate_enriched

from app.ai import AIError, AIReply
from app.sources import describe as describer
from app.sources import structure_ai, structure_scan
from tests.conftest import client, reauth, signed_in, sql

HOST = "api.coinmarketcap.test"
PASSWORD = "cmc-secret-key-9931"
ROW_VALUE = "ACME-SECRET-CUSTOMER-9931"

REST = {"name": "coinmarketcap", "kind": "rest",
        "settings": {"base_url": f"https://{HOST}", "auth": "none", "test_path": "/v1/listings"},
        "secrets": {}}

LISTINGS = {
    "status": {"timestamp": "2026-11-03T00:00:00.000Z", "credit_count": 2},
    "data": [
        {"id": 1, "name": "Bitcoin", "symbol": "BTC", "category": "coin",
         "tags": ["store-of-value"], "last_updated": "2026-11-03T00:00:00.000Z",
         "quote": {"USD": {"price": 68000.12, "percent_change_90d": 12.5}}},
        {"id": 1027, "name": ROW_VALUE, "symbol": "ETH", "category": "coin",
         "tags": ["smart-contracts"], "last_updated": "2026-11-03T00:00:00.000Z",
         "quote": {"USD": {"price": 3400.5, "percent_change_90d": -3.1}}},
    ],
}

ANSWER = {
    "tables": [
        {"id": "v1/listings", "path": "v1/listings", "records": "$.data",
         "params": {}, "pagination": {"type": "none"},
         "row_is": "una moneda del top N en la última toma",
         "key": ["id"], "date_field": "last_updated", "personal": [],
         "fields": [
             {"name": "id", "path": "$.id", "type": "integer", "semantic": "identifier"},
             {"name": "category", "path": "$.category", "type": "text", "semantic": "category"},
             {"name": "last_updated", "path": "$.last_updated", "type": "timestamptz",
              "semantic": "timestamp", "units": "iso8601"},
             {"name": "price_usd", "path": "$.quote.USD.price", "type": "numeric",
              "semantic": "amount", "unit": "USD"},
         ],
         "notes": ["sin open interest en este plan"]},
    ],
    "relations": [],
    "suggested_metrics": [
        {"id": "altcoin_season_index", "from": "v1/listings",
         "formula_words": "porcentaje del top 100 sin stablecoins que supera a BTC"}],
    "dropped": [],
}


class FakeProvider:
    """Answers with the scripted documents, in order, and records what it was sent."""

    name, model = "openai_compatible", "fake-model"

    def __init__(self, answers, tokens=(800, 120)):
        self.answers = list(answers)
        self.tokens = tokens
        self.calls: list[dict] = []

    def complete(self, prompt, *, system=None, max_tokens=1024, effort=None):
        self.calls.append({"prompt": prompt, "system": system, "max_tokens": max_tokens})
        if not self.answers:
            raise AssertionError("the provider was called more times than scripted")
        answer = self.answers.pop(0)
        if isinstance(answer, AIError):
            raise answer
        text = answer if isinstance(answer, str) else json.dumps(answer)
        return AIReply(text=text, model=self.model, tokens_in=self.tokens[0],
                       tokens_out=self.tokens[1])


@pytest.fixture
def su(superuser):
    return reauth(signed_in("root@example.com"))


@pytest.fixture
def ai_on(monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "ai_provider", "openai_compatible")
    monkeypatch.setattr(settings, "ai_model", "fake-model")
    monkeypatch.setattr(settings, "ai_base_url", "http://ai.test/v1")
    monkeypatch.setattr(settings, "ai_structure_tokens", 150_000)
    return settings


@pytest.fixture
def recorded(monkeypatch):
    """Every GET the scan makes, answered from the recorded responses (no network, ever)."""
    pages = {"v1/listings": LISTINGS, "v1/global": {"data": {"total_market_cap": 1.5}},
             "": {"ok": True}}
    seen: list[str] = []

    def fake_get_json(settings, secrets, app, path, params=None, timeout=20):
        seen.append(path)
        if path in pages:
            return 200, pages[path]
        from app.engine.extract import ExtractError
        from app.i18n import t

        raise ExtractError(t("sources.http_status", status=404))

    from app.sources import samples as sample_service

    monkeypatch.setattr(sample_service, "get_json", fake_get_json)
    # The tab's scan and `?mode=scan` go through the describe; answer it from the same recording.
    monkeypatch.setattr(describer, "describe", lambda kind, settings, secrets, app, path=None,
                        write_probe=False, date_ranges=False: {
                            "kind": "rest", "path": "/v1/listings",
                            "shape": describer.shape(LISTINGS)})
    return seen


@pytest.fixture
def provider(monkeypatch):
    fake = FakeProvider([ANSWER])
    monkeypatch.setattr(structure_ai, "get_provider", lambda settings: fake)
    return fake


@pytest.fixture
def source(su, recorded):
    created = su.post("/api/sources", json=REST)
    assert created.status_code == 201, created.text
    return created.json()


def generate(su):
    return su.post("/api/sources/coinmarketcap/structure/generate")


# --- the happy path -----------------------------------------------------------------------

def test_generate_scans_enriches_verifies_and_saves(su, ai_on, provider, source):
    r = generate(su)
    assert r.status_code == 200, r.text
    pack = r.json()["pack"]
    assert validate_enriched(pack) == []
    assert pack["generator"]["mode"] == "ai" and pack["generator"]["model"] == "fake-model"
    assert pack["generator"]["tokens"] == 920
    table = next(t for t in pack["tables"] if t["id"] == "v1/listings")
    assert table["row_is"].startswith("una moneda")
    assert [f["name"] for f in table["fields"]] == ["id", "category", "last_updated", "price_usd"]
    # the enum the scan measured travels as a format, not as a row
    assert r.text.find("BTC") >= 0                     # the symbol repeats: it is an enum
    assert pack["suggested_metrics"][0]["id"] == "altcoin_season_index"
    stored = sql("SELECT structure_pack FROM data_source")[0][0]
    assert isinstance(stored, dict) and stored["tables"]
    kinds = [k for (k,) in sql("SELECT kind FROM audit_event WHERE kind = "
                               "'source_structure_generated'")]
    assert kinds == ["source_structure_generated"]


def test_the_download_serves_the_generated_pack(su, ai_on, provider, source):
    made = generate(su)
    assert made.status_code == 200, made.text
    as_json = su.get("/api/sources/coinmarketcap/structure?format=json")
    as_md = su.get("/api/sources/coinmarketcap/structure?format=md")
    assert as_json.status_code == 200 and as_md.status_code == 200
    doc = as_json.json()
    assert validate_enriched(doc) == []
    assert enriched_markdown(doc) == as_md.text
    assert "## Relaciones" in as_md.text or "## Métricas sugeridas" in as_md.text
    assert "Fuente «coinmarketcap»" in as_md.text


def test_the_tab_reads_the_pack_and_the_live_scan(su, ai_on, provider, source):
    before = su.get("/api/sources/coinmarketcap/structure/pack").json()
    assert before["generated"] is None and before["scan"]["structure"]["kind"] == "rest"
    assert before["ai"] == {"enabled": True, "model": "fake-model", "ceiling": 150_000}
    generate(su)
    after = su.get("/api/sources/coinmarketcap/structure/pack").json()
    assert after["generated"]["generator"]["mode"] == "ai"
    assert after["scan"]["structure"]["kind"] == "rest"


def test_mode_scan_still_downloads_the_plain_scan(su, ai_on, provider, source):
    generate(su)
    scan = su.get("/api/sources/coinmarketcap/structure?format=json&mode=scan").json()
    assert "pack" in scan and scan["pack"]["kind"] == "rest"


# --- what reaches the provider -------------------------------------------------------------

def test_payload_is_the_scan_and_never_a_value_host_or_credential(su, ai_on, provider, source):
    generate(su)
    sent = json.dumps(provider.calls, ensure_ascii=False)
    assert "v1/listings" in sent and "$.quote.USD.price" in sent
    for secret in (ROW_VALUE, HOST, PASSWORD, "cmc-secret"):
        assert secret not in sent


def test_the_prompt_is_data_and_names_the_rules(provider):
    text = structure_ai.prompt()
    assert "structure.schema.json" in text
    assert "Solo nombres que están en el escaneo" in text
    assert "Nada de valores" in text


# --- verification drops what the source does not have -------------------------------------

def test_invented_objects_are_dropped_and_listed(su, ai_on, monkeypatch, source):
    invented = json.loads(json.dumps(ANSWER))
    invented["tables"].append({"id": "ventas_fantasma", "row_is": "una venta",
                               "fields": [{"name": "total", "type": "numeric"}]})
    invented["tables"][0]["fields"].append({"name": "paid_at", "path": "$.paid_at",
                                            "type": "timestamp"})
    invented["relations"] = [{"from": "v1/listings.id", "to": "ventas_fantasma.total",
                              "kind": "one_to_many"}]
    invented["suggested_metrics"].append({"id": "margen", "from": "ventas_fantasma",
                                          "formula_words": "precio menos costo"})
    monkeypatch.setattr(structure_ai, "get_provider", lambda s: FakeProvider([invented]))
    r = generate(su)
    assert r.status_code == 200, r.text
    pack = r.json()["pack"]
    assert [t["id"] for t in pack["tables"]] == ["v1/listings"]
    assert "paid_at" not in [f["name"] for f in pack["tables"][0]["fields"]]
    assert pack["relations"] == []
    assert [m["id"] for m in pack["suggested_metrics"]] == ["altcoin_season_index"]
    dropped = " ".join(pack["dropped"])
    assert "ventas_fantasma" in dropped
    assert "paid_at" in dropped
    assert "margen" in dropped


def test_a_rest_field_must_have_a_path_the_shape_proves(su, ai_on, monkeypatch, source):
    wrong = json.loads(json.dumps(ANSWER))
    wrong["tables"][0]["fields"] = [{"name": "inventado", "path": "$.no.existe",
                                     "type": "text"}]
    monkeypatch.setattr(structure_ai, "get_provider", lambda s: FakeProvider([wrong]))
    r = generate(su)
    # every field was dropped, so the table had nothing left: the run refuses to save an empty pack
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "ai_provider_error"
    assert sql("SELECT structure_pack FROM data_source")[0][0] == {}


# --- the repair round and the failure path -------------------------------------------------

def test_one_repair_round_recovers_a_malformed_answer(su, ai_on, monkeypatch, source):
    fake = FakeProvider(["esto no es JSON", ANSWER])
    monkeypatch.setattr(structure_ai, "get_provider", lambda s: fake)
    r = generate(su)
    assert r.status_code == 200, r.text
    assert len(fake.calls) == 2
    assert "no se pudo usar" in fake.calls[1]["prompt"]


def test_two_malformed_answers_fail_without_losing_the_previous_pack(su, ai_on, monkeypatch,
                                                                   source):
    monkeypatch.setattr(structure_ai, "get_provider", lambda s: FakeProvider([ANSWER]))
    assert generate(su).status_code == 200
    good = sql("SELECT structure_pack FROM data_source")[0][0]
    monkeypatch.setattr(structure_ai, "get_provider",
                        lambda s: FakeProvider(["nada", "tampoco"]))
    r = generate(su)
    assert r.status_code == 502 and r.json()["error"]["code"].startswith("ai_")
    assert sql("SELECT structure_pack FROM data_source")[0][0] == good


def test_a_previous_pack_is_kept_for_the_diff(su, ai_on, monkeypatch, source):
    monkeypatch.setattr(structure_ai, "get_provider", lambda s: FakeProvider([ANSWER]))
    assert generate(su).status_code == 200
    second = json.loads(json.dumps(ANSWER))
    second["tables"][0]["fields"].append({"name": "symbol", "path": "$.symbol", "type": "text"})
    monkeypatch.setattr(structure_ai, "get_provider", lambda s: FakeProvider([second]))
    r = generate(su)
    assert r.status_code == 200
    assert r.json()["previous"]["tables"][0]["id"] == "v1/listings"
    assert len(r.json()["previous"]["tables"][0]["fields"]) == 4
    assert len(r.json()["pack"]["tables"][0]["fields"]) == 5


def test_provider_errors_keep_the_035_vocabulary(su, ai_on, monkeypatch, source):
    monkeypatch.setattr(structure_ai, "get_provider",
                        lambda s: FakeProvider([AIError("no_credit", "sin saldo")]))
    r = generate(su)
    assert r.status_code == 502 and r.json()["error"]["code"] == "ai_no_credit"
    assert r.json()["error"]["ai"]["action"] == "admin_ai"


# --- the guards ---------------------------------------------------------------------------

def test_ai_off_is_a_typed_error(superuser, source):
    authed = reauth(signed_in("root@example.com"))
    r = authed.post("/api/sources/coinmarketcap/structure/generate")
    assert r.status_code == 409 and r.json()["error"]["code"] == "ai_not_configured"
    assert authed.get("/api/sources/coinmarketcap/structure/pack").status_code == 200


def test_soap_has_no_generation(su, ai_on, provider, recorded):
    created = su.post("/api/sources", json={
        "name": "erp-soap", "kind": "soap",
        "settings": {"wsdl_url": "https://203.0.113.9/x?wsdl", "auth": "none"},
        "secrets": {}})
    assert created.status_code == 201, created.text
    r = su.post("/api/sources/erp-soap/structure/generate")
    assert r.status_code == 422 and r.json()["error"]["fields"] == {"kind": "unsupported"}


def test_the_token_ceiling_stops_chunking(su, ai_on, monkeypatch, source):
    # two endpoints, so the run has two chunks; the first one already spends past the ceiling
    su.post("/api/sources/coinmarketcap/samples", json={"name": "global",
                                                        "path": "v1/global"})
    monkeypatch.setattr(ai_on, "ai_structure_tokens", 500)
    fake = FakeProvider([ANSWER], tokens=(800, 300))
    monkeypatch.setattr(structure_ai, "get_provider", lambda s: fake)
    r = generate(su)
    assert r.status_code == 200, r.text
    incomplete = r.json()["pack"]["generator"].get("incomplete") or []
    # the first chunk costs 1 100 tokens, past the 500 ceiling: what is left is not examined
    assert incomplete and len(fake.calls) == 1


def test_a_zero_ceiling_turns_the_button_off(su, ai_on, provider, source, monkeypatch):
    monkeypatch.setattr(ai_on, "ai_structure_tokens", 0)
    r = generate(su)
    assert r.status_code == 429 and r.json()["error"]["code"] == "ai_structure_ceiling"


def test_generation_requires_a_super_user(admin, user, source):
    for who in (admin, user):
        assert signed_in(who.email).post(
            "/api/sources/coinmarketcap/structure/generate").status_code == 403
    assert client().post("/api/sources/coinmarketcap/structure/generate").status_code == 401


def test_the_chat_is_gone(su, source):
    for method in ("get", "post", "delete"):
        r = getattr(su, method)("/api/sources/coinmarketcap/chat")
        assert r.status_code in (404, 405), (method, r.status_code)


# --- PostgreSQL: relations the catalogue already knows ------------------------------------

PG = {"name": "ERP ventas", "kind": "postgresql", "settings": {
    "host": "203.0.113.9", "port": 5432, "database": "erp", "username": "bi_ro"},
      "secrets": {"password": "Origin-Secret-9f3k"}}

PG_STRUCTURE = {
    "kind": "postgresql", "truncated": False,
    "tables": [
        {"schema": "ventas", "name": "orders", "kind": "table", "estimated_rows": 1200,
         "primary_key": ["id"],
         "foreign_keys": [{"column": "customer_id", "references": "customers.id"}],
         "columns": [{"name": "id", "type": "integer", "nullable": False},
                     {"name": "customer_id", "type": "uuid", "nullable": True}]},
        {"schema": "ventas", "name": "customers", "kind": "table", "estimated_rows": 300,
         "primary_key": ["id"], "foreign_keys": [],
         "columns": [{"name": "id", "type": "uuid", "nullable": False}]},
    ],
}


def test_postgres_relations_come_from_the_catalogue(su, ai_on, monkeypatch, recorded):
    monkeypatch.setattr(describer, "describe", lambda *a, **kw: PG_STRUCTURE)
    answer = {"tables": [
        {"id": "orders", "schema": "ventas", "row_is": "un pedido", "key": ["id"],
         "date_field": None, "fields": [{"name": "id", "type": "integer"},
                                        {"name": "customer_id", "type": "uuid"}]},
        {"id": "customers", "schema": "ventas", "row_is": "un cliente", "key": ["id"],
         "date_field": None, "fields": [{"name": "id", "type": "uuid"}]}],
        "relations": [], "suggested_metrics": []}
    monkeypatch.setattr(structure_ai, "get_provider", lambda s: FakeProvider([answer]))
    su.post("/api/sources", json=PG)
    r = su.post("/api/sources/ERP ventas/structure/generate")
    assert r.status_code == 200, r.text
    relations = r.json()["pack"]["relations"]
    assert {"from": "ventas.orders.customer_id", "to": "customers.id", "kind": "many_to_one",
            "confidence": "high"} in relations


# --- the scan itself ----------------------------------------------------------------------

def test_scan_keeps_formats_and_repeated_enums_but_no_value(su):
    """A value that repeats is an enum a reader needs; a value that appears once is a row."""
    scan = structure_scan.enums_of(LISTINGS["data"])
    assert scan["category"]["enum"] == ["coin"]
    assert "symbol" not in scan and "name" not in scan    # BTC, ETH and the seeded name: once each
    assert ROW_VALUE not in json.dumps(scan)
    assert json.dumps(structure_scan.formats_of(LISTINGS["data"][0])) == \
        '{"last_updated": {"format": "iso8601"}}'


def test_the_scan_reports_an_endpoint_that_fails_without_stopping(su, monkeypatch, recorded):
    from app.engine.extract import ExtractError

    def failing(settings, secrets, app, path, params=None, timeout=20):
        if path == "v1/broken":
            raise ExtractError("la fuente respondió HTTP 500")
        return 200, LISTINGS

    from app.sources import samples as sample_service

    monkeypatch.setattr(sample_service, "get_json", failing)
    src = su.post("/api/sources", json=REST).json()
    su.post("/api/sources/coinmarketcap/samples", json={"name": "roto", "path": "v1/broken"})
    from app.config import get_settings
    from app.db import get_sessionmaker
    from app.sources import service as source_service

    with get_sessionmaker().begin() as db:
        source = source_service.get(db, src["id"])
        scan = structure_scan.scan(db, source, get_settings())
    error = next(e for e in scan["endpoints"] if e["path"] == "v1/broken")
    assert error["error"] == "ExtractError"
    assert any(e.get("shape") for e in scan["endpoints"] if e["path"] == "v1/listings")
