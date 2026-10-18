"""Transform engine module tests (feature 005 amendment 2026-10-08, T034)."""

from __future__ import annotations

import copy
import os
import time
from decimal import Decimal
from typing import Any

import polars as pl
import pytest
import yaml

from app.config import get_settings
from app.db import get_engine
from app.engine import datasets, extract, runner, transform
from app.engine.extract import ExtractError
from app.engine.transform import CopyTextSplitter, Sink, parse_text
from tests.conftest import TEST_SCHEMA, sql
from tests.test_bulk_extract import origin_conn
from tests.test_runner import (  # noqa: F401  (fixtures are used by name)
    NOW,
    ORIGIN,
    QUERY,
    TZ,
    ds_sql,
    ds_table,
    integration,
    lines,
    run,
)
from tests.test_runner import (
    origin as origin,
)
from tests.test_runner import (
    pg_source as pg_source,
)
from tests.test_runner import (
    rest_origin as rest_origin,
)

ROW_SQL = (
    "SELECT document_id, line_no, line_kind, completed_at, local_date, "
    "upper(product_code) AS product_code, net_amount * 2 AS net_amount FROM input"
)
SQL_ONLY_QUERY = QUERY.replace("product AS product_code", "upper(product) AS product_code").replace(
    "amount AS net_amount", "amount * 2 AS net_amount"
)

INPUT_COLUMNS = {
    "document_id": "text",
    "line_no": "integer",
    "line_kind": "text",
    "completed_at": "timestamptz",
    "local_date": "date",
    "product_code": "text",
    "net_amount": "numeric",
}

EDGE_ROWS = [
    "(1, E'line\\nbreak\\ttab \\\\ back', '', '2026-03-08 01:30-05', '2026-03-08', 1.5, "
    "9223372036854775807, true)",
    "(2, 'quotes '' \" and emoji 😀 ñ á', NULL, '2026-03-08 03:30-04', NULL, -0.000000001, "
    "-1, false)",
    "(3, NULL, 'x', NULL, '1999-12-31', 0, 0, NULL)",
]


def transformed(sql_text: str = ROW_SQL, input: dict | None = None,
                batch_rows: int | None = None) -> tuple[dict, dict]:
    definition, files = integration()
    defn = copy.deepcopy(definition)
    tr: dict[str, Any] = {
        "input": {c: {"type": t} for c, t in (input or INPUT_COLUMNS).items()},
        "sql": sql_text,
    }
    if batch_rows is not None:
        tr["batch_rows"] = batch_rows
    defn["datasets"]["sale_lines"]["transform"] = tr
    defn["datasets"]["sale_lines"]["checks"] = [{"type": "row_count", "min": 1}]
    files = copy.deepcopy(files)
    return defn, files


def snapshot() -> list[tuple[str, str, str, str, str, str, str]]:
    return ds_sql(
        f"SELECT document_id, line_no::text, line_kind, completed_at::text, "
        f"local_date::text, product_code, trim_scale(net_amount)::text "
        f"FROM {ds_table('ventas-prueba', 'sale_lines')} ORDER BY 1, 2, 3"
    )


def rest_definition() -> tuple[dict, dict]:
    definition = {
        "id": "rest-prueba",
        "spec": "specs/integrations/002-rest-prueba",
        "source": "API prueba",
        "schedule": "0 * * * *",
        "timezone": TZ,
        "datasets": {
            "orders": {
                "primary_key": ["id"],
                "date_column": "day",
                "columns": {
                    "id": {"type": "bigint", "nullable": False},
                    "total": {"type": "numeric"},
                    "day": {"type": "date"},
                    "tags": {"type": "text"},
                },
                "extract": {"request": "requests/orders.yaml"},
                "incremental": {"window_days": 3},
            }
        },
    }
    request = {
        "method": "GET",
        "path": "/orders",
        "params": {"from": "{window_start_date}", "to": "{window_end_date}"},
        "pagination": {"type": "page", "param": "page", "size_param": "per_page", "size": 2},
        "records": "$.data.items",
        "fields": {"id": "id", "total": "total", "day": "when", "tags": "tags"},
    }
    return definition, {"requests/orders.yaml": yaml.safe_dump(request)}


