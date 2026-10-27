import type { ReportData, ReportDefinition } from "../../api/types";
import { DataTable } from "./DataTable";
import { NoDataCard, RenderErrorCard } from "./RenderErrorCard";
import { KpiGrid } from "./KpiGrid";
import { LayoutRenderer } from "./LayoutRenderer";
import { RankingTable } from "./RankingTable";
import { TrendChart } from "./TrendChart";
import type { LayoutParamsWiring } from "./LayoutBlocks";

/** The views of a report payload, shared by the report screen and the assistant preview. */
export function ReportViews({
  data,
  def,
  kpiSize = "normal",
  csvBase,
  params,
}: {
  data: ReportData;
  def: ReportDefinition;
  kpiSize?: "normal" | "tv";
  csvBase?: string;
  /** The report screen's own filter wiring, for a layout's `filters` component. */
  params?: LayoutParamsWiring;
}) {
  const compared = !!data.selection.previous;

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
      />
    );
  }

  return data.views.map((v, i) => {
    // Feature 038: a view that failed (or came back empty) is its own card; the rest still draws.
    if (v.error) return <RenderErrorCard key={i} error={v.error} />;
    if (v.empty) return <NoDataCard key={i} error={v.empty} />;
    if (v.type === "kpis")
      return (
        <KpiGrid key={i} items={v.items} currency={def.currency} compared={compared} size={kpiSize} />
      );
    if (v.type === "trend") return <TrendChart key={i} view={v} currency={def.currency} />;
    if (v.type === "ranking")
      return (
        <RankingTable
          key={i}
          view={v}
          currency={def.currency}
          compared={compared}
          better={def.metrics[v.metric]?.better ?? "higher"}
          csvFileBase={kpiSize === "normal" ? csvBase : undefined}
        />
      );
    return (
      <DataTable
        key={i}
        view={v}
        currency={def.currency}
        csvFileBase={kpiSize === "normal" ? csvBase : undefined}
      />
    );
  });
}
