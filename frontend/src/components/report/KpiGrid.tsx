import { ArrowDownRight, ArrowUpRight, Banknote, Hash, Minus, Percent, Type } from "lucide-react";
import type { ColorRole, KpiItem, ReportImageSet, TrendPoint } from "../../api/types";
import { changeTone, formatChange, formatValue, formatValueCompact } from "../../lib/numbers";
import { StatTile } from "../StatTile";
import { Sparkline } from "./charts/Sparkline";
import { RenderErrorCard } from "./RenderErrorCard";
import { ReportImage } from "./ReportImage";
import { useT } from "../../i18n";
import { localized } from "../../lib/labels";

/** Feature 030 FR-009: filled delta badges whose colours come from the palette preset. */
const TONE = {
  good: "bg-kpi-delta-bg-positive text-chart-positive ring-kpi-delta-bg-positive",
  bad: "bg-kpi-delta-bg-negative text-chart-negative ring-kpi-delta-bg-negative",
  flat: "bg-surface-2 text-kpi-neutral ring-line",
};

const ICONS: Record<KpiItem["format"], typeof Hash> = {
  currency: Banknote,
  percent: Percent,
  number: Hash,
  integer: Hash,
  text: Type,
};

export function ChangeChip({ item }: { item: Pick<KpiItem, "change" | "better"> }) {
  if (!item.change) return null;
  const tone = changeTone(item.change, item.better);
  const Icon = item.change.pct === null || tone === "flat" ? Minus : item.change.pct > 0 ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={`inline-flex items-center gap-0.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${TONE[tone]}`}>
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {formatChange(item.change)}
    </span>
  );
}

export function KpiGrid({
  items,
  currency,
  compared,
  size = "normal",
  metric,
  sparkline,
  sparklineRole,
  image,
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
}) {
  const t = useT();
  const isTv = size === "tv";
  const shown = metric ? items.filter((item) => item.metric === metric) : items;

  return (
    <section aria-label={t.reportParams.display.indicators}>
      <ul
        className={
          isTv
            ? "grid grid-cols-1 gap-3 sm:gap-4 min-[480px]:grid-cols-2 lg:grid-cols-4"
            : "grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4"
        }
      >
        {shown.map((k) => {
          // Feature 038: the metric that failed shows its own card; the other tiles still render.
          if (k.error) {
            return (
              <li key={k.metric} className="min-w-0">
                <RenderErrorCard error={k.error} />
              </li>
            );
          }
          const Icon = ICONS[k.format] ?? Hash;
          const points = sparkline?.find((entry) => entry.metric === k.metric)?.points;
          const display = formatValueCompact(k.value, k.format, currency);
          const full = formatValue(k.value, k.format, currency);
          const small = display.length > 7;
          return (
            <li key={k.metric} className="min-w-0">
              <StatTile
                className="h-full"
                label={localized(k, "label")}
                icon={
                  image ? (
                    <ReportImage set={image} name={k.metric} label={localized(k, "label")}
                                 size={40} />
                  ) : (
                    <Icon className="h-5 w-5" aria-hidden />
                  )
                }
                size={size}
                value={
                  <>
                    <span
                      className={`${
                        isTv
                          ? "block text-[length:var(--kpi-numeral-tv)] tabular-nums tracking-[var(--kpi-tracking)] whitespace-nowrap sm:text-[length:var(--kpi-numeral-tv-lg)] xl:text-[length:var(--kpi-numeral-tv-xl)]"
                          : "block text-[length:var(--kpi-numeral)] tabular-nums tracking-[var(--kpi-tracking)] whitespace-nowrap sm:text-[length:var(--kpi-numeral-lg)]"
                      }${small ? " text-[0.85em]" : ""}`}
                      title={full !== display ? full : undefined}
                    >
                      {display}
                    </span>
                    {points ? (
                      <Sparkline values={points.map((point) => point.value)} role={sparklineRole} className="mt-1" />
                    ) : null}
                  </>
                }
                footnote={
                  compared ? (
                    <span className={isTv ? "mt-1 flex flex-wrap items-center gap-1.5 text-sm xl:text-base" : "mt-1 flex flex-wrap items-center gap-1.5"}>
                      <ChangeChip item={k} />
                      <span className="[overflow-wrap:anywhere]">{t.reportParams.display.before(formatValue(k.previous, k.format, currency))}</span>
                    </span>
                  ) : undefined
                }
              />
            </li>
          );
        })}
      </ul>
    </section>
  );
}
