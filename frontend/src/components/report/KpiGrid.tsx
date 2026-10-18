import { ArrowDownRight, ArrowUpRight, Banknote, Hash, Minus, Percent, Type } from "lucide-react";
import type { ColorRole, KpiItem, TrendPoint } from "../../api/types";
import { changeTone, formatChange, formatValue } from "../../lib/numbers";
import { StatTile } from "../StatTile";
import { Sparkline } from "./charts/Sparkline";
import { useT } from "../../i18n";
import { localized } from "../../lib/labels";

const TONE = {
  good: "bg-success-soft text-success-strong ring-success-line",
  bad: "bg-danger-soft text-danger-strong ring-danger-line",
  flat: "bg-surface-2 text-ink-3 ring-line",
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
          const Icon = ICONS[k.format] ?? Hash;
          const points = sparkline?.find((entry) => entry.metric === k.metric)?.points;
          return (
            <li key={k.metric} className="min-w-0">
              <StatTile
                className="h-full"
                label={localized(k, "label")}
                icon={<Icon className="h-5 w-5" aria-hidden />}
                size={size}
                value={
                  <>
                    <span
                      className={
                        isTv
                          ? "block text-4xl tabular-nums [overflow-wrap:anywhere] sm:text-5xl xl:text-6xl"
                          : "block text-xl tabular-nums [overflow-wrap:anywhere] sm:text-3xl"
                      }
                    >
                      {formatValue(k.value, k.format, currency)}
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
