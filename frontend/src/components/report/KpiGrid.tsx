import type { ColorRole, KpiItem, ReportImageSet, TrendPoint } from "../../api/types";
import { useT } from "../../i18n";
import { KpiCard } from "./KpiCard";
import { RenderErrorCard } from "./RenderErrorCard";

export { ChangeChip } from "./KpiCard";

/**
 * The `kpis` view: a 2/4-column grid when nothing declares how wide it is, or one full-width card
 * per metric when a `layout.web` `kpi` component already owns the cell (feature 056, FR-001).
 */
export function KpiGrid({
  items,
  currency,
  compared,
  size = "normal",
  metric,
  sparkline,
  sparklineRole,
  image,
  mode = "grid",
  maximized = false,
}: {
  items: KpiItem[];
  currency: string;
  compared: boolean;
  size?: "normal" | "tv";
  /** Layout attributes (feature 026, data-model §3): which metric the KPI shows and, when the
   * component asks for one, that metric's own series as a sparkline. */
  metric?: string;
  sparkline?: { metric: string; points: TrendPoint[] }[];
  sparklineRole?: ColorRole;
  /** Feature 044: a declared image set, keyed by the item's metric id (a KPI has no row key). */
  image?: ReportImageSet;
  /** `single`: the component fills its span, so no inner grid is drawn. */
  mode?: "grid" | "single";
  /** Feature 056b: drawn inside the full-screen dialog — bigger value, no card chrome. */
  maximized?: boolean;
}) {
  const t = useT();
  const isTv = size === "tv";
  const shown = metric ? items.filter((item) => item.metric === metric) : items;

  const card = (k: KpiItem) => {
    // Feature 038: the metric that failed shows its own card; the other tiles still render.
    if (k.error) return <RenderErrorCard error={k.error} />;
    return (
      <KpiCard
        maximized={maximized}
        item={k}
        currency={currency}
        compared={compared}
        size={size}
        points={sparkline?.find((entry) => entry.metric === k.metric)?.points}
        sparklineRole={sparklineRole}
        image={image}
      />
    );
  };

  if (mode === "single") {
    return (
      <section aria-label={t.reportParams.display.indicators} className="h-full w-full">
        {shown.map((k) => (
          <div key={k.metric} className="h-full w-full">{card(k)}</div>
        ))}
      </section>
    );
  }

  return (
    <section aria-label={t.reportParams.display.indicators}>
      <ul
        className={
          isTv
            ? "grid grid-cols-1 gap-3 sm:gap-4 min-[480px]:grid-cols-2 lg:grid-cols-4"
            : "grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4"
        }
      >
        {shown.map((k) => (
          <li key={k.metric} className="min-w-0 h-full">{card(k)}</li>
        ))}
      </ul>
    </section>
  );
}
