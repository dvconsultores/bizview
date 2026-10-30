import type { KpiItem, WebComponent } from "../../../api/types";
import { localized } from "../../../lib/labels";
import { formatValue } from "../../../lib/numbers";

export function IndexTile({ component, items }: { component: WebComponent; items: KpiItem[] }) {
  const item = component.metric ? items.find((i) => i.metric === component.metric) : undefined;
  const raw = item?.value;
  const value = Number(raw);
  const min = component.min ?? 0;
  const max = component.max ?? 100;
  const hasValue = raw !== null && raw !== undefined && Number.isFinite(value);
  const ratio = hasValue && max > min ? Math.min(1, Math.max(0, (value - min) / (max - min))) : 0;
  const pct = ratio * 100;
  const shown = hasValue ? formatValue(raw, item?.format ?? "number") : "—";
  const lowLabel = localized(
    { label: component.low_label, label_en: component.low_label_en },
    "label",
  );
  const highLabel = localized(
    { label: component.high_label, label_en: component.high_label_en },
    "label",
  );

  return (
    <div className="h-full rounded-card border border-line bg-surface p-4 shadow-card">
      <div className="text-3xl font-bold tabular-nums">{shown}</div>
      {item ? <div className="mt-0.5 text-xs text-ink-muted">{localized(item, "label")}</div> : null}
      <div className="relative mt-4 h-3 rounded-full">
        <div
          className="h-full w-full rounded-full"
          style={{
            background:
              "linear-gradient(to right, var(--series-1), var(--neutral), var(--series-2))",
          }}
        />
        {hasValue ? (
          <div
            className="absolute top-1/2 h-5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded"
            style={{
              left: `${pct}%`,
              backgroundColor: "var(--kpi-text-color)",
            }}
          />
        ) : null}
      </div>
      <div className="mt-2 flex justify-between text-xs text-ink-muted">
        <span>{lowLabel}</span>
        <span>{highLabel}</span>
      </div>
    </div>
  );
}
