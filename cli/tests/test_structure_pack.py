"""Feature 052 / US1: one generator produces `structure.md` + `structure.json` (pack format).

Structure only: the fixture seeds distinctive row values (customer e-mail, amount, host, password)
and the test proves none of them reaches either file — the 014 SC-002 trick, reused.
"""
import json
from pathlib import Path

from bizview_cli.describe import structure_from
from bizview_cli.structure import (
    build_pack,
    infer_timestamp_units,
    is_personal,
    pagination_hint,
    structure_json,
    structure_markdown,
    suggest,
)

SECRET_VALUE = "ACME-SECRET-CUSTOMER-9931"
HOST = "db.internal.customer.example"
PASSWORD = "Sup3r-Origin-Pass"

POSTGRES = {
    "kind": "postgresql",
    "truncated": False,
    "tables": [
        {
            "schema": "ventas", "name": "orders", "kind": "table", "estimated_rows": 1200,
            "primary_key": ["id"],
            "foreign_keys": [{"column": "customer_id", "references": "customers.id"}],
            "columns": [
                {"name": "id", "type": "integer", "nullable": False},
                {"name": "created_at", "type": "timestamp with time zone", "nullable": False,
                 "range": {"min": "2023-01-04", "max": "2026-11-02"}},
                {"name": "customer_email", "type": "text", "nullable": True},
                {"name": "total_amount", "type": "numeric(12,2)", "nullable": False},
                {"name": "customer_id", "type": "uuid", "nullable": True},
            ],
        },
        {
            "schema": "public", "name": "customers", "kind": "table", "estimated_rows": 300,
            "primary_key": ["id"], "columns": [
                {"name": "id", "type": "uuid", "nullable": False},
                {"name": "full_name", "type": "text", "nullable": True},
                {"name": "ruta", "type": "text", "nullable": True},
            ],
        },
    ],
}

REST_SHAPE = {"data": [{"id": "integer", "last_updated": "string", "quote": {
    "price": "number"}}], "status": {"total_count": "integer"}}


def pg_pack(**kw):
    return build_pack(POSTGRES, source="erp-ventas", kind="postgresql", **kw)


# --- heuristics ---------------------------------------------------------------------------

def test_personal_columns_by_heuristic():
    for name in ("customer_email", "correo", "full_name", "nombre_cliente", "phone_number",
                 "cedula", "dni", "chat_id", "telegram_user", "address_line"):
        assert is_personal(name), name
    for name in ("id", "total_amount", "created_at", "ruta", "status", "order_id"):
        assert not is_personal(name), name


def test_personal_flag_is_overridable_per_column():
    pack = pg_pack(flags={"ventas.orders.customer_email": False,
                          "ventas.orders.total_amount": True})
    columns = {c["name"]: c for t in pack["structure"]["tables"] for c in t["columns"]}
    assert columns["customer_email"]["personal"] is False
    assert columns["total_amount"]["personal"] is True
    assert columns["full_name"]["personal"] is True


def test_timestamp_units_from_a_value():
    assert infer_timestamp_units("2026-11-02T10:00:00Z") == "iso8601"
    assert infer_timestamp_units("2026-11-02") == "iso8601"
    assert infer_timestamp_units(1_700_000_000) == "epoch_s"
    assert infer_timestamp_units(1_700_000_000_000) == "epoch_ms"
    assert infer_timestamp_units("no es una fecha") is None
    assert infer_timestamp_units(True) is None


def test_records_fields_and_pagination_suggestions():
    found = suggest(REST_SHAPE)
    assert found["records"] == "$.data"
    assert found["fields"] == {"id": "$.id", "last_updated": "$.last_updated", "quote": "$.quote"}
    assert found["types"]["id"] == "integer" and found["types"]["quote"] == "object"
    assert pagination_hint(REST_SHAPE) == "total_count"
    assert pagination_hint({"data": [{"id": "integer"}]}) is None
    assert suggest([{"id": "integer"}])["records"] == "$"


# --- structure.md -------------------------------------------------------------------------

def test_markdown_follows_the_pack_template():
    text = structure_markdown(pg_pack(notes="Plan free: 333 llamadas al día."))
    lines = text.splitlines()
    assert lines[0] == "# Fuente «erp-ventas» — estructura"
    assert "Tipo: postgresql · Zona horaria de los datos: UTC" in lines[2]
    assert "Plan free: 333 llamadas al día." in lines[2]
    for heading in ("## PostgreSQL", "### Esquema `public`", "### Esquema `ventas`",
                    "## Observaciones"):
        assert heading in lines
    assert ("#### Tabla `orders` — ~1200 filas · fecha: `created_at` "
            "(2023-01-04 → 2026-11-02)") in lines
    assert "| Columna | Tipo | Nulo | Clave | Personal | Nota |" in lines
    assert "| created_at | timestamp with time zone | no |  |  | fecha |" in lines
    assert "| customer_email | text | sí |  | **sí** |  |" in lines
    assert "| customer_id | uuid | sí | FK → customers.id |  |  |" in lines
    assert "| id | integer | no | PK |  |  |" in lines
    assert "- Datos personales: `orders.customer_email`, `customers.full_name`." in lines


