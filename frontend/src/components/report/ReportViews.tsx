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

/** Feature 056: the id a default view card uses for `?ampliar=`; a layout uses the component id. */
export const VIEW_CARD_PREFIX = "view-";

interface CardProps {
  data: ReportData;
  def: ReportDefinition;
  kpiSize?: "normal" | "tv";
  csvBase?: string;
  params?: LayoutParamsWiring;
  onMaximize?: (id: string) => void;
}

/** One payload view as a card; `id` is what the full-screen dialog needs to find it again. */
function ViewCard({ index, view, card }: { index: number; view: ReportView; card: CardProps }) {
  const { data, def, kpiSize = "normal", csvBase, onMaximize } = card;
  const compared = !!data.selection.previous;
  const maximize = onMaximize ? () => onMaximize(`${VIEW_CARD_PREFIX}${index}`) : undefined;

  // Feature 038: a view that failed (or came back empty) is its own card; the rest still draws.
  if (view.error) return <RenderErrorCard error={view.error} />;
  if (view.empty) return <NoDataCard error={view.empty} />;
  if (view.type === "kpis") {
    return <KpiGrid items={view.items} currency={def.currency} compared={compared} size={kpiSize} />;
  }
  if (view.type === "trend") return <TrendChart view={view} currency={def.currency} />;
  if (view.type === "ranking") {
    return (
      <RankingTable view={view} currency={def.currency} compared={compared}
                    better={def.metrics[view.metric]?.better ?? "higher"}
                    csvFileBase={kpiSize === "normal" ? csvBase : undefined}
                    onMaximize={maximize} />
    );
  }
  return (
    <DataTable view={view} currency={def.currency}
               csvFileBase={kpiSize === "normal" ? csvBase : undefined}
               onMaximize={maximize} />
  );
}

/** The views of a report payload, shared by the report screen, the TV layout and the preview. */
export function ReportViews({ data, def, kpiSize = "normal", csvBase, params, onMaximize }: CardProps) {
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
        onMaximize={onMaximize}
      />
    );
  }

  const card = { data, def, kpiSize, csvBase, params, onMaximize };
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
export function SingleView({ index, data, def, csvBase, params }: Omit<CardProps, "onMaximize" | "kpiSize"> & {
  index: number;
}) {
  const view = data.views[index];
  if (!view) return null;
  return <ViewCard index={index} view={view} card={{ data, def, csvBase, params }} />;
}
