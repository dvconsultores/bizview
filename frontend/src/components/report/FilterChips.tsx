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
  /** Feature 063: a multi-value chip removes the dimension's whole selection. */
  onRemoveAll: (filterId: string) => void;
  /** Opens the sheet's Filtros tab ("+N más"). */
  onMore: () => void;
  /** How many chips fit before the overflow (feature 030 edge case: two lines, then "+N más"). */
  limit?: number;
}

/** The applied filters as removable chips under the meta line (FR-004, US3.2). */
export function FilterChips({ def, applied, onRemove, onRemoveAll, onMore, limit = 6 }: FilterChipsProps) {
  const t = useT();
  const chipsId = useId();
  // Feature 063: a click can filter a dimension the sheet does not list, so every applied filter
  // has a chip; a multi-select collapses to one chip with its count.
  const entries = Object.entries(applied.filters)
    .filter(([, values]) => values.length > 0)
    .map(([filterId, values]) => ({
      filterId,
      values,
      label: localized(def.dimensions[filterId], "label") ?? filterId,
    }));
  if (entries.length === 0) return null;

  const shown = entries.slice(0, limit);
  const hidden = entries.length - shown.length;

  return (
    <div className="min-w-0">
      <ul aria-labelledby={chipsId} className="flex flex-wrap gap-2">
        <li className="sr-only" id={chipsId}>
          {t.reportParams.activeFilters}
        </li>
        {shown.map(({ filterId, values, label }) => {
          const multiple = values.length > 1;
          return (
            <li key={filterId} className="max-w-full">
              <button
                type="button"
                aria-label={multiple
                  ? t.reportParams.removeFilterAll(label)
                  : t.reportParams.removeFilter(label, values[0])}
                onClick={() => (multiple ? onRemoveAll(filterId) : onRemove(filterId, values[0]))}
                className="flex min-h-tap max-w-full items-center gap-1.5 rounded-full bg-accent-soft px-3 py-1 text-left text-sm font-semibold text-accent ring-1 ring-inset ring-accent-line transition-colors hover:bg-accent-soft-2 hover:text-accent-deep"
              >
                <span className="min-w-0 [overflow-wrap:anywhere]">
                  <span className="font-normal">{label}:</span>{" "}
                  {multiple ? t.reportParams.selectedValues(values.length) : values[0]}
                </span>
                <X className="h-4 w-4 shrink-0" aria-hidden />
              </button>
            </li>
          );
        })}
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
