import { useMemo, useRef, useState } from "react";
import type { ReportView } from "../../api/types";
import { formatBucket, formatCompact, formatIsoDate, formatValue } from "../../lib/numbers";
import { Card } from "../Card";
import { useT } from "../../i18n";
import { localized } from "../../lib/labels";
import { CHART_HEIGHT as HEIGHT, PAD, chartScale, gapPath, useChartWidth } from "./charts/chartScale";

type Trend = Extract<ReportView, { type: "trend" }>;

/** Line chart drawn as SVG at the container's width; gaps where a bucket has no data. */
export function TrendChart({ view, currency }: { view: Trend; currency: string }) {
  const t = useT();
  const ref = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const width = useChartWidth(ref);

  const hasPrev = view.points.some((p) => p.previous !== undefined);
  const { ticks, x, y } = useMemo(
    () =>
      chartScale(
        view.points.flatMap((p) => [p.value, hasPrev ? p.previous ?? null : null]),
        view.points.length,
        width,
      ),
    [view.points, width, hasPrev],
  );

  const path = (pick: (i: number) => number | null | undefined) =>
    gapPath(view.points.map((_, i) => pick(i)), x, y);

  const labels = view.points.length <= 1 ? [0] : [0, Math.floor((view.points.length - 1) / 2), view.points.length - 1];
  const active = hover !== null ? view.points[hover] : null;
  const onMove = (clientX: number, rect: DOMRect) => {
    const rel = clientX - rect.left;
    let best = 0;
    view.points.forEach((_, i) => {
      if (Math.abs(x(i) - rel) < Math.abs(x(best) - rel)) best = i;
    });
    setHover(best);
  };
  const first = view.points[0];
  const last = view.points[view.points.length - 1];
  const summary = first && last
    ? t.reportParams.display.trendSummary(
        localized(view, "label"),
        formatValue(first.value, view.format, currency),
        formatIsoDate(first.bucket),
        formatValue(last.value, view.format, currency),
        formatIsoDate(last.bucket),
      )
    : localized(view, "label");

  return (
    <Card className="p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between">
        <h2 className="mr-3 text-lg font-semibold text-ink">{t.reportParams.display.trend(localized(view, "label"))}</h2>
        <p className="text-xs text-ink-muted" aria-live="polite">
          {active
            ? `${formatBucket(active.bucket, view.grain)}: ${formatValue(active.value, view.format, currency)}${
                hasPrev ? ` · ${t.reportParams.display.before(formatValue(active.previous ?? null, view.format, currency))}` : ""
              }`
            : hasPrev ? t.reportParams.display.legend : ""}
        </p>
      </div>
      <div ref={ref} className="mt-2 w-full" style={{ minHeight: HEIGHT }}>
        {width > 0 && (
          <svg
            width={width}
            height={HEIGHT}
            role="img"
            aria-label={summary}
            className="block touch-pan-y"
            onPointerMove={(e) => onMove(e.clientX, e.currentTarget.getBoundingClientRect())}
            onPointerLeave={() => setHover(null)}
          >
            {ticks.map((t) => (
              <g key={t}>
                <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} className={t === 0 ? "stroke-chart-axis" : "stroke-chart-grid"} />
                <text x={PAD.left - 6} y={y(t) + 4} textAnchor="end" fontSize="11" className="fill-chart-label">
                  {formatCompact(t)}
                </text>
              </g>
            ))}
            {labels.map((i) => (
              <text key={i} x={x(i)} y={HEIGHT - 6} fontSize="11" className="fill-chart-label"
                textAnchor={i === 0 && labels.length > 1 ? "start" : i === view.points.length - 1 && labels.length > 1 ? "end" : "middle"}>
                {view.points[i] ? formatBucket(view.points[i].bucket, view.grain) : ""}
              </text>
            ))}
            {view.points.length > 1 && view.points.every((p) => p.value !== null) ? (
              <path
                d={`${path((i) => view.points[i].value)} L${x(view.points.length - 1)},${y(ticks[0])} L${x(0)},${y(ticks[0])} Z`}
                className="fill-chart-1"
                fillOpacity={0.12}
                stroke="none"
              />
            ) : null}
            {hasPrev ? <path d={path((i) => view.points[i].previous)} fill="none" className="stroke-chart-2" strokeWidth="1.5" strokeDasharray="4 3" /> : null}
            <path d={path((i) => view.points[i].value)} fill="none" className="stroke-chart-1" strokeWidth="2.5" strokeLinejoin="round" />
            {view.points.length <= 1 && first?.value !== null && first ? <circle cx={x(0)} cy={y(first.value as number)} r="4" className="fill-chart-1" /> : null}
            {hover !== null && active ? (
              <g>
                <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={HEIGHT - PAD.bottom} className="stroke-chart-axis" />
                {active.value !== null ? <circle cx={x(hover)} cy={y(active.value)} r="4" className="fill-chart-1" /> : null}
              </g>
            ) : null}
          </svg>
        )}
      </div>
      <details className="mt-2 text-sm">
        <summary className="inline-flex min-h-tap cursor-pointer items-center font-medium text-accent">{t.reportParams.display.viewData}</summary>
        <div className="max-h-72 overflow-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="bg-subtle text-xs font-semibold text-ink-muted">
                <th scope="col" className="px-3 py-2">{t.reportParams.display.from}</th>
                <th scope="col" className="px-3 py-2 text-right">{localized(view, "label")}</th>
                {hasPrev ? <th scope="col" className="px-3 py-2 text-right">{t.reportParams.display.previous}</th> : null}
              </tr>
            </thead>
            <tbody className="divide-y divide-line tabular-nums">
              {view.points.map((p) => (
                <tr key={p.bucket}>
                  <th scope="row" className="px-3 py-2 font-normal">{formatIsoDate(p.bucket)}</th>
                  <td className="px-3 py-2 text-right">{formatValue(p.value, view.format, currency)}</td>
                  {hasPrev ? <td className="px-3 py-2 text-right">{formatValue(p.previous ?? null, view.format, currency)}</td> : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </Card>
  );
}
