import { useState } from "react";
import type { BarOrientation } from "../../../api/types";
import { formatCompact, formatValue } from "../../../lib/numbers";
import { LABEL_ABOVE, fitLabel, labelColumn, measureText, trimLabel } from "../../../lib/chartLabel";
import { useReducedMotion } from "../../../lib/useReducedMotion";
import { usePointerChip } from "../../../lib/usePointerChip";
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
import { markState, type CrossFilterState } from "../crossFilter";
import { useT } from "../../../i18n";

export interface BarChartProps {
  frame: ChartFrame;
  categories: ChartCategory[];
  series: ChartSeries[];
  orientation: BarOrientation;
  stacked: boolean;
  /** Feature 056: print the value at the end of each bar, hiding the ones that do not fit. */
  labels?: boolean;
  /** Feature 056b: the card is drawn in the dialog, so its labels get the dialog's width. */
  maximized?: boolean;
  /** Feature 063: click a bar to filter its dimension. */
  crossFilter?: CrossFilterState;
  dimension?: string;
}

const HORIZONTAL_ROW = 26;
/** Phone layout: one label line over its bar, 12 px bar and 8 px gap (feature 056, FR-005). */
const ROW_ABOVE = 34;
const CHIP_W = 190;

/** Bars as SVG: vertical or horizontal, grouped or stacked (feature 026, research R5). */
export function BarChart({ frame, categories, series, orientation, stacked, labels,
                          maximized = false, crossFilter, dimension }: BarChartProps) {
  const label = chartSummary(frame);
  const drawn = series.filter((entry) => entry.values.some((value) => value !== null));

  return (
    <ChartCard
      title={frame.title}
      legend={<ChartLegend series={drawn} />}
      caption={label}
      signature={JSON.stringify([stacked, categories.length, drawn.map((entry) => [entry.id, entry.values])])}
      maximized={maximized}
    >
      {(width, available) =>
        orientation === "horizontal" ? (
          <HorizontalBars width={width} height={Math.max(CHART_MIN_HEIGHT, available)}
                          categories={categories} series={drawn} stacked={stacked}
                          label={label} labels={labels} frame={frame} maximized={maximized}
                          crossFilter={crossFilter} dimension={dimension} />
        ) : (
          <VerticalBars width={width} categories={categories} series={drawn} stacked={stacked}
                        label={label} labels={labels} frame={frame}
                        crossFilter={crossFilter} dimension={dimension} />
        )
      }
    </ChartCard>
  );
}

/** The hovered element's value: full name, formatted value and share of the series total. */
function ValueChip({ x, y, width, text }: { x: number; y: number; width: number; text: string }) {
  const left = Math.max(4, Math.min(x, Math.max(4, width - CHIP_W - 4)));
  return (
    <div
      data-value-chip=""
      role="status"
      className="pointer-events-none absolute z-10 w-max max-w-[190px] rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs shadow-raised"
      style={{ left, top: Math.max(0, y) }}
    >
      <span className="block [overflow-wrap:anywhere] text-ink">{text}</span>
    </div>
  );
}

function parts(category: ChartCategory, entry: ChartSeries, index: number, frame: ChartFrame) {
  const value = entry.values[index];
  if (value === null || value === undefined) return null;
  const total = entry.values.reduce<number>((sum, v) => sum + (v ?? 0), 0);
  const share = total === 0 ? null : (value / total) * 100;
  return {
    name: trimLabel(category.label),
    value: formatValue(value, entry.format, frame.currency),
    share: share === null ? null : `${share.toFixed(1).replace(".", ",")} %`,
  };
}

