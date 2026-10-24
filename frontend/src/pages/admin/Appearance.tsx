import { Check, Palette } from "lucide-react";
import { useEffect, useState, type CSSProperties } from "react";
import { api, ApiError } from "../../api/client";
import type { AppearanceSettings, PaletteId } from "../../api/types";
import { Alert } from "../../components/Alert";
import { BackLink } from "../../components/BackLink";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { PageHeader } from "../../components/PageHeader";
import { Spinner } from "../../components/Spinner";
import { useToast } from "../../components/Toast";
import { useT } from "../../i18n";
import { PALETTES, paletteVariables, PRESET_IDS } from "../../theme/palette";

const DESCRIPTIONS: Record<PaletteId, "impactoText" | "clasicoText" | "monocromoText" | "contrasteText" | "daltonicoText"> = {
  impacto: "impactoText",
  clasico: "clasicoText",
  monocromo: "monocromoText",
  contraste: "contrasteText",
  daltonico: "daltonicoText",
};

/** A preset previewed in both themes: the variables are scoped to this card, so the page's own
 * palette is untouched and no colour literal appears in the source (colour guard, feature 006). */
function PreviewCard({ preset }: { preset: PaletteId }) {
  const t = useT();
  const themes = ["light", "dark"] as const;
  return (
    <div className="flex flex-col gap-2">
      {themes.map((theme) => {
        const values = paletteVariables(PALETTES[preset], theme);
        const style = Object.fromEntries(
          Object.entries(values).map(([name, value]) => [`--c-${name}`, value]),
        ) as CSSProperties;
        return (
          <div
            key={theme}
            style={style}
            className="rounded-lg border border-line bg-[var(--c-kpi-surface)] p-3"
            data-theme-preview={theme}
          >
            <div className="flex items-baseline gap-2">
              <span className="text-lg font-bold tabular-nums text-[var(--c-kpi-text)]">1.284</span>
              <span className="rounded-full bg-[var(--c-kpi-delta-bg-positive)] px-2 py-0.5 text-[10px] font-semibold text-[var(--c-chart-positive)]">
                +12,4 %
              </span>
            </div>
            <div className="mt-2 flex items-end gap-1" aria-hidden>
              {[14, 22, 18, 28, 24].map((height, index) => (
                <span
                  key={index}
                  className="w-3 rounded-sm"
                  style={{ height, backgroundColor: `var(--c-chart-${(index % 8) + 1})` }}
                />
              ))}
            </div>
            <svg viewBox="0 0 120 24" className="mt-1 h-6 w-full" aria-hidden>
              <polyline
                points="0,18 20,14 40,16 60,8 80,10 100,4 120,6"
                fill="none"
                stroke="var(--c-chart-2)"
                strokeWidth="2"
              />
            </svg>
            <p className="mt-1 text-[10px] text-[var(--c-chart-label)]">
              {theme === "light" ? t.appearance.lightPreview : t.appearance.darkPreview}
            </p>
          </div>
        );
      })}
    </div>
  );
}

/** Administración → Apariencia (feature 030, FR-008): the installation's palette preset. */
export function Appearance() {
  const t = useT();
  const toast = useToast();
  const [settings, setSettings] = useState<AppearanceSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<PaletteId | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .get<AppearanceSettings>("/api/admin/appearance")
      .then((value) => {
        setSettings(value);
        setSelected(value.palette_preset);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : t.common.unexpected));
  }, [t]);

  const save = async () => {
    if (!selected) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await api.put<{ palette_preset: PaletteId }>("/api/admin/appearance", {
        palette_preset: selected,
      });
      setSettings({ ...settings!, palette_preset: saved.palette_preset });
      // The installation default changed: reload so every page applies it from /api/config.
      toast(t.appearance.saved);
      window.setTimeout(() => window.location.reload(), 600);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.common.unexpected);
    } finally {
      setSaving(false);
    }
  };

  const dirty = !!settings && selected !== null && selected !== settings.palette_preset;

  return (
    <div className="max-w-3xl space-y-5">
      <BackLink to="/admin" />
      <PageHeader title={t.appearance.title} subtitle={t.appearance.subtitle} />

      {error ? <Alert tone="error">{error}</Alert> : null}

      {!settings ? (
        <div role="status" className="flex justify-center py-12 text-accent">
          <Spinner className="h-8 w-8" />
          <span className="sr-only">{t.common.loading}</span>
        </div>
      ) : (
        <>
          <div role="radiogroup" aria-label={t.appearance.title} className="grid gap-4 sm:grid-cols-2">
            {PRESET_IDS.map((preset) => {
              const checked = selected === preset;
              return (
                <Card
                  key={preset}
                  className={`p-4 ${checked ? "ring-2 ring-primary" : ""}`}
                >
                  <button
                    type="button"
                    role="radio"
                    aria-checked={checked}
                    onClick={() => setSelected(preset)}
                    className="flex w-full items-start gap-2 text-left"
                  >
                    <span
                      className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${
                        checked ? "border-primary bg-primary text-on-primary" : "border-line-strong"
                      }`}
                      aria-hidden
                    >
                      {checked ? <Check className="h-3.5 w-3.5" /> : null}
                    </span>
                    <span className="min-w-0">
                      <span className="block font-semibold text-ink">
                        {t.palette[preset]}
                        {preset === settings.palette_preset ? (
                          <span className="ml-2 text-xs font-normal text-ink-muted">{t.appearance.current}</span>
                        ) : null}
                      </span>
                      <span className="mt-1 block text-sm text-ink-muted">{t.palette[DESCRIPTIONS[preset]]}</span>
                    </span>
                  </button>
                  <div className="mt-3">
                    <PreviewCard preset={preset} />
                  </div>
                </Card>
              );
            })}
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="primary"
              loading={saving}
              disabled={!dirty}
              icon={<Palette className="h-5 w-5" aria-hidden />}
              onClick={() => void save()}
            >
              {t.common.save}
            </Button>
            {dirty ? (
              <Button variant="secondary" onClick={() => setSelected(settings.palette_preset)}>
                {t.common.cancel}
              </Button>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}
