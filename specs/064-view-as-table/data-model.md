# Data model — 064 view as table

## Frontend

```ts
export type DataColumnKind = "dimension" | "metric" | "derived";

export interface DataColumn {
  id: string;
  label: string;
  kind: DataColumnKind;
  format?: MetricFormat;
  align: "left" | "right";
}

export interface DataRow {
  id: string;
  cells: (string | number | null)[];
  /** Present only when the row can cross-filter (ranking/table dimension). */
  dimension?: string;
  value?: string;
  selected?: boolean;
}

export interface DataTableModel {
  title: string;
  columns: DataColumn[];
  rows: DataRow[];
  /** The payload cut the view; «Ver todas las filas» is offered. */
  truncated: boolean;
}
```

- `kpis`: `Métrica | Valor | Anterior | Variación` (only columns the view has).
- `trend`: `Período | <metric label> | Anterior`.
- `ranking`: `Dimensión | Métrica | Anterior | Variación | % del total`.
- `table`: its declared columns, narrowed/ordered by `component.columns` when present.
- `gauge`/`share`/`index`/`asset`: the underlying view's rows (kpis or table/ranking).
- `source_views`/`ignore_views` resolution happens before the model is built.

## Backend

- `ReportView` ranking/table gains `truncated: boolean`.
- `GET /data?full=1`: ranking/table limit becomes `min(1000, direct.max_rows)`; the cache key is
  `selection_hash + ":full"` and stores under the existing `data` cache with that key.
- `full` is ignored by selection parsing.

## URL

- `tabla=<component id>`: opens the table. With `ampliar=<id>` it is the dialog's table mode.
- `tabla` and `ampliar` are preserved independently; ← → keeps `tabla`.
