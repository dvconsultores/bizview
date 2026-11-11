import type { MetricFormat, ReportDefinition, ReportView, WebComponent } from "../api/types";
import { t } from "../i18n/live";
import { localized } from "./labels";
import { formatBucket, formatValue } from "./numbers";

/** Feature 064: one column of the table behind a card. */
export interface DataColumn {
  id: string;
  label: string;
  kind: "dimension" | "metric" | "derived";
  format?: MetricFormat | "bucket";
  align: "left" | "right";
}

/** One row as the card draws it; `values` keep the raw value so sorting and CSV stay exact. */
export interface DataRow {
  id: string;
  values: (string | number | null)[];
  /** Present only when the row can cross-filter (a ranking/table dimension). */
  dimension?: string;
  value?: string;
}

export interface DataTableModel {
  title: string;
  columns: DataColumn[];
  rows: DataRow[];
  truncated: boolean;
  /** A KPI sparkline's series by date, shown under the KPI rows. */
  series?: DataTableModel;
  /** The grain a `bucket` column formats with. */
  grain?: "day" | "week" | "month";
}

export interface DataTableOptions {
  component?: WebComponent;
  def: ReportDefinition;
  filters?: Record<string, string[]>;
  /** The report's trend views, for a KPI card's sparkline. */
  trend?: (metric: string) => Extract<ReportView, { type: "trend" }> | undefined;
}

function title(view: ReportView, component: WebComponent | undefined): string {
  const own = component ? localized(component, "title") : undefined;
  if (own) return own;
  if (view.type === "ranking") return localized(view, "title") ?? localized(view, "label");
  if (view.type === "table") return localized(view, "title") ?? t.reportParams.detailTitle;
  if (view.type === "trend") return localized(view, "label");
  if (view.type === "kpis" && view.items.length === 1) return localized(view.items[0], "label");
  return t.reportParams.detailTitle;
}

function selected(filters: Record<string, string[]> | undefined, dimension: string | undefined,
                  value: string | null | undefined): boolean {
  if (!filters || !dimension || value === null || value === undefined) return false;
  return (filters[dimension] ?? []).includes(value);
}

function kpiModel(view: Extract<ReportView, { type: "kpis" }>, options: DataTableOptions): DataTableModel {
  const hasPrevious = view.items.some((item) => item.previous !== null);
  const columns: DataColumn[] = [
    { id: "metric", label: t.reportParams.dataTable.metricColumn, kind: "dimension", align: "left" },
    { id: "value", label: t.reportParams.dataTable.valueColumn, kind: "metric", align: "right" },
  ];
  if (hasPrevious) {
    columns.push({ id: "previous", label: t.reportParams.display.previousPeriodColumn, kind: "derived", align: "right" });
    columns.push({ id: "change", label: t.reportParams.display.changeColumn, kind: "derived", format: "percent", align: "right" });
  }
  const rows = view.items.map((item, index) => ({
    id: `${item.metric}-${index}`,
    values: hasPrevious
      ? [localized(item, "label"), item.value, item.previous, item.change?.pct ?? (item.change?.new ? t.common.new : null)]
      : [localized(item, "label"), item.value],
  }));
  const metric = options.component?.metric ?? (view.items.length === 1 ? view.items[0].metric : undefined);
  const trend = metric ? options.trend?.(metric) : undefined;
  return {
    title: title(view, options.component),
    columns,
    rows,
    truncated: false,
    series: trend ? trendModel(trend, options) : undefined,
  };
}

function trendModel(view: Extract<ReportView, { type: "trend" }>, options: DataTableOptions): DataTableModel {
  const hasPrevious = view.points.some((point) => point.previous !== undefined);
  const columns: DataColumn[] = [
    { id: "bucket", label: t.reportParams.dataTable.periodColumn, kind: "dimension", format: "bucket", align: "left" },
    { id: view.metric, label: localized(view, "label"), kind: "metric", format: view.format, align: "right" },
  ];
  if (hasPrevious) {
    columns.push({ id: `${view.metric}:previous`, label: t.reportParams.display.previousPeriodColumn, kind: "derived", format: view.format, align: "right" });
  }
  const rows = view.points.map((point, index) => ({
    id: `${point.bucket}-${index}`,
    values: hasPrevious
      ? [point.bucket, point.value, point.previous ?? null]
      : [point.bucket, point.value],
  }));
  return { title: title(view, options.component), columns, rows, truncated: false, grain: view.grain };
}

