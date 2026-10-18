import type { ReportData, ReportDefinition } from "../api/types";
import { t } from "../i18n/live";
import { formatDateTime } from "./format";

/** Whether this report is in direct-source (live) mode. */
export function isDirect(data: ReportData | null | undefined): boolean {
  return data?.freshness.mode === "direct";
}

/** Whether the direct source failed and the data is stale. */
export function isStale(data: ReportData | null | undefined): boolean {
  return isDirect(data) && data?.freshness.stale === true;
}

/** Text used when the direct source did not respond. */
export function staleText(data: ReportData): string {
  const time = data.freshness.queried_at ?? data.freshness.updated_at;
  return t.reportParams.stale(formatDateTime(time));
}

/**
 * User-facing freshness text for the report context block.
 * Dataset reports keep the existing "Datos actualizados" wording.
 */
export function freshnessText(
  data: ReportData | null | undefined,
  def?: ReportDefinition | null,
): string {
  if (!data) {
    return "—";
  }
  if (!isDirect(data)) {
    return data.freshness.updated_at
      ? formatDateTime(data.freshness.updated_at)
      : t.reportParams.notLoaded;
  }
  const time = data.freshness.queried_at ?? data.freshness.updated_at;
  if (!time) {
    return t.reportParams.notLoaded;
  }
  if (data.freshness.stale === true) {
    return staleText(data);
  }
  const raw = data.freshness.source || def?.direct?.source || "";
  const source = raw === "bi" ? t.directReads.bi : raw;
  return t.reportParams.live(source, formatDateTime(time));
}
