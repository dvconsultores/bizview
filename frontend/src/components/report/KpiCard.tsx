import { ArrowDownRight, ArrowUpRight, Banknote, Hash, Minus, Percent, Type } from "lucide-react";
import type { ColorRole, KpiItem, ReportImageSet, TrendPoint } from "../../api/types";
import { changeTone, formatChange, formatValue, formatValueCompact } from "../../lib/numbers";
import { localized } from "../../lib/labels";
import { useT } from "../../i18n";
import { Card } from "../Card";
import { Sparkline } from "./charts/Sparkline";
import { ReportImage } from "./ReportImage";

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

/** Minimum height of a KPI card (feature 056): four cards in a row keep one rhythm. */
export const KPI_MIN_HEIGHT = 150;
/** Height reserved for the delta row so cards with and without a comparison align. */
const DELTA_ROW = "1.75rem";

export function ChangeChip({ item }: { item: Pick<KpiItem, "change" | "better"> }) {
  if (!item.change) return null;
  const tone = changeTone(item.change, item.better);
  const Icon = item.change.pct === null || tone === "flat" ? Minus : item.change.pct > 0 ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={`inline-flex shrink-0 items-center gap-0.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${TONE[tone]}`}>
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {formatChange(item.change)}
    </span>
  );
}

/**
 * Feature 056: one KPI card that fills its cell.
 *
 * A `kpi` layout component used to render through `KpiGrid`, whose `<ul>` kept its 2/4-column grid
 * even for a single metric: a `span: 6` card drew a quarter of its column and left the rest empty.
 * This card is the only thing the component renders, `w-full h-full`, and its anatomy is fixed: icon
 * and label, the value, then a delta row that has room of its own so a two-line value never collides
 * with the "antes" line.
 */
export function KpiCard({
  item,
  currency,
  compared,
  size = "normal",
  points,
  sparklineRole,
  image,
  className = "",
  maximized = false,
}: {
  item: KpiItem;
  currency: string;
  compared: boolean;
  size?: "normal" | "tv";
  points?: TrendPoint[];
  sparklineRole?: ColorRole;
  image?: ReportImageSet;
  className?: string;
  /** Feature 056b: the dialog draws the card, so it drops its own chrome and grows the value. */
  maximized?: boolean;
}) {
  const t = useT();
  const isTv = size === "tv";
  const Icon = ICONS[item.format] ?? Hash;
  const display = formatValueCompact(item.value, item.format, currency);
  const full = formatValue(item.value, item.format, currency);

  return (
    <Card className={`flex h-full w-full flex-col ${maximized ? "border-0 p-0 shadow-none" : "p-5"} ${className}`}
          data-kpi-card={item.metric}
          data-maximized={maximized ? "" : undefined}
          style={maximized ? undefined : { minHeight: KPI_MIN_HEIGHT }}>
      <div className="flex items-center gap-3">
        <span
          aria-hidden
          className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent"
        >
          {image ? (
            <ReportImage set={image} name={item.metric} label={localized(item, "label")} size={40} />
          ) : (
            <Icon className="h-5 w-5" aria-hidden />
          )}
        </span>
        <span className={`${isTv ? "text-sm sm:text-base xl:text-lg" : "text-xs"} font-medium text-ink-muted [overflow-wrap:anywhere]`}>
          {localized(item, "label")}
        </span>
      </div>

      <div
        className="mt-3 font-bold leading-tight tracking-tight text-ink"
        style={{
          fontSize: maximized
            ? "clamp(44px, 6vw, 96px)"
            : isTv ? "clamp(32px, 3.2vw, 56px)" : "clamp(28px, 2.6vw, 44px)",
        }}
        title={full !== display ? full : undefined}
        data-kpi-value=""
      >
        <span className="tabular-nums [overflow-wrap:anywhere]">{display}</span>
      </div>

      {points && points.length > 0 ? (
        <Sparkline values={points.map((point) => point.value)} role={sparklineRole} className="mt-2" />
      ) : null}

      {/* The row exists with and without a comparison: the cards in a row keep the same rhythm. */}
      <div className={`mt-auto flex flex-wrap items-center gap-x-2 gap-y-1 ${maximized ? "pt-4 text-sm" : "pt-3 text-xs"}`}
           style={{ minHeight: `calc(12px + ${DELTA_ROW})` }} data-kpi-delta-row="">
        {compared ? (
          <>
            <ChangeChip item={item} />
            <span className="min-w-0 text-ink-muted [overflow-wrap:anywhere]">
              {t.reportParams.display.before(formatValue(item.previous, item.format, currency))}
            </span>
          </>
        ) : null}
      </div>
    </Card>
  );
}
