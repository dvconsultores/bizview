import { BottomLabels, ValueAxis } from "./ChartAxes";
import { ChartCard, ChartLegend } from "./ChartCard";
import { CHART_HEIGHT, axisLabelIndexes, chartScale, gapPath } from "./chartScale";
import { fillClass, strokeClass } from "../layoutRoles";
import { chartSummary, type ChartCategory, type ChartFrame, type ChartSeries } from "./series";

export interface TrendChartProps {
  frame: ChartFrame;
  categories: ChartCategory[];
  /** First entry is the current period, a second one the previous period (dashed). */
  series: ChartSeries[];
  /** `area` fills the current period's line, as `TrendChart` fills it today. */
  area?: boolean;
}

/** The trend chart's line (and fill) as a component; gaps stay gaps instead of a bridged line. */
export function LineChart({ frame, categories, series, area = false }: TrendChartProps) {
  const label = chartSummary(frame);
  const drawn = series.filter((entry) => entry.values.some((value) => value !== null));
  const current = drawn[0];
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
        return (
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
            <BottomLabels
              indexes={indexes}
              x={scale.x}
              height={CHART_HEIGHT}
              labelAt={(i) => categories[i]?.label ?? ""}
            />
          </svg>
        );
      }}
    </ChartCard>
  );
}