def copy_csv_line(*, document_id: str, line_no: int, line_kind: str, local_date: str,
                  product_code: str, net_amount: str, completed_at: str) -> bytes:
    return (
        f"{document_id}\t{line_no}\t{line_kind}\t{completed_at}\t{local_date}"
        f"\t{product_code}\t{net_amount}\n"
    ).encode()


class _FakeCopy:
    def __init__(self, blocks: list[bytes]):
        self.blocks = blocks
        self.calls = 0

    def __call__(self, *a, **k):
        self.calls += 1
        write = k["write"]
        for block in self.blocks:
            write(block)
        return sum(block.count(b"\n") for block in self.blocks)


def test_parse_text_escapes_and_types():
    ds = {
        "columns": {
            "t": {"type": "text"},
            "i": {"type": "integer"},
            "n": {"type": "numeric"},
            "b": {"type": "boolean"},
            "d": {"type": "date"},
            "ts": {"type": "timestamptz"},
        },
        "transform": {
            "input": {
                "t": {"type": "text"},
                "i": {"type": "integer"},
                "n": {"type": "numeric"},
                "b": {"type": "boolean"},
                "d": {"type": "date"},
                "ts": {"type": "timestamptz"},
            },
            "sql": "SELECT * FROM input",
        },
    }
    compiled = transform.compile(ds, TZ)
    raw = pl.DataFrame(
        {
            "t": ["a\\\\b", "c\\td", "e\\nf", "g\\rh", None, ""],
            "i": ["1", "2", "3", "4", "5", "6"],
            "n": ["1.5", "2", "-0.000000001", "3.25", "4", "5"],
            "b": ["t", "f", "TRUE", "false", "1", "0"],
            "d": ["2026-03-08", "2026-03-08", "2026-03-08", "2026-03-08",
                  "2026-03-08", "2026-03-08"],
            "ts": [
                "2026-03-08 01:30:00-04",
                "2026-03-08T03:30:00+05:30",
                "2026-03-08 03:15:00Z",
                "2026-03-08 04:30:00.123456",
                "2026-03-08T05:00:00.5",
                "2026-03-08",
            ],
        },
        schema={c: pl.String for c in ["t", "i", "n", "b", "d", "ts"]},
    )
    out = parse_text(raw, compiled, escaped=True)
    assert out["t"].to_list()[0] == "a\\b"
    assert out["t"].to_list()[1] == "c\td"
    assert out["t"].to_list()[2] == "e\nf"
    assert out["t"].to_list()[3] == "g\rh"
    assert out["t"].to_list()[4] is None
    assert out["t"].to_list()[5] == ""
    assert out["i"].to_list() == [1, 2, 3, 4, 5, 6]
    assert out["n"].to_list() == [
        Decimal("1.5"),
        Decimal("2"),
        Decimal("-0.000000001"),
        Decimal("3.25"),
        Decimal("4"),
        Decimal("5"),
    ]
    assert out["b"].to_list() == [True, False, True, False, True, False]
    assert out["d"].to_list()[0].isoformat() == "2026-03-08"
    assert out["ts"].to_list()[0].isoformat() == "2026-03-08T01:30:00-04:00"
    assert out["ts"].to_list()[1].isoformat() == "2026-03-07T18:00:00-04:00"
    assert out["ts"].to_list()[2].isoformat() == "2026-03-07T23:15:00-04:00"
    assert out["ts"].to_list()[3].isoformat() == "2026-03-08T04:30:00.123456-04:00"
    assert out["ts"].to_list()[4].isoformat() == "2026-03-08T05:00:00.500000-04:00"
    assert out["ts"].to_list()[5].isoformat() == "2026-03-08T00:00:00-04:00"
    raw_unescaped = pl.DataFrame({"t": ["c\\td", "e\\nf", "a\\\\b"]})
    ds2 = {
        "columns": {"t": {"type": "text"}},
        "transform": {"input": {"t": {"type": "text"}}, "sql": "SELECT t FROM input"},
    }
    compiled2 = transform.compile(ds2, TZ)
    out2 = parse_text(raw_unescaped, compiled2, escaped=False)
    assert out2["t"].to_list() == ["c\\td", "e\\nf", "a\\\\b"]


