"""Feature 040 (E): `fields` come from a checked shape, and time units are inferred.

The production run wrote `global-metrics` fields without `check_request` (the preview then said
«columnas o campos que no coinciden») and mapped a `fear_greed` timestamp in the wrong unit (the
preview said «date/time field value out of range»).
"""
from types import SimpleNamespace

import pytest

from app.assistant import origin, tools


def test_the_unit_is_inferred_from_the_magnitude_or_the_format():
    assert origin.timestamp_unit(1_758_067_200) == "seconds"
    assert origin.timestamp_unit(1_758_067_200_000) == "milliseconds"
    assert origin.timestamp_unit("2025-09-17T00:00:00Z") == "iso8601"
    assert origin.timestamp_unit("2025-09-17") == "iso8601"
    assert origin.timestamp_unit("no aplica") is None
    assert origin.timestamp_unit(None) is None
    assert origin.timestamp_unit(True) is None
    # A value outside 1990-2100 is not a time field this rule can vouch for.
    assert origin.timestamp_unit(12_345) is None


def test_the_shape_names_the_actual_keys_and_the_unit_mismatch():
    request = {"fields": {"symbol": "$.symbol", "hour": "$.hour"},
               "timestamp_units": {"hour": "seconds"}}
    first = {"symbol": "BTC", "hour": 1_758_067_200_000}
    result = origin._shape_result(request, first, ["symbol", "hour"])
    assert result["keys"] == ["hour", "symbol"]
    assert result["timestamp_units"] == {"hour": "milliseconds"}
    assert result["unit_mismatch"] == [{"column": "hour", "declared": "seconds",
                                        "suggested": "milliseconds"}]
    assert result["ok"] is False


def test_a_matching_unit_is_ok():
    request = {"fields": {"hour": "$.hour"}, "timestamp_units": {"hour": "milliseconds"}}
    result = origin._shape_result(request, {"hour": 1_758_067_200_000}, ["hour"])
    assert result["ok"] is True and result["unit_mismatch"] == []


def test_the_shape_reports_a_missing_field_without_the_keys():
    result = origin._shape_result({"fields": {"nope": "$.nope"}}, {"symbol": "BTC"}, ["nope"])
    assert result["ok"] is False
    assert result["missing"] == ["nope"]
    assert result["keys"] == ["symbol"]


def _session(query_checks=None, command="speckit-implement"):
    return SimpleNamespace(
        command_run=SimpleNamespace(command=command),
        query_checks=query_checks,
    )


def test_fields_are_not_written_before_check_request():
    request = "records: $.data\nfields:\n  hour: $.hour\n"
    with pytest.raises(tools.ToolError) as exc:
        tools._requests_checked(
            _session(), [{"op": "write", "path": "integrations/cmc/requests/x.yaml",
                          "content": request}])
    assert "check_query" in str(exc.value)


def test_a_field_the_shape_does_not_have_names_the_real_keys():
    session = _session({"integrations/cmc/requests/x.yaml": {
        "ok": True, "keys": ["symbol", "hour"]}})
    request = "records: $.data\nfields:\n  ghost: $.ghost\n"
    with pytest.raises(tools.ToolError) as exc:
        tools._requests_checked(session, [{"op": "write",
                                           "path": "integrations/cmc/requests/x.yaml",
                                           "content": request}])
    assert "ghost" in str(exc.value) and "symbol" in str(exc.value)


def test_a_checked_shape_that_matches_is_written():
    session = _session({"integrations/cmc/requests/x.yaml": {
        "ok": True, "keys": ["symbol", "hour"]}})
    request = "records: $.data\nfields:\n  hour: $.hour\n"
    tools._requests_checked(session, [{"op": "write",
                                       "path": "integrations/cmc/requests/x.yaml",
                                       "content": request}])


def test_authoring_a_spec_is_not_held_to_the_check():
    request = "records: $.data\nfields:\n  hour: $.hour\n"
    tools._requests_checked(_session(command="speckit-converge"),
                            [{"op": "write", "path": "integrations/cmc/requests/x.yaml",
                              "content": request}])


def test_the_preview_names_the_timestamp_unit_mismatch():
    from app.assistant import preview

    text = preview.ai_error_text(
        'date/time field value out of range: "1758067200000"')
    assert "timestamp_units" in text and "1990-2100" in text
