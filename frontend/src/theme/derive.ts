/** From a theme to every colour the application's own chrome paints with (feature 051).
 *
 * A theme declares its report palette (feature 047) and, optionally, seven chrome tokens. This
 * module turns that into the complete semantic token set `index.css` used to hold as literals, so
 * applying a theme repaints the header, the sidebar, the cards, the buttons, the tables and the
 * dialogs — not only the charts — without a component knowing which theme is in force.
 *
 * Everything here is pure: no React, no DOM. `palette.ts` writes the result to `<html>`, the
 * appearance previews paint from the same functions, and the tests read them directly.
 */
import type { Theme, ThemeMode, ThemeShape, ThemeTokens } from "./themes";
import { shapeOf } from "./themes";

/** The seven tokens a theme may author for the chrome; absent ones are derived from its palette. */
export const CHROME_TOKENS = [
  "canvas", "chrome", "chrome_text", "field", "line", "accent", "warning",
] as const;

export type ChromeTokens = Record<(typeof CHROME_TOKENS)[number], string>;

type RGB = [number, number, number];

const HEX = /^#?[0-9a-fA-F]{6}$/;

export function hexToRgb(hex: string): RGB {
  const value = hex.replace("#", "");
  return [
    parseInt(value.slice(0, 2), 16),
    parseInt(value.slice(2, 4), 16),
    parseInt(value.slice(4, 6), 16),
  ];
}

export function rgbToHex([r, g, b]: RGB): string {
  const part = (n: number) => Math.max(0, Math.min(255, Math.round(n))).toString(16).padStart(2, "0");
  return `#${part(r)}${part(g)}${part(b)}`.toUpperCase();
}

/** `t` of `b` over `a` — an sRGB mix, which is what a designer does by eye in a colour picker. */
export function mix(a: string, b: string, t: number): string {
  const [ar, ag, ab] = hexToRgb(a);
  const [br, bg, bb] = hexToRgb(b);
  return rgbToHex([ar + (br - ar) * t, ag + (bg - ag) * t, ab + (bb - ab) * t]);
}

/** WCAG 2.2 relative luminance of one channel set. */
function channel(value: number): number {
  const s = value / 255;
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}

function luminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex);
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

/** WCAG contrast ratio between two opaque colours. */
export function contrast(a: string, b: string): number {
  const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (high + 0.05) / (low + 0.05);
}

/** `colour` deepened (or lightened) toward `toward` until it reads on `background` at `needs`:1.
 *
 * A theme's accent is a hue intent — "cyan", "bronze" — and this is what makes the token usable as
 * text and as a selected-state ink whatever the hue: the derivation moves the lightness, never the
 * hue, and stops at the first value that passes. */
export function ensureReadable(
  colour: string,
  background: string,
  toward: string,
  needs = 4.5,
): string {
  let candidate = colour;
  for (let step = 0; step <= 25; step += 1) {
    candidate = step === 0 ? colour : mix(colour, toward, step * 0.04);
    if (contrast(candidate, background) >= needs) return candidate;
  }
  return candidate;
}

/** The first candidate that reads on `background` at `needs`:1, else the one with the best ratio. */
export function readableOn(background: string, candidates: readonly string[], needs = 4.5): string {
  return (
    candidates.find((candidate) => contrast(candidate, background) >= needs) ??
    [...candidates].sort((a, b) => contrast(b, background) - contrast(a, background))[0]
  );
}

/** `#RRGGBB` → `"R G B"`: the triplet every `--c-*` token holds, consumed with an alpha placeholder. */
export function triplet(hex: string): string {
  return hexToRgb(hex).join(" ");
}

const sure = (value: string | undefined, fallback: string): string =>
  value && HEX.test(value) ? (value.startsWith("#") ? value : `#${value}`).toUpperCase() : fallback;

/** The theme's chrome tokens: the ones it declares, else read off its own palette. A theme written
 * before feature 051 has none, and still themes the whole application. */
export function chromeOf(theme: Theme, mode: ThemeMode): ChromeTokens {
  const t: ThemeTokens = theme[mode];
  const dark = mode === "dark";
  const primary = sure(t.primary, "#3A7393");
  const surface = sure(t.surface, "#FFFFFF");
  const canvas = sure(t.canvas, mix(surface, primary, dark ? 0.1 : 0.05));
  const chrome = sure(t.chrome, dark ? mix(canvas, primary, 0.35) : primary);
  return {
    canvas,
    chrome,
    chrome_text: sure(t.chrome_text, readableOn(chrome, ["#FFFFFF", sure(t.text, "#0F172A")])),
    field: sure(t.field, mix(surface, sure(t.card, surface), dark ? 0.5 : 0.6)),
    line: sure(t.line, sure(t.grid, mix(surface, sure(t.text, "#0F172A"), 0.12))),
    accent: sure(t.accent, primary),
    warning: sure(t.warning, dark ? mix("#FBBF24", surface, 0.15) : mix("#B45309", surface, 0.08)),
  };
}