def test_parse_text_bad_integer_raises_safe_error():
    ds = {
        "columns": {"i": {"type": "integer"}},
        "transform": {
            "input": {"i": {"type": "integer"}},
            "sql": "SELECT * FROM input",
        },
    }
    compiled = transform.compile(ds, TZ)
    raw = pl.DataFrame({"i": ["1", "2", "3", "not-an-integer", "5"]})
    with pytest.raises(ExtractError) as e:
        parse_text(raw, compiled, escaped=False)
    assert "no cumple el tipo declarado" in str(e.value)
    assert "i" in str(e.value)
    assert "not-an-integer" not in str(e.value)


def test_copy_text_splitter_chunking_equivalent():
    payload = b"".join(
        [
            b"a\t1\tx\n",
            b"b\t\\N\t\n",
            b"c\t3\tline\\twith\\ttabs\n",
            b"d\t4\tback\\\\slash\n",
            b"e\t5\t\\N\n",
            b"f\t6\tlast\n",
        ]
    )
    columns = ["t", "n", "e"]

    def collect_all(feed: callable, close: callable) -> pl.DataFrame:
        batches: list[pl.DataFrame] = []
        splitter = CopyTextSplitter(lambda f, escaped: batches.append(f), columns, 2)
        feed(splitter)
        close(splitter)
        return pl.concat(batches)

    whole = collect_all(lambda s: s.write(payload), lambda s: s.close())
    bytewise = collect_all(
        lambda s: [s.write(bytes([b])) for b in payload], lambda s: s.close()
    )
    chunked = collect_all(
        lambda s: [s.write(payload[i:i + 7]) for i in range(0, len(payload), 7)],
        lambda s: s.close(),
    )
    assert whole.equals(bytewise)
    assert whole.equals(chunked)
    assert whole.height == 6
    assert whole["t"].to_list() == ["a", "b", "c", "d", "e", "f"]
    assert whole["e"].to_list()[1] == ""
    assert whole["e"].to_list()[2] == r"line\twith\ttabs"
    assert whole["n"].to_list()[1] is None
    assert whole["e"].to_list()[4] is None


def test_copy_text_splitter_final_line_without_newline():
    data = b"a\t1\nb\t2\nc\t3"
    batches: list[pl.DataFrame] = []
    splitter = CopyTextSplitter(lambda f, escaped: batches.append(f), ["t", "n"], 2)
    splitter.write(data)
    splitter.close()
    assert [f.height for f in batches] == [2, 1]


def test_splitter_error_on_wrong_columns():
    batches: list[pl.DataFrame] = []
    splitter = CopyTextSplitter(lambda f, escaped: batches.append(f), ["t", "n"], 2)
    with pytest.raises(ExtractError) as e:
        splitter.write(b"a\t1\tX\nb\t2\n")
    assert "número de columnas inesperado" in str(e.value)


