/** Palette presets (feature 030) as themes (feature 047): the five built-ins are **themes** in the
 * published format (`./themes/*.json`), and the roles every token class paints with
 * (`fill-chart-3`, `text-chart-positive`) are derived from their tokens. No hex value lives in a
 * report definition (026 FR-005); the installation or the report only names a theme.
 *
 * The built-in files exist byte-identical under `backend/app/reports/themes/` for the PDF renderer
 * (`tests/unit/themes.test.ts` fails on drift), and `cli/bizview_cli/theme.py` validates both with
 * the same rules the server applies to an uploaded one. */
import type { PaletteId } from "../api/types";
import { BUILTIN_THEMES, deriveTokens, shapeVariables, type Theme, type ThemeMode } from "./themes";

export type PaletteTheme = ReturnType<typeof deriveTokens>;

export interface PalettePreset {
  id: PaletteId;
  label_key: string;
  /** `sequential` presets are one hue and are checked on lightness steps, not on ΔE. */
  strategy: "categorical" | "sequential";
  light: PaletteTheme;
  dark: PaletteTheme;
}

function presetOf(theme: Theme): PalettePreset {
  return {
    id: theme.id as PaletteId,
    label_key: `palette.${theme.id}`,
    strategy: theme.strategy ?? "categorical",
    light: deriveTokens(theme, "light" as ThemeMode),
    dark: deriveTokens(theme, "dark" as ThemeMode),
  };
}

// Derived from the themes: one authored source, and the palette test re-checks every value and role.
export const PALETTES: Record<PaletteId, PalettePreset> = {
  impacto: presetOf(BUILTIN_THEMES.impacto),
  clasico: presetOf(BUILTIN_THEMES.clasico),
  monocromo: presetOf(BUILTIN_THEMES.monocromo),
  contraste: presetOf(BUILTIN_THEMES.contraste),
  daltonico: presetOf(BUILTIN_THEMES.daltonico),
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

/** The custom properties any theme's tokens resolve to, one mode at a time: what a preview card or
 * a report container paints with. Shared by the built-ins and by an uploaded theme, so a preview
 * cannot disagree with the page it previews. */
export function variablesForTokens(t: PaletteTheme): Record<string, string> {
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

/** The custom properties of `contracts/palette-preset.md` → "Web token mapping". */
export function paletteVariables(preset: PalettePreset, theme: "light" | "dark"): Record<string, string> {
  return variablesForTokens(preset[theme]);
}

/** Applies the preset for the resolved theme on `<html>`; `data-palette` lets `index.css` add the
 * preset's own typography/surfaces (FR-009). Idempotent and cheap: called on theme or preset change. */
export function applyPalette(presetId: PaletteId, theme: "light" | "dark"): void {
  const preset = PALETTES[presetId] ?? PALETTES[DEFAULT_PRESET];
  const root = document.documentElement;
  for (const [name, value] of Object.entries(paletteVariables(preset, theme))) {
    root.style.setProperty(`--c-${name}`, value);
  }
  root.dataset.palette = preset.id;
}

/** The same, for any theme — a built-in or one the installation uploaded (feature 047). An
 * uploaded theme has no rules of its own in `index.css`, so `data-palette` only carries its id. */
export function applyThemeVariables(theme: Theme, mode: "light" | "dark", id?: string): void {
  const root = document.documentElement;
  for (const [name, value] of Object.entries(variablesForTokens(deriveTokens(theme, mode)))) {
    root.style.setProperty(`--c-${name}`, value);
  }
  for (const [name, value] of Object.entries(shapeVariables(theme))) {
    root.style.setProperty(`--${name}`, value);
  }
  root.dataset.palette = id ?? theme.id;
}

/** The custom properties of one theme for one mode, as a JSX `style`: a report whose mode differs
 * from the application's repaints its own area without touching the chrome (047 FR-019). */
export function themeStyle(theme: Theme, mode: "light" | "dark"): Record<string, string> {
  const style: Record<string, string> = {};
  for (const [name, value] of Object.entries(variablesForTokens(deriveTokens(theme, mode)))) {
    style[`--c-${name}`] = value;
  }
  for (const [name, value] of Object.entries(shapeVariables(theme))) style[`--${name}`] = value;
  return style;
}
