"""Transform stage of the BizView ETL engine (feature 005 amendment 2026-10-08).

Only the regenerated SQL produced by sqlsafety.check_transform is ever executed.
Memory is bounded by row-wise batches: one raw batch + one typed batch + one output slice
(FR-A01 to FR-A05). Whole-mode transforms spill typed batches to Arrow IPC files and run
with the Polars streaming engine, bounded by spilling to disk.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import polars as pl
from bizview_cli import sqlsafety
from bizview_cli import transform as contract
from polars.exceptions import PolarsError

from app.config import get_settings
from app.engine.extract import ExtractError
from app.i18n import M

# Row-wise batch size: bounds memory (one raw batch + typed batch + output slice) and is the
# best measured trade-off on a same-host origin (1 M rows: +28.6 % median extraction time over
# the COPY path and ~210 MB peak at 20 000, against +45 %/291 MB at 50 000 and +69 %/391 MB at
# 200 000; see the same-host section of specs/008-fast-pg-extraction/research.md).
DEFAULT_BATCH_ROWS = 20_000
OUTPUT_SLICE_ROWS = 50_000
POLL_SECONDS = 0.25


@dataclass(frozen=True)
class Compiled:
    sql: str
    mode: str
    input: dict
    input_columns: list[str]
    input_types: dict[str, str]
    input_schema: dict[str, pl.DataType]
    columns: dict
    output_columns: list[str]
    batch_rows: int
    tz: str


def compile(ds: dict, tz: str) -> Compiled | None:
    """Compile the transformation declared in `ds`; return None when absent."""
    tr = ds.get("transform")
    if not tr:
        return None
    tr_input = tr["input"]
    input_types = {c: d["type"] for c, d in tr_input.items()}
    check = sqlsafety.check_transform(tr["sql"], input_types)
    if check.problems:
        raise ExtractError(M("transform.invalid", detail=check.problems[0].message))
    errors = [
        p
        for p in contract.check_output(check, tr_input, ds["columns"], tz)
        if p.level == "error"
    ]
    if errors:
        raise ExtractError(M("transform.columns_mismatch", detail=errors[0].message))
    batch_rows = int(tr.get("batch_rows") or DEFAULT_BATCH_ROWS)
    return Compiled(
        sql=check.sql,
        mode=check.mode,
        input=tr_input,
        input_columns=list(tr_input),
        input_types=input_types,
        input_schema=contract.input_schema(tr_input, tz),
        columns=ds["columns"],
        output_columns=list(ds["columns"]),
        batch_rows=batch_rows,
        tz=tz,
    )


def _unescape_text(s: pl.Expr) -> pl.Expr:
    """Undo PostgreSQL COPY text escaping on a text column."""
    sentinel = "\x00"
    s = s.str.replace_all(r"\\", sentinel, literal=True)
    for esc, ch in [("t", "\t"), ("n", "\n"), ("r", "\r"), ("b", "\b"), ("f", "\f"), ("v", "\v")]:
        s = s.str.replace_all("\\" + esc, ch, literal=True)
    return s.str.replace_all(sentinel, "\\", literal=True)


def _cast_column(name: str, ctype: str, tz: str) -> pl.Expr:
    col = pl.col(name)
    if ctype == "integer":
        return col.str.strip_chars().cast(pl.Int32, strict=False)
    if ctype == "bigint":
        return col.str.strip_chars().cast(pl.Int64, strict=False)
    if ctype == "numeric":
        return col.str.strip_chars().cast(pl.Decimal(38, 9), strict=False)
    if ctype == "boolean":
        v = col.str.to_lowercase().str.strip_chars()
        return (
            pl.when(v.is_in(["t", "true", "1"]))
            .then(pl.lit(True))
            .when(v.is_in(["f", "false", "0"]))
            .then(pl.lit(False))
            .otherwise(None)
        )
    if ctype == "date":
        return col.str.to_date("%Y-%m-%d", strict=False)
    if ctype == "timestamptz":
        tz_aware = pl.coalesce(
            col.str.to_datetime("%Y-%m-%d %H:%M:%S%.f%#z", time_unit="us", strict=False),
            col.str.to_datetime("%Y-%m-%dT%H:%M:%S%.f%#z", time_unit="us", strict=False),
        ).dt.convert_time_zone(tz)
        naive = pl.coalesce(
            col.str.to_datetime("%Y-%m-%d %H:%M:%S%.f", time_unit="us", strict=False),
            col.str.to_datetime("%Y-%m-%dT%H:%M:%S%.f", time_unit="us", strict=False),
            col.str.to_date("%Y-%m-%d", strict=False).cast(pl.Datetime("us")),
        ).dt.replace_time_zone(tz, ambiguous="earliest", non_existent="null")
        return pl.coalesce(tz_aware, naive)
    return col


def parse_text(frame_str: pl.DataFrame, compiled: Compiled, *, escaped: bool) -> pl.DataFrame:
    """Cast an all-String frame to the typed input frame of the transformation."""
    for c in compiled.input_columns:
        if c not in frame_str.columns:
            raise ExtractError(M("transform.missing_column", column=c))
    frame_str = frame_str.select(
        [pl.col(c).cast(pl.String) for c in compiled.input_columns]
    )
    typed_exprs: list[pl.Expr] = []
    for c in compiled.input_columns:
        ctype = compiled.input_types[c]
        if ctype == "text":
            expr = _unescape_text(pl.col(c)) if escaped else pl.col(c)
        else:
            expr = _cast_column(c, ctype, compiled.tz)
        typed_exprs.append(expr.alias(c))
    typed = frame_str.select(typed_exprs)
    # The declared-type check reads the typed frame instead of re-evaluating every cast in a
    # second select: a null where the raw value was not null means the value does not fit the
    # contract. (SC-A01: this halves the per-batch work of the transform.)
    for c in compiled.input_columns:
        if compiled.input_types[c] == "text":
            continue
        if (frame_str[c].is_not_null() & typed[c].is_null()).any():
            raise ExtractError(
                f"la columna {c} no cumple el tipo declarado en transform.input"
                f" ({compiled.input_types[c]})"
            )
    return typed


class BatchSink(Protocol):
    """What a batch splitter calls: `escaped` says whether the frame came from COPY text, where
    a backslash starts an escape sequence."""

    def __call__(self, frame: pl.DataFrame, *, escaped: bool) -> None: ...


class CopyTextSplitter:
    """Split COPY text output into batches of about `batch_rows` rows without per-row work.

    Each batch is handed over with `escaped=False` when the batch bytes contain no backslash:
    nothing can be escaped then, so the unescape pass (`_unescape_text`) is skipped — most
    batches of most datasets (SC-A01)."""

    def __init__(
        self,
        on_batch: BatchSink,
        columns: list[str],
        batch_rows: int,
    ):
        self._on_batch = on_batch
        self._columns = columns
        self._batch_rows = batch_rows
        self._parts: list[bytes] = []
        self._lines = 0
        self.rows = 0

    def write(self, block: bytes) -> None:
        self._parts.append(block)
        self._lines += block.count(b"\n")
        if self._lines >= self._batch_rows:
            last = self._parts.pop()
            k = last.rfind(b"\n") + 1
            self._parts.append(last[:k])
            chunk = b"".join(self._parts)
            tail = last[k:]
            self._parts = [tail] if tail else []
            self._lines = 0
            self._parse(chunk)

    def _parse(self, data: bytes) -> None:
        try:
            frame = pl.read_csv(
                data,
                separator="\t",
                quote_char=None,
                has_header=False,
                schema={c: pl.String for c in self._columns},
                null_values=["\\N"],
                empty_string_is_null=False,
                raise_if_empty=False,
            )
        except PolarsError as exc:
            raise ExtractError(
                M("transform.copy_columns")
            ) from exc
        self.rows += frame.height
        if frame.height:
            # COPY text escapes are backslash sequences: without a backslash in the batch there
            # is nothing to undo, so the sink can skip its unescape pass.
            self._on_batch(frame, escaped=b"\\" in data)

    def close(self) -> None:
        if not self._parts:
            return
        data = b"".join(self._parts)
        self._parts.clear()
        if not data:
            return
        if not data.endswith(b"\n"):
            data += b"\n"
        self._parse(data)


class Sink:
    """Transformation sink supporting rows and whole modes.

    Rows mode processes one typed batch at a time with bounded memory.
    Whole mode spills typed input batches to Arrow IPC files and runs the SQL with
    the Polars streaming engine, reading the result in output slices.
    """

    def __init__(
        self,
        compiled: Compiled,
        write: Callable[[pl.DataFrame], None],
        check: Callable[[], None],
        *,
        deadline: float | None = None,
        spill_dir: str | None = None,
        max_rows: int | None = None,
        label: str = "run",
    ):
        settings = get_settings()
        self._compiled = compiled
        self._write = write
        self._check = check
        self._deadline = deadline
        self._spill_dir = spill_dir or settings.transform_spill_dir
        self._max_rows = max_rows if max_rows is not None else settings.transform_max_rows
        self._mode = compiled.mode
        self._label = re.sub(r"[^A-Za-z0-9_-]", "_", label)[:80] or "run"
        self._run_dir: str | None = None
        self._files: list[str] = []
        self.rows_in = 0
        self.rows_out = 0
        self._transform_ns = 0

    @property
    def transform_ms(self) -> int:
        return self._transform_ns // 1_000_000

    def add(self, frame: pl.DataFrame, *, escaped: bool) -> None:
        if self._mode != "rows":
            return self._add_whole(frame, escaped=escaped)
        self.rows_in += frame.height
        if frame.height == 0:
            self._check()
            return
        t0 = time.perf_counter()
        typed = parse_text(frame, self._compiled, escaped=escaped)
        try:
            out = (
                pl.SQLContext(input=typed.lazy())
                .execute(self._compiled.sql)
                .collect()
            )
        except PolarsError as exc:
            msg = str(exc).strip().splitlines()[0][:300]
            raise ExtractError(M("transform.failed", detail=msg)) from exc
        errors = [
            p
            for p in contract.compare(dict(out.schema), self._compiled.columns)
            if p.level == "error"
        ]
        if errors:
            raise ExtractError(
                M("transform.columns_mismatch", detail=errors[0].message)
            )
        self._transform_ns += int((time.perf_counter() - t0) * 1_000_000_000)
        sel = out.select(self._compiled.output_columns)
        for off in range(0, sel.height, OUTPUT_SLICE_ROWS):
            self._write(sel.slice(off, OUTPUT_SLICE_ROWS))
        self.rows_out += out.height
        del typed, out, sel, frame
        self._check()
        if self._deadline is not None and time.monotonic() > self._deadline:
            raise ExtractError(M("run.timeout"))

    def _add_whole(self, frame: pl.DataFrame, *, escaped: bool) -> None:
        self.rows_in += frame.height
        if self.rows_in > self._max_rows:
            raise ExtractError(
                M("transform.max_rows", max=self._max_rows)
            )
        if frame.height == 0:
            self._check()
            return
        t0 = time.perf_counter()
        typed = parse_text(frame, self._compiled, escaped=escaped)
        path = os.path.join(self._ensure_dir(), f"in-{len(self._files):05d}.arrow")
        typed.write_ipc(path)
        self._files.append(path)
        self._transform_ns += int((time.perf_counter() - t0) * 1_000_000_000)
        del typed, frame
        self._check()
        self._deadline_check()

    def _ensure_dir(self) -> str:
        if self._run_dir is None:
            os.makedirs(self._spill_dir, exist_ok=True)
            self._run_dir = tempfile.mkdtemp(prefix=f"{self._label}-", dir=self._spill_dir)
        return self._run_dir

    def _deadline_check(self) -> None:
        if self._deadline is not None and time.monotonic() > self._deadline:
            raise ExtractError(M("run.timeout"))

    def finish(self) -> None:
        if self._mode == "rows":
            return
        try:
            self._finish_whole()
        finally:
            self.close()

    def _finish_whole(self) -> None:
        run_dir = self._ensure_dir()
        if not self._files:
            empty = pl.DataFrame(schema=self._compiled.input_schema)
            path = os.path.join(run_dir, "in-00000.arrow")
            empty.write_ipc(path)
            self._files.append(path)

        t0 = time.perf_counter()
        out_path = os.path.join(run_dir, "out.arrow")
        try:
            query = (
                pl.SQLContext(input=pl.scan_ipc(self._files))
                .execute(self._compiled.sql)
                .sink_ipc(out_path, lazy=True, engine="streaming")
                .collect(background=True)
            )
        except PolarsError as exc:
            raise ExtractError(M("transform.failed", detail=_polars_message(exc))) from exc

        while True:
            try:
                self._check()
                self._deadline_check()
            except BaseException:
                query.cancel()
                raise
            try:
                done = query.fetch()
            except PolarsError as exc:
                raise ExtractError(M("transform.failed", detail=_polars_message(exc))) from exc
            if done is not None:
                break
            time.sleep(POLL_SECONDS)

        self._transform_ns += int((time.perf_counter() - t0) * 1_000_000_000)

        out_lf = pl.scan_ipc(out_path)
        errors = [
            p
            for p in contract.compare(dict(out_lf.collect_schema()), self._compiled.columns)
            if p.level == "error"
        ]
        if errors:
            raise ExtractError(
                M("transform.columns_mismatch", detail=errors[0].message)
            )

        batches = iter(
            out_lf.select(self._compiled.output_columns).collect_batches(
                chunk_size=OUTPUT_SLICE_ROWS, engine="streaming"
            )
        )
        while True:
            t1 = time.perf_counter()
            try:
                batch = next(batches, None)
            except PolarsError as exc:
                raise ExtractError(M("transform.failed", detail=_polars_message(exc))) from exc
            self._transform_ns += int((time.perf_counter() - t1) * 1_000_000_000)
            if batch is None:
                break
            if batch.height:
                self._write(batch)
                self.rows_out += batch.height
            del batch
            self._check()
            self._deadline_check()

    def close(self) -> None:
        """Idempotent cleanup; callers should call it in a finally block."""
        if self._run_dir is not None:
            shutil.rmtree(self._run_dir, ignore_errors=True)
            self._run_dir = None
            self._files = []


def _polars_message(exc: PolarsError) -> str:
    return str(exc).strip().splitlines()[0][:300]


SPILL_STALE_SECONDS = 3600


def sweep_spill_dir(path: str | None = None, *, older_than: float = SPILL_STALE_SECONDS,
                    now: float | None = None) -> int:
    """Remove entries left by a crashed run at worker startup; safe while previews in other
    processes are active: recent folders are kept."""
    target = path or get_settings().transform_spill_dir
    if not os.path.isdir(target):
        return 0
    timestamp = time.time() if now is None else now
    removed = 0
    for entry in os.listdir(target):
        full = os.path.join(target, entry)
        try:
            st = os.stat(full)
            if timestamp - st.st_mtime < older_than:
                continue
            if os.path.isdir(full):
                shutil.rmtree(full, ignore_errors=True)
            else:
                os.remove(full)
            removed += 1
        except OSError:
            continue
    return removed
