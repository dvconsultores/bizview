import type { KpiItem, WebComponent } from "../../../api/types";
import { localized } from "../../../lib/labels";
import { formatValue } from "../../../lib/numbers";

const SEGMENT_COLORS = [
  "var(--series-1)",
  "var(--series-2)",
  "var(--series-3)",
  "var(--series-4)",
];

type Segment = { label: string; value: number; color: string };

export function ShareTile({ component, items }: { component: WebComponent; items: KpiItem[] }) {
  const metricIds = component.items ?? [];
  const segments: Segment[] = [];
  let total = 0;
  metricIds.forEach((id, i) => {
    const item = items.find((it) => it.metric === id);
    if (!item) return;
    const raw = item.value;
    const value = raw !== null && raw !== undefined && Number.isFinite(Number(raw)) ? Number(raw) : 0;
    total += value;
    segments.push({
      label: localized(item, "label"),
      value,
      color: SEGMENT_COLORS[i % SEGMENT_COLORS.length],
    });
  });

  if (component.remainder_label) {
    const remainder = Math.max(0, 100 - total);
    segments.push({
      label: localized(
        { label: component.remainder_label, label_en: component.remainder_label_en },
        "label",
      ),
      value: remainder,
      color: SEGMENT_COLORS[segments.length % SEGMENT_COLORS.length],
    });
  }

  if (segments.length === 0) {
    return (
      <div className="h-full rounded-card border border-line bg-surface p-4 shadow-card text-ink-muted">
        —
      </div>
    );
  }

  return (
    <div className="h-full rounded-card border border-line bg-surface p-4 shadow-card">
      <div className="flex flex-wrap gap-4">
        {segments.map((seg, i) => (
          <div key={i} className="flex min-w-0 flex-col gap-0.5">
            <div className="flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: seg.color }}
              />
              <span className="text-xs text-ink-muted">{seg.label}</span>
            </div>
            <span className="text-xl font-bold tabular-nums">{formatValue(seg.value, "percent")}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 flex h-3 w-full overflow-hidden rounded-full">
        {segments.map((seg, i) => {
          const pct = Math.min(100, Math.max(0, seg.value));
          return <div key={i} style={{ width: `${pct}%`, backgroundColor: seg.color }} />;
        })}
      </div>
    </div>
  );
}
