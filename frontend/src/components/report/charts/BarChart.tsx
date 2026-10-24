import type { BarOrientation } from "../../../api/types";
import { formatCompact } from "../../../lib/numbers";
import { BottomLabels } from "./ChartAxes";
import { ChartCard, ChartLegend } from "./ChartCard";
import {
  CHART_HEIGHT,
  CHART_MIN_HEIGHT,
  PAD,
  axisLabelIndexes,
  chartScale,
  niceTicks,
  valueRange,
} from "./chartScale";
import { fillClass } from "../layoutRoles";
import { chartSummary, type ChartCategory, type ChartFrame, type ChartSeries } from "./series";

export interface BarChartProps {
  frame: ChartFrame;
  categories: ChartCategory[];
  series: ChartSeries[];
  orientation: BarOrientation;
  stacked: boolean;
}

const HORIZONTAL_ROW = 26;
const LABEL_LIMIT = 18;

function ellipsis(text: string, limit = LABEL_LIMIT): string {
  return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
}

/** Bars as SVG: vertical or horizontal, grouped or stacked (feature 026, research R5). */
export function BarChart({ frame, categories, series, orientation, stacked }: BarChartProps) {
  const label = chartSummary(frame);
  const drawn = series.filter((entry) => entry.values.some((value) => value !== null));

  return (
    <ChartCard
      title={frame.title}
      legend={<ChartLegend series={drawn} />}
      caption={label}
      signature={JSON.stringify([stacked, categories.length, drawn.map((entry) => [entry.id, entry.values])])}
    >
      {(width) =>
        orientation === "horizontal" ? (
          <HorizontalBars width={width} categories={categories} series={drawn} stacked={stacked} label={label} />
        ) : (
          <VerticalBars width={width} categories={categories} series={drawn} stacked={stacked} label={label} />
        )
      }
    </ChartCard>
  );
}

function VerticalBars({
  width,
  categories,
  series,
  stacked,
  label,
}: {
  width: number;
  categories: ChartCategory[];
  series: ChartSeries[];
  stacked: boolean;
  label?: string;
}) {
  const scale = chartScale(series.flatMap((entry) => entry.values), categories.length, width);
  const count = Math.max(1, categories.length);
  const step = scale.innerW / count;
  const group = step * (count > 6 ? 0.8 : 0.62);
  const bar = stacked ? group : Math.max(1, group / Math.max(1, series.length));
  const base = scale.y(0);
  const center = (i: number) => PAD.left + i * step + step / 2;

  return (
    <svg width={width} height={CHART_HEIGHT} role={label ? "img" : undefined} aria-label={label} className="block">
      <ValueGrid scale={scale} width={width} />
      {categories.map((category, i) => {
        // A stacked bar accumulates upward for positive values and downward for negative ones.
        let positive = 0;
        let negative = 0;
        return (
          <g key={category.key}>
            {series.map((entry, j) => {
              const value = entry.values[i];
              if (value === null || value === undefined) return null;
              if (stacked) {
                const from = value >= 0 ? positive : negative;
                const to = from + value;
                if (value >= 0) positive = to;
                else negative = to;
                return (
                  <rect
                    key={entry.id}
                    x={center(i) - group / 2}
                    y={Math.min(scale.y(from), scale.y(to))}
                    width={Math.max(1, group - 2)}
                    height={Math.max(0, Math.abs(scale.y(from) - scale.y(to)))}
                    className={fillClass(entry.role)}
                  />
                );
              }
              return (
                <rect
                  key={entry.id}
                  x={center(i) - group / 2 + j * bar}
                  y={Math.min(base, scale.y(value))}
                  width={Math.max(1, bar - 2)}
                  height={Math.max(0, Math.abs(base - scale.y(value)))}
                  className={fillClass(entry.role)}
                />
              );
            })}
          </g>
        );
      })}
      <BottomLabels
        indexes={axisLabelIndexes(categories.length)}
        x={center}
        height={CHART_HEIGHT}
        labelAt={(i) => ellipsis(categories[i]?.label ?? "")}
      />
    </svg>
  );
}

