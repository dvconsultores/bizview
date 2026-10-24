import type { ColorRole, MetricFormat } from "../../../api/types";
import { formatValue } from "../../../lib/numbers";
import { ChartCard } from "./ChartCard";
import { fillClass, roleAt, surfaceClass } from "../layoutRoles";
import { chartSummary, type ChartCategory, type ChartFrame } from "./series";

export interface PieChartProps {
  frame: ChartFrame;
  categories: ChartCategory[];
  values: (number | null)[];
  roles: ColorRole[];
  /** Keep the top N categories; the rest become one slice with their summed value (2–12). */
  topN: number;
  otherLabel: string;
  donut: boolean;
  format: MetricFormat;
  emptyText: string;
}

interface Slice {
  key: string;
  label: string;
  value: number;
  role: ColorRole;
}

const SIZE = 240;
const GAP_DEG = 1;

function point(cx: number, cy: number, radius: number, degrees: number): [number, number] {
  const radians = ((degrees - 90) * Math.PI) / 180;
  return [cx + radius * Math.cos(radians), cy + radius * Math.sin(radians)];
}

function arcPath(cx: number, cy: number, radius: number, inner: number, from: number, to: number): string {
  const large = to - from > 180 ? 1 : 0;
  const [x0, y0] = point(cx, cy, radius, from);
  const [x1, y1] = point(cx, cy, radius, to);
  if (inner <= 0) {
    return `M${cx.toFixed(1)},${cy.toFixed(1)} L${x0.toFixed(1)},${y0.toFixed(1)} A${radius.toFixed(1)},${radius.toFixed(1)} 0 ${large} 1 ${x1.toFixed(1)},${y1.toFixed(1)} Z`;
  }
  const [i1, j1] = point(cx, cy, inner, to);
  const [i0, j0] = point(cx, cy, inner, from);
  return `M${x0.toFixed(1)},${y0.toFixed(1)} A${radius.toFixed(1)},${radius.toFixed(1)} 0 ${large} 1 ${x1.toFixed(1)},${y1.toFixed(1)} L${i1.toFixed(1)},${j1.toFixed(1)} A${inner.toFixed(1)},${inner.toFixed(1)} 0 ${large} 0 ${i0.toFixed(1)},${j0.toFixed(1)} Z`;
}

/** Top-N slices: the remainder is grouped under the localised label with its summed value. */
export function topSlices(
  categories: ChartCategory[],
  values: (number | null)[],
  topN: number,
  otherLabel: string,
  roles: ColorRole[],
): Slice[] {
  const usable = categories
    .map((category, i) => ({ key: category.key, label: category.label, value: values[i] ?? null }))
    .filter((entry): entry is { key: string; label: string; value: number } => entry.value !== null && entry.value > 0);
  const kept = usable.slice(0, Math.max(1, topN));
  const slices = kept.map((entry, i) => ({ ...entry, role: roleAt(roles, i) }));
  const rest = usable.slice(kept.length);
  if (rest.length > 0) {
    slices.push({
      key: "__other__",
      label: otherLabel,
      value: rest.reduce((sum, entry) => sum + entry.value, 0),
      role: roleAt(roles, kept.length),
    });
  }
  return slices;
}

/** Pie and donut as SVG, with a real legend so every slice is readable as text. */
export function PieChart({
  frame,
  categories,
  values,
  roles,
  topN,
  otherLabel,
  donut,
  format,
  emptyText,
}: PieChartProps) {
  const label = chartSummary(frame);
  const slices = topSlices(categories, values, topN, otherLabel, roles);
  const total = slices.reduce((sum, slice) => sum + slice.value, 0);

  return (
    <ChartCard title={frame.title} caption={label} signature={JSON.stringify(values)}>
      {() => {
        if (total <= 0) return <p className="text-sm text-ink-muted">{emptyText}</p>;
        const radius = SIZE / 2 - 4;
        const inner = donut ? radius * 0.55 : 0;
        let angle = 0;
        return (
          <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center sm:justify-between">
            <svg
              width={SIZE}
              height={SIZE}
              viewBox={`0 0 ${SIZE} ${SIZE}`}
              role={label ? "img" : undefined}
              aria-label={label}
              className="shrink-0"
            >
              {slices.length === 1 ? (
                // A 360° arc has coincident endpoints, which SVG draws as nothing: use a circle.
                <>
                  <circle cx={SIZE / 2} cy={SIZE / 2} r={radius} className={fillClass(slices[0].role)} />
                  {inner > 0 ? <circle cx={SIZE / 2} cy={SIZE / 2} r={inner} className="fill-surface" /> : null}
                </>
              ) : null}
              {(slices.length === 1 ? [] : slices).map((slice) => {
                const sweep = (slice.value / total) * 360;
                const from = angle;
                const to = Math.max(angle + GAP_DEG, angle + sweep);
                angle += sweep;
                return (
                  <path
                    key={slice.key}
                    d={arcPath(SIZE / 2, SIZE / 2, radius, inner, from, to)}
                    className={fillClass(slice.role)}
                  />
                );
              })}
            </svg>
            <ul className="w-full min-w-0 space-y-1.5 text-sm">
              {slices.map((slice) => (
                <li key={slice.key} className="flex items-center gap-2">
                  <span className={`${surfaceClass(slice.role)} h-2.5 w-2.5 shrink-0 rounded-sm`} aria-hidden />
                  <span className="min-w-0 flex-1 [overflow-wrap:anywhere] text-ink-2">{slice.label}</span>
                  <span className="shrink-0 tabular-nums text-ink-muted">
                    {formatValue(slice.value, format, frame.currency)}
                  </span>
                  <span className="w-14 shrink-0 text-right tabular-nums text-ink">
                    {formatValue((slice.value / total) * 100, "percent")}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        );
      }}
    </ChartCard>
  );
}