def test_edge_identity_pg_copy_equals_pg_rows(pg_source):
    sql("DROP TABLE IF EXISTS edge")
    sql(
        "CREATE TABLE edge (id integer, t text, e text, ts timestamptz, d date, "
        "n numeric(38,9), b bigint, f boolean)"
    )
    sql("INSERT INTO edge VALUES " + ", ".join(EDGE_ROWS))
    try:
        settings, secrets = origin_conn()
        q = f'SELECT id, t, e, ts, d, n, b, f FROM "{TEST_SCHEMA}".edge'
        inp = {
            "id": {"type": "integer"},
            "t": {"type": "text"},
            "e": {"type": "text"},
            "ts": {"type": "timestamptz"},
            "d": {"type": "date"},
            "n": {"type": "numeric"},
            "b": {"type": "bigint"},
            "f": {"type": "boolean"},
        }
        cols = {c: {"type": v["type"]} for c, v in inp.items()}
        ds = {"columns": cols, "transform": {"input": inp, "sql": "SELECT * FROM input"}}
        compiled = transform.compile(ds, TZ)
        copy_out: list[pl.DataFrame] = []
        copy_sink = Sink(compiled, copy_out.append, lambda: None)
        splitter = CopyTextSplitter(
            copy_sink.add,
            compiled.input_columns,
            compiled.batch_rows,
        )
        extract.pg_copy(
            settings, secrets, get_settings(), q, {}, columns=compiled.input_columns,
            timezone=TZ, time_limit_s=60, deadline=time.monotonic() + 60,
            write=splitter.write, check=lambda: None,
        )
        splitter.close()
        rows_out: list[pl.DataFrame] = []
        rows_sink = Sink(compiled, rows_out.append, lambda: None)
        for got, rows in extract.pg_rows(
            settings, secrets, get_settings(), q, {}, timezone=TZ, time_limit_s=60
        ):
            rows_sink.add(runner._text_frame(rows, got), escaped=False)
        copy_frame = pl.concat(copy_out).sort("id")
        rows_frame = pl.concat(rows_out).sort("id")
        assert copy_frame.equals(rows_frame)
        text_rows = copy_frame.select("t", "e").rows()
        db_rows = sql("SELECT t, e FROM edge ORDER BY id")
        assert text_rows == db_rows
        assert text_rows[0] == ("line\nbreak\ttab \\ back", "")
        assert text_rows[1] == ("quotes ' \" and emoji 😀 ñ á", None)
        assert text_rows[2] == (None, "x")
    finally:
        sql("DROP TABLE IF EXISTS edge")


def test_copy_polars_equals_sql_only(origin):
    assert SQL_ONLY_QUERY != QUERY
    definition, files = transformed()
    r = runner.run_integration(definition, files, version_id=None, kind="incremental", now=NOW)
    assert r.status == "succeeded", r.message
    entry = r.rows["sale_lines"]
    assert entry["path"] == "copy+polars"
    assert entry["transform_mode"] == "rows"
    assert entry["rows_in"] == 4
    assert entry["extracted"] == 4
    assert isinstance(entry["transform_ms"], int)
    assert r.rows["products"] == {"extracted": 2, "written": 2, "full": True, "path": "copy"}
    transformed_snapshot = snapshot()
    definition, files = integration()
    definition = copy.deepcopy(definition)
    files = copy.deepcopy(files)
    files["queries/lines.sql"] = SQL_ONLY_QUERY
    definition["datasets"]["sale_lines"]["checks"] = [{"type": "row_count", "min": 1}]
    r2 = runner.run_integration(definition, files, version_id=None, kind="full", now=NOW)
    assert r2.status == "succeeded", r2.message
    assert r2.rows["sale_lines"]["path"] == "copy"
    assert snapshot() == transformed_snapshot


def test_rows_polars_when_copy_refused(origin, monkeypatch):
    definition, files = transformed()
    r = runner.run_integration(definition, files, version_id=None, kind="incremental", now=NOW)
    assert r.status == "succeeded", r.message
    first = snapshot()

    def refuse(*a, **k):
        raise extract.BulkUnsupported("FeatureNotSupported")

    monkeypatch.setattr(extract, "pg_copy", refuse)
    r = runner.run_integration(definition, files, version_id=None, kind="full", now=NOW)
    assert r.status == "succeeded", r.message
    entry = r.rows["sale_lines"]
    assert entry["path"] == "rows+polars"
    assert entry["fallback"] == "FeatureNotSupported"
    assert entry["rows_in"] == 4
    assert entry["extracted"] == 4
    assert snapshot() == first


