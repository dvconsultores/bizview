"""Authoring pack: golden workspaces, generated summary, guide topics (feature 017)."""
import json
import re
from pathlib import Path

import pytest
import yaml

from bizview_cli import authoring, report_layout, sqlsafety, transform, validate


def _walk(schema: dict, *keys: str) -> dict:
    node = schema
    for key in keys:
        node = node[key]
    return node


GOLDEN_NAMES = list(authoring.GOLDEN)


def _golden_path(name: str) -> Path:
    return Path(str(authoring.golden_root(authoring.GOLDEN[name])))


def _issues(result):
    issues = result.issues
    if not transform.available():
        issues = [i for i in issues if i.code != "transform_unchecked"]
    return issues


GOLDEN_FACTS = {
    "example": {
        "integrations": {"facturas"},
        "reports": {"facturas-dia"},
    },
    "example-direct": {
        "integrations": set(),
        "reports": {"ventas-directo"},
    },
    "example-supabase": {
        "integrations": {"facturas-api"},
        "reports": set(),
    },
    "example-large": {
        "integrations": {"pedidos"},
        "reports": {"pedidos-dia"},
    },
}


@pytest.mark.parametrize("name", GOLDEN_NAMES)
def test_golden_workspaces_validate_with_zero_issues(name: str) -> None:
    root = _golden_path(name)
    result = validate.validate(
        root, known_sources={authoring.GOLDEN_SOURCES[authoring.GOLDEN[name]]}
    )
    assert result.ok, f"golden workspace {name} has issues: {result.issues}"
    assert _issues(result) == []
    assert set(result.integrations) == GOLDEN_FACTS[name]["integrations"]
    assert set(result.reports) == GOLDEN_FACTS[name]["reports"]


@pytest.mark.parametrize("name", GOLDEN_NAMES)
def test_guide_files_round_trip_validate(tmp_path: Path, name: str) -> None:
    guide = authoring.guide(name)
    (tmp_path / "bizview.yaml").write_text(
        "name: ejemplo\nproduct: bizview\ntimezone: America/Caracas\ncurrency: USD\n"
    )
    for rel, content in guide["files"].items():
        target = tmp_path / "projects" / "ejemplo" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    result = validate.validate(tmp_path, known_sources={guide["source"]})
    assert result.ok, f"round trip {name} has issues: {result.issues}"
    assert _issues(result) == []


def test_golden_report_uses_every_view_type_and_pdf() -> None:
    report_schema = validate.SCHEMAS["report"].schema
    view_items = _walk(report_schema, "properties", "views", "items")
    expected_view_types = {
        branch["properties"]["type"]["const"] for branch in view_items["oneOf"]
    }
    orientation_enum = _walk(
        report_schema, "$defs", "pdf_page", "properties", "orientation"
    )["enum"]
    files = authoring.golden_files(authoring.GOLDEN["example"])
    report = yaml.safe_load(files["reports/facturas-dia/report.yaml"])

    assert report["pdf"]["enabled"] is True
    # El layout declara la página y el orden de los bloques (pdf.views/pdf.orientation se retiran).
    page = report["layout"]["pdf"]["page"]
    assert page["orientation"] in orientation_enum
    assert [block["type"] for block in report["layout"]["pdf"]["blocks"]] == [
        "header", "kpi_row", "chart", "table", "footer"]
    assert {view["type"] for view in report["views"]} == expected_view_types
    ids = {view["id"] for view in report["views"]}
    assert len(ids) == len(report["views"])
    refs = {comp["view"] for comp in report["layout"]["web"]["components"] if "view" in comp}
    refs |= {block["view"] for block in report["layout"]["pdf"]["blocks"] if "view" in block}
    assert refs <= ids


