from bizview_cli import materialize
from bizview_cli.validate import DirectContext, validate


def test_decompose_sum():
    d = materialize.decompose('sum(lines.net_amount)')
    assert isinstance(d, materialize.Decomposition)
    assert len(d.components) == 1
    comp = d.components[0]
    assert comp.kind == "sum"
    assert comp.name.startswith("c_")
    assert len(comp.name) == 2 + 12
    assert '"lines"."net_amount"' in comp.sql
    assert comp.sql == 'SUM("lines"."net_amount")'
    assert d.slots[0].kind == "sum"
    assert d.slots[0].components == (comp.name,)
    assert d.template == '"__slot_0"'


def test_decompose_count_star():
    d = materialize.decompose("count(*)")
    assert isinstance(d, materialize.Decomposition)
    assert d.components[0].kind == "count"
    assert d.components[0].sql == "COUNT(*)"
    assert d.template == '"__slot_0"'


def test_decompose_count_expr():
    d = materialize.decompose("count(lines.line_no)")
    assert isinstance(d, materialize.Decomposition)
    assert d.components[0].kind == "count"
    assert d.components[0].sql == 'COUNT("lines"."line_no")'


def test_decompose_min_max():
    d = materialize.decompose("min(lines.net_amount)")
    assert d.components[0].kind == "min"
    assert d.components[0].sql == 'MIN("lines"."net_amount")'
    d = materialize.decompose("max(lines.net_amount)")
    assert d.components[0].kind == "max"
    assert d.components[0].sql == 'MAX("lines"."net_amount")'


def test_decompose_avg_two_components():
    d = materialize.decompose("avg(lines.net_amount)")
    assert isinstance(d, materialize.Decomposition)
    assert len(d.components) == 2
    comps_by_kind = {c.kind: c for c in d.components}
    assert "sum" in comps_by_kind
    assert "count" in comps_by_kind
    assert comps_by_kind["sum"].sql == 'SUM("lines"."net_amount")'
    assert comps_by_kind["count"].sql == 'COUNT("lines"."net_amount")'
    assert d.slots[0].kind == "avg"
    assert set(d.slots[0].components) == {
        comps_by_kind["sum"].name,
        comps_by_kind["count"].name,
    }
    assert d.template == '"__slot_0"'


def test_decompose_filter_sum():
    sql = "sum(lines.net_amount) FILTER (WHERE lines.line_kind = 'sale')"
    d = materialize.decompose(sql)
    assert isinstance(d, materialize.Decomposition)
    assert len(d.components) == 1
    assert d.components[0].kind == "sum"
    canonical = d.components[0].sql
    assert "FILTER" in canonical
    assert "WHERE" in canonical
    assert "'sale'" in canonical
    assert d.template == '"__slot_0"'


def test_decompose_filter_avg():
    sql = "avg(lines.net_amount) FILTER (WHERE lines.line_kind = 'sale')"
    d = materialize.decompose(sql)
    assert isinstance(d, materialize.Decomposition)
    assert len(d.components) == 2
    comps_by_kind = {c.kind: c for c in d.components}
    assert "sum" in comps_by_kind
    assert "count" in comps_by_kind
    assert "FILTER" in comps_by_kind["sum"].sql
    assert "FILTER" in comps_by_kind["count"].sql


def test_decompose_case_wrapped_sum_one_component():
    sql = (
        "sum(case when lines.line_kind = 'devolucion' "
        "then -lines.net_amount else lines.net_amount end)"
    )
    d = materialize.decompose(sql)
    assert isinstance(d, materialize.Decomposition)
    assert len(d.components) == 1
    assert d.components[0].kind == "sum"
    assert "CASE" in d.components[0].sql
    assert d.template == '"__slot_0"'


def test_decompose_outer_template_kept():
    sql = "round(sum(lines.net_amount) / nullif(count(*), 0), 2)"
    d = materialize.decompose(sql)
    assert isinstance(d, materialize.Decomposition)
    template = d.template
    assert '"__slot_0"' in template
    assert '"__slot_1"' in template
    assert "ROUND" in template
    assert "NULLIF" in template


def test_recompose_round_template():
    sql = "round(sum(lines.net_amount) / nullif(count(*), 0), 2)"
    d = materialize.decompose(sql)
    assert isinstance(d, materialize.Decomposition)
    comps_by_kind = {c.kind: c for c in d.components}
    out = materialize.recompose(
        d,
        {comps_by_kind["sum"].name: "numeric", comps_by_kind["count"].name: "bigint"},
    )
    assert out.startswith("ROUND(")


