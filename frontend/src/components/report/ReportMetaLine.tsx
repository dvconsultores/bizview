import type { ReactElement } from "react";
import type { ReportData, ReportDefinition } from "../../api/types";
import { useT } from "../../i18n";
import { freshnessText } from "../../lib/freshness";
import { formatRange } from "../../lib/numbers";
import type { ReportSelection } from "../../lib/reportQuery";
import { FilterChips } from "./FilterChips";

interface ReportMetaLineProps {
  def: ReportDefinition;
  applied: ReportSelection;
  data: ReportData | null;
  onRemoveFilter: (filterId: string, value: string) => void;
  onOpenFilters: () => void;
}

/**
 * Feature 030 (FR-002, US2.1): one compact meta line under the title — period · compared with ·
 * updated — plus the applied-filter chips. Replaces the old "Parámetros del reporte" card; on phones
 * the period keeps the first line and the rest wraps to a second. "Consultado por" is no longer
 * shown here (it lives in the PDF footer and the audit).
 */
export function ReportMetaLine({ def, applied, data, onRemoveFilter, onOpenFilters }: ReportMetaLineProps) {
  const t = useT();
  const periodText = t.reportParams.periodLabels[applied.period] ?? applied.period;
  const rangeText = data ? formatRange(data.selection.current) : null;
  const comparedText =
    applied.compare === "none"
      ? null
      : data?.selection.previous
        ? `${t.reportParams.metaCompared} ${formatRange(data.selection.previous)}`
        : (t.reportParams.compareLabels[applied.compare] ?? applied.compare);
  const updatedText = freshnessText(data, def);

  const parts = [
    <span key="period" className="font-semibold text-ink-2">
      {periodText}
    </span>,
    rangeText ? <span key="range">{rangeText}</span> : null,
    comparedText ? <span key="compared">{comparedText}</span> : null,
    updatedText ? <span key="updated">{updatedText}</span> : null,
  ].filter((part): part is ReactElement => part !== null);

  return (
    <div className="space-y-2">
      <p
        data-testid="report-meta-line"
        className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1 text-sm text-ink-muted [overflow-wrap:anywhere]"
      >
        {parts.map((part, index) => (
          <span key={index} className="inline-flex min-w-0 items-baseline gap-2">
            {index > 0 ? (
              <span aria-hidden className="text-ink-faint">
                ·
              </span>
            ) : null}
            {part}
          </span>
        ))}
      </p>
      <FilterChips def={def} applied={applied} onRemove={onRemoveFilter} onMore={onOpenFilters} />
    </div>
  );
}