def test_guide_report_documents_every_layout_component_and_block() -> None:
    """FR-010/FR-014: el catálogo del layout es el del esquema que recibe el Asistente."""
    schema = authoring.guide("report")["schema"]
    web = _walk(schema, "$defs", "web_component", "properties", "type")["enum"]
    pdf = _walk(schema, "$defs", "pdf_block", "properties", "type")["enum"]
    assert web == list(report_layout.WEB_COMPONENT_TYPES)
    assert pdf == list(report_layout.PDF_BLOCK_TYPES)

    documented = json.dumps(schema, ensure_ascii=False)
    for kind in report_layout.WEB_COMPONENT_TYPES + report_layout.PDF_BLOCK_TYPES:
        assert f'"{kind}"' in documented

    assert _walk(schema, "$defs", "pdf_block", "properties", "kind")["enum"] == list(
        report_layout.CHART_KINDS)
    assert _walk(schema, "$defs", "color_role")["enum"] == list(report_layout.COLOR_ROLES)
    assert _walk(schema, "$defs", "font_name")["enum"] == list(report_layout.FONT_NAMES)
    assert "layout" in authoring.summary()

    fragment = authoring.guide("fragment:report#/$defs/web_component")
    assert fragment["fragment"] is schema["$defs"]["web_component"]


def test_golden_supabase_has_request_file() -> None:
    files = authoring.golden_files("golden-supabase")
    assert "integrations/facturas-api/requests/facturas.yaml" in files


def test_golden_integration_contract_facts() -> None:
    files = authoring.golden_files(authoring.GOLDEN["example"])
    integration = yaml.safe_load(files["integrations/facturas/integration.yaml"])
    dataset = integration["datasets"]["facturas"]

    assert "primary_key" in dataset
    assert "date_column" in dataset
    assert "window_days" in dataset["incremental"]
    assert {check["type"] for check in dataset["checks"]} == {"row_count", "not_null"}
    assert integration["schedule"] == "0 * * * *"


def _expected_strings() -> set[str]:
    """Strings the summary must contain, derived from schemas and DRAFT_PATHS."""
    expected: set[str] = set()
    for _name, validator in validate.SCHEMAS.items():
        schema = validator.schema
        for key in schema.get("required", []):
            expected.add(str(key))

    integration = validate.SCHEMAS["integration"].schema
    dataset = _walk(integration, "properties", "datasets", "additionalProperties")
    for key in dataset.get("required", []):
        expected.add(str(key))

    column = _walk(dataset, "properties", "columns", "additionalProperties")
    for key in column.get("required", []):
        expected.add(str(key))

    report = validate.SCHEMAS["report"].schema
    metric = _walk(report, "properties", "metrics", "additionalProperties")
    for key in metric.get("required", []):
        expected.add(str(key))
    for branch in metric.get("oneOf", []):
        for key in branch.get("required", []):
            expected.add(str(key))

    views = _walk(report, "properties", "views", "items")
    for branch in views.get("oneOf", []):
        for key in branch.get("required", []):
            expected.add(str(key))

    request = validate.SCHEMAS["request"].schema
    pagination = _walk(request, "properties", "pagination")
    for key in pagination.get("required", []):
        expected.add(str(key))

    for value in _walk(column, "properties", "type").get("enum", []):
        expected.add(str(value))
    for branch in views.get("oneOf", []):
        expected.add(str(branch["properties"]["type"]["const"]))
    for branch in _walk(
        integration, "properties", "datasets", "additionalProperties",
        "properties", "checks", "items"
    ).get("oneOf", []):
        expected.add(str(branch["properties"]["type"]["const"]))
    for value in _walk(metric, "properties", "format").get("enum", []):
        expected.add(str(value))
    orientation = _walk(report, "properties", "pdf", "properties", "orientation")
    for value in orientation.get("enum", []):
        expected.add(str(value))
    schedule = _walk(integration, "properties", "schedule")
    expected.add(schedule["pattern"])
    return expected


