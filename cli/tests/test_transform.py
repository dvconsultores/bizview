"""Tests for integration transform SQL checking and output-column validation.

Covers sqlsafety.check_transform refusals/regeneration and transform.check_output schema
comparison, plus validate() integration behaviour with and without Polars installed.
"""
import sys
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
import sqlglot
import yaml
from sqlglot import exp

from bizview_cli import sqlsafety, transform
from bizview_cli.validate import validate
from tests.conftest import write

pl = pytest.importorskip("polars")

TZ = "America/Caracas"
INPUT = {
    "t": {"type": "text"},
    "i": {"type": "integer"},
    "b": {"type": "bigint"},
    "n": {"type": "numeric"},
    "f": {"type": "boolean"},
    "d": {"type": "date"},
    "ts": {"type": "timestamptz"},
}
TYPES = {k: v["type"] for k, v in INPUT.items()}


def run(sql, rows=None):
    """Check, regenerate, and optionally execute a transform over a typed frame."""
    check = sqlsafety.check_transform(sql, TYPES)
    assert not check.problems, check.problems
    assert check.sql is not None
    if rows is None:
        frame = transform.empty_frame(INPUT, TZ)
    else:
        frame = pl.DataFrame([rows], schema=transform.input_schema(INPUT, TZ), orient="row")
    result = pl.SQLContext(input=frame.lazy()).execute(check.sql).collect()
    return check, result


ALLOWED = [
    ("abs n", "SELECT abs(n) AS x FROM input"),
    ("ceil n", "SELECT ceil(n) AS x FROM input"),
    ("floor n", "SELECT floor(n) AS x FROM input"),
    ("round n", "SELECT round(n, 2) AS x FROM input"),
    ("sign i", "SELECT sign(i) AS x FROM input"),
    ("sqrt b", "SELECT sqrt(b) AS x FROM input"),
    ("power b", "SELECT power(b, 2) AS x FROM input"),
    ("ln b", "SELECT ln(b) AS x FROM input"),
    ("exp i", "SELECT exp(i) AS x FROM input"),
    ("greatest", "SELECT greatest(i, b) AS x FROM input"),
    ("least", "SELECT least(i, b) AS x FROM input"),
    ("mod", "SELECT mod(i, 2) AS x FROM input"),
    ("mod pct", "SELECT i % 2 AS x FROM input"),
    ("coalesce", "SELECT coalesce(t, 'x') AS x FROM input"),
    ("ifnull", "SELECT ifnull(t, 'x') AS x FROM input"),
    ("nullif", "SELECT nullif(i, 3) AS x FROM input"),
    ("if", "SELECT if(i > 1, 1, 2) AS x FROM input"),
    ("case", "SELECT CASE WHEN i > 1 THEN 'a' ELSE 'b' END AS x FROM input"),
    ("lower", "SELECT lower(t) AS x FROM input"),
    ("upper", "SELECT upper(t) AS x FROM input"),
    ("trim", "SELECT trim(t) AS x FROM input"),
    ("ltrim", "SELECT ltrim(t) AS x FROM input"),
    ("rtrim", "SELECT rtrim(t) AS x FROM input"),
    ("length", "SELECT length(t) AS x FROM input"),
    ("char length", "SELECT char_length(t) AS x FROM input"),
    ("concat", "SELECT concat(t, 'x') AS x FROM input"),
    ("concat ws", "SELECT concat_ws(',', t, 'x') AS x FROM input"),
    ("left", "SELECT left(t, 2) AS x FROM input"),
    ("right", "SELECT right(t, 2) AS x FROM input"),
    ("substring", "SELECT substring(t, 1, 2) AS x FROM input"),
    ("substr", "SELECT substr(t, 1, 2) AS x FROM input"),
    ("replace", "SELECT replace(t, 'a', 'b') AS x FROM input"),
    ("split part", "SELECT split_part(t, ',', 1) AS x FROM input"),
    ("strpos", "SELECT strpos(t, 'l') AS x FROM input"),
    ("starts with", "SELECT starts_with(t, 'H') AS x FROM input"),
    ("ends with", "SELECT ends_with(t, 'w') AS x FROM input"),
    ("initcap", "SELECT initcap(t) AS x FROM input"),
    ("reverse", "SELECT reverse(t) AS x FROM input"),
    ("regexp like", "SELECT regexp_like(t, 'l+') AS x FROM input"),
    ("lpad", "SELECT lpad(t, 10, '0') AS x FROM input"),
    ("rpad", "SELECT rpad(t, 10, '0') AS x FROM input"),
    ("concat op", "SELECT t || 'x' AS x FROM input"),
    ("like", "SELECT t LIKE 'H%' AS x FROM input"),
    ("ilike", "SELECT t ILIKE 'h%' AS x FROM input"),
    ("extract year", "SELECT extract(year FROM d) AS x FROM input"),
    ("date part", "SELECT date_part('month', d) AS x FROM input"),
    ("extract hour", "SELECT extract(hour FROM ts) AS x FROM input"),
    ("strftime", "SELECT strftime(ts, '%Y-%m-%d') AS x FROM input"),
    ("strptime", "SELECT strptime(t, '%Y-%m-%d') AS x FROM input"),
    ("cast bigint", "SELECT CAST(i AS BIGINT) AS x FROM input"),
    ("cast op", "SELECT i::text AS x FROM input"),
    ("try cast", "SELECT TRY_CAST(t AS INT) AS x FROM input"),
    ("cast decimal", "SELECT CAST(n AS DECIMAL(38, 9)) AS x FROM input"),
    ("cast strftime", "SELECT CAST(strftime(ts, '%Y-%m-%d') AS DATE) AS x FROM input"),
    ("interval", "SELECT d + INTERVAL '1 day' AS x FROM input"),
    ("between", "SELECT i BETWEEN 1 AND 5 AS x FROM input"),
    ("in", "SELECT i IN (1, 2, -3) AS x FROM input"),
    ("is null", "SELECT t IS NULL AS x FROM input"),
    ("not", "SELECT NOT f AS x FROM input"),
    ("neg", "SELECT -i AS x FROM input"),
    ("mixed bool", "SELECT f AND TRUE OR i > 0 AS x FROM input"),
]