/**
 * Every `--c-*` token the chrome paints with, for one mode.
 *
 * The ramps (ink, accent, status) are mixed from the theme's own anchors rather than hand-written,
 * so a theme authored with seven colours still gets a complete, coherent set — and so the product
 * has one place where "a shade of the accent" is defined.
 */
export function semanticVariables(theme: Theme, mode: ThemeMode): Record<string, string> {
  const t = theme[mode];
  const dark = mode === "dark";
  const chrome = chromeOf(theme, mode);
  const surface = sure(t.surface, "#FFFFFF");
  const card = sure(t.card, surface);
  const text = sure(t.text, "#0F172A");
  const muted = sure(t.muted, text);
  const line = chrome.line;
  const primary = sure(t.primary, "#3A7393");
  const positive = sure(t.positive, "#047857");
  const negative = sure(t.negative, "#BE123C");

  // Toward the ink is "darker" in light and "lighter" in dark: one direction per mode, so a shade
  // means the same thing in both.
  const toward = dark ? surface : text;
  // The accent is used as an ink (links, selected states, the bottom bar), so the token that reaches
  // CSS is the theme's hue at a lightness that reads on its own surfaces.
  // Readability moves toward the theme's own ink, which is the direction that increases contrast
  // in both modes; the accent's tinted backgrounds are tints of the accent, not of the primary.
  const accentTint = (amount: number) => mix(surface, chrome.accent, amount);
  const accent = ensureReadable(
    ensureReadable(chrome.accent, surface, text, 4.5),
    accentTint(dark ? 0.2 : 0.1),
    text,
    4.5,
  );
  const deepen = (colour: string, amount: number) => mix(colour, toward, amount);
  const tint = (amount: number) => accentTint(amount);

  const tokens: Record<string, string> = {
    canvas: chrome.canvas,
    surface,
    subtle: card,
    "surface-2": mix(card, line, dark ? 0.35 : 0.45),
    fill: line,
    field: chrome.field,
    "field-focus": primary,
    "line-soft": mix(line, surface, dark ? 0.55 : 0.5),
    line,
    "line-strong": mix(line, text, dark ? 0.35 : 0.25),
    "line-accent": mix(line, primary, 0.45),
    ink: text,
    "ink-2": mix(text, muted, 0.45),
    "ink-3": muted,
    "ink-muted": mix(muted, text, 0.3),
    // A muted label still has to be read: the lightest shade of it that reaches AA on both
    // backgrounds it is painted on.
    "ink-soft": ensureReadable(
      ensureReadable(mix(muted, surface, dark ? 0.3 : 0.4), surface, text, 4.5),
      chrome.canvas,
      text,
      4.5,
    ),
    "ink-faint": mix(muted, surface, 0.62),
    "accent-bright": mix(primary, surface, 0.15),
    accent,
    "accent-strong": deepen(primary, 0.35),
    "accent-deep": deepen(primary, 0.55),
    "accent-soft": tint(dark ? 0.2 : 0.1),
    "accent-soft-2": tint(dark ? 0.28 : 0.2),
    "accent-line": tint(dark ? 0.45 : 0.4),
    "accent-line-strong": tint(dark ? 0.6 : 0.65),
    primary,
    "primary-hover": mix(primary, toward, 0.18),
    "primary-active": mix(primary, toward, 0.32),
    "on-primary": readableOn(primary, ["#FFFFFF", text, surface, "#0B1220"]),
    focus: mix(primary, surface, 0.15),
    "danger-bright": mix(negative, surface, 0.15),
    danger: negative,
    "danger-strong": deepen(negative, 0.25),
    "danger-deep": deepen(negative, 0.45),
    "danger-soft": sure(t.delta_negative, mix(negative, surface, dark ? 0.2 : 0.92)),
    "danger-line": mix(sure(t.delta_negative, surface), negative, dark ? 0.5 : 0.3),
    "danger-border": mix(sure(t.delta_negative, surface), negative, 0.65),
    "danger-focus": mix(negative, surface, 0.15),
    "danger-solid": negative,
    "danger-solid-hover": deepen(negative, 0.15),
    "danger-solid-active": deepen(negative, 0.3),
    "success-bright": mix(positive, surface, 0.15),
    success: positive,
    "success-strong": deepen(positive, 0.2),
    "success-deep": deepen(positive, 0.35),
    "success-soft": sure(t.delta_positive, mix(positive, surface, dark ? 0.2 : 0.92)),
    "success-line": mix(sure(t.delta_positive, surface), positive, dark ? 0.5 : 0.3),
    warning: chrome.warning,
    "warning-strong": deepen(chrome.warning, 0.2),
    "warning-deep": deepen(chrome.warning, 0.35),
    "warning-soft": mix(surface, chrome.warning, dark ? 0.18 : 0.1),
    "warning-line": mix(surface, chrome.warning, dark ? 0.45 : 0.35),
    backdrop: dark ? "#020617" : text,
    toast: dark ? mix(surface, text, 0.15) : text,
    chrome: chrome.chrome,
    "on-chrome": chrome.chrome_text,
  };
  // The theme may pin any of them exactly (`app`, feature 051): Clásico does, so the appearance
  // production has today cannot drift; every other theme declares only its anchors.
  return Object.fromEntries(
    Object.entries({ ...tokens, ...(theme.app?.[mode] ?? {}) }).map(([name, value]) => [
      `c-${name}`,
      triplet(value),
    ]),
  );
}

