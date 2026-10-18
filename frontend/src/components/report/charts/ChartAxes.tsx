import { formatCompact } from "../../../lib/numbers";
import { PAD, type ChartScale } from "./chartScale";

/** Value axis of a vertical chart: grid lines plus compact labels on the left. */
export function ValueAxis({ scale, width }: { scale: ChartScale; width: number }) {
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

/** Category labels under a vertical chart; the first and last ones stay inside the drawing. */export function BottomLabels({
  indexes,
  x,
  height,
  labelAt,
}: {
  indexes: number[];
  x: (i: number) => number;
  height: number;
  labelAt: (i: number) => string;
}) {
  return (
    <>
      {indexes.map((i) => (
        <text
          key={i}
          x={x(i)}
          y={height - 6}
          fontSize="11"
          className="fill-chart-label"
          textAnchor={
            indexes.length > 1 && i === indexes[0]
              ? "start"
              : indexes.length > 1 && i === indexes[indexes.length - 1]
                ? "end"
                : "middle"
          }
        >
          {labelAt(i)}
        </text>
      ))}
    </>
  );
}
