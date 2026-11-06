import { useState } from "react";
import { BottomLabels, ValueAxis } from "./ChartAxes";
import { ChartCard, ChartLegend } from "./ChartCard";
import { CHART_HEIGHT, axisLabelIndexes, chartScale, gapPath } from "./chartScale";
import { formatValue } from "../../../lib/numbers";
import { trimLabel } from "../../../lib/chartLabel";
import { useReducedMotion } from "../../../lib/useReducedMotion";
import { fillClass, strokeClass } from "../layoutRoles";
import { chartSummary, type ChartCategory, type ChartFrame, type ChartSeries } from "./series";

export interface TrendChartProps {
  frame: ChartFrame;
  categories: ChartCategory[];
  /** First entry is the current period, a second one the previous period (dashed). */
  series: ChartSeries[];
  /** `area` fills the current period's line, as `TrendChart` fills it today. */
  area?: boolean;
  /** Feature 056: print the last point's value at the end of the line. */
  labels?: boolean;
}

/** Feature 056: the current series' last value, at the right edge where the line ends. */
function LineEndLabel({ current, scale, length, currency }: {
  current: ChartSeries;
  scale: ReturnType<typeof chartScale>;
  length: number;
  currency: string;
}) {
  const last = current.values[length - 1];
  if (last === null || last === undefined) return null;
  return (
    <text x={scale.x(length - 1)} y={scale.y(last) - 6} textAnchor="end" fontSize="10"
          className="fill-chart-label tabular-nums">
      {formatValue(last, current.format, currency)}
    </text>
  );
}

/** The trend chart's line (and fill) as a component; gaps stay gaps instead of a bridged line. */
export function LineChart({ frame, categories, series, area = false, labels }: TrendChartProps) {
  const label = chartSummary(frame);
  const drawn = series.filter((entry) => entry.values.some((value) => value !== null));
  const current = drawn[0];
  const previous = drawn.find((entry) => entry.dashed);
  const reduced = useReducedMotion();
  const [hover, setHover] = useState<number | null>(null);
  const filled = area && current !== undefined && current.values.length > 1 && current.values.every((value) => value !== null);

  return (
    <ChartCard
      title={frame.title}
      legend={<ChartLegend series={drawn} />}
      caption={label}
      signature={JSON.stringify(drawn.map((entry) => [entry.id, entry.values]))}
    >
      {(width) => {
        const scale = chartScale(drawn.flatMap((entry) => entry.values), categories.length, width);
        const indexes = axisLabelIndexes(categories.length);
        const base = scale.y(0);
        const hovered = hover !== null && current ? current.values[hover] : null;
        return (
          <div className="relative">
          <svg
            width={width}
            height={CHART_HEIGHT}
            role={label ? "img" : undefined}
            aria-label={label}
            className="block"
          >
            <ValueAxis scale={scale} width={width} />
            {filled && current ? (
              <path
                d={`${gapPath(current.values, scale.x, scale.y)} L${scale.x(current.values.length - 1)},${base} L${scale.x(0)},${base} Z`}
                className={fillClass(current.role)}
                fillOpacity={0.12}
                stroke="none"
              />
            ) : null}
            {drawn.map((entry) => (
              <path
                key={entry.id}
                d={gapPath(entry.values, scale.x, scale.y)}
                fill="none"
                className={strokeClass(entry.role)}
                strokeWidth={entry.dashed ? 1.5 : 2.5}
                strokeDasharray={entry.dashed ? "4 3" : undefined}
                strokeLinejoin="round"
              />
            ))}
            {current
              ? categories.map((category, i) => {
                  const value = current.values[i];
                  if (value === null || value === undefined) return null;
                  return (
                    <g key={`dot-${category.key}`}
                       onPointerEnter={() => setHover(i)}
                       onPointerLeave={() => setHover((now) => (now === i ? null : now))}
                       onClick={() => setHover(i)}>
                      <title>{`${trimLabel(category.label)}: ${formatValue(value, current.format, frame.currency)}`}</title>
                      <circle cx={scale.x(i)} cy={scale.y(value)} r={9} fill="transparent" />
                      {hover === i ? (
                        <circle cx={scale.x(i)} cy={scale.y(value)} r={4} className={fillClass(current.role)}
                                style={{
                                  transformBox: "fill-box",
                                  transformOrigin: "center",
                                  transform: reduced ? undefined : "scale(1.03)",
                                  transition: reduced ? "none" : "transform 150ms",
                                }} />
                      ) : null}
                    </g>
                  );
                })
              : null}
            {labels && current ? <LineEndLabel current={current} scale={scale} length={categories.length}
                                              currency={frame.currency} /> : null}
            <BottomLabels
              indexes={indexes}
              x={scale.x}
              height={CHART_HEIGHT}
              labelAt={(i) => categories[i]?.label ?? ""}
            />
          </svg>
          {hovered !== null && hovered !== undefined && current && hover !== null ? (
            <div data-value-chip="" role="status"
                 className="pointer-events-none absolute z-10 w-max max-w-[190px] rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs shadow-raised"
                 style={{ left: Math.max(4, Math.min(scale.x(hover) - 90, width - 194)),
                          top: Math.max(0, scale.y(hovered) - 46) }}>
              <span className="block text-ink [overflow-wrap:anywhere]">
                {[trimLabel(categories[hover]?.label ?? ""),
                  formatValue(hovered, current.format, frame.currency),
                  previous?.values[hover] !== null && previous?.values[hover] !== undefined
                    ? `‹ ${formatValue(previous.values[hover], previous.format, frame.currency)}`
                    : null].filter(Boolean).join(" · ")}
              </span>
            </div>
          ) : null}
          </div>
        );
      }}
    </ChartCard>
  );
}
