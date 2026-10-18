import type { IntegrationRunDataset, RollupOutcome, RunPath } from "../api/types";
import { t } from "../i18n/live";

export function rollupSummary(rollups?: Record<string, RollupOutcome>): string | null {
  if (!rollups || Object.keys(rollups).length === 0) return null;
  const okCount = Object.values(rollups).filter((r) => r.ok).length;
  const failedIds = Object.entries(rollups)
    .filter(([, r]) => !r.ok)
    .map(([id]) => id);
  const parts: string[] = [];
  if (okCount > 0) parts.push(t.integrations.rollups.updated(okCount));
  if (failedIds.length > 0) parts.push(t.integrations.rollups.failed(failedIds.join(", ")));
  return parts.join(" · ") || null;
}

export function pathLabel(path?: RunPath): string | null {
  switch (path) {
    case "copy":
    case "bulk":
      return t.integrations.paths.copy;
    case "copy+polars":
      return t.integrations.paths.copyPolars;
    case "rows":
      return t.integrations.paths.rows;
    case "rows+polars":
      return t.integrations.paths.rowsPolars;
    default:
      return null;
  }
}

export function formatMs(ms: number): string {
  if (ms < 1000) {
    return `${ms} ms`;
  }
  const seconds = ms / 1000;
  return `${seconds.toFixed(1).replace(".", ",")} s`;
}

export function datasetSummary(ds: string, n: IntegrationRunDataset): string {
  let result = t.integrations.transform.rowsWritten(ds, n.written);
  if (n.full) {
    result += ` (${t.integrations.transform.full})`;
  }
  const path = pathLabel(n.path);
  if (path) {
    result += ` · ${path}`;
  }
  if (n.fallback) {
    result += ` · ${t.integrations.transform.fallback(n.fallback)}`;
  }
  if (n.transform_mode) {
    result += ` · Polars ${t.integrations.transform.modes[n.transform_mode]} ${formatMs(n.transform_ms ?? 0)}`;
    if (n.rows_in !== undefined && n.rows_in !== n.extracted) {
      result += ` (${t.integrations.transform.inputRows(n.rows_in)})`;
    }
  }
  return result;
}
