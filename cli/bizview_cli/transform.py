"""Output-column validation for integration transforms (feature 005 amendment 2026-10-08).

Shared by `bizview validate`, the backend engine and the assistant (FR-A02/FR-A05).
The SQL has already been validated by :mod:`bizview_cli.sqlsafety`; this module checks the
output schema that Polars produces against the dataset's declared `columns`.
"""
from dataclasses import dataclass
from importlib import import_module

import sqlglot
from sqlglot import exp

from bizview_cli import sqlsafety

INSTALL_HINT = "instala bizview-cli[transform] (pip install 'bizview-cli[transform]')"
INPUT_DECIMAL = (38, 9)

PG_CAST = {
    "text": "TEXT",
    "integer": "INTEGER",
    "bigint": "BIGINT",
    "numeric": "DECIMAL(38, 9)",
    "boolean": "BOOLEAN",
    "date": "DATE",
    "timestamptz": "TIMESTAMPTZ",
}


@dataclass(frozen=True)
class TransformProblem:
    code: str  # transform_invalid | transform_mismatch | transform_float |
               # transform_tz_date | transform_unchecked
    message: str  # Spanish
    level: str = "error"  # error | warning
    column: str | None = None
    fix: str | None = None


class TransformError(Exception):
    """Polars refused the transform on the empty typed frame."""


def load_polars():
    """Return the polars module, or None when it is not installed."""
    try:
        return import_module("polars")
    except ImportError:
        return None


def available() -> bool:
    return load_polars() is not None


def input_schema(input_cols: dict[str, dict], tz: str) -> dict:
    """Map `transform.input` columns to Polars dtypes."""
    pl = load_polars()
    if pl is None:
        raise RuntimeError(INSTALL_HINT)
    schema: dict = {}
    for name, col in input_cols.items():
        dtype = col["type"]
        if dtype == "text":
            schema[name] = pl.String
        elif dtype == "integer":
            schema[name] = pl.Int32
        elif dtype == "bigint":
            schema[name] = pl.Int64
        elif dtype == "numeric":
            schema[name] = pl.Decimal(*INPUT_DECIMAL)
        elif dtype == "boolean":
            schema[name] = pl.Boolean
        elif dtype == "date":
            schema[name] = pl.Date
        elif dtype == "timestamptz":
            schema[name] = pl.Datetime("us", tz)
        else:
            raise ValueError(f"tipo de entrada desconocido: {dtype}")
    return schema


def empty_frame(input_cols: dict[str, dict], tz: str):
    """Build a zero-row frame with the declared input schema."""
    pl = load_polars()
    if pl is None:
        raise RuntimeError(INSTALL_HINT)
    return pl.DataFrame(schema=input_schema(input_cols, tz))


def _first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:300]
    return str(text)[:300]


def infer(check, input_cols: dict[str, dict], tz: str) -> dict:
    """Return the output schema (name -> dtype) that Polars computes for the transform."""
    if check.sql is None:
        raise ValueError("check.sql no está disponible")
    pl = load_polars()
    if pl is None:
        raise RuntimeError(INSTALL_HINT)
    try:
        frame = empty_frame(input_cols, tz)
        lazies = pl.SQLContext(input=frame.lazy()).execute(check.sql)
        return dict(lazies.collect_schema())
    except Exception as e:
        raise TransformError(_first_line(str(e))) from e


def dtype_name(dtype) -> str:
    return str(dtype)


def accepts(contract_type: str, dtype) -> str | None:
    """Return "ok", "float" (numeric only, warning), or None (mismatch)."""
    pl = load_polars()
    base = dtype.base_type()
    if base is pl.Null:
        return "ok"
    if contract_type == "text":
        return "ok" if base is pl.String else None
    if contract_type == "integer":
        return "ok" if base in {pl.Int8, pl.Int16, pl.Int32, pl.UInt8, pl.UInt16} else None
    if contract_type == "bigint":
        return "ok" if base in {pl.Int8, pl.Int16, pl.Int32, pl.Int64,
                                pl.UInt8, pl.UInt16, pl.UInt32} else None
    if contract_type == "numeric":
        if base in {pl.Float32, pl.Float64}:
            return "float"
        if base in {pl.Decimal, pl.Int8, pl.Int16, pl.Int32, pl.Int64,
                    pl.UInt8, pl.UInt16, pl.UInt32}:
            return "ok"
        return None
    if contract_type == "boolean":
        return "ok" if base is pl.Boolean else None
    if contract_type == "date":
        return "ok" if base is pl.Date else None
    if contract_type == "timestamptz":
        return "ok" if base is pl.Datetime else None
    return None