WHOLE = [
    ("group by", "SELECT t, sum(n) AS s FROM input GROUP BY t"),
    ("group count", "SELECT t, count(*) AS c FROM input GROUP BY t"),
    ("count distinct", "SELECT count(DISTINCT i) AS c FROM input"),
    ("group avg", "SELECT t, avg(n) AS a FROM input GROUP BY t"),
    ("group min max", "SELECT t, min(i) AS mi, max(i) AS ma FROM input GROUP BY t"),
    ("having", "SELECT t, sum(n) AS s FROM input GROUP BY t HAVING sum(n) > 0"),
    ("distinct", "SELECT DISTINCT t FROM input"),
    ("order nulls", "SELECT t, i FROM input ORDER BY i DESC NULLS LAST"),
    ("row number", "SELECT row_number() OVER (PARTITION BY t ORDER BY i) AS x FROM input"),
    ("rank", "SELECT rank() OVER (PARTITION BY t ORDER BY i) AS x FROM input"),
    ("dense rank", "SELECT dense_rank() OVER (PARTITION BY t ORDER BY i) AS x FROM input"),
    ("lag", "SELECT lag(i) OVER (PARTITION BY t ORDER BY i) AS x FROM input"),
    ("lead", "SELECT lead(i) OVER (PARTITION BY t ORDER BY i) AS x FROM input"),
    ("first value", "SELECT first_value(i) OVER (PARTITION BY t ORDER BY i) AS x FROM input"),
    ("last value", "SELECT last_value(i) OVER (PARTITION BY t ORDER BY i) AS x FROM input"),
    ("sum over", "SELECT sum(n) OVER (PARTITION BY t) AS x FROM input"),
    ("qualify", "SELECT t, row_number() OVER (PARTITION BY t ORDER BY i) AS n FROM input "
                "QUALIFY n = 1"),
    ("agg no group", "SELECT sum(n) AS s FROM input"),
]

ROWS = [
    ("projection", "SELECT t, i FROM input"),
    ("where", "SELECT t FROM input WHERE i > 0"),
    ("case rows", "SELECT CASE WHEN i > 1 THEN t ELSE 'x' END AS x FROM input"),
    ("cte chain", "WITH a AS (SELECT t AS y, i FROM input WHERE i > 0), "
                  "b AS (SELECT y FROM a) SELECT y FROM b"),
    ("table alias", "SELECT x.t FROM input AS x WHERE x.i > 1"),
    ("star", "SELECT * FROM input"),
]