def test_rest_rows_polars(rest_origin):
    definition, files = rest_definition()
    definition["datasets"]["orders"]["transform"] = {
        "input": {
            "id": {"type": "bigint"},
            "total": {"type": "numeric"},
            "day": {"type": "date"},
            "tags": {"type": "text"},
        },
        "sql": "SELECT id, total * 2 AS total, day, upper(tags) AS tags FROM input",
    }
    r = runner.run_integration(definition, files, version_id=None, now=NOW)
    assert r.status == "succeeded", r.message
    assert r.rows["orders"]["path"] == "rows+polars"
    assert r.rows["orders"]["extracted"] == 3
    rows = ds_sql(
        f"SELECT id, total::float8, day::text, tags "
        f"FROM {ds_table('rest-prueba', 'orders')} ORDER BY id"
    )
    assert rows == [
        (1, 11.0, "2026-09-28", '["A"]'),
        (2, 14.0, "2026-09-28", "[]"),
        (3, 2.5, "2026-09-27", None),
    ]


def test_output_mismatch_fails_before_extraction(origin, monkeypatch):
    r = run()
    assert r.status == "succeeded", r.message
    before = lines()
    calls = {"copy": 0, "rows": 0}
    real_copy, real_rows = extract.pg_copy, extract.pg_rows

    def spy_copy(*a, **k):
        calls["copy"] += 1
        return real_copy(*a, **k)

    def spy_rows(*a, **k):
        calls["rows"] += 1
        yield from real_rows(*a, **k)

    monkeypatch.setattr(extract, "pg_copy", spy_copy)
    monkeypatch.setattr(extract, "pg_rows", spy_rows)
    definition, files = transformed(
        "SELECT document_id, line_no, line_kind, completed_at, local_date, product_code "
        "FROM input"
    )
    r = runner.run_integration(definition, files, version_id=None, kind="incremental", now=NOW)
    assert r.status == "failed"
    assert "no cumple columns" in r.message
    assert calls == {"copy": 0, "rows": 0}
    assert lines() == before


def _spill_left(path) -> list[str]:
    if not os.path.isdir(path):
        return []
    return os.listdir(path)


def test_whole_mode_equals_rows_mode(origin, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "transform_spill_dir", str(tmp_path / "spill"))
    definition, files = transformed()
    r = runner.run_integration(definition, files, version_id=None, kind="incremental", now=NOW)
    assert r.status == "succeeded", r.message
    snapshot_a = snapshot()

    definition, files = transformed(ROW_SQL + " ORDER BY document_id")
    r = runner.run_integration(definition, files, version_id=None, kind="full", now=NOW)
    assert r.status == "succeeded", r.message
    row = r.rows["sale_lines"]
    assert row["path"] == "copy+polars"
    assert row["transform_mode"] == "whole"
    assert row["rows_in"] == 4
    assert row["extracted"] == 4
    assert isinstance(row["transform_ms"], int)
    assert snapshot() == snapshot_a
    assert _spill_left(tmp_path / "spill") == []


def test_whole_mode_when_copy_refused(origin, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "transform_spill_dir", str(tmp_path / "spill"))
    definition, files = transformed()
    r = runner.run_integration(definition, files, version_id=None, kind="incremental", now=NOW)
    assert r.status == "succeeded", r.message
    snapshot_a = snapshot()

    def refuse(*a, **k):
        raise extract.BulkUnsupported("FeatureNotSupported")

    monkeypatch.setattr(extract, "pg_copy", refuse)
    definition, files = transformed(ROW_SQL + " ORDER BY document_id")
    r = runner.run_integration(definition, files, version_id=None, kind="full", now=NOW)
    assert r.status == "succeeded", r.message
    row = r.rows["sale_lines"]
    assert row["path"] == "rows+polars"
    assert row["fallback"] == "FeatureNotSupported"
    assert row["transform_mode"] == "whole"
    assert row["rows_in"] == 4
    assert row["extracted"] == 4
    assert snapshot() == snapshot_a
    assert _spill_left(tmp_path / "spill") == []