def test_decompose_case_over_aggregates_dedupe():
    sql = "case when sum(lines.net_amount) > 0 then sum(lines.net_amount) else 0 end"
    d = materialize.decompose(sql)
    assert isinstance(d, materialize.Decomposition)
    assert len(d.components) == 1
    assert len(d.slots) == 2
    assert d.slots[0].components == d.slots[1].components
    assert d.template == 'CASE WHEN "__slot_0" > 0 THEN "__slot_1" ELSE 0 END'


def test_decompose_dedupe_avg_plus_sum():
    sql = "sum(lines.net_amount) + avg(lines.net_amount)"
    d = materialize.decompose(sql)
    assert isinstance(d, materialize.Decomposition)
    assert len(d.components) == 2
    assert len(d.slots) == 2
    avg_sum_name = next(c.name for c in d.components if c.kind == "sum")
    assert avg_sum_name in d.slots[1].components


def test_recompose_sum():
    d = materialize.decompose("sum(lines.net_amount)")
    assert isinstance(d, materialize.Decomposition)
    comp = d.components[0]
    out = materialize.recompose(d, {comp.name: "bigint"})
    assert out == f'CAST(SUM("r"."{comp.name}") AS BIGINT)'


def test_recompose_count():
    d = materialize.decompose("count(*)")
    assert isinstance(d, materialize.Decomposition)
    comp = d.components[0]
    out = materialize.recompose(d, {comp.name: "bigint"})
    assert out == f'CAST(COALESCE(SUM("r"."{comp.name}"), 0) AS BIGINT)'


def test_recompose_min():
    d = materialize.decompose("min(lines.net_amount)")
    comp = d.components[0]
    out = materialize.recompose(d, {comp.name: "numeric"})
    assert out == f'MIN("r"."{comp.name}")'


def test_recompose_max():
    d = materialize.decompose("max(lines.net_amount)")
    comp = d.components[0]
    out = materialize.recompose(d, {comp.name: "numeric"})
    assert out == f'MAX("r"."{comp.name}")'


def test_recompose_avg():
    d = materialize.decompose("avg(lines.net_amount)")
    assert isinstance(d, materialize.Decomposition)
    comps_by_kind = {c.kind: c for c in d.components}
    s = comps_by_kind["sum"].name
    n = comps_by_kind["count"].name
    out = materialize.recompose(d, {s: "numeric", n: "bigint"})
    expected = f'CAST(SUM("r"."{s}") AS DECIMAL) / NULLIF(SUM("r"."{n}"), 0)'
    assert out == expected


def test_ineligible_distinct():
    result = materialize.decompose("count(distinct lines.document_id)")
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].message == "DISTINCT dentro de un agregado no se puede materializar por día"
    assert result[0].fix == materialize.DISTINCT_FIX


def test_ineligible_sum_distinct():
    result = materialize.decompose("sum(distinct lines.net_amount)")
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].message == "DISTINCT dentro de un agregado no se puede materializar por día"
    assert result[0].fix == materialize.DISTINCT_FIX


def test_ineligible_percentile():
    result = materialize.decompose(
        "percentile_cont(0.5) within group (order by lines.net_amount)"
    )
    assert isinstance(result, list)
    assert any("percentiles" in r.message for r in result)


def test_ineligible_stddev():
    result = materialize.decompose("stddev(lines.net_amount)")
    assert isinstance(result, list)
    assert any("stddev" in r.message for r in result)


def test_ineligible_variance():
    result = materialize.decompose("variance(lines.net_amount)")
    assert isinstance(result, list)
    assert any("variance" in r.message for r in result)


def test_ineligible_string_agg():
    result = materialize.decompose("string_agg(lines.line_kind, ',')")
    assert isinstance(result, list)
    assert any("string_agg" in r.message for r in result)


def test_ineligible_bool_or():
    result = materialize.decompose("bool_or(lines.line_kind = 'sale')")
    assert isinstance(result, list)
    assert any("bool_or" in r.message for r in result)


def test_ineligible_window():
    result = materialize.decompose("sum(lines.net_amount) over ()")
    assert isinstance(result, list)
    assert any("ventana" in r.message for r in result)


def test_ineligible_nested():
    result = materialize.decompose("sum(max(lines.net_amount))")
    assert isinstance(result, list)
    assert any("anidados" in r.message for r in result)


