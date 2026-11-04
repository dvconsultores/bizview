import { X } from "lucide-react";
import type { ReportDefinition } from "../../api/types";
import { useT } from "../../i18n";
import type { ReportSelection } from "../../lib/reportQuery";
import type { ThemeMode } from "../../theme/themes";
import { isPaletteId } from "../../theme/palette";

export interface ParameterChip {
  key: "period" | "compare" | "theme" | "mode";
  label: string;
  value: string;
}

interface ParameterChipsProps {
  def: ReportDefinition;
  applied: ReportSelection;
  theme: string | null;
  mode: ThemeMode | null;
  declaredTheme: string | null;
  onRemove: (chip: ParameterChip) => void;
}

/** Feature 053: the non-default parameters as removable chips beside the filter chips, so the
 * applied state is readable and undoable without opening the sheet. Only what differs from the
 * report's own defaults gets a chip. */
export function ParameterChips({
  def,
  applied,
  theme,
  mode,
  declaredTheme,
  onRemove,
}: ParameterChipsProps) {
  const t = useT();
  const chips: ParameterChip[] = [];
  if (applied.period !== def.periods.default) {
    chips.push({
      key: "period",
      label: t.reportParams.chipPeriod,
      value: t.reportParams.periodLabels[applied.period] ?? applied.period,
    });
  }
  if (applied.compare !== def.compare.default) {
    chips.push({
      key: "compare",
      label: t.reportParams.chipCompare,
      value: t.reportParams.compareLabels[applied.compare] ?? applied.compare,
    });
  }
  if (theme && theme !== declaredTheme) {
    chips.push({
      key: "theme",
      label: t.reportParams.chipPalette,
      value: isPaletteId(theme) ? t.palette[theme] : theme,
    });
  }
  if (mode) {
    chips.push({
      key: "mode",
      label: t.reportParams.chipTheme,
      value: mode === "dark" ? t.reportParams.themeDark : t.reportParams.themeLight,
    });
  }
  if (chips.length === 0) return null;

  return (
    <ul className="flex flex-wrap gap-2" data-testid="parameter-chips">
      {chips.map((chip) => (
        <li key={chip.key} className="max-w-full">
          <button
            type="button"
            aria-label={t.reportParams.removeParamChip(chip.label, chip.value)}
            onClick={() => onRemove(chip)}
            className="flex min-h-tap max-w-full items-center gap-1.5 rounded-full bg-surface-2 px-3 py-1 text-left text-sm font-semibold text-ink-2 ring-1 ring-inset ring-line transition-colors hover:bg-subtle hover:text-ink"
          >
            <span className="min-w-0 [overflow-wrap:anywhere]">
              <span className="font-normal">{chip.label}:</span> {chip.value}
            </span>
            <X className="h-4 w-4 shrink-0" aria-hidden />
          </button>
        </li>
      ))}
    </ul>
  );
}