REFUSED = [
    ("read csv", "SELECT * FROM read_csv('/etc/passwd')"),
    ("read parquet", "SELECT * FROM read_parquet('/etc/passwd')"),
    ("read json", "SELECT * FROM read_json('/etc/passwd')"),
    ("read ipc", "SELECT * FROM read_ipc('/etc/passwd')"),
    ("table func join", "SELECT * FROM input, read_csv('/etc/passwd')"),
    ("join", "SELECT t FROM input a JOIN input b ON TRUE"),
    ("comma join", "SELECT t FROM input, input"),
    ("union", "SELECT t FROM input UNION SELECT t FROM input"),
    ("scalar subquery", "SELECT (SELECT 1) AS x FROM input"),
    ("in subquery", "SELECT t FROM input WHERE i IN (SELECT i FROM input)"),
    ("exists", "SELECT t FROM input WHERE EXISTS (SELECT 1 FROM input)"),
    ("derived table", "SELECT * FROM (SELECT * FROM input) AS s"),
    ("limit", "SELECT t FROM input LIMIT 1"),
    ("offset", "SELECT t FROM input OFFSET 1"),
    ("fetch", "SELECT t FROM input FETCH FIRST 1 ROWS ONLY"),
    ("placeholder", "SELECT t FROM input WHERE i = $1"),
    ("named param", "SELECT t FROM input WHERE i = :x"),
    ("qualified table", "SELECT t FROM public.input"),
    ("qualified column", "SELECT a.b.t FROM input"),
    ("unknown table", "SELECT t FROM other"),
    ("unknown func", "SELECT foo(t) AS x FROM input"),
    ("date trunc", "SELECT date_trunc('month', d) AS x FROM input"),
    ("now", "SELECT now() AS x FROM input"),
    ("random", "SELECT random() AS x FROM input"),
    ("md5", "SELECT md5(t) AS x FROM input"),
    ("current date", "SELECT current_date AS x FROM input"),
    ("filter", "SELECT sum(n) FILTER (WHERE i > 0) AS s FROM input"),
    ("values", "SELECT * FROM (VALUES (1)) AS v(a)"),
    ("recursive", "WITH RECURSIVE r AS (SELECT t FROM input) SELECT t FROM r"),
    ("self cte", "WITH a AS (SELECT t FROM a) SELECT t FROM a"),
    ("into", "SELECT t INTO z FROM input"),
    ("window frame", "SELECT sum(n) OVER (ORDER BY i ROWS BETWEEN 1 PRECEDING AND "
                     "CURRENT ROW) AS x FROM input"),
    ("no from", "SELECT 1 AS x"),
    ("two statements", "SELECT t FROM input; SELECT 1"),
    ("insert", "INSERT INTO input SELECT * FROM input"),
    ("tablesample", "SELECT t FROM input TABLESAMPLE SYSTEM (10)"),
    ("array", "SELECT ARRAY[1, 2] AS x FROM input"),
    ("json op", "SELECT t->>'a' AS x FROM input"),
    ("distinct on", "SELECT DISTINCT ON (t) t FROM input"),
    ("cast json", "SELECT CAST(t AS JSON) AS x FROM input"),
    ("windowless row number", "SELECT row_number() AS x FROM input"),
    ("alias columns", "SELECT t FROM input AS x(a)"),
    ("pg read file", "SELECT pg_read_file('/etc/passwd') AS x FROM input"),
    ("token error", "SELECT 'x\\'' || t AS z FROM input"),
    ("unknown column", "SELECT nope FROM input"),
]


def _as_problems(sql):
    check = sqlsafety.check_transform(sql, TYPES)
    assert check.problems, sql
    assert check.mode is None
    assert check.sql is None
    for p in check.problems:
        assert p.code in {"unsafe_sql", "invalid_reference"}
    return check


def _setup_transform(ws, transform_values):
    path = ws / "integrations/ventas/integration.yaml"
    with path.open() as f:
        data = yaml.safe_load(f)
    data["datasets"]["products"]["transform"] = transform_values
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    return data


class TestAllowed:
    @pytest.mark.parametrize("sql", [s for _, s in ALLOWED],
                             ids=[i for i, _ in ALLOWED])
    def test_allowed(self, sql):
        run(sql)

    def test_functions_coverage(self):
        seen = set()
        for _, s in ALLOWED + WHOLE:
            tree = sqlglot.parse_one(s, read="postgres")
            for node in tree.walk():
                if isinstance(node, exp.Func) and not isinstance(node, exp.And | exp.Or):
                    seen.add(sqlsafety._function_name(node))
        assert sqlsafety.TRANSFORM_FUNCTIONS <= seen


