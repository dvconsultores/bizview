import { useRef, type ReactNode } from "react";
import { Card } from "../../Card";
import { CHART_MIN_HEIGHT, useChartWidth } from "./chartScale";
import { surfaceClass } from "../layoutRoles";
import type { ChartSeries } from "./series";

/** Card chrome and measured width shared by the layout's charts: `children` receives the width in
 * px to draw with, so every kind stays responsive through the same measuring path. */
export function ChartCard({
  title,
  legend,
  caption,
  children,
}: {
  title: string;
  legend?: ReactNode;
  caption?: string;
  children: (width: number) => ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const width = useChartWidth(ref);

  return (
    <Card className="p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="min-w-0 text-lg font-semibold text-ink [overflow-wrap:anywhere]">{title}</h2>
        {legend ? <p className="text-xs text-ink-muted">{legend}</p> : null}
      </div>
      <figure className="mt-3">
        <div ref={ref} className="w-full" style={{ minHeight: CHART_MIN_HEIGHT }}>
          {width > 0 ? children(width) : null}
        </div>
        {caption ? <figcaption className="mt-2 text-xs text-ink-muted [overflow-wrap:anywhere]">{caption}</figcaption> : null}
      </figure>
    </Card>
  );
}

/** Series legend with the role the chart actually draws. */
export function ChartLegend({ series }: { series: ChartSeries[] }) {
  if (series.length < 2) return null;
  return (
    <ul className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {series.map((item) => (
        <li key={item.id} className="flex min-w-0 items-center gap-1.5">
          <span className={`${surfaceClass(item.role)} h-2.5 w-2.5 shrink-0 rounded-sm`} aria-hidden />
          <span className="[overflow-wrap:anywhere]">{item.label}</span>
        </li>
      ))}
    </ul>
  );
}
