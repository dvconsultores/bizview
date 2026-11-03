/** Palette presets (feature 030) as themes (feature 047): the five built-ins are **themes** in the
 * published format (`./themes/*.json`), and the roles every token class paints with
 * (`fill-chart-3`, `text-chart-positive`) are derived from their tokens. No hex value lives in a
 * report definition (026 FR-005); the installation or the report only names a theme.
 *
 * The built-in files exist byte-identical under `backend/app/reports/themes/` for the PDF renderer
 * (`tests/unit/themes.test.ts` fails on drift), and `cli/bizview_cli/theme.py` validates both with
 * the same rules the server applies to an uploaded one. */
import type { PaletteId } from "../api/types";
import { designVariables, readableOn, semanticVariables } from "./derive";
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
  elegante: presetOf(BUILTIN_THEMES.elegante),
  monocromo: presetOf(BUILTIN_THEMES.monocromo),
  contraste: presetOf(BUILTIN_THEMES.contraste),
  daltonico: presetOf(BUILTIN_THEMES.daltonico),
};

export const PRESET_IDS: readonly PaletteId[] = [
  "impacto",
  "clasico",
  "elegante",
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
  for (const n of SERIES) {
    const colour = t[`series${n}`];
    vars[`chart-${n}`] = triplet(colour);
    // Feature 051: a label drawn *on* a series must read on it in every theme — Contraste's dark
    // series are near-white and Monocromo's light one runs the other way.
    vars[`chart-${n}-ink`] = triplet(readableOn(colour, [t.surface, t.text]));
  }
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

/** Every custom property one theme paints one mode with: the report roles (047) plus the chrome and
 * the geometry (051). The single source the page, the previews and the PDF's web mirror read. */
export function themeVariables(theme: Theme, mode: "light" | "dark"): Record<string, string> {
  const vars: Record<string, string> = { ...semanticVariables(theme, mode) };
  for (const [name, value] of Object.entries(variablesForTokens(deriveTokens(theme, mode)))) {
    vars[`c-${name}`] = value;
  }
  for (const [name, value] of Object.entries(shapeVariables(theme))) vars[name] = value;
  for (const [name, value] of Object.entries(designVariables(theme, mode))) vars[name] = value;
  return vars;
}

/** The device cache: what `public/theme-init.js` replays before first paint, so a reload shows the
 * installation's theme immediately instead of flashing Clásico (FR-006). */
export const TOKENS_KEY = "bizview.theme.tokens";
const TOKENS_VERSION = 1;
const TOKENS_MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;

interface CachedTokens {
  version: number;
  id: string;
  mode: string;
  at: number;
  vars: Record<string, string>;
  /** The enums `index.css` keys its rules on, so the band and the navigation are right at first
   * paint and not one frame later. */
  attrs?: Record<string, string>;
}

function cacheTokens(
  id: string,
  mode: string,
  vars: Record<string, string>,
  attrs: Record<string, string>,
): void {
  try {
    const payload: CachedTokens = {
      version: TOKENS_VERSION, id, mode, at: Date.now(), vars, attrs,
    };
    window.localStorage.setItem(TOKENS_KEY, JSON.stringify(payload));
  } catch {
    /* storage blocked: the theme still applies for this page */
  }
}

/** The cached payload, if it is ours, recent and for this mode; `null` otherwise. */
export function readCachedTokens(mode: string, now: number = Date.now()): CachedTokens | null {
  try {
    const raw = window.localStorage.getItem(TOKENS_KEY);
    if (!raw) return null;
    const payload = JSON.parse(raw) as Partial<CachedTokens>;
    if (payload.version !== TOKENS_VERSION || payload.mode !== mode) return null;
    if (typeof payload.at !== "number" || now - payload.at > TOKENS_MAX_AGE_MS) return null;
    if (!payload.vars || typeof payload.vars !== "object") return null;
    return payload as CachedTokens;
  } catch {
    return null;
  }
}

/** The same, for any theme — a built-in or one the installation uploaded (feature 047). An
 * uploaded theme has no rules of its own in `index.css`, so `data-palette` only carries its id. */
export function applyThemeVariables(theme: Theme, mode: "light" | "dark", id?: string): void {
  const root = document.documentElement;
  const vars = themeVariables(theme, mode);
  for (const [name, value] of Object.entries(vars)) {
    root.style.setProperty(`--${name}`, value);
  }
  const palette = id ?? theme.id;
  // The enums `index.css` turns into styling: a theme names them, it does not write CSS.
  const design = designVariables(theme, mode);
  const attrs: Record<string, string> = {
    palette,
    nav: design["nav-mark"],
    elevation: design["shadow-card"].includes("0 0 0 1px") ? "flat" : "raised",
    cardBorder: design["card-border"],
    heading: String(design["heading-weight"]),
  };
  for (const [name, value] of Object.entries(attrs)) root.dataset[name] = value;
  // The browser's own chrome follows the band, so an installed PWA matches the theme.
  const band = tripletsToColour(vars["c-chrome"]);
  if (band) document.querySelector('meta[name="theme-color"]')?.setAttribute("content", band);
  cacheTokens(palette, mode, vars, attrs);
}

/** A `"R G B"` triplet as a CSS colour, for the places that need one (the meta tag); `""` when the
 * value is not a triplet, so a malformed theme leaves the tag alone instead of painting it wrong. */
export function tripletsToColour(triplet: string | undefined): string {
  const parts = (triplet ?? "").split(" ").map(Number);
  if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) return "";
  return `rgb(${parts.join(" ")})`;
}

/** The custom properties of one theme for one mode, as a JSX `style`: a report whose mode differs
 * from the application's repaints its own area without touching the chrome (047 FR-019). */
export function themeStyle(theme: Theme, mode: "light" | "dark"): Record<string, string> {
  const style: Record<string, string> = {};
  for (const [name, value] of Object.entries(themeVariables(theme, mode))) {
    style[`--${name}`] = value;
  }
  return style;
}
