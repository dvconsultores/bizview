import { Maximize2 } from "lucide-react";
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
  /** Feature 056b: this card is the one the dialog draws. */
  maximized?: boolean;
}

/** Feature 063: a default card keeps its own dimension while it is cross-filtered. */
function sourceView(view: ReportView, data: ReportData, crossFilter?: CrossFilterState): ReportView {
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
  const { data, def, kpiSize = "normal", csvBase, crossFilter, onMaximize, maximized } = card;
  const shown = sourceView(view, data, crossFilter);
  const compared = !!data.selection.previous;
  const maximize = onMaximize ? () => onMaximize(`${VIEW_CARD_PREFIX}${index}`) : undefined;

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
                    onMaximize={maximize} maximized={maximized}
                    crossFilter={crossFilter} />
    );
  }
  return (
    <DataTable view={shown} currency={def.currency}
               csvFileBase={kpiSize === "normal" ? csvBase : undefined}
               onMaximize={maximize} maximized={maximized}
               crossFilter={crossFilter} />
  );
}

/** The views of a report payload, shared by the report screen, the TV layout and the preview. */
export function ReportViews({ data, def, kpiSize = "normal", csvBase, params, crossFilter, onMaximize }: CardProps) {
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
      />
    );
  }

  const card = { data, def, kpiSize, csvBase, params, crossFilter, onMaximize };
  return (
    <>
      {data.views.map((view, index) => (
        <div key={index} className="relative h-full" data-view-id={`${VIEW_CARD_PREFIX}${index}`}>
          <ViewCard index={index} view={view} card={card} />
          {onMaximize ? (
            <button
              type="button"
              onClick={() => onMaximize(`${VIEW_CARD_PREFIX}${index}`)}
              aria-label={t.layout.maximize(
                ("title" in view && localized(view as { title?: string }, "title"))
                  || t.reportParams.detailTitle,
              )}
              data-maximize={`${VIEW_CARD_PREFIX}${index}`}
              className="absolute right-1 top-1 z-10 inline-flex h-11 w-11 items-center justify-center rounded-lg text-ink-faint opacity-80 transition-opacity hover:bg-subtle hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              <Maximize2 className="h-5 w-5" aria-hidden />
            </button>
          ) : null}
        </div>
      ))}
    </>
  );
}

/** One default view, rendered alone: what the full-screen dialog draws for a `view-<n>` id. */
export function SingleView({ index, data, def, csvBase, params, crossFilter }: Omit<CardProps, "onMaximize" | "kpiSize"> & {
  index: number;
}) {
  const view = data.views[index];
  if (!view) return null;
  return <ViewCard index={index} view={view} card={{ data, def, csvBase, params, crossFilter, maximized: true }} />;
}