def test_summary_covers_contract_keys_and_values() -> None:
    text = authoring.summary()
    missing = sorted(s for s in _expected_strings() if s not in text)
    assert not missing, f"summary missing: {missing}"

    for path in authoring.DRAFT_PATHS:
        assert path in text


def test_summary_deterministic_and_cached() -> None:
    first = authoring.summary()
    second = authoring.summary()
    assert second is first


def test_guide_schema_objects_are_validator_objects() -> None:
    for name in validate.SCHEMAS:
        assert authoring.guide(name)["schema"] is validate.SCHEMAS[name].schema


def test_guide_fragments() -> None:
    integration = validate.SCHEMAS["integration"].schema
    incremental = _walk(
        integration,
        "properties",
        "datasets",
        "additionalProperties",
        "properties",
        "incremental",
    )
    frag = authoring.guide(
        "fragment:integration#/properties/datasets/additionalProperties/properties/incremental"
    )
    assert frag["schema"] == "integration"
    assert frag["pointer"] == (
        "/properties/datasets/additionalProperties/properties/incremental"
    )
    assert frag["fragment"] is incremental

    view0 = authoring.guide("fragment:report#/properties/views/items/oneOf/0")
    assert view0["fragment"]["properties"]["type"]["const"] == "kpis"

    whole = authoring.guide("fragment:report")
    assert whole["fragment"] is validate.SCHEMAS["report"].schema

    assert "error" in authoring.guide("fragment:nope#/x")
    assert "error" in authoring.guide("fragment:report#/properties/missing")


def test_guide_index_unknown_spec() -> None:
    index = authoring.guide()
    topic_index = authoring.guide("index")
    assert index["topics"] == authoring.TOPICS
    assert topic_index["topics"] == authoring.TOPICS
    assert index["summary"] == authoring.summary()
    assert topic_index["summary"] == authoring.summary()

    unknown = authoring.guide("zzz")
    assert "error" in unknown
    assert unknown["topics"] == authoring.TOPICS

    spec = authoring.guide("spec")
    assert set(spec["templates"]) == {"spec-template.md", "plan-template.md", "tasks-template.md"}
    assert "**Tipo**" in spec["templates"]["spec-template.md"]

    workspace = authoring.guide("workspace")
    assert workspace["paths"] == list(authoring.DRAFT_PATHS)
    assert workspace["rules"] == authoring.RULES


@pytest.mark.parametrize("name", GOLDEN_NAMES)
def test_golden_files_contain_no_secrets_or_real_data(name: str) -> None:
    forbidden = ("password", "apikey", "service_key", "postgresql://", "http")
    files = authoring.golden_files(authoring.GOLDEN[name])
    for rel, content in files.items():
        lowered = content.casefold()
        assert not any(token in lowered for token in forbidden), \
            f"{rel} contains a forbidden token"


def test_summary_mentions_direct_contract_parts() -> None:
    summary = authoring.summary()
    assert "- exactamente uno de: uses | direct" in summary
    assert "direct" in summary
    assert "cache_seconds" in summary
    assert "timeout_seconds" in summary
    assert "max_rows" in summary
    assert (
        "usa modo directo solo si el usuario indica que los datos ya están preparados"
        " por otro proceso; si no, crea una integración" in summary
    )
    assert (
        "usa modo directo solo si el usuario indica que los datos ya están preparados"
        " por otro proceso; si no, crea una integración" in authoring.RULES
    )
    assert "un reporte usa `uses` o `direct`, nunca ambos" in authoring.RULES
    assert "**Volumen esperado**:" in authoring.RULES


def test_guide_example_direct_returns_direct_golden_details() -> None:
    topic = authoring.guide("example-direct")
    assert topic["topic"] == "example-direct"
    assert topic["source"] == "bi"
    files = topic["files"]
    report = files["reports/ventas-directo/report.yaml"]
    assert "direct:" in report
    assert "uses:" not in report
    assert "cache_seconds: 300" in report