const RADIUS: Record<ThemeShape["radius"], { card: string; button: string; field: string; nav: string }> = {
  sm: { card: "0.75rem", button: "0.5rem", field: "0.5rem", nav: "0.5rem" },
  md: { card: "1.25rem", button: "0.875rem", field: "0.5rem", nav: "0.875rem" },
  lg: { card: "1.5rem", button: "9999px", field: "0.75rem", nav: "1rem" },
};

const ELEVATION: Record<ThemeShape["elevation"], { light: [string, string]; dark: [string, string] }> = {
  flat: {
    light: ["0 0 0 1px rgb(15 23 42 / 0.06)", "0 0 0 1px rgb(15 23 42 / 0.10)"],
    dark: ["0 0 0 1px rgb(148 163 184 / 0.16)", "0 0 0 1px rgb(148 163 184 / 0.24)"],
  },
  soft: {
    light: [
      "0 1px 2px rgb(15 23 42 / 0.06), 0 4px 16px -4px rgb(15 23 42 / 0.08)",
      "0 10px 30px -10px rgb(40 67 84 / 0.30)",
    ],
    dark: [
      "0 0 0 1px rgb(51 65 85 / 0.6), 0 4px 16px -4px rgb(0 0 0 / 0.5)",
      "0 0 0 1px rgb(51 65 85 / 0.8), 0 10px 30px -10px rgb(0 0 0 / 0.7)",
    ],
  },
  strong: {
    light: [
      "0 2px 4px rgb(15 23 42 / 0.08), 0 10px 28px -10px rgb(15 23 42 / 0.22)",
      "0 18px 50px -12px rgb(15 23 42 / 0.35)",
    ],
    dark: [
      "0 0 0 1px rgb(71 85 105 / 0.55), 0 12px 32px -12px rgb(0 0 0 / 0.75)",
      "0 0 0 1px rgb(100 116 139 / 0.7), 0 18px 40px -12px rgb(0 0 0 / 0.85)",
    ],
  },
};

const CARD_BORDER: Record<ThemeShape["card_border"], string> = {
  none: "0px", hairline: "1px", strong: "2px",
};

const DIVIDER: Record<ThemeShape["divider"], string> = { soft: "1px", strong: "2px" };

const HEADING: Record<ThemeShape["heading"], [string, string]> = {
  normal: ["700", "-0.01em"],
  tight: ["800", "-0.03em"],
};

/** `md` keeps the numerals the product shipped with; `lg` is the reference app's larger scale. */
const KPI_SCALE: Record<ThemeShape["kpi_scale"], [string, string, string, string, string, string]> = {
  md: ["1.125rem", "1.5rem", "1.875rem", "2.25rem", "3rem", "-0.01em"],
  lg: ["1.25rem", "1.875rem", "2.25rem", "3rem", "3.75rem", "-0.01em"],
  xl: ["1.75rem", "2.5rem", "3rem", "3.75rem", "4.5rem", "-0.03em"],
};

/** The geometry a theme chooses: radii, elevation, borders, navigation, headings and KPI weight.
 * The enums stay a fixed, validated list (FR-012), so no theme can ask for geometry the components
 * do not have a rule for. */
export function designVariables(theme: Theme, mode: ThemeMode): Record<string, string> {
  const shape = shapeOf(theme);
  const radius = RADIUS[shape.radius];
  const [shadowCard, shadowRaised] = ELEVATION[shape.elevation][mode];
  const [weight, tracking] = HEADING[shape.heading];
  const [numeral, numeralLg, numeralTv, numeralTvLg, numeralTvXl, kpiTracking] = KPI_SCALE[shape.kpi_scale];
  return {
    "radius-card": radius.card,
    "radius-button": shape.button === "square" ? "0.25rem" : shape.button === "pill" ? "9999px" : radius.button,
    "radius-nav": radius.nav,
    "radius-field": radius.field,
    "shadow-card": shadowCard,
    "shadow-raised": shadowRaised,
    "card-border": CARD_BORDER[shape.card_border],
    divider: DIVIDER[shape.divider],
    "heading-weight": weight,
    "heading-tracking": tracking,
    "nav-mark": shape.nav,
    "kpi-numeral": numeral,
    "kpi-numeral-lg": numeralLg,
    "kpi-numeral-tv": numeralTv,
    "kpi-numeral-tv-lg": numeralTvLg,
    "kpi-numeral-tv-xl": numeralTvXl,
    "kpi-tracking": kpiTracking,
    "t-radius": radius.card,
    "t-density": { compact: "0.75", normal: "1" }[shape.density],
    "t-kpi-scale": numeral,
    "t-font": {
      sans: "ui-sans-serif, system-ui, sans-serif",
      serif: "ui-serif, Georgia, serif",
      mono: "ui-monospace, SFMono-Regular, monospace",
    }[shape.font],
    "t-badge": shape.badge,
  };
}
