import { X } from "lucide-react";
import type { ReactNode } from "react";
import type { ReportDefinition } from "../../api/types";
import { useT } from "../../i18n";
import type { ReportSelection } from "../../lib/reportQuery";
import { defaultSelection, sameSelection } from "../../lib/reportQuery";
import type { AutoRefreshMode } from "../../lib/autoRefresh";
import type { MultiSelectOptions } from "../MultiSelect";
import { AutoRefreshControl } from "./AutoRefreshControl";
import { ParamsForm } from "./ParamsForm";
import { PaletteSelect } from "./PaletteSelect";
import { iconButtonClass } from "../IconButton";

interface ParamBarProps {
  def: ReportDefinition;
  applied: ReportSelection;
  onApply: (selection: ReportSelection) => void;
  loadOptions: (
    filterId: string,
    period: ReportSelection,
    q: string,
    signal: AbortSignal,
  ) => Promise<MultiSelectOptions>;
  onClose: () => void;
  refresh?: { mode: AutoRefreshMode; onChange: (mode: AutoRefreshMode) => void; cacheSeconds?: number | null };
  palette?: { value: string | null; onChange: (preset: string | null) => void };
  /** The export options (format + "Generar reporte"), kept as a compact extra in the row. */
  extra?: ReactNode;
}

/**
 * Feature 030 (owner, 2026-10-24): a small control panel for the parameters — hidden until
 * "Parámetros" is pressed, laid out in one compact row under the meta line, so it never covers the
 * dashboard. Changes apply live (250 ms) like the filters sheet.
 */
export function ParamBar({ def, applied, onApply, loadOptions, onClose, refresh, palette, extra }: ParamBarProps) {
  const t = useT();

  const clear = () => {
    const defaults = defaultSelection(def);
    if (!sameSelection(defaults, applied)) onApply(defaults);
  };

  return (
    <section
      data-testid="param-bar"
      aria-label={t.reportActions.params}
      className="mb-5 rounded-card border border-line bg-surface p-3 shadow-card sm:p-4"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
          {t.reportActions.params}
        </h2>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={clear}
            className="min-h-tap rounded-lg px-2 text-sm font-medium text-ink-muted hover:text-ink"
          >
            {t.reportParams.clear}
          </button>
          <button type="button" onClick={onClose} aria-label={t.common.close} className={iconButtonClass()}>
            <X className="h-5 w-5" aria-hidden />
          </button>
        </div>
      </div>

      <ParamsForm
        def={def}
        applied={applied}
        onApply={onApply}
        loadOptions={loadOptions}
        live
        section="period"
        variant="bar"
      >
        {refresh ? (
          <AutoRefreshControl
            compact
            mode={refresh.mode}
            onChange={refresh.onChange}
            cacheSeconds={refresh.cacheSeconds}
          />
        ) : null}
        {palette ? <PaletteSelect compact value={palette.value} onChange={palette.onChange} /> : null}
        {extra}
      </ParamsForm>
    </section>
  );
}
