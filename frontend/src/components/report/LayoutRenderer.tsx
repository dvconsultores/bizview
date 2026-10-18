import type {
  ColorRole,
  ReportData,
  ReportDefinition,
  ReportView,
  TrendPoint,
  WebComponent,
  WebLayout,
  LayoutProblem,
} from "../../api/types";
import { formatBucket } from "../../lib/numbers";
import { localized } from "../../lib/labels";
import { useT } from "../../i18n";
import { Alert } from "../Alert";
import { DataTable } from "./DataTable";
import { KpiGrid } from "./KpiGrid";
import { FiltersBlock, SpacerBlock, TextBlock, type LayoutParamsWiring } from "./LayoutBlocks";
import { componentRoles, roleAt } from "./layoutRoles";
import { AreaChart } from "./charts/AreaChart";
import { BarChart } from "./charts/BarChart";
import { LineChart } from "./charts/LineChart";
import { PieChart } from "./charts/PieChart";
import { toNumber, type ChartCategory, type ChartFrame, type ChartSeries } from "./charts/series";

/** Feature 026: renders a `layout.web` (contracts/layout-web.md). One column on phones, `span`
 * columns of 12 from the md breakpoint, declared order as the DOM order (constitution 2.1).
 * Nothing is `eval`ed and no component reads a URL, an HTML string or a colour literal. */

type Table = Extract<ReportView, { type: "table" }>;

const SPAN: Record<number, string> = {
  1: "md:col-span-1",
  2: "md:col-span-2",
  3: "md:col-span-3",
  4: "md:col-span-4",
  5: "md:col-span-5",
  6: "md:col-span-6",
  7: "md:col-span-7",
  8: "md:col-span-8",
  9: "md:col-span-9",
  10: "md:col-span-10",
  11: "md:col-span-11",
  12: "md:col-span-12",
};

const GUTTER: Record<string, string> = { sm: "gap-3", md: "gap-5", lg: "gap-8" };

/** The component catalogue (data-model §3). An unknown type is an error card, never a blank cell. */
const VIEW_TYPES: readonly string[] = ["kpi", "line", "area", "bar", "pie", "donut", "table"];

const DEFAULT_TOP_N = 6;
const DEFAULT_PAGE_SIZE = 25;

export interface LayoutRendererProps {
  layout: WebLayout;
  data: ReportData;
  def: ReportDefinition;
  size?: "normal" | "tv";
  csvBase?: string;
  problems?: LayoutProblem[];
  /** The report screen's own filter wiring, so a `filters` component reuses the same controls. */
  params?: LayoutParamsWiring;
}

export function LayoutRenderer({
  layout,
  data,
  def,
  size = "normal",
  csvBase,
  problems,
  params,
}: LayoutRendererProps) {
  const notes = problems ?? data.layout_problems ?? def.layout_problems ?? [];
  const components = layout.components ?? [];
  if (components.length === 0 && notes.length === 0) return null;

  return (
    <div className={`grid grid-cols-1 md:grid-cols-12 ${GUTTER[layout.gutter ?? "md"] ?? GUTTER.md}`} data-testid="layout-grid">
      {components.map((component, index) => (
        <div
          key={`${component.id}-${index}`}
          className={`min-w-0 ${SPAN[clampSpan(component)]}`}
          data-layout-id={component.id}
          data-layout-type={component.type}
          data-layout-span={clampSpan(component)}
        >
          <Component component={component} data={data} def={def} size={size} csvBase={csvBase} params={params} />
        </div>
      ))}
      {notes.length > 0 ? <Notes notes={notes} /> : null}
    </div>
  );
}

function clampSpan(component: WebComponent): number {
  const value = component.span;
  return typeof value === "number" && Number.isInteger(value) && value >= 1 && value <= 12 ? value : 12;
}

/** A component binds to a payload view by its declared id and by nothing else. */
function resolveView(component: WebComponent, data: ReportData): ReportView | null {
  if (!component.view) return null;
  return data.views.find((view) => view.id === component.view) ?? null;
}

function ErrorCard({ message }: { message: string }) {
  return <Alert tone="error">{message}</Alert>;
}

