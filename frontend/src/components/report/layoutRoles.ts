import type { ColorRole, FontName, WebComponent } from "../../api/types";

/** Feature 026 (data-model §6, research R8): a layout names semantic roles and named fonts, never
 * colours; this module is the single place that resolves them to the app's own tokens. An unknown
 * or missing role falls back to `primary` and never throws. */

const FALLBACK: ColorRole = "primary";

const FILL: Record<ColorRole, string> = {
  primary: "fill-primary",
  positive: "fill-success",
  negative: "fill-danger",
  neutral: "fill-ink-soft",
  muted: "fill-ink-faint",
  series1: "fill-chart-1",
  series2: "fill-chart-2",
  series3: "fill-chart-3",
  series4: "fill-chart-4",
  series5: "fill-chart-5",
  series6: "fill-chart-6",
  series7: "fill-chart-7",
  series8: "fill-chart-8",
};

const STROKE: Record<ColorRole, string> = {
  primary: "stroke-primary",
  positive: "stroke-success",
  negative: "stroke-danger",
  neutral: "stroke-ink-soft",
  muted: "stroke-ink-faint",
  series1: "stroke-chart-1",
  series2: "stroke-chart-2",
  series3: "stroke-chart-3",
  series4: "stroke-chart-4",
  series5: "stroke-chart-5",
  series6: "stroke-chart-6",
  series7: "stroke-chart-7",
  series8: "stroke-chart-8",
};

const SURFACE: Record<ColorRole, string> = {
  primary: "bg-primary",
  positive: "bg-success",
  negative: "bg-danger",
  neutral: "bg-ink-soft",
  muted: "bg-ink-faint",
  series1: "bg-chart-1",
  series2: "bg-chart-2",
  series3: "bg-chart-3",
  series4: "bg-chart-4",
  series5: "bg-chart-5",
  series6: "bg-chart-6",
  series7: "bg-chart-7",
  series8: "bg-chart-8",
};

const SERIES_ROLES: ColorRole[] = [
  "series1",
  "series2",
  "series3",
  "series4",
  "series5",
  "series6",
  "series7",
  "series8",
];

/** A role the theme does not define (`undefined`, a typo or a hex value) is treated as absent. */
export function knownRole(role: unknown): ColorRole | null {
  return typeof role === "string" && role in FILL ? (role as ColorRole) : null;
}

/** The roles a component declares, in order; anything unusable is dropped. */
export function componentRoles(component: Pick<WebComponent, "colors">): ColorRole[] {
  const declared = Array.isArray(component.colors) ? component.colors : component.colors ? [component.colors] : [];
  return declared.map(knownRole).filter((role): role is ColorRole => role !== null);
}

/** Role of the n-th series: the component's own role when it declares one, otherwise the series
 * palette in order (`series1` is the current period, `series2` the previous one, dashed). */
export function roleAt(roles: ColorRole[], index: number): ColorRole {
  return roles[index] ?? SERIES_ROLES[index % SERIES_ROLES.length] ?? FALLBACK;
}

export function fillClass(role?: ColorRole | null): string {
  return FILL[knownRole(role) ?? FALLBACK];
}

export function strokeClass(role?: ColorRole | null): string {
  return STROKE[knownRole(role) ?? FALLBACK];
}

/** Swatches and legends: the same role as a flat surface. */
export function surfaceClass(role?: ColorRole | null): string {
  return SURFACE[knownRole(role) ?? FALLBACK];
}

const FONT: Record<FontName, string> = {
  sans: "font-sans",
  sans_bold: "font-sans font-bold",
  serif: "font-serif",
  mono: "font-mono",
};

/** Named fonts only apply inside a `text` block; the app shell keeps its own face. */
export function fontClass(name?: FontName | null): string {
  return name && name in FONT ? FONT[name] : "";
}