function VerticalBars({
  width, categories, series, stacked, label, labels, frame, crossFilter, dimension,
}: {
  width: number;
  categories: ChartCategory[];
  series: ChartSeries[];
  stacked: boolean;
  label?: string;
  labels?: boolean;
  frame: ChartFrame;
  crossFilter?: CrossFilterState;
  dimension?: string;
}) {
  const t = useT();
  const reduced = useReducedMotion();
  const pointer = usePointerChip();
  const [hover, setHover] = useState<number | null>(null);
  const scale = chartScale(series.flatMap((entry) => entry.values), categories.length, width);
  const count = Math.max(1, categories.length);
  const step = scale.innerW / count;
  const group = step * (count > 6 ? 0.8 : 0.62);
  const bar = stacked ? group : Math.max(1, group / Math.max(1, series.length));
  const base = scale.y(0);
  const center = (i: number) => PAD.left + i * step + step / 2;
  const hovered = hover === null ? null : parts(categories[hover], series[0], hover, frame);

  const spot = pointer.place(width, CHART_HEIGHT);
  const selected = dimension ? crossFilter?.filters[dimension] ?? [] : [];
  const selectMark = (additive: boolean, mark: ReturnType<typeof markState>) => {
    if (mark && dimension) crossFilter?.toggle(dimension, mark.value, additive);
  };
  const dims = (value: string | null | undefined) =>
    selected.length > 0 && value !== null && value !== undefined && !selected.includes(value);
  return (
    <div className="relative" ref={pointer.ref} onPointerMove={pointer.onPointerMove}
         onPointerLeave={() => { pointer.onPointerLeave(); setHover(null); }}>
      <svg width={width} height={CHART_HEIGHT}
             role={crossFilter?.enabled && dimension ? "group" : label ? "img" : undefined}
             aria-label={label} className="block">
        <ValueGrid scale={scale} width={width} />
        {categories.map((category, i) => {
          let positive = 0;
          let negative = 0;
          const dim = hover !== null && hover !== i;
          const mark = markState(crossFilter, dimension, category.value);
          return (
            <g key={category.key}
               onPointerEnter={() => setHover(i)}
               onPointerLeave={() => setHover((current) => (current === i ? null : current))}
               role={mark ? "button" : undefined}
               tabIndex={mark ? 0 : undefined}
               aria-pressed={mark ? mark.selected : undefined}
               aria-label={mark ? `${category.label}` : undefined}
               className={mark ? "cursor-pointer focus-visible:outline-none" : undefined}
               onClick={(event) => selectMark(event.ctrlKey || event.metaKey, mark)}
               onKeyDown={(event) => {
                 if (!mark || (event.key !== "Enter" && event.key !== " ")) return;
                 event.preventDefault();
                 selectMark(event.ctrlKey || event.metaKey, mark);
               }}>
              <title>{`${trimLabel(category.label)}: ${formatValue(series[0]?.values[i], series[0]?.format, frame.currency)}`}</title>
              {series.map((entry, j) => {
                const value = entry.values[i];
                if (value === null || value === undefined) return null;
                const from = stacked ? (value >= 0 ? positive : negative) : 0;
                const to = from + value;
                if (stacked) {
                  if (value >= 0) positive = to;
                  else negative = to;
                }
                const x = stacked ? center(i) - group / 2 : center(i) - group / 2 + j * bar;
                const y = Math.min(scale.y(from), scale.y(to));
                const h = Math.max(0, Math.abs(scale.y(from) - scale.y(to)));
                return (
                  <rect
                    key={entry.id}
                    x={x}
                    y={y}
                    width={Math.max(1, stacked ? group : bar - 2)}
                    height={h}
                    className={fillClass(entry.role)}
                    stroke={mark?.selected ? "var(--focus)" : undefined}
                    strokeWidth={mark?.selected ? 2 : undefined}
                    opacity={dim || dims(category.value) ? 0.7 : 1}
                    style={{
                      transition: reduced ? "opacity 150ms" : "opacity 150ms, transform 150ms",
                      transformBox: "fill-box",
                      transformOrigin: "center",
                      transform: hover === i && !reduced ? "scale(1.03)" : undefined,
                    }}
                  />
                );
              })}
              {labels ? (
                <BarValue x={center(i)} y={Math.min(base, scale.y(series[0]?.values[i] ?? 0)) - 4}
                          text={formatCompact(series[0]?.values[i] ?? 0)} barPx={Math.abs(base - scale.y(series[0]?.values[i] ?? 0))} />
              ) : null}
            </g>
          );
        })}
        <BottomLabels
          indexes={axisLabelIndexes(categories.length)}
          x={center}
          height={CHART_HEIGHT}
          labelAt={(i) => fitLabel(trimLabel(categories[i]?.label ?? ""), step - 6)}
        />
      </svg>
      {hovered ? (
        <ValueChip x={spot?.left ?? center(hover!) - CHIP_W / 2} y={spot?.top ?? PAD.top - 6}
                   width={width}
                   text={[hovered.name, hovered.value, hovered.share,
                          markState(crossFilter, dimension, categories[hover ?? 0]?.value)
                            ?.selected ? t.reportParams.clickToRemoveFilter : t.reportParams.clickToFilter]
                     .filter(Boolean).join(" · ")} />
      ) : null}
    </div>
  );
}