def test_markdown_omits_the_sections_that_do_not_apply():
    text = structure_markdown(pg_pack())
    assert "## REST" not in text and "## SOAP" not in text
    rest = structure_markdown(build_pack(
        {"kind": "rest", "path": "/v1/listings", "shape": REST_SHAPE},
        source="coinmarketcap", kind="rest",
        samples=[{"name": "listados", "method": "GET", "path": "v1/cryptocurrency/listings",
                  "params": {"limit": "100"}, "shape": REST_SHAPE, "records": "$.data",
                  "fields": {"id": "$.id", "last_updated": "$.last_updated"},
                  "types": {"id": "integer", "last_updated": "string"},
                  "timestamp_units": "iso8601", "pagination": "total_count"}]))
    assert "## PostgreSQL" not in rest and "## REST" in rest
    assert "### Petición `listados` — GET `v1/cryptocurrency/listings`" in rest
    assert "Params: `limit=100`. Paginación: total_count." in rest
    assert '`records: "$.data"`.' in rest
    assert "| `$.id` | integer |  |" in rest
    assert "| `$.last_updated` | string | fecha (iso8601) |" in rest


def test_soap_pack_lists_operations():
    pack = build_pack(
        {"kind": "soap", "services": [{"name": "ERP", "ports": [{"name": "P", "operations": [
            {"name": "GetOrders", "input": "(since: date)", "output": "(orders: Array)"}]}]}]},
        source="erp-soap", kind="soap")
    assert "Operación `GetOrders`: entrada `(since: date)`, salida `(orders: Array)`." in \
        structure_markdown(pack)


# --- what a pack must never contain -------------------------------------------------------

def test_no_row_value_host_or_credential_reaches_the_files():
    text = structure_markdown(pg_pack(notes=""))
    data = structure_json(pg_pack())
    for secret in (SECRET_VALUE, HOST, PASSWORD):
        assert secret not in text and secret not in data


def test_truncation_is_stated_in_the_observations():
    truncated = {**POSTGRES, "truncated": True}
    pack = build_pack(truncated, source="erp", kind="postgresql")
    assert pack["pack"]["truncated"] is True
    assert "- El catálogo se truncó: no caben todas las tablas de la fuente." in \
        structure_markdown(pack)


def test_bi_ready_flag_travels_with_its_scopes():
    pack = pg_pack(bi_ready={"enabled": True, "schemas": ["ventas"]})
    assert pack["pack"]["bi_ready"] is True
    assert "- Fuente declarada BI-ready; los reportes pueden leer: ventas." in \
        structure_markdown(pack)


# --- structure.json -----------------------------------------------------------------------

def test_json_wrapper_keeps_the_describe_body_and_a_header():
    pack = pg_pack(notes="notas")
    data = json.loads(structure_json(pack))
    assert data["pack"]["version"] == 1 and data["pack"]["source"] == "erp-ventas"
    assert data["pack"]["kind"] == "postgresql" and data["pack"]["notes"] == "notas"
    assert data["structure"]["kind"] == "postgresql"
    assert len(data["structure"]["tables"]) == 2


def test_structure_from_accepts_the_wrapper_and_the_bare_describe():
    wrapped = json.loads(structure_json(pg_pack()))
    for payload in (wrapped, POSTGRES):
        result = structure_from(payload, ["ventas.orders"])
        assert result["error"] is None
        assert set(result["tables"]) == {"ventas.orders"}
        assert result["tables"]["ventas.orders"]["columns"]["customer_email"] == "text"


# --- the CLI verb -------------------------------------------------------------------------

def test_cli_writes_both_files_where_the_pack_expects(tmp_path, monkeypatch):
    from bizview_cli import describe as cli_describe

    monkeypatch.setattr(cli_describe, "fetch_pack", lambda source, path=None: pg_pack())
    code = cli_describe.describe("erp-ventas", pack=True, out=str(tmp_path))
    assert code == 0
    folder = Path(tmp_path) / "sources" / "erp-ventas"
    assert (folder / "structure.md").read_text("utf-8").startswith("# Fuente «erp-ventas»")
    assert json.loads((folder / "structure.json").read_text("utf-8"))["pack"]["source"] == \
        "erp-ventas"
