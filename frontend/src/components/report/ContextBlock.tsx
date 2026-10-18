import { Clock, X } from "lucide-react";
import { useId, type ReactNode } from "react";
import type {
  ReportData,
  ReportDefinition,
} from "../../api/types";
import type { ReportSelection } from "../../lib/reportQuery";
import { Badge } from "../Badge";
import { Card } from "../Card";
import { useT } from "../../i18n";
import { localized } from "../../lib/labels";
import { freshnessText } from "../../lib/freshness";
import { formatRange } from "../../lib/numbers";

export interface ContextBlockProps {
  def: ReportDefinition;
  applied: ReportSelection;
  data: ReportData | null;
  incompleteCustom: boolean;
  onRemoveFilter: (filterId: string, value: string) => void;
  actions?: ReactNode;
  viewer?: string | null;
}

export function ContextBlock({
  def,
  applied,
  data,
  incompleteCustom,
  onRemoveFilter,
  actions,
  viewer,
}: ContextBlockProps) {
  const t = useT();
  const titleId = useId();
  const chipsId = useId();
  const periodLabels = t.reportParams.periodLabels;
  const compareLabels = t.reportParams.compareLabels;

  const periodText = periodLabels[applied.period] ?? applied.period;

  const comparedText = data?.selection.previous
    ? formatRange(data.selection.previous)
    : applied.compare === "none" || data
      ? compareLabels.none
      : (compareLabels[applied.compare] ?? applied.compare);

  const updatedText = freshnessText(data, def);

  const chipEntries = def.filters.flatMap((filterId) => {
    const values = applied.filters[filterId] ?? [];
    return values.map((value) => ({
      filterId,
      value,
      label: localized(def.dimensions[filterId], "label") ?? filterId,
    }));
  });

  return (
    <Card className="p-5 sm:p-6">
      <section aria-labelledby={titleId}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h2
            id={titleId}
            className="text-lg font-semibold text-ink"
          >
            {t.reportParams.contextTitle}
          </h2>
          {actions ? (
            <div className="flex flex-wrap gap-2">{actions}</div>
          ) : null}
        </div>

        <dl
          className={`mt-4 grid grid-cols-1 gap-4 ${
            viewer?.trim() ? "sm:grid-cols-2 xl:grid-cols-4" : "sm:grid-cols-3"
          }`}
        >
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
              {t.reportParams.contextPeriod}
            </dt>
            <dd className="mt-1 text-sm text-ink-2">
              <span className="font-semibold text-ink">{periodText}</span>
              {incompleteCustom ? (
                <span className="block text-ink-muted">
                  {t.reportParams.chooseDates}
                </span>
              ) : data ? (
                <span className="block">
                  {formatRange(data.selection.current)}
                </span>
              ) : null}
              {data?.selection.partial ? (
                <span className="mt-1 block">
                  <Badge
                    tone="amber"
                    icon={<Clock className="h-3.5 w-3.5" aria-hidden />}
                  >
                    {t.reportParams.inProgress}
                  </Badge>
                </span>
              ) : null}
            </dd>
          </div>

          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
              {t.reportParams.contextCompared}
            </dt>
            <dd className="mt-1 text-sm text-ink-2">{comparedText}</dd>
          </div>

          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
              {t.reportParams.contextUpdated}
            </dt>
            <dd className="mt-1 text-sm text-ink-2">{updatedText}</dd>
          </div>

          {viewer?.trim() ? (
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
                {t.reportParams.contextViewer}
              </dt>
              <dd className="mt-1 text-sm text-ink-2 [overflow-wrap:anywhere]">{viewer}</dd>
            </div>
          ) : null}
        </dl>

        {chipEntries.length > 0 ? (
          <div className="mt-4 border-t border-line pt-4">
            <p
              id={chipsId}
              className="text-xs font-semibold uppercase tracking-wide text-ink-soft"
            >
              {t.reportParams.activeFilters}
            </p>
            <ul
              aria-labelledby={chipsId}
              className="mt-2 flex flex-wrap gap-2"
            >
              {chipEntries.map(({ filterId, value, label }) => (
                <li key={`${filterId}:${value}`} className="max-w-full">
                  <button
                    type="button"
                    aria-label={t.reportParams.removeFilter(label, value)}
                    onClick={() => onRemoveFilter(filterId, value)}
                    className="flex min-h-tap max-w-full items-center gap-1.5 rounded-full bg-accent-soft px-3 py-1 text-left text-sm font-semibold text-accent ring-1 ring-inset ring-accent-line transition-colors hover:bg-accent-soft-2 hover:text-accent-deep"
                  >
                    <span className="min-w-0 [overflow-wrap:anywhere]">
                      <span className="font-normal">{label}:</span> {value}
                    </span>
                    <X className="h-4 w-4 shrink-0" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>
    </Card>
  );
}
