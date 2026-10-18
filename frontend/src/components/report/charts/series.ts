import type { ColorRole, MetricFormat } from "../../../api/types";

/** What every layout chart draws from: categories along the axis, one entry per series (feature
 * 026, research R5). The renderer builds these from the payload view the component is bound to. */

export interface ChartCategory {
  key: string;
  label: string;
}

export interface ChartSeries {
  id: string;
  label: string;
  values: (number | null)[];
  format: MetricFormat;
  role: ColorRole;
  /** The previous-period series is drawn dashed, exactly as `TrendChart` draws it today. */
  dashed?: boolean;
}

/** Card title, accessible name and currency: shared by every chart in a layout. */
export interface ChartFrame {
  title: string;
  summary: string;
  /** `summary: false` in the layout omits both the `role="img"`/`aria-label` and the caption. */
  showSummary: boolean;
  currency: string;
}

/** The engine's sentence is the chart's accessible name and its visible caption. */
export function chartSummary(frame: ChartFrame): string | undefined {
  return frame.showSummary && frame.summary ? frame.summary : undefined;
}

/** A payload cell → number, or `null` when the figure is absent (a gap, never a zero). */
export function toNumber(value: unknown): number | null {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}
