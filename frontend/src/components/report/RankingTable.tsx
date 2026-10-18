import type { ReportView } from "../../api/types";
import { csvFileName, downloadCsv, toCsv, viewCsvTable } from "../../lib/csv";
import { formatValue } from "../../lib/numbers";
import { Card } from "../Card";
import { CardMenu } from "./CardMenu";
import { ChangeChip } from "./KpiGrid";
import { useT } from "../../i18n";
import { localized } from "../../lib/labels";

type Ranking = Extract<ReportView, { type: "ranking" }>;

interface RankingTableProps {
  view: Ranking;
  currency: string;
  compared: boolean;
  better: "higher" | "lower";
  csvFileBase?: string;
}

export function RankingTable({ view, currency, compared, better, csvFileBase }: RankingTableProps) {
  const t = useT();
  const max = Math.max(0, ...view.items.map((i) => Math.abs(i.value ?? 0)));

  function handleDownloadCsv() {
    const table = viewCsvTable(view);
    if (!table) return;
    const filename = csvFileBase ? csvFileName(`${csvFileBase}-${table.title}`) : csvFileName(table.title);
    downloadCsv(filename, toCsv(table.columns, table.rows));
  }

  return (
    <Card className="p-5 sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <h2 className="min-w-0 text-lg font-semibold text-ink [overflow-wrap:anywhere]">{localized(view, "title")}</h2>
        {view.items.length > 0 ? <CardMenu title={localized(view, "title")} onDownloadCsv={handleDownloadCsv} /> : null}
      </div>
      {view.items.length === 0 ? (
        <p className="mt-3 text-sm text-ink-muted">{t.reportParams.display.noData}</p>
      ) : (
        <ol className="mt-4 space-y-4">
          {view.items.map((it, i) => (
            <li key={`${it.key}-${i}`} className="min-w-0">
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
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