def test_whole_mode_aggregates_across_batches(tmp_path):
    ds = {
        "columns": {
            "k": {"type": "text"},
            "n": {"type": "bigint"},
            "total": {"type": "numeric"},
        },
        "transform": {
            "input": {"k": {"type": "text"}, "v": {"type": "numeric"}},
            "sql": "SELECT k, count(*) AS n, sum(v) AS total FROM input GROUP BY k",
        },
    }
    compiled = transform.compile(ds, TZ)
    assert compiled.mode == "whole"
    out = []
    sink = Sink(
        compiled,
        out.append,
        lambda: None,
        spill_dir=str(tmp_path),
        max_rows=1000,
        label="7-ds",
    )
    frame = pl.DataFrame({"k": ["a", "b", "a"], "v": ["1.5", "2", "3"]})
    sink.add(frame, escaped=True)
    sink.add(frame, escaped=True)
    sink.add(frame, escaped=True)

    before = _spill_left(tmp_path)
    assert len(before) == 1
    assert before[0].startswith("7-ds-")
    in_dir = os.path.join(tmp_path, before[0])
    in_files = sorted(os.listdir(in_dir))
    assert in_files == ["in-00000.arrow", "in-00001.arrow", "in-00002.arrow"]

    sink.finish()
    assert sink.rows_in == 9
    assert sink.rows_out == 2
    result = pl.concat(out).sort("k")
    assert result["k"].to_list() == ["a", "b"]
    assert result["n"].to_list() == [6, 3]
    assert Decimal(result["total"][0]) == Decimal("13.5")
    assert Decimal(result["total"][1]) == Decimal("6")
    assert _spill_left(tmp_path) == []


def test_whole_mode_empty_window(tmp_path):
    ds = {
        "columns": {
            "k": {"type": "text"},
            "n": {"type": "bigint"},
            "total": {"type": "numeric"},
        },
        "transform": {
            "input": {"k": {"type": "text"}, "v": {"type": "numeric"}},
            "sql": "SELECT k, count(*) AS n, sum(v) AS total FROM input GROUP BY k",
        },
    }
    compiled = transform.compile(ds, TZ)
    out = []
    sink = Sink(
        compiled,
        out.append,
        lambda: None,
        spill_dir=str(tmp_path),
        max_rows=1000,
        label="empty",
    )
    sink.finish()
    assert sink.rows_in == 0
    assert sink.rows_out == 0
    assert out == []
    assert _spill_left(tmp_path) == []


def test_whole_mode_max_rows(tmp_path):
    ds = {
        "columns": {
            "k": {"type": "text"},
            "n": {"type": "bigint"},
            "total": {"type": "numeric"},
        },
        "transform": {
            "input": {"k": {"type": "text"}, "v": {"type": "numeric"}},
            "sql": "SELECT k, count(*) AS n, sum(v) AS total FROM input GROUP BY k",
        },
    }
    compiled = transform.compile(ds, TZ)
    sink = Sink(
        compiled,
        lambda _: None,
        lambda: None,
        spill_dir=str(tmp_path),
        max_rows=5,
        label="max",
    )
    sink.add(pl.DataFrame({"k": ["a", "b", "a"], "v": ["1", "2", "3"]}), escaped=True)
    with pytest.raises(ExtractError, match="TRANSFORM_MAX_ROWS"):
        sink.add(pl.DataFrame({"k": ["a", "b", "a"], "v": ["1", "2", "3"]}), escaped=True)
    sink.close()
    assert _spill_left(tmp_path) == []


def test_whole_mode_max_rows_run(origin, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "transform_spill_dir", str(tmp_path / "spill"))
    monkeypatch.setattr(get_settings(), "transform_max_rows", 2)
    r = run()
    assert r.status == "succeeded", r.message
    before = lines()

    definition, files = transformed(ROW_SQL + " ORDER BY document_id")
    r = runner.run_integration(definition, files, version_id=None, kind="incremental", now=NOW)
    assert r.status == "failed"
    assert "TRANSFORM_MAX_ROWS" in r.message
    assert lines() == before
    assert _spill_left(tmp_path / "spill") == []


