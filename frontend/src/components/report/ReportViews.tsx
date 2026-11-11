import { Maximize2, Table2 } from "lucide-react";
import { csvFileName, downloadCsv, toCsv } from "../../lib/csv";
import { viewDataTable } from "../../lib/dataTable";
import { CardMenu } from "./CardMenu";
import type { ReportData, ReportDefinition, ReportView } from "../../api/types";
import { useT } from "../../i18n";
import { localized } from "../../lib/labels";
import { DataTable } from "./DataTable";
import { NoDataCard, RenderErrorCard } from "./RenderErrorCard";
import { KpiGrid } from "./KpiGrid";
import { LayoutRenderer } from "./LayoutRenderer";
import { RankingTable } from "./RankingTable";
import { TrendChart } from "./TrendChart";
import type { LayoutParamsWiring } from "./LayoutBlocks";
import type { CrossFilterState } from "./crossFilter";

/** Feature 056: the id a default view card uses for `?ampliar=`; a layout uses the component id. */
export const VIEW_CARD_PREFIX = "view-";

interface CardProps {
  data: ReportData;
  def: ReportDefinition;
  kpiSize?: "normal" | "tv";
  csvBase?: string;
  params?: LayoutParamsWiring;
  crossFilter?: CrossFilterState;
  onMaximize?: (id: string) => void;
  /** Feature 064: opens a default card's rows as a table. */
  onViewAsTable?: (id: string) => void;
  /** Feature 056b: this card is the one the dialog draws. */
  maximized?: boolean;
}

/** Feature 063: a default card keeps its own dimension while it is cross-filtered. */
export function sourceView(view: ReportView, data: ReportData, crossFilter?: CrossFilterState): ReportView {
  if (!crossFilter?.enabled) return view;
  const dims = Object.keys(crossFilter.filters);
  const used = view.type === "ranking"
    ? [view.dimension]
    : view.type === "table"
      ? view.columns.filter((column) => column.kind === "dimension").map((column) => column.id)
      : [];
  const dimension = dims.find((dim) => used.includes(dim));
  return (dimension && view.id && data.source_views?.[dimension]?.[view.id]) || view;
}

/** One payload view as a card; `id` is what the full-screen dialog needs to find it again. */
function ViewCard({ index, view, card }: { index: number; view: ReportView; card: CardProps }) {
  const { data, def, kpiSize = "normal", csvBase, crossFilter, onMaximize, onViewAsTable, maximized } = card;
  const shown = sourceView(view, data, crossFilter);
  const compared = !!data.selection.previous;
  const id = `${VIEW_CARD_PREFIX}${index}`;
  const table = onViewAsTable && def.interactions?.data_table !== false && !shown.error && !shown.empty
    ? () => onViewAsTable(id) : undefined;
  const maximize = onMaximize ? () => onMaximize(id) : undefined;

  // Feature 038: a view that failed (or came back empty) is its own card; the rest still draws.
  if (view.error) return <RenderErrorCard error={view.error} />;
  if (view.empty) return <NoDataCard error={view.empty} />;
  if (shown.type === "kpis") {
    return <KpiGrid items={shown.items} currency={def.currency} compared={compared} size={kpiSize}
                    maximized={maximized} />;
  }
  if (shown.type === "trend") {
    return <TrendChart view={shown} currency={def.currency} maximized={maximized} />;
  }
  if (shown.type === "ranking") {
    return (
      <RankingTable view={shown} currency={def.currency} compared={compared}
                    better={def.metrics[shown.metric]?.better ?? "higher"}
                    csvFileBase={kpiSize === "normal" ? csvBase : undefined}
                    onMaximize={maximize} onViewAsTable={table} maximized={maximized}
                    crossFilter={crossFilter} />
    );
  }
  return (
    <DataTable view={shown} currency={def.currency}
               csvFileBase={kpiSize === "normal" ? csvBase : undefined}
               onMaximize={maximize} onViewAsTable={table} maximized={maximized}
               crossFilter={crossFilter} />
  );
}