def compare(inferred: dict, columns: dict[str, dict]) -> list[TransformProblem]:
    """Compare inferred output dtypes with the declared stored-column contract."""
    problems: list[TransformProblem] = []
    missing = sorted(c for c in columns if c not in inferred)
    if missing:
        problems.append(TransformProblem(
            "transform_mismatch",
            f"faltan columnas en la salida de la transformación: {', '.join(missing)}",
            column=None,
            fix="añade al SELECT las columnas declaradas en columns (con AS <nombre>)",
        ))
    extra = sorted(c for c in inferred if c not in columns)
    if extra:
        problems.append(TransformProblem(
            "transform_mismatch",
            f"la transformación produce columnas no declaradas en columns: {', '.join(extra)}",
            column=None,
            fix="decláralas en columns o quítalas del SELECT",
        ))
    for col, d in inferred.items():
        if col not in columns:
            continue
        contract = columns[col]["type"]
        verdict = accepts(contract, d)
        if verdict is None:
            problems.append(TransformProblem(
                "transform_mismatch",
                f"la columna {col} sale como {dtype_name(d)} y columns declara {contract}",
                column=col,
                fix=f"convierte con CAST(<expresión> AS {PG_CAST[contract]})",
            ))
        elif verdict == "float":
            problems.append(TransformProblem(
                "transform_float",
                f"la columna {col} sale como {dtype_name(d)} (coma flotante) "
                f"y columns declara numeric",
                level="warning",
                column=col,
                fix="usa CAST(<expresión> AS DECIMAL(38, 9))",
            ))
    return problems


def tz_date_problems(check, input_cols: dict[str, dict], tz: str) -> list[TransformProblem]:
    """Warn when CAST(timestamptz AS DATE) would use UTC instead of the local date."""
    pl = load_polars()
    if check.sql is None or pl is None:
        return []
    try:
        root = sqlglot.parse_one(check.sql, read=sqlsafety.PolarsSQL)
    except Exception:
        return []
    try:
        context = pl.SQLContext(input=empty_frame(input_cols, tz).lazy())
    except Exception:
        return []
    problems: list[TransformProblem] = []
    seen_messages: set[str] = set()
    for node in root.walk():
        if not isinstance(node, exp.Cast | exp.TryCast):
            continue
        if node.to.this != exp.DataType.Type.DATE:
            continue
        scope = node.find_ancestor(exp.Select)
        if scope is None:
            continue
        operand_has_agg = any(n for n in node.this.walk() if isinstance(n, exp.AggFunc))
        probe = scope.copy()
        probe.set("expressions", [exp.alias_(node.this.copy(), "__probe", quoted=True)])
        probe.set("order", None)
        probe.set("qualify", None)
        probe.set("having", None)
        probe.set("distinct", None)
        if not operand_has_agg:
            probe.set("group", None)
        if scope is not root:
            root_with = root.args.get("with_")
            if root_with is not None:
                probe.set("with_", root_with.copy())
        try:
            result = context.execute(probe.sql(dialect=sqlsafety.PolarsSQL, identify=True))
            dtype = dict(result.collect_schema()).get("__probe")
        except Exception:  # infer reports the real error
            continue
        if dtype is None or dtype.base_type() is not pl.Datetime:
            continue
        if dtype.time_zone is None:
            continue
        operand_sql = node.this.sql(dialect=sqlsafety.PolarsSQL)
        message = (f"CAST(… AS DATE) de un timestamptz usa la fecha UTC, no la local: "
                   f"{operand_sql}")
        if message in seen_messages:
            continue
        seen_messages.add(message)
        problems.append(TransformProblem(
            "transform_tz_date",
            message,
            column=None,
            fix=f"usa CAST(strftime({operand_sql}, '%Y-%m-%d') AS DATE)",
        ))
    return problems


def check_output(check, input_cols: dict[str, dict], columns: dict[str, dict],
                 tz: str) -> list[TransformProblem]:
    """Run the previously checked transform on the empty frame and compare outputs."""
    if not available():
        return [TransformProblem(
            "transform_unchecked",
            "no se comprobó la salida de la transformación: Polars no está instalado "
            "(el servidor la comprobará)",
            level="warning",
            fix=INSTALL_HINT,
        )]
    try:
        inferred = infer(check, input_cols, tz)
    except TransformError as e:
        return [TransformProblem(
            "transform_invalid",
            f"la transformación falla en el motor: {e}",
            fix="revisa nombres de columnas, tipos y funciones del SQL",
        )]
    return tz_date_problems(check, input_cols, tz) + compare(inferred, columns)
