import type { ReactNode } from "react";
import type { ReportDefinition } from "../../api/types";
import { useT } from "../../i18n";
import type { AutoRefreshMode } from "../../lib/autoRefresh";
import type { ReportSelection } from "../../lib/reportQuery";
import type { ThemeMode } from "../../theme/themes";
import type { MultiSelectOptions } from "../MultiSelect";
import { Select } from "../Select";
import { AutoRefreshControl } from "./AutoRefreshControl";
import { PaletteSelect } from "./PaletteSelect";
import { ParamsForm } from "./ParamsForm";

export interface ReportParamsPanelProps {
  def: ReportDefinition;
  applied: ReportSelection;
  onApply: (selection: ReportSelection) => void;
  loadOptions: (
    filterId: string,
    period: ReportSelection,
    q: string,
    signal: AbortSignal,
  ) => Promise<MultiSelectOptions>;
  /** Auto-refresh cadence (kept per report, not in the URL). */
  refresh?: {
    mode: AutoRefreshMode;
    onChange: (mode: AutoRefreshMode) => void;
    cacheSeconds?: number | null;
  };
  /** The palette preview and the theme mode are view-only and live in the URL (053). */
  palette?: { value: string | null; onChange: (preset: string | null) => void };
  /** Offered only when the report declares its own theme (047). */
  themeMode?: { value: ThemeMode | null; onChange: (mode: ThemeMode | null) => void };
  /** The mode the swatches paint in (the report area's own). */
  mode?: ThemeMode;
  /** Extra content under the rows (the shared page has none). */
  children?: ReactNode;
}

/**
 * Feature 053: the Parámetros tab of the report sheet — one control per row, label above, in the
 * order a reader thinks of them. It replaces the inline card that pushed the dashboard down and
 * mixed export with parameters. Every control applies live; `Limpiar` and `Listo` live in the
 * sheet's footer, so this panel is only the list.
 */
export function ReportParamsPanel({
  def,
  applied,
  onApply,
  loadOptions,
  refresh,
  palette,
  themeMode,
  mode = "light",
  children,
}: ReportParamsPanelProps) {
  const t = useT();
  const modeOptions: { id: ThemeMode | null; label: string }[] = [
    { id: null, label: t.reportParams.themeAuto },
    { id: "light", label: t.reportParams.themeLight },
    { id: "dark", label: t.reportParams.themeDark },
  ];

  return (
    <div className="space-y-5" data-testid="report-params-panel">
      <ParamsForm
        def={def}
        applied={applied}
        onApply={onApply}
        loadOptions={loadOptions}
        live
        section="period"
        showClear={false}
      >
        {refresh ? (
          <AutoRefreshControl
            mode={refresh.mode}
            onChange={refresh.onChange}
            cacheSeconds={refresh.cacheSeconds}
          />
        ) : null}

        {palette ? (
          <PaletteSelect value={palette.value} onChange={palette.onChange} mode={mode} />
        ) : null}

        {themeMode ? (
          <section className="mt-5 border-t border-line pt-5">
            <Select
              label={t.reportParams.theme}
              value={themeMode.value ?? ""}
              onChange={(event) =>
                themeMode.onChange((event.target.value || null) as ThemeMode | null)
              }
              hint={t.reportParams.themeHint}
            >
              {modeOptions.map((option) => (
                <option key={option.id ?? "auto"} value={option.id ?? ""}>
                  {option.label}
                </option>
              ))}
            </Select>
          </section>
        ) : null}

        {children}
      </ParamsForm>
    </div>
  );
}
