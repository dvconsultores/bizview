/** Palette presets (feature 030): product data in `./palettes/*.json`, resolved from semantic roles
 * to CSS custom properties so every existing token class (`fill-chart-3`, `text-chart-positive`)
 * follows the preset in both themes. No hex value lives in a report definition (026 FR-005); the
 * installation or the report only names a preset. The same files exist, byte-identical, under
 * `backend/app/reports/palettes/` for the PDF renderer (`tests/unit/palette-presets.test.ts` fails
 * on drift). */
import type { PaletteId } from "../api/types";
import clasicoJson from "./palettes/clasico.json";
import contrasteJson from "./palettes/contraste.json";
import daltonicoJson from "./palettes/daltonico.json";
import impactoJson from "./palettes/impacto.json";
import monocromoJson from "./palettes/monocromo.json";

export interface PaletteTheme {
  primary: string;
  series1: string;
  series2: string;
  series3: string;
  series4: string;
  series5: string;
  series6: string;
  series7: string;
  series8: string;
  positive: string;
  negative: string;
  neutral: string;
  grid: string;
  surface: string;
  kpi_text: string;
  kpi_delta_bg: { positive: string; negative: string };
}

export interface PalettePreset {
  id: PaletteId;
  label_key: string;
  /** `sequential` presets are one hue and are checked on lightness steps, not on ΔE. */
  strategy: "categorical" | "sequential";
  light: PaletteTheme;
  dark: PaletteTheme;
}

// The JSON files widen their string literals; the palette test re-checks every value and role.
export const PALETTES: Record<PaletteId, PalettePreset> = {
  impacto: impactoJson as PalettePreset,
  clasico: clasicoJson as PalettePreset,
  monocromo: monocromoJson as PalettePreset,
  contraste: contrasteJson as PalettePreset,
  daltonico: daltonicoJson as PalettePreset,
};

export const PRESET_IDS: readonly PaletteId[] = [
  "impacto",
  "clasico",
  "monocromo",
  "contraste",
  "daltonico",
];

export const DEFAULT_PRESET: PaletteId = "impacto";

export const isPaletteId = (value: unknown): value is PaletteId =>
  typeof value === "string" && (PRESET_IDS as readonly string[]).includes(value);

/** Report override → installation default → the product default (data-model §4). An unknown value
 * is ignored rather than breaking the page: the report keeps rendering with the next one in line. */
export function effectivePreset(
  reportOverride?: string | null,
  installationPreset?: string | null,
): PaletteId {
  if (isPaletteId(reportOverride)) return reportOverride;
  if (isPaletteId(installationPreset)) return installationPreset;
  return DEFAULT_PRESET;
}

const SERIES = [1, 2, 3, 4, 5, 6, 7, 8] as const;

/** `#RRGGBB` → `"R G B"`: the space-separated triplet the semantic tokens expect, since every
 * token is declared as `--c-x: R G B` and consumed with an alpha placeholder. */
function triplet(hex: string): string {
  const v = hex.replace("#", "");
  return `${parseInt(v.slice(0, 2), 16)} ${parseInt(v.slice(2, 4), 16)} ${parseInt(v.slice(4, 6), 16)}`;
}

/** The custom properties of `contracts/palette-preset.md` → "Web token mapping". */
export function paletteVariables(preset: PalettePreset, theme: "light" | "dark"): Record<string, string> {
  const t = preset[theme];
  const vars: Record<string, string> = {
    "chart-positive": triplet(t.positive),
    "chart-negative": triplet(t.negative),
    "chart-neutral": triplet(t.neutral),
    "chart-grid": triplet(t.grid),
    "chart-axis": triplet(t.grid),
    "chart-label": triplet(t.neutral),
    "kpi-text": triplet(t.kpi_text),
    "kpi-surface": triplet(t.surface),
    "kpi-neutral": triplet(t.neutral),
    "kpi-delta-bg-positive": triplet(t.kpi_delta_bg.positive),
    "kpi-delta-bg-negative": triplet(t.kpi_delta_bg.negative),
  };
  for (const n of SERIES) vars[`chart-${n}`] = triplet(t[`series${n}`]);
  return vars;
}

/** Applies the preset for the resolved theme on `<html>`; `data-palette` lets `index.css` add the
 * preset's own typography/surfaces (FR-009). Idempotent and cheap: called on theme or preset change. */
export function applyPalette(presetId: PaletteId, theme: "light" | "dark"): void {
  const root = document.documentElement;
  const preset = PALETTES[presetId] ?? PALETTES[DEFAULT_PRESET];
  for (const [name, value] of Object.entries(paletteVariables(preset, theme))) {
    root.style.setProperty(`--c-${name}`, value);
  }
  root.dataset.palette = preset.id;
}