def test_whole_mode_stop_during_poll(tmp_path, monkeypatch):
    ds = {
        "columns": {
            "k": {"type": "text"},
            "n": {"type": "bigint"},
            "total": {"type": "numeric"},
        },
        "transform": {
            "input": {"k": {"type": "text"}, "v": {"type": "numeric"}},
            "sql": "SELECT k, count(*) AS n, sum(v) AS total FROM input GROUP BY k",
        },
    }
    compiled = transform.compile(ds, TZ)
    cancel_calls = []
    original_collect = pl.LazyFrame.collect

    def collect_wrapper(self, *a, **k):
        result = original_collect(self, *a, **k)
        if k.get("background"):
            real_cancel = result.cancel

            class Proxy:
                def cancel(self):
                    cancel_calls.append(1)
                    real_cancel()

                def fetch(self):
                    return result.fetch()

            return Proxy()
        return result

    monkeypatch.setattr(pl.LazyFrame, "collect", collect_wrapper)

    class Stop(Exception):
        pass

    check_calls = {"n": 0}
    written = []

    def stop_check():
        check_calls["n"] += 1
        if check_calls["n"] >= 2:
            raise Stop()

    sink = Sink(
        compiled,
        written.append,
        stop_check,
        spill_dir=str(tmp_path),
        max_rows=1000,
        label="poll",
    )
    sink.add(pl.DataFrame({"k": ["a"], "v": ["1"]}), escaped=True)
    with pytest.raises(Stop):
        sink.finish()
    assert cancel_calls == [1]
    assert written == []
    assert _spill_left(tmp_path) == []


def test_whole_mode_stop_during_poll_run(origin, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "transform_spill_dir", str(tmp_path / "spill"))
    r = run()
    assert r.status == "succeeded", r.message
    before = lines()

    original_finish = transform.Sink.finish
    state = {"finishing": False}

    def finish_wrapper(self):
        state["finishing"] = True
        return original_finish(self)

    monkeypatch.setattr(transform.Sink, "finish", finish_wrapper)

    class FakeStop:
        def __call__(self):
            if state["finishing"]:
                raise runner.RunStopped("Ana Admin")
            return None

    monkeypatch.setattr(runner, "StopFlag", lambda run_id: FakeStop())

    write_calls = {"n": 0}
    original_write = runner._CsvCopyOut.write

    def write_spy(self, frame):
        write_calls["n"] += 1
        return original_write(self, frame)

    monkeypatch.setattr(runner._CsvCopyOut, "write", write_spy)

    definition, files = transformed(ROW_SQL + " ORDER BY document_id")
    r = runner.run_integration(definition, files, version_id=None, kind="incremental", now=NOW)
    assert r.status == "stopped"
    assert r.message == "detenida por Ana Admin"
    assert write_calls["n"] == 0
    assert lines() == before
    assert _spill_left(tmp_path / "spill") == []


def test_sweep_spill_dir(tmp_path):
    spill = tmp_path / "spill"
    os.makedirs(spill)
    old = time.time() - 2 * 3600
    os.makedirs(spill / "a")
    with open(spill / "a" / "file.arrow", "w") as f:
        f.write("x")
    os.utime(spill / "a", (old, old))
    os.makedirs(spill / "b")
    os.utime(spill / "b", (old, old))
    with open(spill / "plain.txt", "w") as f:
        f.write("y")
    os.utime(spill / "plain.txt", (old, old))
    assert transform.sweep_spill_dir(str(spill)) == 3
    assert os.listdir(spill) == []
    assert transform.sweep_spill_dir(str(tmp_path / "missing")) == 0


def test_sweep_spill_dir_keeps_recent_folders(tmp_path):
    spill = tmp_path / "spill"
    os.makedirs(spill)
    old = time.time() - 2 * 3600
    os.makedirs(spill / "old-folder")
    os.utime(spill / "old-folder", (old, old))
    os.makedirs(spill / "run-1")
    with open(spill / "run-1" / "file.arrow", "w") as f:
        f.write("x")
    assert transform.sweep_spill_dir(str(spill)) == 1
    assert os.listdir(spill) == ["run-1"]
    assert os.listdir(spill / "run-1") == ["file.arrow"]
    assert transform.sweep_spill_dir(str(spill), now=time.time() + 7200) == 1
    assert os.listdir(spill) == []