function rankingModel(view: Extract<ReportView, { type: "ranking" }>, options: DataTableOptions): DataTableModel {
  const hasPrevious = view.items.some((item) => item.previous !== null);
  const columns: DataColumn[] = [
    { id: "key", label: localized(view, "dimension_label"), kind: "dimension", align: "left" },
    { id: "value", label: localized(view, "label"), kind: "metric", format: view.format, align: "right" },
  ];
  if (hasPrevious) {
    columns.push({ id: "previous", label: t.reportParams.display.previousPeriodColumn, kind: "derived", format: view.format, align: "right" });
    columns.push({ id: "change", label: t.reportParams.display.changeColumn, kind: "derived", format: "percent", align: "right" });
  }
  columns.push({ id: "share", label: t.reportParams.dataTable.totalColumn, kind: "derived", format: "percent", align: "right" });
  const rows = view.items.map((item, index) => {
    const raw = item.filter ?? item.key;
    const value = raw === null || raw === undefined ? null : String(raw);
    return {
      id: `${value ?? ""}-${index}`,
      values: hasPrevious
        ? [item.key, item.value, item.previous, item.change?.pct ?? (item.change?.new ? t.common.new : null), item.share]
        : [item.key, item.value, item.share],
      dimension: view.dimension,
      value: value ?? undefined,
    };
  });
  return {
    title: title(view, options.component),
    columns,
    rows,
    truncated: view.truncated === true,
  };
}

function tableModel(view: Extract<ReportView, { type: "table" }>, options: DataTableOptions): DataTableModel {
  const wanted = options.component?.columns;
  const chosen = wanted?.length
    ? wanted.flatMap((id) => view.columns.filter((column) => column.id === id))
    : view.columns;
  const columns: DataColumn[] = chosen.map((column) => ({
    id: column.id,
    label: localized(column, "label"),
    kind: column.kind,
    format: column.kind === "metric" ? column.format ?? "number" : undefined,
    align: column.kind === "metric" ? "right" : "left",
  }));
  const dimension = chosen.find((column) => column.kind === "dimension");
  const rows: DataRow[] = view.rows.map((row, index) => {
    const raw = dimension ? row[dimension.id] : null;
    const key = dimension ? row[`__key_${dimension.id}`] ?? raw : raw;
    return {
      id: `${raw ?? ""}-${index}`,
      values: columns.map((column) => row[column.id] ?? null),
      dimension: dimension?.id,
      value: key === null || key === undefined ? undefined : String(key),
    };
  });
  if (options.component?.totals === true && view.totals) {
    rows.push({
      id: "totals",
      values: columns.map((column, index) => index === 0 ? t.layout.totals : view.totals?.[column.id] ?? null),
    });
  }
  return { title: title(view, options.component), columns, rows, truncated: view.truncated === true };
}

/** The rows a card draws, as columns and rows; `null` when the view has nothing to show. */
export function viewDataTable(view: ReportView, options: DataTableOptions): DataTableModel | null {
  if (view.error || view.empty) return null;
  if (view.type === "kpis") return kpiModel(view, options);
  if (view.type === "trend") return trendModel(view, options);
  if (view.type === "ranking") return rankingModel(view, options);
  return tableModel(view, options);
}

/** The display string of one cell, in the report's formats. */
export function formatCell(
  value: string | number | null,
  column: DataColumn,
  currency: string,
  grain = "day",
): string {
  if (column.format === "bucket") return typeof value === "string" ? formatBucket(value, grain) : "—";
  if (column.kind === "dimension" || column.kind === "derived" && column.format === undefined) {
    return value === null || value === undefined ? "—" : String(value);
  }
  return formatValue(value, column.format as MetricFormat | undefined, currency);
}

export { selected };