function HorizontalBars({
  width,
  categories,
  series,
  stacked,
  label,
}: {
  width: number;
  categories: ChartCategory[];
  series: ChartSeries[];
  stacked: boolean;
  label?: string;
}) {
  const count = Math.max(1, categories.length);
  const height = Math.max(CHART_MIN_HEIGHT, PAD.top + PAD.bottom + count * HORIZONTAL_ROW + 6);
  const left = Math.min(112, Math.max(64, width * 0.28));
  const innerW = Math.max(1, width - left - PAD.right - 8);
  const [lo, hi] = valueRange(series.flatMap((entry) => entry.values));
  const ticks = niceTicks(lo, hi);
  const span = (ticks[ticks.length - 1] - ticks[0]) || 1;
  const xOf = (value: number) => left + ((value - ticks[0]) / span) * innerW;
  const zero = xOf(0);
  const row = (height - PAD.top - PAD.bottom) / count;
  const bar = stacked ? row * 0.62 : Math.max(1, (row * 0.62) / Math.max(1, series.length));
  const axisLine = height - PAD.bottom + 14;

  return (
    <svg width={width} height={height} role={label ? "img" : undefined} aria-label={label} className="block">
      {ticks.map((tick) => (
        <g key={tick}>
          <line
            x1={xOf(tick)}
            x2={xOf(tick)}
            y1={PAD.top}
            y2={height - PAD.bottom}
            className={tick === 0 ? "stroke-chart-axis" : "stroke-chart-grid"}
          />
          <text x={xOf(tick)} y={axisLine} textAnchor="middle" fontSize="11" className="fill-chart-label">
            {formatCompact(tick)}
          </text>
        </g>
      ))}
      {categories.map((category, i) => {
        const center = PAD.top + i * row + row / 2;
        // A stacked row grows away from the zero line, so the running total is the next start.
        let accumulated = 0;
        return (
          <g key={category.key}>
            <text x={left - 8} y={center + 4} textAnchor="end" fontSize="11" className="fill-chart-label">
              {ellipsis(category.label)}
            </text>
            {series.map((entry, j) => {
              const value = entry.values[i];
              if (value === null || value === undefined) return null;
              const start = xOf(accumulated);
              if (stacked) accumulated += value;
              const end = xOf(accumulated);
              const from = stacked ? start : zero;
              const to = stacked ? end : xOf(value);
              return (
                <rect
                  key={entry.id}
                  x={Math.min(from, to)}
                  y={stacked ? center - bar / 2 : center - (series.length * bar) / 2 + j * bar}
                  width={Math.max(1, Math.abs(to - from))}
                  height={Math.max(1, stacked ? bar : bar - 2)}
                  className={fillClass(entry.role)}
                />
              );
            })}
          </g>
        );
      })}
      <line x1={left - 2} x2={left - 2} y1={PAD.top} y2={height - PAD.bottom} className="stroke-chart-axis" />
    </svg>
  );
}

/** Ticks and grid lines of a vertical bar chart (the same grammar as the line charts). */
function ValueGrid({ scale, width }: { scale: ReturnType<typeof chartScale>; width: number }) {
  return (
    <>
      {scale.ticks.map((tick) => (
        <g key={tick}>
          <line
            x1={PAD.left}
            x2={width - PAD.right}
            y1={scale.y(tick)}
            y2={scale.y(tick)}
            className={tick === 0 ? "stroke-chart-axis" : "stroke-chart-grid"}
          />
          <text x={PAD.left - 6} y={scale.y(tick) + 4} textAnchor="end" fontSize="11" className="fill-chart-label">
            {formatCompact(tick)}
          </text>
        </g>
      ))}
    </>
  );
}