class TestWholeRows:
    @pytest.mark.parametrize("sql", [s for _, s in WHOLE], ids=[i for i, _ in WHOLE])
    def test_whole(self, sql):
        check, _ = run(sql)
        assert check.mode == "whole"

    @pytest.mark.parametrize("sql", [s for _, s in ROWS], ids=[i for i, _ in ROWS])
    def test_rows(self, sql):
        check, _ = run(sql)
        assert check.mode == "rows"


class TestTryCast:
    def test_survives_regeneration(self):
        check, result = run("SELECT TRY_CAST(t AS INT) AS x FROM input",
                            rows=["abc", 1, 2, Decimal("2.5"), True,
                                  datetime(2024, 1, 1).date(),
                                  datetime(2024, 1, 2, 23, 0, tzinfo=ZoneInfo(TZ))])
        assert "TRY_CAST(" in check.sql
        assert result["x"][0] is None


class TestLiteralRoundTrip:
    def test_strings_and_quoted_identifier(self):
        raw = "SELECT 'a\\' AS a, 'it''s' AS b, '\\n' AS c, t AS \"we\"\"ird\" FROM input"
        _, result = run(raw, rows=["ok", 1, 2, Decimal("2.5"), True,
                                       datetime(2024, 1, 1).date(),
                                       datetime(2024, 1, 2, 23, 0, tzinfo=ZoneInfo(TZ))])
        assert result.columns == ["a", "b", "c", 'we"ird']
        assert result["a"][0] == "a\\"
        assert result["b"][0] == "it's"
        assert result["c"][0] == "\\n"


class TestRefused:
    @pytest.mark.parametrize("sql", [s for _, s in REFUSED], ids=[i for i, _ in REFUSED])
    def test_refused(self, sql):
        _as_problems(sql)

    def test_specific_messages(self):
        cases = [
            ("SELECT * FROM read_csv('/etc/passwd')", "funciones de tabla"),
            ("SELECT t FROM input a JOIN input b ON TRUE", "JOIN"),
            ("SELECT t FROM input LIMIT 1", "LIMIT"),
            ("SELECT date_trunc('month', d) AS x FROM input", "no disponible en el motor"),
        ]
        for sql, fragment in cases:
            check = _as_problems(sql)
            assert any(fragment in p.message for p in check.problems)

    def test_why_it_matters(self, tmp_path):
        csv = tmp_path / "secret.csv"
        csv.write_text("secret\nclassified\n")
        raw = f"SELECT * FROM read_csv('{csv}')"
        result = pl.SQLContext().execute(raw).collect()
        assert "secret" in result.columns
        assert result["secret"][0] == "classified"
        _as_problems(raw)


def _check(sql):
    return sqlsafety.check_transform(sql, TYPES)


def _checked(sql):
    check = _check(sql)
    assert not check.problems
    return check


