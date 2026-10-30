import { useMemo, useState } from "react";
import type { ReportImageSet, ReportView, SortDirection } from "../../api/types";
import { csvFileName, downloadCsv, toCsv, viewCsvTable } from "../../lib/csv";
import { formatValue } from "../../lib/numbers";
import { Card } from "../Card";
import { Button } from "../Button";
import { CardMenu } from "./CardMenu";
import { useT } from "../../i18n";
import { localized } from "../../lib/labels";
import { ReportImage } from "./ReportImage";

type Table = Extract<ReportView, { type: "table" }>;

interface DataTableProps {
  view: Table;
  currency: string;
  csvFileBase?: string;
  /** Layout attributes (feature 026, data-model §3): the declared title, an ordered subset of the
   * emitted columns, the engine's totals as a last row, a client-side sort and page size. */
  title?: string;
  columns?: string[];
  totals?: boolean;
  sort?: { by: string; dir: SortDirection };
  pageSize?: number;
  /** Feature 044: draw the image of `set` in the cell of `column` (the column the set is keyed by). */
  image?: { set: ReportImageSet; column: string };
}

/** The declared order wins, unknown ids are dropped and a column is never repeated. */
function pickColumns<T extends { id: string }>(emitted: T[], wanted?: string[]): T[] {
  if (!wanted || wanted.length === 0) return emitted;
  const picked: T[] = [];
  for (const id of wanted) {
    const column = emitted.find((entry) => entry.id === id);
    if (column && !picked.includes(column)) picked.push(column);
  }
  return picked.length > 0 ? picked : emitted;
}

function comparable(value: string | number | null): string | number {
  return value === null ? "" : value;
}

function sortRows(rows: Table["rows"], sort: { by: string; dir: SortDirection }): Table["rows"] {
  const direction = sort.dir === "asc" ? 1 : -1;
  return rows
    .map((row, index) => ({ row, index }))
    .sort((a, b) => {
      const left = comparable(a.row[sort.by] ?? null);
      const right = comparable(b.row[sort.by] ?? null);
      if (left === right) return a.index - b.index;
      if (typeof left === "number" && typeof right === "number") return (left - right) * direction;
      return String(left).localeCompare(String(right)) * direction;
    })
    .map((entry) => entry.row);
}

export function DataTable({
  view,
  currency,
  csvFileBase,
  title,
  columns,
  totals = false,
  sort,
  pageSize,
  image,
}: DataTableProps) {
  const t = useT();
  const [page, setPage] = useState(0);
  const heading = title ?? localized(view, "title") ?? t.reportParams.detailTitle;

  const shown = useMemo(() => pickColumns(view.columns, columns), [view.columns, columns]);
  const rows = useMemo(() => (sort ? sortRows(view.rows, sort) : view.rows), [view.rows, sort]);

  const footerTotals = totals ? view.totals : undefined;
  // The label sits in the first real category column; with metric-only columns it shares the first
  // cell with that metric's figure, so a total is never hidden.
  const labelIndex = Math.max(0, shown.findIndex((column) => column.kind === "dimension"));
  const pages = pageSize && pageSize > 0 ? Math.max(1, Math.ceil(rows.length / pageSize)) : 1;
  const current = Math.min(page, pages - 1);
  const visible =
    pageSize && pageSize > 0 ? rows.slice(current * pageSize, current * pageSize + pageSize) : rows;

  function handleDownloadCsv() {
    const exported = viewCsvTable(view);
    if (!exported) return;
    // The CSV stays the whole table, in the declared column order and sort, not just the page.
    const table =
      columns || sort
        ? {
            title: exported.title,
            columns: shown.map((column) => ({ id: column.id, label: localized(column, "label") })),
            rows: rows.map((row) =>
              Object.fromEntries(shown.map((column) => [column.id, row[column.id] ?? null])),
            ),
          }
        : exported;
    const filename = csvFileBase ? csvFileName(`${csvFileBase}-${exported.title}`) : csvFileName(exported.title);
    downloadCsv(filename, toCsv(table.columns, table.rows));
  }

  return (
    <Card>
      <div className="flex items-start justify-between gap-3 px-5 pt-5 pb-3">
        <h2 className="min-w-0 text-lg font-semibold text-ink [overflow-wrap:anywhere]">{heading}</h2>
        {view.rows.length > 0 ? <CardMenu title={heading} onDownloadCsv={handleDownloadCsv} /> : null}
      </div>
      {/* Wide tables scroll inside the card, never the page. */}
      <div className="max-w-full overflow-x-auto rounded-b-card" tabIndex={0} role="region" aria-label={heading}>
        <table className="min-w-full text-left text-sm">
          <thead>
            <tr className="bg-subtle text-xs font-semibold text-ink-muted">
              {shown.map((c) => (
                <th
                  key={c.id}
                  scope="col"
                  aria-sort={sort && sort.by === c.id ? (sort.dir === "asc" ? "ascending" : "descending") : undefined}
                  className={`whitespace-nowrap px-4 py-3 ${c.kind === "metric" ? "text-right" : ""}`}
                >
                  <span className="uppercase tracking-wide">{localized(c, "label")}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line tabular-nums">
            {visible.map((r, i) => (
              <tr key={i} className="transition-colors hover:bg-subtle">
                {shown.map((c, idx) => (
                  <td
                    key={c.id}
                    className={`px-4 py-3 ${c.kind === "metric" ? "whitespace-nowrap text-right" : ""} ${
                      idx === 0 ? "font-semibold text-ink" : "text-ink-2"
                    }`}
                  >
                    {image && c.id === image.column ? (
                      <span className="flex items-center gap-2">
                        <ReportImage set={image.set} name={r[c.id]} size={20} />
                        {r[c.id] ?? "—"}
                      </span>
                    ) : c.kind === "metric" ? (
                      formatValue(r[c.id] as number | null, c.format, currency)
                    ) : (
                      (r[c.id] ?? "—")
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
          {/* The totals row prints the engine's figures; it never adds up the rendered rows. */}
          {footerTotals ? (
            <tfoot className="border-t border-line bg-subtle font-semibold">
              <tr>
                {shown.map((c, idx) => (
                  <td
                    key={c.id}
                    className={`px-4 py-3 ${c.kind === "metric" ? "whitespace-nowrap text-right" : ""} ${
                      idx === 0 ? "text-ink" : "text-ink-2"
                    }`}
                  >
                    {idx === labelIndex
                      ? c.kind === "metric"
                        ? `${t.layout.totals} · ${formatValue(footerTotals?.[c.id] ?? null, c.format, currency)}`
                        : t.layout.totals
                      : c.kind === "metric"
                        ? formatValue(footerTotals?.[c.id] ?? null, c.format, currency)
                        : ""}
                  </td>
                ))}
              </tr>
            </tfoot>
          ) : null}
        </table>
      </div>
      {pages > 1 ? (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3">
          <Button variant="secondary" size="sm" disabled={current <= 0} onClick={() => setPage(current - 1)}>
            {t.layout.previousPage}
          </Button>
          <p role="status" className="text-xs text-ink-muted">
            {t.layout.page(current + 1, pages)}
          </p>
          <Button variant="secondary" size="sm" disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>
            {t.layout.nextPage}
          </Button>
        </div>
      ) : null}
    </Card>
  );
}