def test_golden_direct_report_uses_every_view_type_and_pdf() -> None:
    files = authoring.golden_files("golden-direct")
    report = yaml.safe_load(files["reports/ventas-directo/report.yaml"])
    assert report["pdf"]["enabled"] is True
    view_types = {view["type"] for view in report["views"]}
    assert view_types == {"kpis", "trend", "ranking", "table"}
    assert report["direct"]["source"] == "bi"
    assert report["direct"]["tables"]["v"]["table"] == "public.bi_ventas"
    assert report["date"] == "v.fecha"


def test_golden_direct_spec_contains_five_direct_lines() -> None:
    files = authoring.golden_files("golden-direct")
    spec = files["specs/001-ventas-directo/spec.md"]
    for line in ("**Modo**: directo", "**Fuente**: bi", "**Tablas**:",
                 "**Mantenido por**:", "**Volumen esperado**: ~1 M filas"):
        assert line in spec
    tasks = files["specs/001-ventas-directo/tasks.md"]
    assert tasks.count("- [X]") == 4


def test_golden_large_transform_is_row_wise() -> None:
    files = authoring.golden_files("golden-large")
    integration_yaml = yaml.safe_load(files["integrations/pedidos/integration.yaml"])
    dataset = integration_yaml["datasets"]["pedidos"]
    transform_node = dataset["transform"]
    sql = transform_node["sql"]
    input_types = {c: d["type"] for c, d in transform_node["input"].items()}
    check = sqlsafety.check_transform(sql, input_types)
    assert check.problems == []
    assert check.mode == "rows"

    query = files["integrations/pedidos/queries/pedidos.sql"]
    aliases = re.findall(r" AS (\w+)", query)
    assert aliases == list(transform_node["input"])

    report_yaml = yaml.safe_load(files["reports/pedidos-dia/report.yaml"])
    assert report_yaml["materialize"] == "daily"
    for metric in report_yaml["metrics"].values():
        if "sql" in metric:
            assert metric["sql"].startswith(("sum(", "count(", "avg("))

    spec = files["specs/002-pedidos-dia/spec.md"]
    assert "**Volumen esperado**" in spec


def test_guide_transform_topic() -> None:
    guide = authoring.guide("transform")
    dataset_schema = validate.SCHEMAS["integration"].schema["properties"]["datasets"][
        "additionalProperties"
    ]["properties"]["transform"]
    assert guide["schema"] is dataset_schema
    rows_set = set(guide["functions"]["rows"])
    whole_set = set(guide["functions"]["whole"])
    assert rows_set.isdisjoint(whole_set)
    assert rows_set | whole_set == set(sqlsafety.TRANSFORM_FUNCTIONS)
    assert "row_number" in guide["functions"]["whole"]
    assert "sum" in guide["functions"]["whole"]
    assert "upper" in guide["functions"]["rows"]
    assert "strftime" in guide["functions"]["rows"]
    assert guide["not_offered"] == sorted(sqlsafety.TRANSFORM_UNSUPPORTED)
    for name in guide["not_offered"]:
        assert name in guide["replacements"]
    assert set(guide["types"]) == {
        "text", "integer", "bigint", "numeric", "boolean", "date", "timestamptz"
    }
    assert "transform.input" in guide["rules"]
    assert "TRANSFORM_MAX_ROWS" in guide["rules"]
    assert "CAST(strftime(x, '%Y-%m-%d') AS DATE)" in guide["rules"]
    assert guide["example"] == "example-large"
    assert "transform" in authoring.TOPICS
    assert "example-large" in authoring.TOPICS


def test_summary_mentions_transform_and_materialize() -> None:
    summary = authoring.summary()
    assert "- transform:" in summary
    assert "get_authoring_guide('transform')" in summary
    assert "materialize en [none, daily]" in summary
    assert "propon `materialize: daily`" in summary
    assert "usa `transform` solo cuando" in summary
