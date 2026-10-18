# Quickstart & Validation: Faster PostgreSQL extraction

**Feature**: [spec.md](./spec.md) | **Contract**: [engine](./contracts/engine.md) |
**Research**: [research.md](./research.md)

## Run

```bash
cd backend && uv run pytest tests/test_runner.py tests/test_bulk_extract.py
# benchmark (opt-in, writes only to a throwaway schema in the BI database). BENCH_DATABASE_URL
# moves both sides to a database on the same host or LAN, which is what SC-001 needs; without it
# both sides are DATABASE_URL_BI.
BENCH_DATABASE_URL=postgresql://user:pass@localhost:5432/bench BENCH_ROWS=1000000 \
  uv run python scripts/bench_extract.py
```

## Validation scenarios

| # | Scenario | Expected | Covers |
|---|---|---|---|
| 1 | Existing runner tests (incremental, full, contract checks, reconciliation) | all pass unchanged; run rows record `path: bulk` | US1 AS1, FR-007 |
| 2 | Edge-case fixture (newlines, tabs, backslashes, quotes, emoji, empty vs NULL, timestamptz across DST, numeric(38,10), bytea, arrays, json) through bulk and rows paths | identical staging contents (`EXCEPT` both ways empty) | FR-007, SC-003 |
| 3 | Query columns differ from contract | today's message, no rows loaded | US2 AS2, FR-004 |
| 4 | Value not matching declared type | "los datos no cumplen el contrato", dataset unchanged | US2 AS3, FR-005 |
| 5 | Query attempts a write / session check | refused (read-only) | US2 AS1, FR-003 |
| 6 | Deadline passed during transfer | "se superó el tiempo máximo", run failed | US2 AS4, FR-006 |
| 7 | Origin raises FeatureNotSupported on COPY | fallback to rows, run succeeds, `fallback: FeatureNotSupported` recorded | US3 AS1, FR-008/009 |
| 8 | Origin connection lost mid-COPY | run fails, no fallback, dataset unchanged | US3 AS2 |
| 9 | REST/SOAP integration | unchanged behaviour, `path: rows` | FR-010 |
| 10 | Benchmark 10 k vs 1 M rows | ≥ 5× faster than rows path at 1 M; peak RSS delta < 50 MB | SC-001, SC-002 |
| 11 | Constitution V | describes COPY pipe + Polars for REST/SOAP; no ConnectorX | FR-011 |
