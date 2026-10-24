import { Copy } from "lucide-react";
import { useState } from "react";
import type { PaletteId } from "../../api/types";
import { useT } from "../../i18n";
import { isPaletteId, PRESET_IDS } from "../../theme/palette";
import { Button } from "../Button";
import { iconButtonClass } from "../IconButton";
import { Select } from "../Select";

interface PaletteSelectProps {
  /** The preset in force: the report's declared one, or `null` for the installation's. */
  value: string | null;
  /** Applies a preview for this view. `null` restores the declared/installation preset. */
  onChange: (preset: string | null) => void;
  /** Feature 030: just the field, for the parameter panel's row. */
  compact?: boolean;
}

const DESCRIPTIONS: Record<PaletteId, "impactoText" | "clasicoText" | "monocromoText" | "contrasteText" | "daltonicoText"> = {
  impacto: "impactoText",
  clasico: "clasicoText",
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
export function PaletteSelect({ value, onChange, compact = false }: PaletteSelectProps) {
  const t = useT();
  const [copied, setCopied] = useState(false);
  const declared = isPaletteId(value) ? value : null;
  const shown: PaletteId = declared ?? "impacto";
  const snippet = `layout:\n  theme:\n    palette: ${declared ?? "impacto"}`;

  if (compact) {
    return (
      <div className="flex min-w-[9rem] flex-1 items-end gap-1">
        <div className="min-w-0 flex-1" title={t.palette[DESCRIPTIONS[shown]]}>
          <Select label={t.palette.label} value={declared ?? ""} onChange={(event) => onChange(event.target.value || null)}>
            <option value="">{t.palette.installation}</option>
            {PRESET_IDS.map((id) => (
              <option key={id} value={id}>
                {t.palette[id]}
              </option>
            ))}
          </Select>
        </div>
        <button
          type="button"
          aria-label={t.palette.declare}
          title={copied ? t.palette.copied : t.palette.declare}
          onClick={() => {
            void navigator.clipboard?.writeText(snippet).then(
              () => setCopied(true),
              () => setCopied(false),
            );
          }}
          className={iconButtonClass()}
        >
          <Copy className="h-5 w-5" aria-hidden />
        </button>
      </div>
    );
  }

  return (
    <section className="space-y-3 border-t border-line pt-5">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-soft">{t.palette.label}</h3>
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