/** The views of a report payload, shared by the report screen, the TV layout and the preview. */
export function ReportViews({ data, def, kpiSize = "normal", csvBase, params, crossFilter, onMaximize, onViewAsTable }: CardProps) {
  const t = useT();

  // Feature 026: a declared layout composes the dashboard; without one the payload order stands.
  if (def.layout?.web) {
    return (
      <LayoutRenderer
        layout={def.layout.web}
        data={data}
        def={def}
        size={kpiSize}
        csvBase={kpiSize === "normal" ? csvBase : undefined}
        problems={data.layout_problems}
        params={params}
        crossFilter={crossFilter}
        onMaximize={onMaximize}
        onViewAsTable={onViewAsTable}
      />
    );
  }

  const card = { data, def, kpiSize, csvBase, params, crossFilter, onMaximize, onViewAsTable };
  return (
    <>
      {data.views.map((view, index) => (
        <div key={index} className="relative h-full" data-view-id={`${VIEW_CARD_PREFIX}${index}`}
             tabIndex={onViewAsTable ? -1 : undefined}
             onDoubleClick={(event) => {
               const target = event.target as Element;
               if (def.interactions?.data_table === false
                 || target.closest('button, a, input, textarea, select, [role="button"]')) return;
               onViewAsTable?.(`${VIEW_CARD_PREFIX}${index}`);
             }}
             onKeyDown={(event) => {
               if (def.interactions?.data_table === false || (event.key !== "t" && event.key !== "T")) return;
               const target = event.target as Element;
               if (target.closest('input, textarea, select, [role="button"]')) return;
               event.preventDefault();
               onViewAsTable?.(`${VIEW_CARD_PREFIX}${index}`);
             }}>
          <ViewCard index={index} view={view} card={card} />
          {(onMaximize || onViewAsTable) ? (
            <div className="absolute right-1 top-1 z-10 flex items-center gap-1 opacity-80 transition-opacity group-hover:opacity-100">
              {(() => {
                const model = viewDataTable(sourceView(view, data, crossFilter), { def, filters: crossFilter?.filters });
                if (!model) return null;
                const exportCsv = () => downloadCsv(csvFileName(model.title), toCsv(
                  model.columns.map((column) => ({ id: column.id, label: column.label })),
                  model.rows.map((row) => Object.fromEntries(
                    model.columns.map((column, i) => [column.id, row.values[i]]))),
                ));
                if (view.type === "ranking" || view.type === "table") return null;
                return <CardMenu title={model.title} onDownloadCsv={exportCsv}
                                 onViewAsTable={onViewAsTable ? () => onViewAsTable(`${VIEW_CARD_PREFIX}${index}`) : undefined} />;
              })()}
              {onViewAsTable && def.interactions?.data_table !== false ? (
                <button
                  type="button"
                  onClick={() => onViewAsTable(`${VIEW_CARD_PREFIX}${index}`)}
                  aria-label={t.reportParams.dataTable.title(
                    ("title" in view && localized(view as { title?: string }, "title"))
                      || t.reportParams.detailTitle,
                  )}
                  title={t.reportParams.dataTable.action}
                  data-table-action={`${VIEW_CARD_PREFIX}${index}`}
                  className="hidden h-11 w-11 items-center justify-center rounded-lg text-ink-faint hover:bg-subtle hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus sm:inline-flex"
                >
                  <Table2 className="h-5 w-5" aria-hidden />
                </button>
              ) : null}
              {onMaximize ? (
                <button
                  type="button"
                  onClick={() => onMaximize(`${VIEW_CARD_PREFIX}${index}`)}
                  aria-label={t.layout.maximize(
                    ("title" in view && localized(view as { title?: string }, "title"))
                      || t.reportParams.detailTitle,
                  )}
                  data-maximize={`${VIEW_CARD_PREFIX}${index}`}
                  className="inline-flex h-11 w-11 items-center justify-center rounded-lg text-ink-faint hover:bg-subtle hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                >
                  <Maximize2 className="h-5 w-5" aria-hidden />
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
      ))}
    </>
  );
}

/** One default view, rendered alone: what the full-screen dialog draws for a `view-<n>` id. */
export function SingleView({ index, data, def, csvBase, params, crossFilter }: Omit<CardProps, "onMaximize" | "onViewAsTable" | "kpiSize"> & {
  index: number;
}) {
  const view = data.views[index];
  if (!view) return null;
  return <ViewCard index={index} view={view} card={{ data, def, csvBase, params, crossFilter, maximized: true }} />;
}