class TestOutputComparison:
    def test_missing_and_extra(self):
        check = _checked("SELECT t FROM input")
        problems = transform.check_output(check, INPUT, {"t": {"type": "text"},
                                                         "i": {"type": "integer"}}, TZ)
        assert len(problems) == 1
        assert problems[0].code == "transform_mismatch"
        assert problems[0].message == "faltan columnas en la salida de la transformación: i"

    def test_extra(self):
        check = _checked("SELECT * FROM input")
        problems = transform.check_output(check, INPUT, {"t": {"type": "text"}}, TZ)
        assert len(problems) == 1
        assert problems[0].code == "transform_mismatch"
        assert (problems[0].message ==
                "la transformación produce columnas no declaradas en columns: b, d, f, i, n, ts")

    def test_type_mismatch(self):
        check = _checked("SELECT length(t) AS x FROM input")
        problems = transform.check_output(check, INPUT, {"x": {"type": "integer"}}, TZ)
        assert len(problems) == 1
        assert problems[0].code == "transform_mismatch"
        assert problems[0].column == "x"
        problems = transform.check_output(check, INPUT, {"x": {"type": "bigint"}}, TZ)
        assert not problems

    def test_float_warning(self):
        check = _checked("SELECT sqrt(n) AS x FROM input")
        problems = transform.check_output(check, INPUT, {"x": {"type": "numeric"}}, TZ)
        assert len(problems) == 1
        assert problems[0].code == "transform_float"
        assert problems[0].level == "warning"
        check2 = _checked("SELECT CAST(sqrt(n) AS DECIMAL(38, 9)) AS x FROM input")
        assert not transform.check_output(check2, INPUT, {"x": {"type": "numeric"}}, TZ)

    @pytest.mark.parametrize("sql, columns", [
        ("SELECT CAST(ts AS DATE) AS x FROM input", {"x": {"type": "date"}}),
        ("WITH a AS (SELECT ts::date AS x FROM input) SELECT x FROM a",
         {"x": {"type": "date"}}),
        ("SELECT t, CAST(max(ts) AS DATE) AS x FROM input GROUP BY t",
         {"t": {"type": "text"}, "x": {"type": "date"}}),
    ])
    def test_tz_date(self, sql, columns):
        check = _checked(sql)
        problems = transform.check_output(check, INPUT, columns, TZ)
        assert [p for p in problems if p.code == "transform_tz_date"]
        assert any("strftime" in p.fix for p in problems if p.code == "transform_tz_date")

    def test_tz_date_semantics(self):
        row = ["ok", 1, 2, Decimal("2.5"), True, datetime(2024, 1, 1).date(),
               datetime(2024, 1, 2, 23, 0, tzinfo=ZoneInfo(TZ))]
        _, r1 = run("SELECT CAST(ts AS DATE) AS x FROM input", rows=row)
        _, r2 = run("SELECT CAST(strftime(ts, '%Y-%m-%d') AS DATE) AS x FROM input", rows=row)
        assert r1["x"][0] == datetime(2024, 1, 3).date()
        assert r2["x"][0] == datetime(2024, 1, 2).date()

    def test_no_tz_date_problem_for_date_and_strftime(self):
        check = _checked("SELECT CAST(d AS DATE) AS x FROM input")
        assert not transform.check_output(check, INPUT, {"x": {"type": "date"}}, TZ)
        check2 = _checked("SELECT CAST(strftime(ts, '%Y-%m-%d') AS DATE) AS x FROM input")
        assert not transform.check_output(check2, INPUT, {"x": {"type": "date"}}, TZ)

    def test_accepted(self):
        naive = _checked("SELECT strptime(t, '%Y-%m-%d') AS x FROM input")
        assert not transform.check_output(naive, INPUT, {"x": {"type": "timestamptz"}}, TZ)
        aware = _checked("SELECT ts AS x FROM input")
        assert not transform.check_output(aware, INPUT, {"x": {"type": "timestamptz"}}, TZ)
        nullcol = _checked("SELECT NULL AS x FROM input")
        for contract in ("text", "integer", "bigint", "numeric", "boolean", "date",
                         "timestamptz"):
            assert not transform.check_output(nullcol, INPUT, {"x": {"type": contract}}, TZ)
        countbig = _checked("SELECT count(*) AS x FROM input")
        assert not transform.check_output(countbig, INPUT, {"x": {"type": "bigint"}}, TZ)
        countnum = _checked("SELECT count(*) AS x FROM input")
        assert not transform.check_output(countnum, INPUT, {"x": {"type": "numeric"}}, TZ)
        dec = _checked("SELECT n AS x FROM input")
        assert not transform.check_output(dec, INPUT, {"x": {"type": "numeric"}}, TZ)

    def test_transform_invalid(self):
        check = _checked("SELECT t + i AS x FROM input")
        problems = transform.check_output(check, INPUT, {"x": {"type": "text"}}, TZ)
        assert len(problems) == 1
        assert problems[0].code == "transform_invalid"


class TestNoPolars:
    def test_check_output_unchecked(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "polars", None)
        assert not transform.available()
        check = _checked("SELECT t FROM input")
        problems = transform.check_output(check, INPUT, {"t": {"type": "text"}}, TZ)
        assert len(problems) == 1
        assert problems[0].code == "transform_unchecked"
        assert problems[0].level == "warning"
        assert "bizview-cli[transform]" in problems[0].fix

    def test_input_schema_raises(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "polars", None)
        with pytest.raises(RuntimeError) as exc:
            transform.input_schema(INPUT, TZ)
        assert "bizview-cli[transform]" in str(exc.value)

    def test_check_transform_works(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "polars", None)
        assert not _check("SELECT t FROM input").problems

    def test_validate_without_polars(self, ws, monkeypatch):
        monkeypatch.setitem(sys.modules, "polars", None)
        _setup_transform(ws, {
            "input": {"product_code": {"type": "text"}, "name": {"type": "text"}},
            "sql": "SELECT product_code, upper(name) AS name FROM input",
        })
        result = validate(ws)
        unchecked = [i for i in result.issues if i.code == "transform_unchecked"]
        assert len(unchecked) == 1
        assert unchecked[0].level == "warning"
        assert result.ok