/** Validation warnings travel with the payload; they are a quiet note, never a failure. */
function Notes({ notes }: { notes: LayoutProblem[] }) {
  const t = useT();
  return (
    <div className="md:col-span-12">
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">{t.layout.problemsTitle}</p>
      <ul className="mt-1 space-y-0.5 text-xs text-ink-muted">
        {notes.map((note, index) => (
          <li key={`${note.code}-${index}`} className="[overflow-wrap:anywhere]">
            {note.path ? `${note.message} · ${note.path}` : note.message}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Component({
  component,
  data,
  def,
  size,
  csvBase,
  params,
}: {
  component: WebComponent;
  data: ReportData;
  def: ReportDefinition;
  size: "normal" | "tv";
  csvBase?: string;
  params?: LayoutParamsWiring;
}) {
  const t = useT();

  if (component.type === "text") return <TextBlock component={component} />;
  if (component.type === "spacer") return <SpacerBlock component={component} />;
  if (component.type === "filters") {
    return <FiltersBlock component={component} def={def} data={data} params={params} />;
  }
  if (!VIEW_TYPES.includes(component.type)) {
    return <ErrorCard message={t.layout.errorCard(component.id, component.type)} />;
  }

  const view = resolveView(component, data);
  if (!view) return <ErrorCard message={t.layout.missingView(component.id, component.view ?? "")} />;

  switch (component.type) {
    case "kpi":
      return <KpiComponent component={component} view={view} data={data} def={def} size={size} />;
    case "line":
    case "area":
    case "bar":
    case "pie":
    case "donut":
      return <ChartComponent component={component} view={view} def={def} />;
    case "table":
      return <TableComponent component={component} view={view} def={def} csvBase={csvBase} size={size} />;
    default:
      return <ErrorCard message={t.layout.errorCard(component.id, component.type)} />;
  }
}

function KpiComponent({
  component,
  view,
  data,
  def,
  size,
}: {
  component: WebComponent;
  view: ReportView;
  data: ReportData;
  def: ReportDefinition;
  size: "normal" | "tv";
}) {
  const t = useT();
  if (view.type !== "kpis") return <ErrorCard message={t.layout.viewShape(component.id, component.view ?? "")} />;
  if (component.metric && !view.items.some((item) => item.metric === component.metric)) {
    return <ErrorCard message={t.layout.missingMetric(component.id, component.metric)} />;
  }

  // The sparkline needs a series, which a KPI view does not carry: the trend view of the same
  // metric provides it (a report that shows both is the usual shape).
  const sparkline = component.sparkline
    ? view.items
        .map((item) => ({ metric: item.metric, points: trendPoints(item.metric, data) }))
        .filter((entry): entry is { metric: string; points: TrendPoint[] } => entry.points !== null)
    : undefined;

  return (
    <KpiGrid
      items={view.items}
      currency={def.currency}
      compared={component.delta !== "none" && Boolean(data.selection.previous)}
      size={size}
      metric={component.metric}
      sparkline={sparkline}
      sparklineRole={roleAt(componentRoles(component), 0)}
    />
  );
}

function trendPoints(metric: string, data: ReportData): TrendPoint[] | null {
  const trend = data.views.find((view) => view.type === "trend" && view.metric === metric);
  return trend && trend.type === "trend" ? trend.points : null;
}

function viewTitle(view: ReportView): string | undefined {
  if (view.type === "trend") return localized(view, "label");
  if (view.type === "ranking") return localized(view, "title") ?? localized(view, "label");
  if (view.type === "table") return localized(view, "title") ?? undefined;
  return undefined;
}

function chartFrame(component: WebComponent, view: ReportView, def: ReportDefinition, fallbackTitle: string): ChartFrame {
  return {
    title: localized(component, "title") ?? viewTitle(view) ?? fallbackTitle,
    summary: localized(view, "summary") ?? "",
    showSummary: component.summary !== false,
    currency: def.currency,
  };
}

interface ChartData {
  categories: ChartCategory[];
  series: ChartSeries[];
  /** True when the categories are an ordered time axis (a trend view), which is what a line needs. */
  ordered: boolean;
}

function buildChartData(
  component: WebComponent,
  view: ReportView,
  roles: ColorRole[],
  previousLabel: string,
): ChartData | { problem: string } | { shape: true } {
  if (view.type === "trend") {
    const declared = component.series;
    if (declared && declared.length > 0 && declared[0] !== view.metric) {
      return { problem: declared[0] };
    }
    const hasPrevious = view.points.some((point) => point.previous !== undefined);
    const series: ChartSeries[] = [
      {
        id: view.metric,
        label: localized(view, "label"),
        values: view.points.map((point) => point.value),
        format: view.format,
        role: roleAt(roles, 0),
      },
    ];
    if (hasPrevious) {
      series.push({
        id: `${view.metric}:previous`,
        label: previousLabel,
        values: view.points.map((point) => point.previous ?? null),
        format: view.format,
        role: roleAt(roles, 1),
        dashed: true,
      });
    }
    return {
      categories: view.points.map((point) => ({
        key: point.bucket,
        label: formatBucket(point.bucket, view.grain),
      })),
      series,
      ordered: true,
    };
  }

  if (view.type === "ranking") {
    if (component.value && component.value !== view.metric) return { problem: component.value };
    if (component.series && component.series.length > 0 && component.series[0] !== view.metric) {
      return { problem: component.series[0] };
    }
    if (component.category && component.category !== view.dimension) return { problem: component.category };
    return {
      categories: view.items.map((item, index) => ({
        key: `${item.key ?? ""}-${index}`,
        label: item.key === null || item.key === undefined ? "—" : String(item.key),
      })),
      series: [
        {
          id: view.metric,
          label: localized(view, "label"),
          values: view.items.map((item) => item.value),
          format: view.format,
          role: roleAt(roles, 0),
        },
      ],
      ordered: false,
    };
  }

  if (view.type === "table") {
    const dimension = view.columns.filter((column) => column.kind === "dimension");
    const metrics = view.columns.filter((column) => column.kind === "metric");
    const wanted = component.x ?? component.category;
    const category = wanted ? dimension.find((column) => column.id === wanted) : dimension[0];
    if (!category) return { problem: wanted ?? "" };
    const wantedSeries = component.series && component.series.length > 0 ? component.series : metrics.map((column) => column.id);
    const chosen: { column: (typeof metrics)[number]; role: ColorRole }[] = [];
    for (const [index, id] of wantedSeries.entries()) {
      const column = metrics.find((entry) => entry.id === id);
      if (!column) return { problem: id };
      chosen.push({ column, role: roleAt(roles, index) });
    }
    if (chosen.length === 0) return { shape: true };
    return {
      categories: view.rows.map((row, index) => ({
        key: `${row[category.id] ?? ""}-${index}`,
        label: row[category.id] === null || row[category.id] === undefined ? "—" : String(row[category.id]),
      })),
      series: chosen.map(({ column, role }) => ({
        id: column.id,
        label: localized(column, "label"),
        values: view.rows.map((row) => toNumber(row[column.id])),
        format: column.format ?? "number",
        role,
      })),
      ordered: false,
    };
  }

  return { shape: true };
}

function ChartComponent({
  component,
  view,
  def,
}: {
  component: WebComponent;
  view: ReportView;
  def: ReportDefinition;
}) {
  const t = useT();
  const roles = componentRoles(component);
  const built = buildChartData(component, view, roles, t.reportParams.display.previous);
  if ("shape" in built) {
    return <ErrorCard message={t.layout.viewShape(component.id, component.view ?? "")} />;
  }
  if ("problem" in built) {
    return <ErrorCard message={t.layout.missingMetric(component.id, built.problem)} />;
  }

  const frame = chartFrame(component, view, def, component.id);

  if (component.type === "pie" || component.type === "donut") {
    const first = built.series[0];
    return (
      <PieChart
        frame={frame}
        categories={built.categories}
        values={first.values}
        roles={roles}
        topN={clampNumber(component.top_n, 2, 12, DEFAULT_TOP_N)}
        otherLabel={localized(component, "other_label") ?? t.layout.others}
        donut={component.type === "donut"}
        format={first.format}
        emptyText={t.reportParams.display.noData}
      />
    );
  }

  if (component.type === "bar") {
    const top = component.top_n;
    const cut = typeof top === "number" && top >= 2 && built.categories.length > top;
    const categories = cut ? built.categories.slice(0, top) : built.categories;
    const series = cut
      ? built.series.map((entry) => ({ ...entry, values: entry.values.slice(0, top) }))
      : built.series;
    return (
      <BarChart
        frame={frame}
        categories={categories}
        series={series}
        orientation={component.orientation ?? "vertical"}
        // `stacked` needs two or more series; with fewer it draws as the grouped bars it is.
        stacked={component.stacked === true && series.length >= 2}
      />
    );
  }

  if (built.ordered) {
    const props = { frame, categories: built.categories, series: built.series };
    return component.type === "area" ? <AreaChart {...props} /> : <LineChart {...props} />;
  }

  // Validation warns about a line over a non-ordered dimension; the documented fallback is bars.
  return (
    <BarChart
      frame={frame}
      categories={built.categories}
      series={built.series}
      orientation="vertical"
      stacked={false}
    />
  );
}

function clampNumber(value: number | undefined, min: number, max: number, fallback: number): number {
  return typeof value === "number" && Number.isInteger(value) && value >= min && value <= max ? value : fallback;
}

function TableComponent({
  component,
  view,
  def,
  csvBase,
  size,
}: {
  component: WebComponent;
  view: ReportView;
  def: ReportDefinition;
  csvBase?: string;
  size: "normal" | "tv";
}) {
  const t = useT();
  if (view.type !== "table") return <ErrorCard message={t.layout.viewShape(component.id, component.view ?? "")} />;
  const table: Table = view;
  const emitted = table.columns.map((column) => column.id);
  const requested = component.columns && component.columns.length > 0 ? component.columns : emitted;
  const missing = requested.find((id) => !emitted.includes(id));
  if (missing) return <ErrorCard message={t.layout.missingMetric(component.id, missing)} />;
  if (component.sort && !requested.includes(component.sort.by)) {
    return <ErrorCard message={t.layout.missingMetric(component.id, component.sort.by)} />;
  }

  return (
    <DataTable
      view={table}
      currency={def.currency}
      csvFileBase={size === "normal" ? csvBase : undefined}
      title={localized(component, "title")}
      columns={requested}
      totals={component.totals === true}
      sort={component.sort}
      pageSize={clampNumber(component.page_size, 5, 200, DEFAULT_PAGE_SIZE)}
    />
  );
}