/** A value printed above a vertical bar, only when the bar is tall enough to carry it. */
function BarValue({ x, y, text, barPx }: { x: number; y: number; text: string; barPx: number }) {
  if (barPx < 18 || measureText(text) > 60) return null;
  return (
    <text x={x} y={y} textAnchor="middle" fontSize="10" className="fill-chart-label tabular-nums">
      {text}
    </text>
  );
}

function HorizontalBars({
  width, height, categories, series, stacked, label, labels, frame, maximized = false,
  crossFilter, dimension,
}: {
  width: number;
  height: number;
  categories: ChartCategory[];
  series: ChartSeries[];
  stacked: boolean;
  label?: string;
  labels?: boolean;
  frame: ChartFrame;
  maximized?: boolean;
  crossFilter?: CrossFilterState;
  dimension?: string;
}) {
  const t = useT();
  const reduced = useReducedMotion();
  const pointer = usePointerChip();
  const [hover, setHover] = useState<number | null>(null);
  const above = width < LABEL_ABOVE;
  const count = Math.max(1, categories.length);
  // Feature 056: the card's own height wins, so a chart with few categories gets taller bars
  // instead of a shorter card.
  const natural = PAD.top + PAD.bottom + count * (above ? ROW_ABOVE : HORIZONTAL_ROW) + 6;
  const chartHeight = Math.max(natural, height);
  // Feature 056: the column is measured from the real font, up to 220 px and 40 % of the chart.
  const left = above ? 8 : labelColumn(width, categories.map((c) => c.label), { maximized });
  const innerW = Math.max(1, width - left - PAD.right - (labels ? 56 : 8));
  const [lo, hi] = valueRange(series.flatMap((entry) => entry.values));
  const ticks = niceTicks(lo, hi);
  const span = (ticks[ticks.length - 1] - ticks[0]) || 1;
  const xOf = (value: number) => left + ((value - ticks[0]) / span) * innerW;
  const zero = xOf(0);
  const row = (height - PAD.top - PAD.bottom) / count;
  const bar = stacked ? row * 0.62 : Math.max(1, (row * 0.62) / Math.max(1, series.length));
  const axisLine = chartHeight - PAD.bottom + 14;
  const hovered = hover === null ? null : parts(categories[hover], series[0], hover, frame);
  const selected = dimension ? crossFilter?.filters[dimension] ?? [] : [];
  const selectMark = (additive: boolean, mark: ReturnType<typeof markState>) => {
    if (mark && dimension) crossFilter?.toggle(dimension, mark.value, additive);
  };
  const dims = (value: string | null | undefined) =>
    selected.length > 0 && value !== null && value !== undefined && !selected.includes(value);

  const spot = pointer.place(width, chartHeight);
  return (
    <div className="relative" ref={pointer.ref} onPointerMove={pointer.onPointerMove}
         onPointerLeave={() => { pointer.onPointerLeave(); setHover(null); }}>
      <svg width={width} height={chartHeight}
             role={crossFilter?.enabled && dimension ? "group" : label ? "img" : undefined}
             aria-label={label} className="block">
        {!above ? (
          <>
            {ticks.map((tick) => (
              <g key={tick}>
                <line x1={xOf(tick)} x2={xOf(tick)} y1={PAD.top} y2={chartHeight - PAD.bottom}
                      className={tick === 0 ? "stroke-chart-axis" : "stroke-chart-grid"} />
                <text x={xOf(tick)} y={axisLine} textAnchor="middle" fontSize="11" className="fill-chart-label">
                  {formatCompact(tick)}
                </text>
              </g>
            ))}
            <line x1={left - 2} x2={left - 2} y1={PAD.top} y2={chartHeight - PAD.bottom} className="stroke-chart-axis" />
          </>
        ) : null}
        {categories.map((category, i) => {
          const center = above ? PAD.top + i * row + row / 2 + 8 : PAD.top + i * row + row / 2;
          let accumulated = 0;
          const dim = hover !== null && hover !== i;
          const mark = markState(crossFilter, dimension, category.value);
          return (
            <g key={category.key}
               onPointerEnter={() => setHover(i)}
               onPointerLeave={() => setHover((current) => (current === i ? null : current))}
               role={mark ? "button" : undefined}
               tabIndex={mark ? 0 : undefined}
               aria-pressed={mark ? mark.selected : undefined}
               aria-label={mark ? `${category.label}` : undefined}
               className={mark ? "cursor-pointer focus-visible:outline-none" : undefined}
               onClick={(event) => selectMark(event.ctrlKey || event.metaKey, mark)}
               onKeyDown={(event) => {
                 if (!mark || (event.key !== "Enter" && event.key !== " ")) return;
                 event.preventDefault();
                 selectMark(event.ctrlKey || event.metaKey, mark);
               }}>
              <title>{`${trimLabel(category.label)}: ${formatValue(series[0]?.values[i], series[0]?.format, frame.currency)}`}</title>
              {above ? (
                <text x={4} y={center - row / 2 + 11} fontSize="11" textAnchor="start" className="fill-chart-label">
                  {category.label}
                </text>
              ) : (
                <text x={left - 8} y={center + 4} textAnchor="end" fontSize="11" className="fill-chart-label">
                  {fitLabel(trimLabel(category.label), left - 14)}
                </text>
              )}
              {series.map((entry, j) => {
                const value = entry.values[i];
                if (value === null || value === undefined) return null;
                const start = xOf(accumulated);
                if (stacked) accumulated += value;
                const from = stacked ? start : zero;
                const to = stacked ? xOf(accumulated) : xOf(value);
                const barHeight = stacked ? (above ? 12 : bar) : Math.max(1, (above ? 12 : bar) - 2);
                const y = above
                  ? center + row / 2 - 8 - barHeight
                  : stacked ? center - bar / 2 : center - (series.length * bar) / 2 + j * bar;
                return (
                  <rect
                    key={entry.id}
                    x={Math.min(from, to)}
                    y={y}
                    width={Math.max(1, Math.abs(to - from))}
                    height={barHeight}
                    className={fillClass(entry.role)}
                    stroke={mark?.selected ? "var(--focus)" : undefined}
                    strokeWidth={mark?.selected ? 2 : undefined}
                    opacity={dim || dims(category.value) ? 0.7 : 1}
                    style={{
                      transition: reduced ? "opacity 150ms" : "opacity 150ms, transform 150ms",
                      transformBox: "fill-box",
                      transformOrigin: "center",
                      transform: hover === i && !reduced ? "scale(1.03)" : undefined,
                    }}
                  />
                );
              })}
              {labels ? (
                <BarValue x={Math.min(xOf(accumulated), width - PAD.right) + 6}
                          y={center + 3} text={formatCompact(series[0]?.values[i] ?? 0)}
                          barPx={Math.abs(xOf(series[0]?.values[i] ?? 0) - zero)} />
              ) : null}
            </g>
          );
        })}
      </svg>
      {hovered ? (
        <ValueChip x={spot?.left ?? left} y={spot?.top ?? PAD.top + (hover ?? 0) * row - 4}
                   width={width}
                   text={[hovered.name, hovered.value, hovered.share,
                          markState(crossFilter, dimension, categories[hover ?? 0]?.value)
                            ?.selected ? t.reportParams.clickToRemoveFilter : t.reportParams.clickToFilter]
                     .filter(Boolean).join(" · ")} />
      ) : null}
    </div>
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
