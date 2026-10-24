import { X } from "lucide-react";
import { useId } from "react";
import type { ReportDefinition } from "../../api/types";
import { useT } from "../../i18n";
import { localized } from "../../lib/labels";
import type { ReportSelection } from "../../lib/reportQuery";

interface FilterChipsProps {
  def: ReportDefinition;
  applied: ReportSelection;
  onRemove: (filterId: string, value: string) => void;
  /** Opens the sheet's Filtros tab ("+N más"). */
  onMore: () => void;
  /** How many chips fit before the overflow (feature 030 edge case: two lines, then "+N más"). */
  limit?: number;
}

/** The applied filters as removable chips under the meta line (FR-004, US3.2). */
export function FilterChips({ def, applied, onRemove, onMore, limit = 6 }: FilterChipsProps) {
  const t = useT();
  const chipsId = useId();
  const entries = def.filters.flatMap((filterId) =>
    (applied.filters[filterId] ?? []).map((value) => ({
      filterId,
      value,
      label: localized(def.dimensions[filterId], "label") ?? filterId,
    })),
  );
  if (entries.length === 0) return null;

  const shown = entries.slice(0, limit);
  const hidden = entries.length - shown.length;

  return (
    <div className="min-w-0">
      <ul aria-labelledby={chipsId} className="flex flex-wrap gap-2">
        <li className="sr-only" id={chipsId}>
          {t.reportParams.activeFilters}
        </li>
        {shown.map(({ filterId, value, label }) => (
          <li key={`${filterId}:${value}`} className="max-w-full">
            <button
              type="button"
              aria-label={t.reportParams.removeFilter(label, value)}
              onClick={() => onRemove(filterId, value)}
              className="flex min-h-tap max-w-full items-center gap-1.5 rounded-full bg-accent-soft px-3 py-1 text-left text-sm font-semibold text-accent ring-1 ring-inset ring-accent-line transition-colors hover:bg-accent-soft-2 hover:text-accent-deep"
            >
              <span className="min-w-0 [overflow-wrap:anywhere]">
                <span className="font-normal">{label}:</span> {value}
              </span>
              <X className="h-4 w-4 shrink-0" aria-hidden />
            </button>
          </li>
        ))}
        {hidden > 0 ? (
          <li>
            <button
              type="button"
              onClick={onMore}
              className="flex min-h-tap items-center rounded-full bg-surface-2 px-3 text-sm font-semibold text-ink-2 ring-1 ring-inset ring-line hover:text-ink"
            >
              {t.reportSheet.moreChips(hidden)}
            </button>
          </li>
        ) : null}
      </ul>
    </div>
  );
}
