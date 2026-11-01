"""Feature 048: the short direct-table form and the declared scope, at validation time."""
import yaml

from bizview_cli import validate
from tests.conftest import write
from tests.test_report_layout import REPORT, _with_view_ids

SOURCE = "Almacén ventas"
STRUCTURE = {"tables": {"reporting.v_ventas_dia": {
    "columns": {"fecha": "date", "importe": "numeric"}}}}


def _direct(ws, tables: dict, source: str = SOURCE) -> None:
    data = yaml.safe_load((ws / REPORT).read_text(encoding="utf-8"))
    data.pop("uses", None)
    direct = {"source": source, "tables": tables}
    data["direct"] = direct
    data["date"] = f"{next(iter(tables))}.fecha"
    for metric in data["metrics"].values():
        metric.pop("sql", None)
        metric["formula"] = "1"
    write(ws, REPORT, yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def _ctx(**kw):
    options = {"sources": {"almacén ventas": {"name": SOURCE, "kind": "postgresql",
                                              "enabled": True, "direct": True}},
               "structure": lambda source, tables: STRUCTURE}
    options.update(kw)
    return validate.DirectContext(**options)


def _codes(result) -> list[str]:
    return [issue.code for issue in result.issues]


def test_the_short_form_resolves_its_columns_from_the_source(ws):
    """`alias: schema.object`: the source declares the columns, so the report need not."""
    _with_view_ids(ws)
    _direct(ws, {"v": "reporting.v_ventas_dia"})
    seen = []

    def structure(source, tables):
        seen.append((source, tables))
        return STRUCTURE

    result = validate.validate(ws, direct=_ctx(structure=structure))
    codes = _codes(result)
    # The fixture's joins and its free-form metrics are not what this test is about: the direct
    # path resolved the short form and found every column it needed.
    assert "direct_columns_unresolved" not in codes, codes
    assert "direct_table_missing" not in codes, codes
    assert "direct_out_of_scope" not in codes, codes
    # The resolver asks once for the short form; the live check asks again on its own.
    assert seen and all(source == SOURCE for source, _ in seen)
    assert seen[0] == (SOURCE, ["reporting.v_ventas_dia"])


def test_a_short_object_that_is_not_there_is_a_problem(ws):
    _with_view_ids(ws)
    _direct(ws, {"v": "reporting.v_ventas_dia"})
    result = validate.validate(ws, direct=_ctx(structure=lambda s, t: {"tables": {}}))
    assert "direct_table_missing" in _codes(result), _codes(result)


def test_a_report_may_not_read_outside_the_declared_scope(ws):
    _with_view_ids(ws)
    _direct(ws, {"v": "otro.v_ventas"})
    result = validate.validate(ws, direct=_ctx(
        structure=lambda s, t: {"tables": {"otro.v_ventas": {
            "columns": {"fecha": "date", "importe": "numeric"}}}},
        allowed=lambda source, schema, table: False))
    issue = next(i for i in result.issues if i.code == "direct_out_of_scope")
    assert issue.path == "/direct/tables/v"
    assert "fuera del alcance" in issue.message
    assert "Lista para BI" in (issue.fix or "")


def test_without_a_readable_structure_the_short_form_only_warns(ws):
    _with_view_ids(ws)
    _direct(ws, {"v": "reporting.v_ventas_dia"})
    result = validate.validate(ws)
    warning = next(i for i in result.issues if i.code == "direct_columns_unresolved")
    assert warning.level == "warning"
    assert "se comprobará al importar o aplicar" in warning.message


def test_the_long_form_still_works_and_needs_no_structure(ws):
    _with_view_ids(ws)
    _direct(ws, {"v": {"table": "reporting.v_ventas_dia",
                       "columns": {"fecha": {"type": "date"},
                                   "importe": {"type": "numeric"}}}})
    result = validate.validate(ws, direct=_ctx())
    codes = _codes(result)
    assert "direct_columns_unresolved" not in codes, codes
    assert "direct_table_missing" not in codes, codes


def test_the_schema_refuses_an_alias_that_is_neither_a_string_nor_a_definition(ws):
    _with_view_ids(ws)
    _direct(ws, {"v": 42})
    result = validate.validate(ws, direct=_ctx())
    assert "schema_error" in _codes(result), _codes(result)
