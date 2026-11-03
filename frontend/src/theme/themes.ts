/** Themes as data (feature 047): the six built-ins in the authored format, plus the derivation the
 * renderers need.
 *
 * A theme is the product's published contract — `cli/bizview_cli/schemas/theme.schema.json`, the same
 * file the backend validates and the authoring pack ships — and the built-ins obey it like any
 * uploaded one. The runtime roles the components already paint with (`series1..8`, `kpi_text`,
 * `kpi_delta_bg`, …) are **derived** here, so the authored contract can grow without touching a
 * renderer. The JSON files exist byte-identical under `backend/app/reports/themes/` for the PDF
 * (`tests/unit/themes.test.ts` fails on drift). */
import clasicoJson from "./themes/clasico.json";
import contrasteJson from "./themes/contraste.json";
import daltonicoJson from "./themes/daltonico.json";
import eleganteJson from "./themes/elegante.json";
import impactoJson from "./themes/impacto.json";
import monocromoJson from "./themes/monocromo.json";

export type ThemeMode = "light" | "dark";
export type ThemeId =
  | "impacto"
  | "clasico"
  | "elegante"
  | "monocromo"
  | "contraste"
  | "daltonico";

/** The authored tokens of one mode. The last seven are the chrome (feature 051): optional, and
 * derived from the report tokens above when a theme does not declare them. */
export interface ThemeTokens {
  surface: string;
  card: string;
  text: string;
  muted: string;
  grid: string;
  primary: string;
  positive: string;
  negative: string;
  neutral: string;
  delta_positive: string;
  delta_negative: string;
  series: string[];
  canvas?: string;
  chrome?: string;
  chrome_text?: string;
  field?: string;
  line?: string;
  accent?: string;
  warning?: string;
}

/** The shape choices, all from fixed lists so a theme cannot ask for what the renderers lack. */
export interface ThemeShape {
  radius: "sm" | "md" | "lg";
  density: "compact" | "normal";
  kpi_scale: "md" | "lg" | "xl";
  font: "sans" | "serif" | "mono";
  badge: "filled" | "outline";
  // Feature 051: the dimensions a theme differs on beyond colour.
  elevation: "flat" | "soft" | "strong";
  button: "rounded" | "pill" | "square";
  nav: "gradient" | "solid" | "bar" | "outline";
  divider: "soft" | "strong";
  heading: "normal" | "tight";
  card_border: "none" | "hairline" | "strong";
}

export interface Theme {
  /** Feature 051: the exact chrome token set, by semantic name, per mode. Optional. */
  app?: Partial<Record<ThemeMode, Record<string, string>>>;
  id: string;
  name: string;
  name_en: string;
  version: number;
  strategy?: "categorical" | "sequential";
  light: ThemeTokens;
  dark: ThemeTokens;
  shape?: Partial<ThemeShape>;
}

/** What the components and the PDF paint with — the roles 030 defined. */
export interface RuntimeTheme {
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
  card: string;
  muted: string;
  text: string;
  kpi_text: string;
  kpi_delta_bg: { positive: string; negative: string };
}

export const SHAPE_DEFAULTS: ThemeShape = {
  radius: "md", density: "normal", kpi_scale: "lg", font: "sans", badge: "filled",
  elevation: "soft", button: "rounded", nav: "gradient", divider: "soft", heading: "normal",
  card_border: "hairline",
};

export const BUILTIN_THEMES: Record<ThemeId, Theme> = {
  impacto: impactoJson as Theme,
  clasico: clasicoJson as Theme,
  elegante: eleganteJson as Theme,
  monocromo: monocromoJson as Theme,
  contraste: contrasteJson as Theme,
  daltonico: daltonicoJson as Theme,
};

export const THEME_IDS: readonly ThemeId[] = [
  "impacto", "clasico", "elegante", "monocromo", "contraste", "daltonico",
];

/** The four the product offers as identities (feature 051). The rest stay valid — a report or a
 * project may name them — and appear under "compatibility" in the appearance page. */
export const OFFICIAL_THEME_IDS: readonly ThemeId[] = [
  "clasico", "impacto", "elegante", "contraste",
];

export const LEGACY_THEME_IDS: readonly ThemeId[] = ["daltonico", "monocromo"];

export const DEFAULT_THEME: ThemeId = "impacto";

/** Authored tokens → the roles the renderers consume. A theme may carry 3 to 8 series; the chart
 * maps eight, so the last one repeats rather than leaving a hole. */
export function deriveTokens(theme: Theme, mode: ThemeMode): RuntimeTheme {
  const t = theme[mode];
  const series = [...t.series];
  while (series.length < 8) series.push(series[series.length - 1]);
  const out = {
    primary: t.primary, positive: t.positive, negative: t.negative, neutral: t.neutral,
    grid: t.grid, surface: t.surface, card: t.card, muted: t.muted, text: t.text,
    kpi_text: t.text,
    kpi_delta_bg: { positive: t.delta_positive, negative: t.delta_negative },
  } as RuntimeTheme;
  series.slice(0, 8).forEach((colour, index) => {
    (out as unknown as Record<string, string>)[`series${index + 1}`] = colour;
  });
  return out;
}

export function shapeOf(theme: Theme): ThemeShape {
  return { ...SHAPE_DEFAULTS, ...(theme.shape ?? {}) };
}

export function isThemeId(value: unknown): value is ThemeId {
  return typeof value === "string" && (THEME_IDS as readonly string[]).includes(value);
}

/** The shape tokens as CSS custom properties: the enums every component reads instead of a number. */
export function shapeVariables(theme: Theme): Record<string, string> {
  const shape = shapeOf(theme);
  return {
    "t-radius": { sm: "4px", md: "8px", lg: "14px" }[shape.radius],
    "t-density": { compact: "0.75", normal: "1" }[shape.density],
    "t-kpi-scale": { md: "1", lg: "1.25", xl: "1.5" }[shape.kpi_scale],
    "t-font": { sans: "ui-sans-serif, system-ui, sans-serif", serif: "ui-serif, Georgia, serif",
                mono: "ui-monospace, SFMono-Regular, monospace" }[shape.font],
    "t-badge": shape.badge,
  };
}