def test_bounded_writer_psycopg_internals():
    import inspect

    from psycopg.copy import QueuedLibpqWriter
    from psycopg.generators import copy_to

    assert issubclass(runner._BoundedWriter, QueuedLibpqWriter)
    assert "worker" in vars(QueuedLibpqWriter)
    assert "write" in vars(QueuedLibpqWriter)
    assert "flush" in inspect.signature(copy_to).parameters

    with get_engine().connect() as conn:
        pg = conn.connection.driver_connection
        with pg.cursor() as cur:
            w = runner._BoundedWriter(cur)
            assert w._queue.maxsize == runner.COPY_QUEUE_ITEMS
            assert hasattr(w, "_pgconn")
            assert w._worker_error is None
            assert w.connection is pg
            assert hasattr(w, "_worker")
        pg.rollback()


def test_input_type_error(origin):
    r = run()
    assert r.status == "succeeded", r.message
    before = lines()
    bad_query = QUERY.replace("line AS line_no", "'x' || line AS line_no")
    assert bad_query != QUERY
    definition, files = transformed()
    files = copy.deepcopy(files)
    files["queries/lines.sql"] = bad_query
    r = runner.run_integration(definition, files, version_id=None, kind="incremental", now=NOW)
    assert r.status == "failed"
    assert "no cumple el tipo declarado" in r.message
    assert "line_no" in r.message
    assert lines() == before


def test_stop_between_transform_batches(origin, monkeypatch):
    r = run()
    assert r.status == "succeeded", r.message
    before = lines()
    definition, files = transformed(batch_rows=1)
    blocks = [
        copy_csv_line(document_id="Z1", line_no=1, line_kind="sale",
                      completed_at="2026-09-28 10:00:00-04", local_date="2026-09-28",
                      product_code="p1", net_amount="1"),
        copy_csv_line(document_id="Z2", line_no=1, line_kind="sale",
                      completed_at="2026-09-28 10:00:00-04", local_date="2026-09-28",
                      product_code="p2", net_amount="1"),
        copy_csv_line(document_id="Z3", line_no=1, line_kind="sale",
                      completed_at="2026-09-28 10:00:00-04", local_date="2026-09-28",
                      product_code="p3", net_amount="1"),
    ]
    fake_copy = _FakeCopy(blocks)
    monkeypatch.setattr(extract, "pg_copy", fake_copy)
    copy_calls = {"n": 0}
    real_write = runner._CsvCopyOut.write

    def spy_write(self, frame):
        copy_calls["n"] += 1
        return real_write(self, frame)

    monkeypatch.setattr(runner._CsvCopyOut, "write", spy_write)

    class FakeStop:
        def __init__(self):
            self.calls = 0

        def __call__(self):
            self.calls += 1
            if self.calls == 3:
                raise runner.RunStopped("Ana Admin")

    fake = FakeStop()
    monkeypatch.setattr(runner, "StopFlag", lambda run_id: fake)
    r = runner.run_integration(definition, files, version_id=None, kind="incremental", now=NOW)
    assert r.status == "stopped"
    assert r.message == "detenida por Ana Admin"
    assert fake.calls == 3
    assert copy_calls["n"] == 2
    assert lines() == before


def test_preview_runs_transform(origin):
    definition, files = transformed()
    sid = 990_001
    try:
        r = runner.run_preview(definition, files, session_id=sid, now=NOW)
        assert r["status"] == "succeeded", r["message"]
        assert r["datasets"]["sale_lines"]["rows"] == 3
        with datasets.preview_schemas(datasets.preview_prefix(sid)):
            rows = ds_sql(
                f"SELECT product_code FROM {ds_table('ventas-prueba', 'sale_lines')}"
            )
            assert rows
            assert all(value == value.upper() for (value,) in rows)
    finally:
        with datasets.preview_schemas(datasets.preview_prefix(sid)):
            with get_engine().begin() as conn:
                datasets.drop_integration(conn.connection.driver_connection, "ventas-prueba")