class TestValidateIntegration:
    def _add_transform(self, ws, transform_values):
        _setup_transform(ws, transform_values)

    def test_valid(self, ws):
        self._add_transform(ws, {
            "input": {"product_code": {"type": "text"}, "name": {"type": "text"}},
            "sql": "SELECT product_code, upper(name) AS name FROM input",
        })
        result = validate(ws)
        assert result.ok
        assert not [i for i in result.issues if i.code.startswith("transform_")]

    def test_mismatch(self, ws):
        self._add_transform(ws, {
            "input": {"product_code": {"type": "text"}, "name": {"type": "text"}},
            "sql": "SELECT product_code FROM input",
        })
        result = validate(ws)
        problems = [i for i in result.issues if i.code == "transform_mismatch"]
        assert len(problems) == 1
        assert problems[0].file == "integrations/ventas/integration.yaml"
        assert problems[0].path == "/datasets/products/transform/sql"
        assert problems[0].expected == {"columns": {"product_code": "text", "name": "text"}}
        assert problems[0].fix

    def test_unsafe(self, ws):
        self._add_transform(ws, {
            "input": {"product_code": {"type": "text"}, "name": {"type": "text"}},
            "sql": "SELECT * FROM read_csv('/etc/passwd')",
        })
        result = validate(ws)
        problems = [i for i in result.issues if i.code == "unsafe_sql"]
        assert problems
        assert not result.ok

    def test_float(self, ws):
        data = _setup_transform(ws, {
            "input": {"product_code": {"type": "text"}, "name": {"type": "text"},
                      "price": {"type": "numeric"}},
            "sql": "SELECT product_code, name, sqrt(price) AS price FROM input",
        })
        data["datasets"]["products"]["columns"]["price"] = {"type": "numeric"}
        with (ws / "integrations/ventas/integration.yaml").open("w") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
        result = validate(ws)
        floats = [i for i in result.issues if i.code == "transform_float"]
        assert len(floats) == 1
        assert floats[0].level == "warning"
        assert result.ok

    @pytest.mark.parametrize("batch_rows, expect_error", [
        (9999, True),
        (1000001, True),
        (10000, False),
        (1000000, False),
    ])
    def test_batch_rows_bounds(self, ws, batch_rows, expect_error):
        self._add_transform(ws, {
            "input": {"product_code": {"type": "text"}, "name": {"type": "text"}},
            "sql": "SELECT product_code, name FROM input",
            "batch_rows": batch_rows,
        })
        result = validate(ws)
        assert any(i.code == "schema_error" for i in result.issues) is expect_error

    def test_missing_input(self, ws):
        self._add_transform(ws, {
            "sql": "SELECT product_code, name FROM input",
        })
        result = validate(ws)
        assert any(i.code == "schema_error" for i in result.issues)

    def test_empty_sql(self, ws):
        self._add_transform(ws, {
            "input": {"product_code": {"type": "text"}, "name": {"type": "text"}},
            "sql": "",
        })
        result = validate(ws)
        assert any(i.code == "schema_error" for i in result.issues)

    def test_unknown_key(self, ws):
        self._add_transform(ws, {
            "input": {"product_code": {"type": "text"}, "name": {"type": "text"}},
            "sql": "SELECT product_code, name FROM input",
            "unknown": True,
        })
        result = validate(ws)
        assert any(i.code == "schema_error" for i in result.issues)

    def test_request_fields(self, ws):
        path = ws / "integrations/ventas/integration.yaml"
        data = yaml.safe_load(path.read_text())
        data["datasets"]["products"]["extract"] = {"request": "requests/products.yaml"}
        data["datasets"]["products"]["transform"] = {
            "input": {"product_code": {"type": "text"}, "name": {"type": "text"}},
            "sql": "SELECT product_code, name FROM input",
        }
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
        write(ws, "integrations/ventas/requests/products.yaml",
              "path: 'items'\nrecords: $.items\n"
              "fields: {product_code: code, name: name}\n")
        assert not [i for i in validate(ws).issues if i.code == "invalid_reference"]
        # Re-run with an extra field that is not in transform.input.
        write(ws, "integrations/ventas/requests/products.yaml",
              "path: 'items'\nrecords: $.items\n"
              "fields: {product_code: code, name: name, extra: x}\n")
        result = validate(ws)
        bad = [i for i in result.issues if i.code == "invalid_reference" and
               "transform.input" in i.message]
        assert bad