def test_ineligible_bare_column():
    result = materialize.decompose("lines.net_amount + sum(lines.quantity)")
    assert isinstance(result, list)
    assert any("columnas fuera" in r.message for r in result)


def test_ineligible_current_date():
    result = materialize.decompose("sum(lines.quantity) + current_date")
    assert isinstance(result, list)
    assert any("current_date" in r.message for r in result)


def test_dimension_aggregate():
    reasons = materialize.dimension_reasons("sum(lines.net_amount)")
    assert any("agregadas" in r.message for r in reasons)


def test_dimension_current_date():
    reasons = materialize.dimension_reasons("current_date")
    assert any("current_date" in r.message for r in reasons)


def test_used_dimensions():
    report = {
        "dimensions": {
            "product": {"sql": "products.name"},
            "unused": {"sql": "unused.col"},
        },
        "filters": ["product"],
        "views": [{"dimension": "product"}, {"dimensions": ["product"]}],
    }
    assert materialize.used_dimensions(report) == ["product"]


def test_unused_ineligible_dimension_ignored():
    report = {
        "metrics": {"m": {"sql": "sum(l.a)"}},
        "dimensions": {
            "used": {"sql": "l.a"},
            "unused_bad": {"sql": "sum(l.a)"},
        },
        "filters": ["used"],
        "views": [{"dimension": "used"}],
    }
    problems = materialize.check_report(report)
    assert all("unused_bad" not in p.path for p in problems)


def test_validation_materialize_daily(ws):
    report_file = ws / "reports" / "resumen" / "report.yaml"
    text = report_file.read_text()
    if "materialize: daily" not in text:
        text += "\nmaterialize: daily\n"
        report_file.write_text(text)

    result = validate(ws)
    materialize_issues = [i for i in result.issues if i.code == "materialize_ineligible"]
    assert len(materialize_issues) == 1
    assert materialize_issues[0].path == "/metrics/orders/sql"
    assert materialize_issues[0].fix == materialize.DISTINCT_FIX


def test_validation_materialize_daily_fixed(ws):
    report_file = ws / "reports" / "resumen" / "report.yaml"
    text = report_file.read_text()
    text = text.replace("count(distinct lines.document_id)", "count(*)")
    if "materialize: daily" not in text:
        text += "\nmaterialize: daily\n"
    report_file.write_text(text)

    result = validate(ws)
    materialize_issues = [i for i in result.issues if i.code == "materialize_ineligible"]
    assert len(materialize_issues) == 0


def test_validation_without_materialize_no_ineligible(ws):
    result = validate(ws)
    materialize_issues = [i for i in result.issues if i.code == "materialize_ineligible"]
    assert len(materialize_issues) == 0


def test_materialize_recommended_warns_for_large_dataset(ws):
    ctx = DirectContext(warn_rows=5_000_000, dataset_rows=lambda iid, ds: 10_000_000)
    result = validate(ws, direct=ctx)
    codes = [i.code for i in result.issues if i.code == "materialize_recommended"]
    assert len(codes) == 1


def test_materialize_recommended_not_for_small_dataset(ws):
    ctx = DirectContext(warn_rows=5_000_000, dataset_rows=lambda iid, ds: 1000)
    result = validate(ws, direct=ctx)
    codes = [i.code for i in result.issues if i.code == "materialize_recommended"]
    assert len(codes) == 0


def test_materialize_recommended_silent_without_context(ws):
    result = validate(ws)
    codes = [i.code for i in result.issues if i.code == "materialize_recommended"]
    assert len(codes) == 0


def test_materialize_large_warns_on_bare_text_dimension(ws):
    report_file = ws / "reports/resumen/report.yaml"
    text = report_file.read_text()
    text = text.replace("count(distinct lines.document_id)", "count(*)")
    text = text.replace(
        "{type: trend, metric: net_sales}",
        "{type: trend, metric: net_sales}\n"
        "  - {type: ranking, dimension: product, metric: net_sales}"
    )
    text = text.rstrip() + "\nmaterialize: daily\n"
    report_file.write_text(text)
    ctx = DirectContext(warn_rows=5_000_000, dataset_rows=lambda iid, ds: 10_000_000)
    result = validate(ws, direct=ctx)
    large_codes = [i for i in result.issues if i.code == "materialize_large"]
    assert len(large_codes) == 1
    assert large_codes[0].path == "/dimensions/product/sql"
    recommended_codes = [i.code for i in result.issues if i.code == "materialize_recommended"]
    assert len(recommended_codes) == 0
