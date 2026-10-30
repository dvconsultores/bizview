import type { Change, MetricFormat } from "../api/types";
import { currentLocale, t } from "../i18n/live";
import { dateTimeFormat, numberFormat } from "./intl";

function percentSuffix(): string {
  return currentLocale() === "es" ? " %" : "%";
}

/** Figures as the PDF prints them (backend `engine/pdf.py` uses the same rules). */
export function formatValue(value: number | string | null | undefined, format: MetricFormat = "number", currency = "USD"): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "string" || format === "text") return String(value);
  if (format === "currency") {
    return numberFormat({ style: "currency", currency, currencyDisplay: "code", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
  }
  if (format === "integer") return numberFormat({ maximumFractionDigits: 0, useGrouping: true }).format(value);
  if (format === "percent") return `${numberFormat({ maximumFractionDigits: 1 }).format(value)}${percentSuffix()}`;
  return numberFormat({ maximumFractionDigits: 2, useGrouping: true }).format(value);
}

/** Short form for chart axes: 1,2 mil / 1.2K. */
export function formatCompact(value: number): string {
  return numberFormat({ notation: "compact", maximumFractionDigits: 1 }).format(value);
}

/** Feature 042: KPI tiles never wrap — big magnitudes compact (es «2,66 B», en "2.66T"), full
 * value in the tooltip. Currency keeps its code via Intl compact. */
export function formatValueCompact(
  value: number | string | null | undefined,
  format: MetricFormat = "number",
  currency = "USD",
): string {
  if (value === null || value === undefined || value === "" || typeof value === "string") {
    return formatValue(value, format, currency);
  }
  if (format === "text" || format === "percent" || Math.abs(value) < 100_000) {
    return formatValue(value, format, currency);
  }
  if (format === "currency") {
    return numberFormat({
      style: "currency",
      currency,
      currencyDisplay: "code",
      notation: "compact",
      maximumFractionDigits: 2,
    }).format(value);
  }
  return numberFormat({ notation: "compact", maximumFractionDigits: 2 }).format(value);
}

export function formatChange(change: Change | null | undefined): string {
  if (!change) return "—";
  if (change.new) return t.common.new;
  if (change.pct === null) return "—";
  const sign = change.pct > 0 ? "+" : "";
  return `${sign}${numberFormat({ maximumFractionDigits: 1 }).format(change.pct)}${percentSuffix()}`;
}

/** "good" | "bad" | "flat" for colouring a change, honouring whether higher is better. */
export function changeTone(change: Change | null | undefined, better: "higher" | "lower" = "higher"): "good" | "bad" | "flat" {
  if (!change || change.pct === null || Math.abs(change.pct) < 0.05) return "flat";
  const up = change.pct > 0;
  return up === (better === "higher") ? "good" : "bad";
}

/** ISO date (YYYY-MM-DD) → "29 sept 2026" / "Sep 29, 2026"; parsed as UTC so the day never shifts. */
export function formatIsoDate(iso: string): string {
  return dateTimeFormat({ day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(`${iso}T00:00:00Z`));
}

export function formatBucket(iso: string, grain: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return grain === "month"
    ? dateTimeFormat({ month: "short", year: "2-digit", timeZone: "UTC" }).format(d)
    : dateTimeFormat({ day: "numeric", month: "short", timeZone: "UTC" }).format(d);
}

export function formatRange(r: { from: string; to: string }): string {
  return r.from === r.to ? formatIsoDate(r.from) : `${formatIsoDate(r.from)} – ${formatIsoDate(r.to)}`;
}
