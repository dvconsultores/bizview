import { Copy } from "lucide-react";
import { useState } from "react";
import type { PaletteId } from "../../api/types";
import { useT } from "../../i18n";
import { isPaletteId, PRESET_IDS, themeStyle } from "../../theme/palette";
import { BUILTIN_THEMES, type ThemeMode } from "../../theme/themes";
import { Button } from "../Button";
import { Select } from "../Select";
import { ChipRow, type ChipOption } from "./ChipRow";

interface PaletteSelectProps {
  /** The preset in force: the report's declared one, or `null` for the installation's. */
  value: string | null;
  /** Applies a preview for this view. `null` restores the declared/installation preset. */
  onChange: (preset: string | null) => void;
  /** The mode the swatches paint in: the report area's own (feature 053). */
  mode?: ThemeMode;
}

/** The eight series roles, as literal class names so the stylesheet builds them (no colour here). */
const SWATCHES = [
  "bg-chart-1", "bg-chart-2", "bg-chart-3", "bg-chart-4",
  "bg-chart-5", "bg-chart-6", "bg-chart-7", "bg-chart-8",
] as const;

const DESCRIPTIONS: Record<PaletteId, "impactoText" | "clasicoText" | "eleganteText" | "monocromoText" | "contrasteText" | "daltonicoText"> = {
  impacto: "impactoText",
  clasico: "clasicoText",
  elegante: "eleganteText",
  monocromo: "monocromoText",
  contraste: "contrasteText",
  daltonico: "daltonicoText",
};

/**
 * Feature 030 (US5.3, FR-008): the report's "Paleta". The declared value lives in the report
 * definition (`layout.theme.palette`), so it travels with the workspace version and reaches the PDF;
 * this panel shows it, previews any preset live, and hands over the exact snippet to declare — the
 * definition itself changes through the project editor + a validated workspace version (IX), never
 * from a reader's screen.
 */
export function PaletteSelect({ value, onChange, mode = "light" }: PaletteSelectProps) {
  const t = useT();
  const [copied, setCopied] = useState(false);
  const declared = isPaletteId(value) ? value : null;
  const shown: PaletteId = declared ?? "impacto";
  const snippet = `layout:\n  theme:\n    palette: ${declared ?? "impacto"}`;

  // Feature 059: one horizontal chip row on phones (a swatch pair + the name), the select above 640.
  const chips: ChipOption[] = [
    { id: "", label: t.palette.installation },
    ...PRESET_IDS.map((id) => ({
      id,
      label: t.palette[id],
      visual: (
        <span aria-hidden style={themeStyle(BUILTIN_THEMES[id], mode)} className="flex items-center gap-0.5">
          <span className="h-2.5 w-2.5 rounded-full bg-chart-1" />
          <span className="h-2.5 w-2.5 rounded-full bg-chart-2" />
          <span className="h-2.5 w-2.5 rounded-full bg-chart-3" />
        </span>
      ),
    })),
  ];

  return (
    <section className="space-y-3 border-t border-line pt-5">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-soft max-sm:sr-only">{t.palette.label}</h3>
      <div className="sm:hidden">
        <ChipRow
          label={t.palette.label}
          labelHidden
          testId="palette-chips"
          options={chips}
          value={declared ?? ""}
          onChange={(id) => onChange(id || null)}
        />
      </div>
      <div className="max-sm:hidden">
        <Select
          label={t.palette.label}
          value={declared ?? ""}
          onChange={(event) => onChange(event.target.value || null)}
        >
          <option value="">{t.palette.installation}</option>
          {PRESET_IDS.map((id) => (
            <option key={id} value={id}>
              {t.palette[id]}
            </option>
          ))}
        </Select>
      </div>
      {/* The selected theme's colours, painted with the same derivation the dashboard uses. */}
      <div
        data-testid="palette-swatches"
        data-theme="preview"
        style={themeStyle(BUILTIN_THEMES[shown], mode)}
        className="flex flex-wrap items-center gap-1"
        aria-hidden
      >
        {SWATCHES.map((role) => (
          <span key={role} className={`h-3 w-6 rounded-full ${role}`} />
        ))}
      </div>
      <p className="text-sm text-ink-muted">{t.palette[DESCRIPTIONS[shown]]}</p>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          icon={<Copy className="h-4 w-4" aria-hidden />}
          onClick={() => {
            void navigator.clipboard?.writeText(snippet).then(
              () => setCopied(true),
              () => setCopied(false),
            );
          }}
        >
          {t.palette.declare}
        </Button>
        {copied ? <span className="text-xs font-medium text-chart-positive">{t.palette.copied}</span> : null}
      </div>
    </section>
  );
}
