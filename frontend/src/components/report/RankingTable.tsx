import type { ReportView } from "../../api/types";
import { csvFileName, downloadCsv, toCsv, viewCsvTable } from "../../lib/csv";
import { formatValue } from "../../lib/numbers";
import { Card } from "../Card";
import { CardMenu } from "./CardMenu";
import { ChangeChip } from "./KpiGrid";
import { useT } from "../../i18n";
import { localized } from "../../lib/labels";
import { markState, type CrossFilterState } from "./crossFilter";

type Ranking = Extract<ReportView, { type: "ranking" }>;

interface RankingTableProps {
  view: Ranking;
  currency: string;
  compared: boolean;
  better: "higher" | "lower";
  csvFileBase?: string;
  /** Feature 056: the card is in a layout cell that can be opened full screen. */
  onMaximize?: () => void;
  /** Feature 056b: in the dialog the rows breathe and the card drops its own heading. */
  maximized?: boolean;
  /** Feature 063: a row filters the ranking's dimension. */
  crossFilter?: CrossFilterState;
}

export function RankingTable({ view, currency, compared, better, csvFileBase, onMaximize,
                              maximized = false, crossFilter }: RankingTableProps) {
  const t = useT();
  const max = Math.max(0, ...view.items.map((i) => Math.abs(i.value ?? 0)));

  function handleDownloadCsv() {
    const table = viewCsvTable(view);
    if (!table) return;
    const filename = csvFileBase ? csvFileName(`${csvFileBase}-${table.title}`) : csvFileName(table.title);
    downloadCsv(filename, toCsv(table.columns, table.rows));
  }

  return (
    <Card className={maximized ? "flex h-full min-h-0 flex-col border-0 p-0 shadow-none" : "p-5 sm:p-6"}
          data-maximized={maximized ? "" : undefined}>
      {maximized ? null : (
        <div className="flex items-start justify-between gap-3">
          <h2 className="min-w-0 text-lg font-semibold text-ink [overflow-wrap:anywhere]">{localized(view, "title")}</h2>
          {view.items.length > 0 ? <CardMenu title={localized(view, "title")} onDownloadCsv={handleDownloadCsv} onMaximize={onMaximize} /> : null}
        </div>
      )}
      {view.items.length === 0 ? (
        <p className="mt-3 text-sm text-ink-muted">{t.reportParams.display.noData}</p>
      ) : (
        <ol className={`${maximized ? "mt-0 space-y-5 sm:space-y-6" : "mt-4 space-y-4"}`}>
          {view.items.map((it, i) => {
            const mark = markState(crossFilter, view.dimension, it.key === null ? null : String(it.key));
            const dimmed = (crossFilter?.filters[view.dimension] ?? []).length > 0
              && mark !== null && !mark.selected;
            return (
            <li key={`${it.key}-${i}`} className={`min-w-0 rounded-lg ${dimmed ? "opacity-60" : ""}`}>
              <div
                role={mark ? "button" : undefined}
                tabIndex={mark ? 0 : undefined}
                aria-pressed={mark ? mark.selected : undefined}
                aria-label={mark ? `${localized(view, "dimension_label")}: ${it.key}` : undefined}
                onClick={(event) => mark && crossFilter?.toggle(view.dimension, mark.value, event.ctrlKey || event.metaKey)}
                onKeyDown={(event) => {
                  if (!mark || (event.key !== "Enter" && event.key !== " ")) return;
                  event.preventDefault();
                  crossFilter?.toggle(view.dimension, mark.value, event.ctrlKey || event.metaKey);
                }}
                className={`min-h-8 rounded-lg ${mark ? "cursor-pointer px-1 -mx-1 hover:bg-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" : ""}`}
              >
              <div className="flex items-baseline justify-between">
                <span className="mr-3 flex min-w-0 items-center text-sm text-ink-2 [overflow-wrap:anywhere]">
                  <span className="mr-2 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-xs font-bold text-accent">
                    {i + 1}
                  </span>
                  <span className="text-sm font-medium text-ink">{it.key ?? "—"}</span>
                </span>
                <span className="shrink-0 text-sm font-bold tabular-nums text-ink">{formatValue(it.value, view.format, currency)}</span>
              </div>
              <div className="mt-1.5 flex items-center">
                <div className="mr-2 h-2 flex-1 overflow-hidden rounded-full bg-surface-2" aria-hidden>
                  <div className="h-full rounded-full bg-gradient-to-r from-primary to-primary-hover" style={{ width: `${max ? (Math.abs(it.value ?? 0) / max) * 100 : 0}%` }} />
                </div>
                <span className="w-14 shrink-0 text-right text-xs tabular-nums text-ink-muted">{formatValue(it.share, "percent")}</span>
                {compared ? (
                  <span className="ml-2 shrink-0">
                    <ChangeChip item={{ change: it.change, better }} />
                  </span>
                ) : null}
              </div>
              </div>
            </li>
            );
          })}
        </ol>
      )}
    </Card>
  );
}
