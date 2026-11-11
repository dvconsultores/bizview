import { useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Check, Copy, Download, Loader2 } from "lucide-react";
import type { ReportView } from "../../api/types";
import { useT } from "../../i18n";
import { csvFileName, downloadCsv, toCsv } from "../../lib/csv";
import { formatCell, type DataColumn, type DataTableModel, type DataTableOptions } from "../../lib/dataTable";
import { viewDataTable } from "../../lib/dataTable";
import type { CrossFilterState } from "./crossFilter";

const PAGE_SIZE = 50;

function normalize(text: string): string {
  return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

function sortValue(model: DataTableModel, rowIndex: number, columnIndex: number): string | number | null {
  return model.rows[rowIndex]?.values[columnIndex] ?? null;
}

/** Feature 064: the rows behind one card, with search, sort, copy and export. */
export function CardDataTable({
  view,
  options,
  currency,
  crossFilter,
  fetchFull,
  hideExport = false,
  grain,
}: {
  view: ReportView;
  options: DataTableOptions;
  currency: string;
  crossFilter?: CrossFilterState;
  fetchFull?: () => Promise<ReportView | null>;
  /** A share link without export keeps the table but loses copy and CSV. */
  hideExport?: boolean;
  grain?: "day" | "week" | "month";
}) {
  const t = useT();
  const [fullView, setFullView] = useState<ReportView | null>(null);
  const [loadingFull, setLoadingFull] = useState(false);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ column: string; dir: "asc" | "desc" } | null>(null);
  const [page, setPage] = useState(0);
  const [copied, setCopied] = useState(false);

  const model = useMemo(
    () => viewDataTable(fullView ?? view, options),
    [fullView, view, options],
  );

  useEffect(() => {
    setQuery("");
    setSort(null);
    setPage(0);
    setCopied(false);
  }, [view]);

  const visible = useMemo(() => {
    if (!model) return [];
    const needle = normalize(query.trim());
    const indexed = model.rows
      .map((row, index) => ({ row, index }))
      .filter(({ row }) => {
        if (!needle) return true;
        return row.values.some((value, column) =>
          normalize(formatCell(value, model.columns[column], currency)).includes(needle));
      });
    if (!sort) return indexed;
    const column = model.columns.findIndex((entry) => entry.id === sort.column);
    if (column < 0) return indexed;
    const dir = sort.dir === "asc" ? 1 : -1;
    return [...indexed].sort((a, b) => {
      const av = sortValue(model, a.index, column);
      const bv = sortValue(model, b.index, column);
      if (av === bv) return a.index - b.index;
      if (av === null || av === "") return 1;
      if (bv === null || bv === "") return -1;
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * dir;
      return String(av).localeCompare(String(bv), undefined, { numeric: true }) * dir;
    });
  }, [model, query, sort, currency]);

  if (!model) return null;

  const pageCount = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const current = Math.min(page, pageCount - 1);
  const shown = visible.slice(current * PAGE_SIZE, current * PAGE_SIZE + PAGE_SIZE);

  const display = (value: string | number | null, column: DataColumn) =>
    formatCell(value, column, currency, grain ?? (view.type === "trend" ? view.grain : "day"));

  const toggleSort = (column: string) =>
    setSort((old) =>
      old?.column === column
        ? old.dir === "asc" ? { column, dir: "desc" } : null
        : { column, dir: "asc" });

  const filteredRows = visible.map(({ row }) => model.columns.map((column, index) => display(row.values[index], column)));
  const headers = model.columns.map((column) => column.label);

  const copy = async () => {
    const text = [headers, ...filteredRows].map((line) => line.join("\t")).join("\n");
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      // A browser that blocks the clipboard still has the CSV button.
    }
  };

  const download = () => {
    downloadCsv(
      csvFileName(model.title),
      toCsv(model.columns.map((column) => ({ id: column.id, label: column.label })),
        visible.map(({ row }) => Object.fromEntries(
          model.columns.map((column, index) => [column.id, row.values[index]]))),
      ),
    );
  };

  const loadFull = async () => {
    if (!fetchFull) return;
    setLoadingFull(true);
    try {
      const full = await fetchFull();
      if (full) setFullView(full);
    } finally {
      setLoadingFull(false);
    }
  };

  return (
    <div className="flex min-h-0 flex-col gap-3" data-card-data-table="">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="search"
          value={query}
          onChange={(event) => { setQuery(event.target.value); setPage(0); }}
          aria-label={t.reportParams.dataTable.search}
          placeholder={t.reportParams.dataTable.search}
          className="min-h-tap min-w-0 flex-1 rounded-lg border border-line bg-surface px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        />
        <span className="text-sm text-ink-muted" data-card-data-count="">
          {t.reportParams.dataTable.rows(visible.length)}
        </span>
        {hideExport ? null : <button type="button" onClick={() => void copy()}
                className="inline-flex min-h-tap items-center gap-1.5 rounded-lg px-2 text-sm font-semibold text-ink-2 hover:bg-subtle">
          {copied ? <Check className="h-4 w-4" aria-hidden /> : <Copy className="h-4 w-4" aria-hidden />}
          {copied ? t.reportParams.dataTable.copied : t.reportParams.dataTable.copy}
        </button>}
        <span role="status" className="text-sm font-semibold text-positive">{copied ? t.reportParams.dataTable.copied : ""}</span>
        {hideExport ? null : <button type="button" onClick={download}
                className="inline-flex min-h-tap items-center gap-1.5 rounded-lg px-2 text-sm font-semibold text-ink-2 hover:bg-subtle">
          <Download className="h-4 w-4" aria-hidden />
          {t.reportParams.downloadCsv}
        </button>}
      </div>

      <div className="min-h-0 overflow-auto rounded-lg border border-line" data-card-data-scroll="">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 z-20 bg-surface">
            <tr>
              {model.columns.map((column) => (
                <th key={column.id} scope="col"
                    className={`whitespace-nowrap border-b border-line px-3 py-2 font-semibold text-ink-2 ${column.align === "right" ? "text-right" : "text-left"} ${column === model.columns[0] ? "sticky left-0 z-30 bg-surface" : ""}`}>
                  <button type="button" onClick={() => toggleSort(column.id)}
                          className="inline-flex items-center gap-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                    {column.label}
                    {sort?.column === column.id
                      ? sort.dir === "asc" ? <ArrowUp className="h-3 w-3" aria-hidden /> : <ArrowDown className="h-3 w-3" aria-hidden />
                      : null}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.length === 0 ? (
              <tr><td colSpan={model.columns.length} className="px-3 py-6 text-center text-ink-muted">
                {t.reportParams.dataTable.noRows}
              </td></tr>
            ) : shown.map(({ row }) => {
              const clickable = !!(row.dimension && row.value && crossFilter?.enabled);
              const on = clickable && (crossFilter?.filters[row.dimension!] ?? []).includes(row.value!);
              return (
                <tr key={row.id}
                    onClick={(event) => clickable && crossFilter?.toggle(
                      row.dimension!, row.value!, event.ctrlKey || event.metaKey)}
                    className={`odd:bg-subtle/40 ${clickable ? "cursor-pointer hover:bg-subtle" : ""} ${on ? "bg-accent-soft" : ""}`}>
                  {model.columns.map((column, index) => (
                    <td key={column.id}
                        className={`border-b border-line px-3 py-2 ${column.align === "right" ? "text-right tabular-nums" : "text-left"} ${index === 0 ? "sticky left-0 z-10 bg-surface" : ""} ${column.kind !== "dimension" && Number(row.values[index]) < 0 ? "text-negative" : ""}`}>
                      {index === 0 && clickable ? (
                        <button type="button" tabIndex={0}
                                aria-pressed={on}
                                aria-label={`${column.label}: ${display(row.values[index], column)}`}
                                onClick={(event) => { event.stopPropagation(); crossFilter?.toggle(
                                  row.dimension!, row.value!, event.ctrlKey || event.metaKey); }}
                                onKeyDown={(event) => {
                                  if (event.key !== "Enter" && event.key !== " ") return;
                                  event.preventDefault();
                                  crossFilter?.toggle(row.dimension!, row.value!, event.ctrlKey || event.metaKey);
                                }}
                                className="min-h-tap w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                          {display(row.values[index], column)}
                        </button>
                      ) : display(row.values[index], column)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        {model.truncated && fetchFull ? (
          <button type="button" onClick={() => void loadFull()} disabled={loadingFull}
                  className="inline-flex min-h-tap items-center gap-1.5 rounded-lg px-2 text-sm font-semibold text-accent hover:bg-subtle disabled:opacity-60">
            {loadingFull ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
            {t.reportParams.dataTable.fullRows}
          </button>
        ) : <span />}
        {pageCount > 1 ? (
          <div className="flex items-center gap-2">
            <button type="button" disabled={current === 0} onClick={() => setPage(current - 1)}
                    className="min-h-tap rounded-lg px-2 text-sm font-semibold text-ink-2 hover:bg-subtle disabled:opacity-50">
              {t.layout.previousPage}
            </button>
            <span className="text-sm text-ink-muted">{current + 1} / {pageCount}</span>
            <button type="button" disabled={current >= pageCount - 1} onClick={() => setPage(current + 1)}
                    className="min-h-tap rounded-lg px-2 text-sm font-semibold text-ink-2 hover:bg-subtle disabled:opacity-50">
              {t.layout.nextPage}
            </button>
          </div>
        ) : null}
      </div>

      {model.series ? (
        <section aria-label={t.reportParams.dataTable.chart} className="border-t border-line pt-3">
          <SeriesRows model={model.series} currency={currency} grain={model.series.grain} />
        </section>
      ) : null}
    </div>
  );
}

/** The sparkline's own rows under a KPI: date and value, with the report's formats. */
function SeriesRows({ model, currency, grain }: {
  model: DataTableModel;
  currency: string;
  grain?: "day" | "week" | "month";
}) {
  return (
    <div className="overflow-auto rounded-lg border border-line">
      <table className="w-full border-collapse text-sm">
        <thead className="bg-surface">
          <tr>
            {model.columns.map((column) => (
              <th key={column.id} scope="col"
                  className={`border-b border-line px-3 py-2 font-semibold text-ink-2 ${column.align === "right" ? "text-right" : "text-left"}`}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {model.rows.map((row) => (
            <tr key={row.id} className="odd:bg-subtle/40">
              {model.columns.map((column, index) => (
                <td key={column.id}
                    className={`border-b border-line px-3 py-2 ${column.align === "right" ? "text-right tabular-nums" : "text-left"}`}>
                  {formatCell(row.values[index], column, currency, grain)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
